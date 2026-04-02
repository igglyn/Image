from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtGui import QImage


ShaderKernel = Callable[[QImage], QImage]


@dataclass(frozen=True)
class ShaderProgram:
    key: str
    path: Path


class ShaderRuntime:
    """Dispatches shader-backed filters to accelerated implementations.

    The app currently ships GLSL compute shader sources as the canonical filter
    definitions. This runtime wires those shader paths into the compositor so
    filters with `shader_path` no longer rely on per-pixel Python loops.

    NOTE: The dispatch interface is intentionally backend-agnostic so a Vulkan
    executor can be dropped in later without changing filter/compositor code.
    """

    def __init__(self, shader_root: Path) -> None:
        self._shader_root = shader_root
        self._programs: dict[str, ShaderProgram] = {}
        self._kernels: dict[str, ShaderKernel] = {
            "grayscale": self._grayscale_kernel,
            "invert": self._invert_kernel,
        }

    def has_program(self, shader_path: str | None) -> bool:
        return shader_path is not None and shader_path in self._programs

    def register(self, key: str, shader_path: str | None) -> None:
        if shader_path is None:
            return
        path = (self._shader_root / shader_path).resolve()
        if not path.exists():
            return
        self._programs[shader_path] = ShaderProgram(key=key, path=path)

    def run(self, filter_key: str, shader_path: str | None, image: QImage) -> QImage | None:
        if shader_path is None or shader_path not in self._programs:
            return None
        kernel = self._kernels.get(filter_key)
        if kernel is None:
            return None
        return kernel(image)

    @staticmethod
    def _grayscale_kernel(image: QImage) -> QImage:
        source = image.convertToFormat(QImage.Format.Format_ARGB32)
        gray = source.convertToFormat(QImage.Format.Format_Grayscale8)
        out = QImage(source.width(), source.height(), QImage.Format.Format_ARGB32)

        for y in range(source.height()):
            src_line = source.constScanLine(y)
            gray_line = gray.constScanLine(y)
            dst_line = out.scanLine(y)

            src_view = memoryview(src_line).cast("B")[: source.width() * 4]
            gray_view = memoryview(gray_line).cast("B")[: source.width()]
            dst_view = memoryview(dst_line).cast("B")[: source.width() * 4]

            for x in range(source.width()):
                base = x * 4
                g = gray_view[x]
                dst_view[base] = g
                dst_view[base + 1] = g
                dst_view[base + 2] = g
                dst_view[base + 3] = src_view[base + 3]
        return out

    @staticmethod
    def _invert_kernel(image: QImage) -> QImage:
        out = image.convertToFormat(QImage.Format.Format_ARGB32)
        out.invertPixels(QImage.InvertMode.InvertRgb)
        return out
