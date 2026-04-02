from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from PySide6.QtGui import QImage

from image_blend_app.renderer.shader_runtime import ShaderRuntime

@dataclass(frozen=True)
class FilterMeta:
    key: str
    display_name: str
    shader_path: str | None = None


class ImageFilter(ABC):
    meta: FilterMeta

    @abstractmethod
    def apply(self, image: QImage, shader_runtime: ShaderRuntime | None = None) -> QImage:
        raise NotImplementedError


class FilterRegistry:
    def __init__(self) -> None:
        self._filters: dict[str, ImageFilter] = {}

    def register(self, image_filter: ImageFilter) -> None:
        self._filters[image_filter.meta.key] = image_filter

    def all(self) -> list[ImageFilter]:
        return list(self._filters.values())

    def get(self, key: str) -> ImageFilter | None:
        return self._filters.get(key)
