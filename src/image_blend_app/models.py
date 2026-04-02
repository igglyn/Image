from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtGui import QImage


@dataclass
class FilterStackItem:
    filter_key: str
    enabled: bool = True
    opacity: float = 1.0
    blend_mode: str = "replace"


@dataclass
class LayerBranch:
    name: str
    enabled: bool = True
    opacity: float = 1.0
    blend_mode: str = "source_over"
    filter_stack: list[FilterStackItem] = field(default_factory=list)


@dataclass
class ImageLayer:
    name: str
    source_path: Path
    image: QImage
    visible: bool = True
    opacity: float = 1.0
    blend_mode: str = "source_over"
    branches: list[LayerBranch] = field(default_factory=lambda: [LayerBranch(name="Base Branch")])
