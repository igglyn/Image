from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from image_blend_app.filters.base import FilterRegistry
from image_blend_app.filters.builtin import (
    BoxBlurFilter,
    EdgeDetectionFilter,
    GrayscaleFilter,
    InvertFilter,
)
from image_blend_app.ui.main_window import MainWindow


def build_registry() -> FilterRegistry:
    registry = FilterRegistry()
    registry.register(GrayscaleFilter())
    registry.register(InvertFilter())
    registry.register(BoxBlurFilter())
    registry.register(EdgeDetectionFilter())
    return registry


def run() -> int:
    app = QApplication(sys.argv)
    window = MainWindow(build_registry())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
