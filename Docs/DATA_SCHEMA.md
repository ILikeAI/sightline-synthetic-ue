# Preview label schema

The MVP writes `Saved/Sightline/preview_label.json`. The production generator
will emit one JSONL or Parquet row per frame with the same conceptual fields.

## Required frame fields

- `schema_version`
- `frame_id`
- `seed`
- normalized screen `u`, `v`
- physical screen dimensions
- 3D target in Unreal world centimetres
- left and right eye origins
- left and right unit gaze directions
- camera position and intrinsics
- background strategy and parameters
- subject identity and visibility state

## Coordinate convention

- Unreal world units are centimetres.
- The subject faces positive X toward the display.
- Screen width runs on world Y.
- Screen height runs on world Z.
- Normalized `(0, 0)` is screen bottom-left.
- Normalized `(1, 1)` is screen top-right.

The convention is intentionally written into every dataset manifest so model
code never needs to infer it from filenames or actor placement.
