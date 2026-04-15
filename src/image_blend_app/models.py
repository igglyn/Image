from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from PySide6.QtGui import QImage


def _id() -> str:
    return uuid4().hex


@dataclass
class FilterStackItem:
    filter_key: str
    enabled: bool = True
    opacity: float = 1.0
    blend_mode: str = "replace"
    settings: dict[str, int | float | str | bool] = field(default_factory=dict)


@dataclass
class LayerBranch:
    branch_id: str = field(default_factory=_id)
    name: str = "Branch"
    enabled: bool = True
    opacity: float = 1.0
    blend_mode: str = "source_over"
    source_branch_id: str | None = None
    filter_stack: list[FilterStackItem] = field(default_factory=list)


@dataclass
class ImageLayer:
    layer_id: str = field(default_factory=_id)
    name: str = "Layer"
    source_path: Path = Path()
    image: QImage = field(default_factory=QImage)
    visible: bool = True
    opacity: float = 1.0
    blend_mode: str = "source_over"
    branches: list[LayerBranch] = field(default_factory=lambda: [LayerBranch(name="Base Branch")])
