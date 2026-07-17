# Unreal Engine 5.8 field notes

Living notes for agents working on this and future UE 5.8 tasks. Read this
before changing the editor integration. Add a dated entry whenever Unreal,
Python, MCP, rendering, or automation behaves differently from the apparent
API contract.

Last updated: 2026-07-17

## Native Unreal MCP

- UE 5.8 ships an experimental native MCP server in
  `Engine/Plugins/Experimental/ModelContextProtocol`. The project enables
  `ModelContextProtocol` and `AllToolsets`.
- The working editor config is in
  `Config/DefaultEditorPerProjectUserSettings.ini`:

  ```ini
  [/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]
  ServerUrlPath=/mcp
  ServerPortNumber=8000
  bAutoStartServer=True
  bEnableToolSearch=True
  ```

- The endpoint is `http://127.0.0.1:8000/mcp`. It is loopback-only and has no
  authentication. Do not expose it to a network.
- In a sandboxed agent shell, `lsof` can show Unreal listening while a normal
  `curl` still receives connection refused. Run the loopback MCP request outside
  the filesystem/network sandbox when the environment requires approval.
- MCP uses Streamable HTTP JSON-RPC. Initialize first, retain the
  `Mcp-Session-Id` response header, send `notifications/initialized`, then call
  `tools/list` or the tool-search meta-tools.
- Tool search exposes `list_toolsets`, `describe_toolset`, and `call_tool`.
  Project tools are addressed with the full toolset name
  `sightline_toolset.__init__.SightlineDatasetTools`.
- Many UE MCP calls complete on the game thread and took roughly 14–18 seconds
  on this Mac, even for simple reads. A 30-second client timeout is safer than a
  short default.
- `CaptureViewport` reports `annotations` as optional in its MCP schema, but UE
  5.8 rejects the call when it is omitted. Supply an explicit disabled
  annotation struct:

  ```json
  {
    "gridSpacing": 0,
    "gridExtent": 0,
    "gridHeight": 0,
    "maxLabelDistance": 0,
    "classFilter": {"refPath": "/Script/Engine.Actor"},
    "maxLabels": 0
  }
  ```

- `CaptureViewport` returns an SSE envelope whose text content contains another
  JSON string; the PNG is base64 inside
  `returnValue.image.data`.

## Python toolset registration

- Constructing `Registration([ToolsetClass])` does not register anything.
  The startup module must retain the registration object and explicitly call
  `_registration.register()`.
- A successful registration emits a log entry like:

  ```text
  Registering Toolset sightline_toolset.__init__.SightlineDatasetTools
  ```

- `unreal.ModelContextProtocolSettings` is not exposed to Python in UE 5.8 even
  though the native MCP plugin is active. Validate MCP settings by reading the
  project INI or by querying the live endpoint, not by requesting that UObject.

## UE 5.8 Python API mismatches

- `unreal.LinearColor` has no `to_fcolor()` method in this build. When a property
  requires `FColor`, clamp the linear channels, multiply by 255, and construct
  `unreal.Color(r, g, b, a)` explicitly.
- `MaterialExpressionComponentMask` exposes its source as the unnamed first
  input pin. Connecting to `"Input"` silently leaves it disconnected and the
  Metal shader compiler later reports:

  ```text
  (Node ComponentMask) Missing ComponentMask input
  ```

  Use:

  ```python
  unreal.MaterialEditingLibrary.connect_material_expressions(
      texture_coordinate, "", component_mask, ""
  )
  ```

- Always inspect `LogMaterial` after programmatic material construction.
  Failed materials fall back to bright default white, which can look like a
  camera/exposure problem instead of a graph compile error.
- Point lights spawned for editor previews default to static mobility and cause
  a `LIGHTING NEEDS TO BE REBUILT` overlay. Set the light component mobility to
  `unreal.ComponentMobility.MOVABLE` for generated preview scenes.
- A lit white primitive against an emissive backdrop can be blown out by editor
  exposure and hide the eyes even when the geometry is correct. Small unlit
  proxy materials with explicit skin, sclera, and iris colours make the MVP
  render deterministic; use physically based skin and lighting when the
  MetaHumans replace the proxy.

## Editor camera and actor lifecycle

- `LevelEditorSubsystem.pilot_level_actor(camera)` can copy the current editor
  viewport transform into the CineCamera. In this project it moved the camera
  behind the virtual screen and made the screen occlude the subject.
- After piloting, explicitly restore the calibrated actor location and
  look-at rotation, then save the level again.
- Rebuilding the scene destroys and respawns actors. Unreal increments internal
  names (`CineCameraActor_0`, `CineCameraActor_1`, and so on), while the actor
  label remains `Sightline_Webcam`. Never retain an actor `refPath` across a
  rebuild; call `SceneTools.find_actors` again by label.
- A viewport can remain locked to a destroyed camera actor after a rebuild.
  For deterministic captures, pass an explicit calibrated transform to
  `EditorAppToolset.CaptureViewport` instead of trusting the visible editor
  pilot state.

## Project/plugin startup

- Enabling `AllToolsets` loads a large set of experimental plugins and currently
  produces a benign `GameFeatureData` Asset Manager warning in a blank project.
  It does not stop MCP or the project toolset from loading.
- Opening a configured default map before it has been generated logs a missing
  map warning and opens an empty editor level. Generate and save the map once
  before treating that startup warning as a project failure.
- If a map references a generated material asset that has been moved or deleted,
  startup reports a missing dependent package. Recreate the material at the same
  package path and resave the map to clear the reference.

## Working verification sequence

1. Confirm the correct project path in the editor log.
2. Confirm port 8000 is listening.
3. Initialize MCP and describe
   `sightline_toolset.__init__.SightlineDatasetTools`.
4. Call `build_demo_scene` with a fixed seed.
5. Call `validate_demo_scene`; require `missing_actors=[]`,
   `mcp_auto_start=true`, `mcp_port=8000`, and `valid=true`.
6. Search the current log for Python tracebacks, material compile failures, and
   map-check errors.
7. Resolve the current camera actor by label after every rebuild.
8. Capture from the explicit calibrated transform and inspect the actual PNG.

## Update format

When adding a finding, include:

- what was expected;
- the actual UE 5.8 behavior or error text;
- the working replacement;
- how it was verified;
- whether the workaround is project-specific or generally reusable.
