"""Build and operate the lightweight Sightline synthetic-data preview scene.

The MVP deliberately uses primitive meshes as a MetaHuman stand-in. It proves
the camera/screen coordinate system, procedural background, deterministic
randomization, labelling, MCP surface, and render path before large character
assets are added.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

import unreal


MAP_PATH = "/Game/Sightline/Maps/L_SightlinePreview"
MATERIAL_PATH = "/Game/Sightline/Materials/M_ProceduralBackdrop"
MATERIAL_INSTANCE_PATH = "/Game/Sightline/Materials/MI_ProceduralBackdrop"
SKIN_MATERIAL_PATH = "/Game/Sightline/Materials/M_ProxySkin"
EYE_MATERIAL_PATH = "/Game/Sightline/Materials/M_ProxyEye"
IRIS_MATERIAL_PATH = "/Game/Sightline/Materials/M_ProxyIris"

CAMERA_LABEL = "Sightline_Webcam"
TARGET_LABEL = "Sightline_GazeTarget"
BACKDROP_LABEL = "Sightline_ProceduralBackdrop"

SCREEN_CENTER = unreal.Vector(60.0, 0.0, 150.0)
SCREEN_HALF_WIDTH_CM = 15.1
SCREEN_HALF_HEIGHT_CM = 9.8
CAMERA_LOCATION = unreal.Vector(58.0, 0.0, 164.0)
LEFT_EYE_ORIGIN = unreal.Vector(9.2, -3.15, 164.0)
RIGHT_EYE_ORIGIN = unreal.Vector(9.2, 3.15, 164.0)


def _asset_tools() -> unreal.AssetTools:
    return unreal.AssetToolsHelpers.get_asset_tools()


def _actor_subsystem() -> unreal.EditorActorSubsystem:
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _level_subsystem() -> unreal.LevelEditorSubsystem:
    return unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)


def _ensure_directory(path: str) -> None:
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        unreal.EditorAssetLibrary.make_directory(path)


def _save_asset(path: str) -> None:
    unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)


def _create_backdrop_material() -> tuple[unreal.Material, unreal.MaterialInstanceConstant]:
    """Create a two-colour unlit gradient material and editable instance."""
    _ensure_directory("/Game/Sightline/Materials")

    material = unreal.load_asset(MATERIAL_PATH)
    if material is None:
        material = _asset_tools().create_asset(
            "M_ProceduralBackdrop",
            "/Game/Sightline/Materials",
            unreal.Material,
            unreal.MaterialFactoryNew(),
        )
        if material is None:
            raise RuntimeError("Failed to create M_ProceduralBackdrop")

        material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)

        color_a = unreal.MaterialEditingLibrary.create_material_expression(
            material, unreal.MaterialExpressionVectorParameter, -720, -180
        )
        color_a.set_editor_property("parameter_name", "ColorA")
        color_a.set_editor_property("default_value", unreal.LinearColor(0.015, 0.08, 0.10, 1.0))

        color_b = unreal.MaterialEditingLibrary.create_material_expression(
            material, unreal.MaterialExpressionVectorParameter, -720, 80
        )
        color_b.set_editor_property("parameter_name", "ColorB")
        color_b.set_editor_property("default_value", unreal.LinearColor(0.10, 0.015, 0.08, 1.0))

        texcoord = unreal.MaterialEditingLibrary.create_material_expression(
            material, unreal.MaterialExpressionTextureCoordinate, -720, 300
        )
        mask = unreal.MaterialEditingLibrary.create_material_expression(
            material, unreal.MaterialExpressionComponentMask, -470, 300
        )
        mask.set_editor_property("r", True)
        lerp = unreal.MaterialEditingLibrary.create_material_expression(
            material, unreal.MaterialExpressionLinearInterpolate, -220, 0
        )

        # UE 5.8 exposes the ComponentMask input as its unnamed first pin.
        unreal.MaterialEditingLibrary.connect_material_expressions(texcoord, "", mask, "")
        unreal.MaterialEditingLibrary.connect_material_expressions(color_a, "", lerp, "A")
        unreal.MaterialEditingLibrary.connect_material_expressions(color_b, "", lerp, "B")
        unreal.MaterialEditingLibrary.connect_material_expressions(mask, "", lerp, "Alpha")
        unreal.MaterialEditingLibrary.connect_material_property(
            lerp, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
        )
        unreal.MaterialEditingLibrary.recompile_material(material)
        _save_asset(MATERIAL_PATH)

    instance = unreal.load_asset(MATERIAL_INSTANCE_PATH)
    if instance is None:
        factory = unreal.MaterialInstanceConstantFactoryNew()
        instance = _asset_tools().create_asset(
            "MI_ProceduralBackdrop",
            "/Game/Sightline/Materials",
            unreal.MaterialInstanceConstant,
            factory,
        )
        if instance is None:
            raise RuntimeError("Failed to create MI_ProceduralBackdrop")
        instance.set_editor_property("parent", material)
        _save_asset(MATERIAL_INSTANCE_PATH)

    return material, instance


def _create_solid_material(path: str, color: unreal.LinearColor) -> unreal.Material:
    """Create a small unlit material so proxy features remain camera-legible."""
    material = unreal.load_asset(path)
    if material is not None:
        return material

    asset_name = path.rsplit("/", 1)[-1]
    material = _asset_tools().create_asset(
        asset_name,
        "/Game/Sightline/Materials",
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    if material is None:
        raise RuntimeError(f"Failed to create {path}")

    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    color_node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, -320, 0
    )
    color_node.set_editor_property("parameter_name", "Color")
    color_node.set_editor_property("default_value", color)
    unreal.MaterialEditingLibrary.connect_material_property(
        color_node, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
    )
    unreal.MaterialEditingLibrary.recompile_material(material)
    _save_asset(path)
    return material


def _spawn_mesh(
    label: str,
    mesh_path: str,
    location: unreal.Vector,
    scale: unreal.Vector,
    rotation: unreal.Rotator | None = None,
    material: unreal.MaterialInterface | None = None,
) -> unreal.StaticMeshActor:
    mesh = unreal.load_asset(mesh_path)
    if mesh is None:
        raise RuntimeError(f"Missing engine mesh: {mesh_path}")
    actor = _actor_subsystem().spawn_actor_from_class(
        unreal.StaticMeshActor,
        location,
        rotation or unreal.Rotator(0.0, 0.0, 0.0),
    )
    actor.set_actor_label(label)
    actor.tags = [unreal.Name("SightlineGenerated")]
    actor.static_mesh_component.set_static_mesh(mesh)
    actor.set_actor_scale3d(scale)
    if material is not None:
        actor.static_mesh_component.set_material(0, material)
    return actor


def _spawn_light(
    label: str,
    location: unreal.Vector,
    intensity: float,
    color: unreal.LinearColor,
) -> unreal.PointLight:
    actor = _actor_subsystem().spawn_actor_from_class(
        unreal.PointLight, location, unreal.Rotator(0.0, 0.0, 0.0)
    )
    actor.set_actor_label(label)
    actor.tags = [unreal.Name("SightlineGenerated")]
    component = actor.point_light_component
    component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    component.set_editor_property("intensity", intensity)
    component.set_editor_property(
        "light_color",
        unreal.Color(
            int(max(0.0, min(1.0, color.r)) * 255.0),
            int(max(0.0, min(1.0, color.g)) * 255.0),
            int(max(0.0, min(1.0, color.b)) * 255.0),
            255,
        ),
    )
    component.set_editor_property("attenuation_radius", 260.0)
    component.set_editor_property("source_radius", 14.0)
    return actor


def _look_at(actor: unreal.Actor, target: unreal.Vector) -> None:
    rotation = unreal.MathLibrary.find_look_at_rotation(actor.get_actor_location(), target)
    actor.set_actor_rotation(rotation, False)


def _screen_point(u: float, v: float) -> unreal.Vector:
    """Convert normalized screen coordinates to the virtual screen plane.

    ``u=0,v=0`` is bottom-left and ``u=1,v=1`` is top-right.
    """
    return unreal.Vector(
        SCREEN_CENTER.x - 1.8,
        SCREEN_CENTER.y + (u * 2.0 - 1.0) * SCREEN_HALF_WIDTH_CM,
        SCREEN_CENTER.z + (v * 2.0 - 1.0) * SCREEN_HALF_HEIGHT_CM,
    )


def _unit_direction(origin: unreal.Vector, target: unreal.Vector) -> dict[str, float]:
    dx = target.x - origin.x
    dy = target.y - origin.y
    dz = target.z - origin.z
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    return {"x": dx / length, "y": dy / length, "z": dz / length}


def _find_actor(label: str) -> unreal.Actor | None:
    for actor in _actor_subsystem().get_all_level_actors():
        if actor.get_actor_label() == label:
            return actor
    return None


def _clear_generated_actors() -> None:
    actors = [
        actor
        for actor in _actor_subsystem().get_all_level_actors()
        if unreal.Name("SightlineGenerated") in list(actor.tags)
    ]
    if actors:
        _actor_subsystem().destroy_actors(actors)


def build_demo_scene(seed: int = 7) -> str:
    """Build a minimal, deterministic gaze-generation preview level."""
    _ensure_directory("/Game/Sightline")
    _ensure_directory("/Game/Sightline/Maps")
    _, backdrop_instance = _create_backdrop_material()
    skin_material = _create_solid_material(
        SKIN_MATERIAL_PATH, unreal.LinearColor(0.32, 0.12, 0.07, 1.0)
    )
    eye_material = _create_solid_material(
        EYE_MATERIAL_PATH, unreal.LinearColor(0.72, 0.72, 0.68, 1.0)
    )
    iris_material = _create_solid_material(
        IRIS_MATERIAL_PATH, unreal.LinearColor(0.015, 0.025, 0.035, 1.0)
    )

    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PATH):
        _level_subsystem().load_level(MAP_PATH)
        _clear_generated_actors()
    else:
        if not _level_subsystem().new_level(MAP_PATH):
            raise RuntimeError(f"Could not create map {MAP_PATH}")

    # MetaHuman-ready proxy: dimensions and eye placement are intentionally human scale.
    head = _spawn_mesh(
        "Sightline_HeadProxy",
        "/Engine/BasicShapes/Sphere.Sphere",
        unreal.Vector(0.0, 0.0, 158.5),
        unreal.Vector(0.15, 0.135, 0.23),
        material=skin_material,
    )
    head.set_folder_path("Sightline/Subject")

    _spawn_mesh(
        "Sightline_LeftEye",
        "/Engine/BasicShapes/Sphere.Sphere",
        LEFT_EYE_ORIGIN,
        unreal.Vector(0.013, 0.013, 0.013),
        material=eye_material,
    ).set_folder_path("Sightline/Subject")
    _spawn_mesh(
        "Sightline_RightEye",
        "/Engine/BasicShapes/Sphere.Sphere",
        RIGHT_EYE_ORIGIN,
        unreal.Vector(0.013, 0.013, 0.013),
        material=eye_material,
    ).set_folder_path("Sightline/Subject")
    _spawn_mesh(
        "Sightline_LeftIris",
        "/Engine/BasicShapes/Sphere.Sphere",
        unreal.Vector(10.35, -3.15, 164.0),
        unreal.Vector(0.006, 0.006, 0.006),
        material=iris_material,
    ).set_folder_path("Sightline/Subject")
    _spawn_mesh(
        "Sightline_RightIris",
        "/Engine/BasicShapes/Sphere.Sphere",
        unreal.Vector(10.35, 3.15, 164.0),
        unreal.Vector(0.006, 0.006, 0.006),
        material=iris_material,
    ).set_folder_path("Sightline/Subject")
    _spawn_mesh(
        "Sightline_TorsoProxy",
        "/Engine/BasicShapes/Cylinder.Cylinder",
        unreal.Vector(-2.0, 0.0, 126.0),
        unreal.Vector(0.20, 0.28, 0.30),
        material=skin_material,
    ).set_folder_path("Sightline/Subject")

    # A thin, asset-free representation of the physical panel.
    _spawn_mesh(
        "Sightline_ScreenPlane",
        "/Engine/BasicShapes/Cube.Cube",
        SCREEN_CENTER,
        unreal.Vector(0.015, 0.165, 0.105),
    ).set_folder_path("Sightline/MacRig")
    _spawn_mesh(
        TARGET_LABEL,
        "/Engine/BasicShapes/Sphere.Sphere",
        _screen_point(0.5, 0.5),
        unreal.Vector(0.011, 0.011, 0.011),
    ).set_folder_path("Sightline/MacRig")

    backdrop = _spawn_mesh(
        BACKDROP_LABEL,
        "/Engine/BasicShapes/Cube.Cube",
        unreal.Vector(-24.0, 0.0, 158.0),
        unreal.Vector(0.015, 0.90, 0.58),
        material=backdrop_instance,
    )
    backdrop.set_folder_path("Sightline/Environment")

    camera = _actor_subsystem().spawn_actor_from_class(
        unreal.CineCameraActor, CAMERA_LOCATION, unreal.Rotator(0.0, 180.0, 0.0)
    )
    camera.set_actor_label(CAMERA_LABEL)
    camera.tags = [unreal.Name("SightlineGenerated")]
    camera.set_folder_path("Sightline/MacRig")
    _look_at(camera, unreal.Vector(0.0, 0.0, 159.0))
    camera_component = camera.get_cine_camera_component()
    filmback = camera_component.get_editor_property("filmback")
    filmback.sensor_width = 5.6
    filmback.sensor_height = 3.15
    camera_component.set_editor_property("filmback", filmback)
    camera_component.set_editor_property("current_focal_length", 4.0)
    camera_component.set_editor_property("current_aperture", 5.6)

    _spawn_light(
        "Sightline_KeyLight",
        unreal.Vector(32.0, -48.0, 192.0),
        180.0,
        unreal.LinearColor(0.72, 0.86, 1.0, 1.0),
    ).set_folder_path("Sightline/Lighting")
    _spawn_light(
        "Sightline_ScreenGlow",
        unreal.Vector(45.0, 0.0, 145.0),
        45.0,
        unreal.LinearColor(0.72, 0.90, 1.0, 1.0),
    ).set_folder_path("Sightline/Lighting")

    randomize_preview(seed)
    unreal.EditorLevelLibrary.save_current_level()
    _level_subsystem().pilot_level_actor(camera)
    # Piloting adopts the previous editor-view transform; restore the calibrated
    # Mac webcam pose after the viewport is locked to this actor.
    camera.set_actor_location(CAMERA_LOCATION, False, False)
    _look_at(camera, unreal.Vector(0.0, 0.0, 159.0))
    unreal.EditorLevelLibrary.save_current_level()
    unreal.log(f"[Sightline] Demo scene built at {MAP_PATH}")
    return f"Built {MAP_PATH} with seed {seed}"


def randomize_preview(seed: int = 7) -> str:
    """Randomize target location and low-frequency procedural backdrop colours."""
    rng = random.Random(seed)
    u = rng.uniform(0.05, 0.95)
    v = rng.uniform(0.05, 0.95)
    target = _find_actor(TARGET_LABEL)
    if target is None:
        raise RuntimeError("Demo scene is missing. Call build_demo_scene first.")
    target.set_actor_location(_screen_point(u, v), False, False)

    instance = unreal.load_asset(MATERIAL_INSTANCE_PATH)
    if instance is None:
        raise RuntimeError("Backdrop material instance is missing.")

    def colour() -> unreal.LinearColor:
        # Mid-dark emissive palettes stay visible without becoming a subject cue.
        return unreal.LinearColor(
            rng.uniform(0.08, 0.45),
            rng.uniform(0.08, 0.45),
            rng.uniform(0.08, 0.45),
            1.0,
        )

    color_a = colour()
    color_b = colour()
    unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
        instance, "ColorA", color_a
    )
    unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
        instance, "ColorB", color_b
    )
    _save_asset(MATERIAL_INSTANCE_PATH)

    write_preview_label(seed, u=u, v=v, color_a=color_a, color_b=color_b)
    unreal.EditorLevelLibrary.save_current_level()
    return f"Seed {seed}: target=({u:.4f}, {v:.4f})"


def _colour_dict(value: unreal.LinearColor) -> dict[str, float]:
    return {"r": value.r, "g": value.g, "b": value.b, "a": value.a}


def write_preview_label(
    seed: int = 7,
    *,
    u: float | None = None,
    v: float | None = None,
    color_a: unreal.LinearColor | None = None,
    color_b: unreal.LinearColor | None = None,
) -> str:
    """Write one representative gaze-label record under Saved/Sightline."""
    rng = random.Random(seed)
    if u is None:
        u = rng.uniform(0.05, 0.95)
    if v is None:
        v = rng.uniform(0.05, 0.95)
    if color_a is None:
        color_a = unreal.LinearColor(0.015, 0.08, 0.10, 1.0)
    if color_b is None:
        color_b = unreal.LinearColor(0.10, 0.015, 0.08, 1.0)

    target = _screen_point(u, v)
    record: dict[str, Any] = {
        "schema_version": "0.1.0",
        "frame_id": f"preview_{seed:06d}",
        "seed": seed,
        "screen": {
            "u": u,
            "v": v,
            "physical_width_cm": SCREEN_HALF_WIDTH_CM * 2.0,
            "physical_height_cm": SCREEN_HALF_HEIGHT_CM * 2.0,
        },
        "target_world_cm": {"x": target.x, "y": target.y, "z": target.z},
        "left_eye": {
            "origin_world_cm": {
                "x": LEFT_EYE_ORIGIN.x,
                "y": LEFT_EYE_ORIGIN.y,
                "z": LEFT_EYE_ORIGIN.z,
            },
            "direction_world": _unit_direction(LEFT_EYE_ORIGIN, target),
        },
        "right_eye": {
            "origin_world_cm": {
                "x": RIGHT_EYE_ORIGIN.x,
                "y": RIGHT_EYE_ORIGIN.y,
                "z": RIGHT_EYE_ORIGIN.z,
            },
            "direction_world": _unit_direction(RIGHT_EYE_ORIGIN, target),
        },
        "camera": {
            "location_world_cm": {
                "x": CAMERA_LOCATION.x,
                "y": CAMERA_LOCATION.y,
                "z": CAMERA_LOCATION.z,
            },
            "sensor_width_mm": 5.6,
            "sensor_height_mm": 3.15,
            "focal_length_mm": 4.0,
        },
        "background": {
            "strategy": "procedural_gradient",
            "color_a": _colour_dict(color_a),
            "color_b": _colour_dict(color_b),
        },
        "subject": {
            "asset": "primitive_proxy",
            "metahuman_ready": True,
        },
    }

    output_dir = Path(unreal.Paths.project_saved_dir()) / "Sightline"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "preview_label.json"
    output_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    unreal.log(f"[Sightline] Wrote preview label: {output_path}")
    return str(output_path)


def validate_demo_scene() -> str:
    """Return a compact validation report for the generated preview scene."""
    required = {
        CAMERA_LABEL,
        TARGET_LABEL,
        BACKDROP_LABEL,
        "Sightline_HeadProxy",
        "Sightline_LeftEye",
        "Sightline_RightEye",
        "Sightline_ScreenPlane",
    }
    present = {actor.get_actor_label() for actor in _actor_subsystem().get_all_level_actors()}
    missing = sorted(required - present)
    settings_path = (
        Path(unreal.Paths.project_config_dir())
        / "DefaultEditorPerProjectUserSettings.ini"
    )
    settings_text = settings_path.read_text(encoding="utf-8")
    port_line = next(
        (
            line
            for line in settings_text.splitlines()
            if line.startswith("ServerPortNumber=")
        ),
        "ServerPortNumber=0",
    )
    result = {
        "map": _level_subsystem().get_current_level().get_path_name()
        if hasattr(_level_subsystem(), "get_current_level")
        else MAP_PATH,
        "required_actor_count": len(required),
        "missing_actors": missing,
        "mcp_auto_start": "bAutoStartServer=True" in settings_text,
        "mcp_port": int(port_line.partition("=")[2]),
        "valid": (
            not missing
            and "bAutoStartServer=True" in settings_text
            and port_line.endswith("=8000")
        ),
    }
    return json.dumps(result, indent=2)


def get_project_status() -> str:
    """Report the project phase and key paths without modifying the level."""
    status = {
        "phase": "MVP procedural-background preview",
        "map_exists": unreal.EditorAssetLibrary.does_asset_exist(MAP_PATH),
        "material_exists": unreal.EditorAssetLibrary.does_asset_exist(MATERIAL_PATH),
        "material_instance_exists": unreal.EditorAssetLibrary.does_asset_exist(
            MATERIAL_INSTANCE_PATH
        ),
        "mcp_url": "http://127.0.0.1:8000/mcp",
        "next_step": "Replace the primitive head proxy with 6-10 MetaHuman variants.",
    }
    return json.dumps(status, indent=2)
