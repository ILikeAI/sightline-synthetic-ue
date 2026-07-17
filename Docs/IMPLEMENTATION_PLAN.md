# Unreal data-generation implementation plan

## Phase 1 — current

- Fixed virtual Mac display and CineCamera.
- Primitive human-scale head/eye proxy.
- Procedural two-colour gradient background.
- Deterministic target and colour randomization.
- Binocular gaze-ray labels.
- Native UE 5.8 MCP plus project-specific toolset.

## Phase 2 — MetaHuman integration

- Add 6–10 MetaHumans selected for eye and eyelid variation.
- Implement `CR_GazeAim` to converge both eyes on the screen target.
- Couple eyelid position to vertical eye rotation.
- Add expression and blink presets.
- Validate rendered iris centres against recorded gaze rays.

## Phase 3 — camera and appearance variation

- Measure the actual MacBook webcam intrinsics and distortion.
- Replace placeholder sensor settings with measured values.
- Add 4–6 simple light rigs and screen-emission presets.
- Add low-frequency backdrop shapes and optional image textures.
- Add webcam degradation after rendering.

## Phase 4 — batch rendering

- Create Movie Render Graph preset at the webcam resolution.
- Generate 1–3 second fixation/saccade clips.
- Export RGB plus compact JSONL/Parquet labels.
- Render masks/depth only for selected auxiliary-training batches.
- Produce coverage reports by target, pose, light, identity and occlusion.

## Gate before scale

Render approximately 300k frames and compare:

1. real-only training;
2. synthetic-only training;
3. synthetic pretraining followed by real fine-tuning.

Do not expand to millions of frames unless synthetic pretraining improves
held-out real-session error by at least 15%, or halves the real calibration
samples required for the same error.
