from __future__ import annotations

from PySide6.QtGui import QImage, QPainter

from image_blend_app.filters.base import FilterRegistry
from image_blend_app.models import FilterStackItem, ImageLayer, LayerBranch


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


class LayerCompositor:
    def __init__(self, filter_registry: FilterRegistry) -> None:
        self._filters = filter_registry

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

        painter = QPainter(layer_out)
        try:
            for branch in layer.branches:
                if not branch.enabled:
                    continue
                branch_image = self._render_branch(layer.image, branch)
                painter.setOpacity(max(0.0, min(1.0, branch.opacity)))
                painter.setCompositionMode(BLEND_MODE_MAP.get(branch.blend_mode, BLEND_MODE_MAP["source_over"]))
                painter.drawImage(0, 0, branch_image)
        finally:
            painter.end()
        return layer_out

    def _render_branch(self, source_image: QImage, branch: LayerBranch) -> QImage:
        current = source_image.convertToFormat(QImage.Format.Format_ARGB32)
        for item in branch.filter_stack:
            if not item.enabled:
                continue
            image_filter = self._filters.get(item.filter_key)
            if image_filter is None:
                continue
            # CPU fallback today; shader_path in metadata is used for future Vulkan dispatch.
            filtered = image_filter.apply(current)
            current = self._blend_images(current, filtered, item)
        return current

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
