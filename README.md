# Image Blend Studio (Qt + Python)

A desktop GUI editor prototype for a **non-destructive, branch-first** image workflow:

- Import three (or more) source images as layers, edit each independently, then combine.
- Keep each layer's source image untouched.
- Create multiple branches from either:
  - the layer source image, or
  - another existing branch in the same layer.
- Stack filters per branch, with per-filter blend mode + opacity.
- Blend branches together, then blend the layer into the document.

## Stack

- Python 3.11+
- PySide6 (Qt Widgets)
- Filter pipeline with shader metadata (`shader_path`) for Vulkan backend integration

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
image-blend-studio
```

## Workflow Model

1. **Source Layer**: original image reference.
2. **Branch Source Selection**: each branch picks either layer source or an existing branch as input.
3. **Filter Stack in Branch**: ordered effects, each with enabled, blend mode, and opacity.
4. **Branch Composite**: visible branches are blended in list order.
5. **Layer Composite**: final layer result blends into document with layer blend mode + opacity.

## Performance Note

The compositor caches per-branch intermediate stages and only recomputes from the first changed filter step, reducing lag when toggling/changing filters in long stacks.

Shader-backed filters are dispatched through a shared shader runtime hook, and all built-in effects now include matching compute shader sources (`grayscale`, `invert`, `box_blur`, `edge_detect`) so the render path is prepared for Vulkan execution.

## Next Steps

1. Add project save/load (layers, branches, source links, stack state).
2. Add automation recording/playback for repeated edit macros.
3. Add Vulkan runtime for SPIR-V dispatch and GPU compositing.
4. Add export pipeline and larger image performance optimizations.
