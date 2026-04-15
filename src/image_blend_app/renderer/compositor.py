from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QImage, QPainter

from image_blend_app.filters.base import FilterRegistry
from image_blend_app.models import FilterStackItem, ImageLayer, LayerBranch
from image_blend_app.renderer.shader_runtime import ShaderRuntime


BLEND_MODE_MAP = {
    "source_over": QPainter.CompositionMode.CompositionMode_SourceOver,
    "multiply": QPainter.CompositionMode.CompositionMode_Multiply,
    "screen": QPainter.CompositionMode.CompositionMode_Screen,
    "overlay": QPainter.CompositionMode.CompositionMode_Overlay,
    "darken": QPainter.CompositionMode.CompositionMode_Darken,
    "lighten": QPainter.CompositionMode.CompositionMode_Lighten,
    "addition": QPainter.CompositionMode.CompositionMode_Plus,
}

FILTER_BLEND_MODE_MAP = {
    "replace": QPainter.CompositionMode.CompositionMode_Source,
    **BLEND_MODE_MAP,
}


@dataclass
class BranchCache:
    source_signature: tuple[int, str | None, int]
    step_signatures: list[tuple[str, bool, float, str, tuple[tuple[str, int | float | str | bool], ...]]]
    stage_images: list[QImage]


class LayerCompositor:
    def __init__(self, filter_registry: FilterRegistry) -> None:
        self._filters = filter_registry
        self._branch_cache: dict[tuple[str, str], BranchCache] = {}
        self._shader_runtime = ShaderRuntime(shader_root=Path(__file__).resolve().parent.parent)
        for image_filter in self._filters.all():
            self._shader_runtime.register(image_filter.meta.key, image_filter.meta.shader_path)

    def composite(self, layers: list[ImageLayer]) -> QImage | None:
        visible_layers = [layer for layer in layers if layer.visible]
        if not visible_layers:
            return None

        width = max(layer.image.width() for layer in visible_layers)
        height = max(layer.image.height() for layer in visible_layers)
        canvas = QImage(width, height, QImage.Format.Format_ARGB32)
        canvas.fill(0)

        painter = QPainter(canvas)
        try:
            for layer in visible_layers:
                layer_image = self._render_layer(layer)
                painter.setOpacity(max(0.0, min(1.0, layer.opacity)))
                painter.setCompositionMode(BLEND_MODE_MAP.get(layer.blend_mode, BLEND_MODE_MAP["source_over"]))
                painter.drawImage(0, 0, layer_image)
        finally:
            painter.end()
        return canvas

    def _render_layer(self, layer: ImageLayer) -> QImage:
        layer_out = QImage(layer.image.width(), layer.image.height(), QImage.Format.Format_ARGB32)
        layer_out.fill(0)

        branch_by_id = {b.branch_id: b for b in layer.branches}
        computed: dict[str, QImage] = {}

        def render_branch(branch: LayerBranch, stack: set[str]) -> QImage:
            if branch.branch_id in computed:
                return computed[branch.branch_id]
            if branch.branch_id in stack:
                # Cycle fallback: break dependency and use layer source.
                image = layer.image.convertToFormat(QImage.Format.Format_ARGB32)
                computed[branch.branch_id] = self._render_filter_stack(image, layer.layer_id, branch, None)
                return computed[branch.branch_id]

            if branch.source_branch_id and branch.source_branch_id in branch_by_id:
                stack.add(branch.branch_id)
                source_image = render_branch(branch_by_id[branch.source_branch_id], stack)
                stack.remove(branch.branch_id)
                source_id = branch.source_branch_id
            else:
                source_image = layer.image
                source_id = None

            computed[branch.branch_id] = self._render_filter_stack(source_image, layer.layer_id, branch, source_id)
            return computed[branch.branch_id]

        painter = QPainter(layer_out)
        try:
            for branch in layer.branches:
                if not branch.enabled:
                    continue
                branch_image = render_branch(branch, set())
                painter.setOpacity(max(0.0, min(1.0, branch.opacity)))
                painter.setCompositionMode(BLEND_MODE_MAP.get(branch.blend_mode, BLEND_MODE_MAP["source_over"]))
                painter.drawImage(0, 0, branch_image)
        finally:
            painter.end()
        return layer_out

    def _render_filter_stack(
        self,
        source_image: QImage,
        layer_id: str,
        branch: LayerBranch,
        source_id: str | None,
    ) -> QImage:
        source = source_image.convertToFormat(QImage.Format.Format_ARGB32)
        source_signature = (source.cacheKey(), source_id, len(branch.filter_stack))
        step_signatures = [
            (
                item.filter_key,
                item.enabled,
                round(item.opacity, 4),
                item.blend_mode,
                self._settings_signature(item.settings),
            )
            for item in branch.filter_stack
        ]

        cache_key = (layer_id, branch.branch_id)
        cached = self._branch_cache.get(cache_key)

        start_idx = 0
        current = source
        stage_images: list[QImage] = []

        if cached and cached.source_signature == source_signature:
            max_shared = min(len(step_signatures), len(cached.step_signatures))
            while start_idx < max_shared and step_signatures[start_idx] == cached.step_signatures[start_idx]:
                start_idx += 1

            if start_idx > 0 and start_idx <= len(cached.stage_images):
                current = QImage(cached.stage_images[start_idx - 1])
                stage_images = [QImage(img) for img in cached.stage_images[:start_idx]]

        for idx in range(start_idx, len(branch.filter_stack)):
            item = branch.filter_stack[idx]
            if item.enabled:
                image_filter = self._filters.get(item.filter_key)
                if image_filter is not None:
                    filtered = image_filter.apply(
                        current,
                        shader_runtime=self._shader_runtime,
                        settings=item.settings,
                    )
                    current = self._blend_images(current, filtered, item)
            stage_images.append(QImage(current))

        self._branch_cache[cache_key] = BranchCache(
            source_signature=source_signature,
            step_signatures=step_signatures,
            stage_images=stage_images,
        )
        return current

    @staticmethod
    def _settings_signature(settings: dict[str, int | float | str | bool]) -> tuple[tuple[str, int | float | str | bool], ...]:
        return tuple(sorted((str(key), value) for key, value in settings.items()))

    def _blend_images(self, base: QImage, top: QImage, item: FilterStackItem) -> QImage:
        out = QImage(base)
        painter = QPainter(out)
        try:
            painter.setOpacity(max(0.0, min(1.0, item.opacity)))
            painter.setCompositionMode(
                FILTER_BLEND_MODE_MAP.get(item.blend_mode, FILTER_BLEND_MODE_MAP["replace"])
            )
            painter.drawImage(0, 0, top)
        finally:
            painter.end()
        return out
