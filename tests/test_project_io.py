from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from PySide6.QtGui import QImage
except ImportError:
    qtgui_module = types.ModuleType("PySide6.QtGui")

    class QImage:  # type: ignore[no-redef]
        class Format:
            Format_ARGB32 = 0

        def __init__(self, *args: object, **kwargs: object) -> None:
            self._path = str(args[0]) if args else ""

        def fill(self, _value: int) -> None:
            return None

        def save(self, path: str) -> bool:
            Path(path).write_bytes(b"fake-image")
            self._path = path
            return True

    qtgui_module.QImage = QImage

    pyside6_module = types.ModuleType("PySide6")
    pyside6_module.QtGui = qtgui_module
    sys.modules.setdefault("PySide6", pyside6_module)
    sys.modules.setdefault("PySide6.QtGui", qtgui_module)

from image_blend_app.models import FilterStackItem, ImageLayer, LayerBranch
from image_blend_app.project_io import load_project, save_project


class ProjectIOTests(unittest.TestCase):
    def test_save_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            image_path = tmp_path / "source.png"
            self._create_fixture_image(image_path)
            project_path = tmp_path / "project.json"

            layer = ImageLayer(
                name="Example Layer",
                source_path=image_path,
                image=QImage(str(image_path)),
                visible=False,
                opacity=0.75,
                blend_mode="multiply",
                branches=[
                    LayerBranch(
                        name="Base Branch",
                        enabled=True,
                        opacity=1.0,
                        blend_mode="source_over",
                        filter_stack=[
                            FilterStackItem(
                                filter_key="grayscale",
                                enabled=True,
                                opacity=0.5,
                                blend_mode="replace",
                                settings={"strength": 2},
                            )
                        ],
                    )
                ],
            )

            save_project(project_path, [layer])
            loaded_layers = load_project(project_path)

            self.assertEqual(len(loaded_layers), 1)
            loaded = loaded_layers[0]
            self.assertEqual(loaded.name, "Example Layer")
            self.assertEqual(loaded.source_path, image_path.resolve())
            self.assertFalse(loaded.visible)
            self.assertAlmostEqual(loaded.opacity, 0.75)
            self.assertEqual(loaded.blend_mode, "multiply")
            self.assertEqual(len(loaded.branches), 1)
            self.assertEqual(loaded.branches[0].name, "Base Branch")
            self.assertEqual(len(loaded.branches[0].filter_stack), 1)
            self.assertEqual(loaded.branches[0].filter_stack[0].filter_key, "grayscale")
            self.assertEqual(loaded.branches[0].filter_stack[0].settings, {"strength": 2})

    def test_save_uses_relative_source_path_within_project_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            images_dir = tmp_path / "assets"
            images_dir.mkdir(parents=True, exist_ok=True)
            image_path = images_dir / "source.png"
            self._create_fixture_image(image_path)
            project_path = tmp_path / "project.json"

            layer = ImageLayer(name="Relative Layer", source_path=image_path, image=QImage(str(image_path)))
            save_project(project_path, [layer])

            payload = json.loads(project_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["layers"][0]["source_path"], "assets/source.png")

    def test_load_skips_invalid_filter_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            image_path = tmp_path / "source.png"
            self._create_fixture_image(image_path)
            project_path = tmp_path / "project.json"

            project_payload = {
                "format": "image_blend_studio_project",
                "version": 1,
                "layers": [
                    {
                        "name": "Layer",
                        "source_path": "source.png",
                        "branches": [
                            {
                                "name": "Base",
                                "filter_stack": [
                                    {"enabled": True, "opacity": 1.0, "blend_mode": "replace"},
                                    {"filter_key": "invert", "enabled": True, "opacity": 1.0, "blend_mode": "replace"},
                                ],
                            }
                        ],
                    }
                ],
            }
            project_path.write_text(json.dumps(project_payload), encoding="utf-8")

            loaded_layers = load_project(project_path)
            loaded_stack = loaded_layers[0].branches[0].filter_stack
            self.assertEqual(len(loaded_stack), 1)
            self.assertEqual(loaded_stack[0].filter_key, "invert")

    @staticmethod
    def _create_fixture_image(path: Path) -> None:
        image = QImage(2, 2, QImage.Format.Format_ARGB32)
        image.fill(0xFFFFFFFF)
        image.save(str(path))


if __name__ == "__main__":
    unittest.main()
