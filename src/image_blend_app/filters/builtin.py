from __future__ import annotations

from PySide6.QtGui import QColor, QImage

from .base import FilterMeta, ImageFilter


class GrayscaleFilter(ImageFilter):
    meta = FilterMeta(
        key="grayscale",
        display_name="Grayscale",
        shader_path="shaders/grayscale.comp",
    )

    def apply(self, image: QImage, shader_runtime=None, settings=None) -> QImage:
        if shader_runtime is not None:
            shader_result = shader_runtime.run(self.meta.key, self.meta.shader_path, image, settings=settings)
            if shader_result is not None:
                return shader_result

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

    def apply(self, image: QImage, shader_runtime=None, settings=None) -> QImage:
        if shader_runtime is not None:
            shader_result = shader_runtime.run(self.meta.key, self.meta.shader_path, image, settings=settings)
            if shader_result is not None:
                return shader_result

        out = image.convertToFormat(QImage.Format.Format_ARGB32)
        out.invertPixels(QImage.InvertMode.InvertRgb)
        return out


class BoxBlurFilter(ImageFilter):
    meta = FilterMeta(
        key="box_blur",
        display_name="Box Blur",
        shader_path="shaders/box_blur.comp",
    )

    def apply(self, image: QImage, shader_runtime=None, settings=None) -> QImage:
        if shader_runtime is not None:
            shader_result = shader_runtime.run(self.meta.key, self.meta.shader_path, image, settings=settings)
            if shader_result is not None:
                return shader_result

        source = image.convertToFormat(QImage.Format.Format_ARGB32)
        width = source.width()
        height = source.height()
        out = QImage(width, height, QImage.Format.Format_ARGB32)
        raw_radius = (settings or {}).get("radius", 1)
        try:
            radius = int(raw_radius)
        except (TypeError, ValueError):
            radius = 1
        radius = max(0, min(32, radius))

        for y in range(height):
            for x in range(width):
                r_total = 0
                g_total = 0
                b_total = 0
                a_total = 0
                count = 0

                for ky in range(-radius, radius + 1):
                    yy = y + ky
                    if yy < 0 or yy >= height:
                        continue
                    for kx in range(-radius, radius + 1):
                        xx = x + kx
                        if xx < 0 or xx >= width:
                            continue
                        c = source.pixelColor(xx, yy)
                        r_total += c.red()
                        g_total += c.green()
                        b_total += c.blue()
                        a_total += c.alpha()
                        count += 1

                out.setPixelColor(
                    x,
                    y,
                    QColor(
                        r_total // count,
                        g_total // count,
                        b_total // count,
                        a_total // count,
                    ),
                )
        return out


class EdgeDetectionFilter(ImageFilter):
    meta = FilterMeta(
        key="edge_detect",
        display_name="Edge Detection",
        shader_path="shaders/edge_detect.comp",
    )

    def apply(self, image: QImage, shader_runtime=None, settings=None) -> QImage:
        source = image.convertToFormat(QImage.Format.Format_ARGB32)
        width = source.width()
        height = source.height()
        out = QImage(width, height, QImage.Format.Format_ARGB32)

        gray: list[list[int]] = [[0] * width for _ in range(height)]
        for y in range(height):
            for x in range(width):
                c = source.pixelColor(x, y)
                gray[y][x] = int(0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue())

        gx_kernel = [
            [-1, 0, 1],
            [-2, 0, 2],
            [-1, 0, 1],
        ]
        gy_kernel = [
            [-1, -2, -1],
            [0, 0, 0],
            [1, 2, 1],
        ]

        for y in range(height):
            for x in range(width):
                gx = 0
                gy = 0

                for ky in range(-1, 2):
                    yy = y + ky
                    if yy < 0 or yy >= height:
                        continue
                    for kx in range(-1, 2):
                        xx = x + kx
                        if xx < 0 or xx >= width:
                            continue
                        intensity = gray[yy][xx]
                        gx += intensity * gx_kernel[ky + 1][kx + 1]
                        gy += intensity * gy_kernel[ky + 1][kx + 1]

                magnitude = min(255, int((gx * gx + gy * gy) ** 0.5))
                alpha = source.pixelColor(x, y).alpha()
                out.setPixelColor(x, y, QColor(magnitude, magnitude, magnitude, alpha))
        return out
