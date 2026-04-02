# Image Blend Studio (Qt + Python)

A desktop GUI editor prototype for a **non-destructive, branch-first** image workflow:

- Import three (or more) source images as layers, edit each independently, then combine.
- Keep each layer's source image untouched.
- Create multiple **branches** from the same source image.
- Stack filters per branch, with per-filter blend mode + opacity.
- Blend branches together, then blend the layer into the document.

This maps closely to a diverging-tree workflow where multiple looks evolve from one source without destructive duplication.

## Stack

- Python 3.11+
- PySide6 (Qt Widgets)
- Filter pipeline with shader metadata (`shader_path`) for Vulkan backend integration

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
image-blend-studio
```

## Workflow Model

1. **Source Layer**: original image (immutable reference in model).
2. **Branches**: one or more derivations from that source.
3. **Filter Stack in Branch**: ordered effects, each with:
   - enabled flag,
   - blend mode,
   - opacity.
4. **Branch Composite**: branches blend together using branch blend mode + opacity.
5. **Layer Composite**: final layer result blends into document with layer blend mode + opacity.

## UI Highlights

- Layer controls: reorder, duplicate, remove, visibility, blend, opacity.
- Branch controls: create, duplicate, remove, enable/disable.
- Filter stack controls: add (double-click), reorder, remove, enable/disable, per-filter blend/opacity.
- Layer controls: blend/opacity/visibility.

## Automation Direction (next)

Instead of presets, the next logical feature is **automation macros**:

- capture action sequences like “add 1px blur -> set addition blend -> set 35% opacity”,
- replay on selected branch(es),
- parameterize common values.

## Vulkan Compatibility Direction

- Keep all blend/filter options available in UI.
- Implement shader-backed filter execution first (compute path).
- Map blend operations to Vulkan-compatible compositing paths, with CPU fallback only when needed.

## Next Steps

1. Add project save/load (layers, branches, stack state).
2. Add automation recording/playback.
3. Add Vulkan runtime for SPIR-V dispatch and GPU compositing.
4. Add export pipeline and larger image performance optimizations.
