from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QImage

from image_blend_app.models import FilterStackItem, ImageLayer, LayerBranch

PROJECT_FORMAT_VERSION = 1


def save_project(path: Path, layers: list[ImageLayer]) -> None:
    """Save project metadata to disk as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    project_dir = path.parent.resolve()
    data = {
        "format": "image_blend_studio_project",
        "version": PROJECT_FORMAT_VERSION,
        "layers": [_serialize_layer(layer, project_dir) for layer in layers],
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_project(path: Path) -> list[ImageLayer]:
    """Load layers from a project JSON file."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("format") != "image_blend_studio_project":
        raise ValueError("Unsupported project format")

    version = payload.get("version")
    if version != PROJECT_FORMAT_VERSION:
        raise ValueError(f"Unsupported project version: {version}")

    layers_payload = payload.get("layers")
    if not isinstance(layers_payload, list):
        raise ValueError("Project data missing layers list")

    project_dir = path.parent.resolve()
    return [_deserialize_layer(layer_data, project_dir) for layer_data in layers_payload if isinstance(layer_data, dict)]


def _serialize_layer(layer: ImageLayer, project_dir: Path) -> dict[str, object]:
    source_path = _serialize_path(layer.source_path, project_dir)
    return {
        "layer_id": layer.layer_id,
        "name": layer.name,
        "source_path": source_path,
        "visible": layer.visible,
        "opacity": layer.opacity,
        "blend_mode": layer.blend_mode,
        "branches": [_serialize_branch(branch) for branch in layer.branches],
    }


def _serialize_branch(branch: LayerBranch) -> dict[str, object]:
    return {
        "branch_id": branch.branch_id,
        "name": branch.name,
        "enabled": branch.enabled,
        "opacity": branch.opacity,
        "blend_mode": branch.blend_mode,
        "source_branch_id": branch.source_branch_id,
        "filter_stack": [_serialize_stack_item(item) for item in branch.filter_stack],
    }


def _serialize_stack_item(item: FilterStackItem) -> dict[str, object]:
    return {
        "filter_key": item.filter_key,
        "enabled": item.enabled,
        "opacity": item.opacity,
        "blend_mode": item.blend_mode,
    }


def _deserialize_layer(payload: dict[str, object], project_dir: Path) -> ImageLayer:
    source_path = _deserialize_path(payload.get("source_path"), project_dir)
    image = QImage(str(source_path))

    branches_payload = payload.get("branches")
    branches: list[LayerBranch] = []
    if isinstance(branches_payload, list):
        branches = [_deserialize_branch(branch_data) for branch_data in branches_payload if isinstance(branch_data, dict)]

    if not branches:
        branches = [LayerBranch(name="Base Branch")]

    layer_id = payload.get("layer_id")
    layer_kwargs: dict[str, object] = {}
    if layer_id:
        layer_kwargs["layer_id"] = str(layer_id)

    return ImageLayer(
        name=str(payload.get("name") or "Layer"),
        source_path=source_path,
        image=image,
        visible=bool(payload.get("visible", True)),
        opacity=float(payload.get("opacity", 1.0)),
        blend_mode=str(payload.get("blend_mode") or "source_over"),
        branches=branches,
        **layer_kwargs,
    )


def _deserialize_branch(payload: dict[str, object]) -> LayerBranch:
    stack_payload = payload.get("filter_stack")
    filter_stack: list[FilterStackItem] = []
    if isinstance(stack_payload, list):
        for item_data in stack_payload:
            if not isinstance(item_data, dict):
                continue
            try:
                filter_stack.append(_deserialize_stack_item(item_data))
            except ValueError:
                continue

    branch_id = payload.get("branch_id")
    branch_kwargs: dict[str, object] = {}
    if branch_id:
        branch_kwargs["branch_id"] = str(branch_id)

    return LayerBranch(
        name=str(payload.get("name") or "Branch"),
        enabled=bool(payload.get("enabled", True)),
        opacity=float(payload.get("opacity", 1.0)),
        blend_mode=str(payload.get("blend_mode") or "source_over"),
        source_branch_id=str(payload["source_branch_id"]) if payload.get("source_branch_id") is not None else None,
        filter_stack=filter_stack,
        **branch_kwargs,
    )


def _deserialize_stack_item(payload: dict[str, object]) -> FilterStackItem:
    filter_key = str(payload.get("filter_key") or "").strip()
    if not filter_key:
        raise ValueError("Filter stack item is missing filter_key")
    return FilterStackItem(
        filter_key=filter_key,
        enabled=bool(payload.get("enabled", True)),
        opacity=float(payload.get("opacity", 1.0)),
        blend_mode=str(payload.get("blend_mode") or "replace"),
    )


def _serialize_path(source_path: Path, project_dir: Path) -> str:
    """Prefer project-relative paths to improve portability."""
    if not str(source_path):
        return ""
    resolved_path = source_path.resolve()
    try:
        return str(resolved_path.relative_to(project_dir))
    except ValueError:
        return str(resolved_path)


def _deserialize_path(value: object, project_dir: Path) -> Path:
    path_value = str(value or "").strip()
    if not path_value:
        return Path()
    parsed = Path(path_value)
    if parsed.is_absolute():
        return parsed
    return (project_dir / parsed).resolve()
