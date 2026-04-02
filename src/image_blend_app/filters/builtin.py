from __future__ import annotations

from PySide6.QtGui import QColor, QImage

from .base import FilterMeta, ImageFilter


class GrayscaleFilter(ImageFilter):
    meta = FilterMeta(
        key="grayscale",
        display_name="Grayscale",
        shader_path="shaders/grayscale.comp",
    )

    def apply(self, image: QImage) -> QImage:
        out = image.convertToFormat(QImage.Format.Format_ARGB32)
        for y in range(out.height()):
            for x in range(out.width()):
                c = out.pixelColor(x, y)
                gray = int(0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue())
                out.setPixelColor(x, y, QColor(gray, gray, gray, c.alpha()))
        return out


class InvertFilter(ImageFilter):
    meta = FilterMeta(
        key="invert",
        display_name="Invert",
        shader_path="shaders/invert.comp",
    )

    def apply(self, image: QImage) -> QImage:
        out = image.convertToFormat(QImage.Format.Format_ARGB32)
        out.invertPixels(QImage.InvertMode.InvertRgb)
        return out
