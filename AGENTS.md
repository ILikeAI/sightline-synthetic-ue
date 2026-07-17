# Agent instructions

## Why this project exists

Generate controllable, correctly labelled webcam-like face and eye images for a
personalized MacBook point-of-gaze model. Prefer correct geometry, labels and
repeatability over cinematic environments.

## MVP constraints

- Unreal Engine version: 5.8.
- Keep backgrounds lightweight: one procedural backdrop, not 3D rooms.
- Start with 6–10 MetaHumans after the proxy scene is proven.
- The camera/display transform is fixed and explicit.
- Generate binocular gaze by aiming both eyes at a 3D screen target.
- All randomization must be seedable and written to metadata.
- Do not commit generated datasets, caches, renders or raw webcam footage.
- Keep Unreal MCP bound to loopback only.

## Validation

Before changing Unreal integration code, read
`Docs/UNREAL_5_8_LEARNINGS.md`. Update it in the same change whenever a UE 5.8
API, MCP, editor, rendering, automation, or platform behavior differs from what
was expected. Record failed approaches as well as the working replacement so
future agents do not repeat the investigation.

Before handing off changes:

```bash
python3 Scripts/validate_project.py
```

When Unreal is available, also call `SightlineDatasetTools.validate_demo_scene`
through MCP or run:

```text
py "import sightline; print(sightline.validate_demo_scene())"
```

## Git

- Track `.uasset` and `.umap` files with Git LFS.
- Stage intentional files explicitly.
- Never commit `Saved/`, `Intermediate/`, `DerivedDataCache/`, or datasets.
- Keep the GitHub repository private unless Josh explicitly changes that.
