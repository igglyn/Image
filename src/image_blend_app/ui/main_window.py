from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from image_blend_app.filters.base import FilterRegistry
from image_blend_app.models import FilterStackItem, ImageLayer, LayerBranch
from image_blend_app.renderer.compositor import BLEND_MODE_MAP, FILTER_BLEND_MODE_MAP, LayerCompositor


class MainWindow(QMainWindow):
    def __init__(self, filter_registry: FilterRegistry) -> None:
        super().__init__()
        self.setWindowTitle("Image Blend Studio")
        self.resize(1400, 820)

        self._layers: list[ImageLayer] = []
        self._filters = filter_registry
        self._compositor = LayerCompositor(filter_registry)

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)

        left_panel = QVBoxLayout()
        root_layout.addLayout(left_panel, 1)

        self.layer_list = QListWidget()
        self.layer_list.currentRowChanged.connect(self._on_layer_selected)
        self.layer_list.itemChanged.connect(self._on_layer_enabled_changed)
        left_panel.addWidget(QLabel("Layers (topmost = last)"))
        left_panel.addWidget(self.layer_list)

        import_btn = QPushButton("Import Image(s)")
        import_btn.clicked.connect(self._import_images)
        left_panel.addWidget(import_btn)

        layer_buttons = QHBoxLayout()
        remove_layer_btn = QPushButton("Remove")
        remove_layer_btn.clicked.connect(self._remove_layer)
        up_layer_btn = QPushButton("Up")
        up_layer_btn.clicked.connect(lambda: self._move_layer(-1))
        down_layer_btn = QPushButton("Down")
        down_layer_btn.clicked.connect(lambda: self._move_layer(1))
        dup_layer_btn = QPushButton("Duplicate")
        dup_layer_btn.clicked.connect(self._duplicate_layer)
        layer_buttons.addWidget(remove_layer_btn)
        layer_buttons.addWidget(up_layer_btn)
        layer_buttons.addWidget(down_layer_btn)
        layer_buttons.addWidget(dup_layer_btn)
        left_panel.addLayout(layer_buttons)

        layer_controls = QFormLayout()
        self.layer_blend_combo = QComboBox()
        for mode in BLEND_MODE_MAP:
            self.layer_blend_combo.addItem(mode)
        self.layer_blend_combo.currentTextChanged.connect(self._on_layer_blend_changed)
        layer_controls.addRow("Layer Blend", self.layer_blend_combo)

        self.layer_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.layer_opacity_slider.setRange(0, 100)
        self.layer_opacity_slider.setValue(100)
        self.layer_opacity_slider.valueChanged.connect(self._on_layer_opacity_changed)
        layer_controls.addRow("Layer Opacity", self.layer_opacity_slider)

        self.layer_visible_checkbox = QCheckBox("Visible")
        self.layer_visible_checkbox.setChecked(True)
        self.layer_visible_checkbox.toggled.connect(self._on_layer_visible_changed)
        layer_controls.addRow(self.layer_visible_checkbox)
        left_panel.addLayout(layer_controls)

        middle_panel = QVBoxLayout()
        root_layout.addLayout(middle_panel, 1)

        middle_panel.addWidget(QLabel("Import Area (Source Images In Play)"))
        self.source_images_list = QListWidget()
        self.source_images_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        middle_panel.addWidget(self.source_images_list)

        import_controls = QHBoxLayout()
        add_sources_btn = QPushButton("Add Source Image(s)")
        add_sources_btn.clicked.connect(self._import_images)
        import_controls.addWidget(add_sources_btn)
        middle_panel.addLayout(import_controls)

        middle_panel.addWidget(QLabel("Available Filters (double-click to add to selected layer)"))
        self.available_filters = QListWidget()
        self.available_filters.itemDoubleClicked.connect(self._on_add_filter)
        middle_panel.addWidget(self.available_filters)

        middle_panel.addWidget(QLabel("Selected Layer Filter Stack"))
        self.stack_list = QListWidget()
        self.stack_list.currentRowChanged.connect(self._on_stack_item_selected)
        self.stack_list.itemChanged.connect(self._on_stack_enabled_changed)
        middle_panel.addWidget(self.stack_list)

        stack_buttons = QHBoxLayout()
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_stack_item)
        up_btn = QPushButton("Up")
        up_btn.clicked.connect(lambda: self._move_stack_item(-1))
        down_btn = QPushButton("Down")
        down_btn.clicked.connect(lambda: self._move_stack_item(1))
        stack_buttons.addWidget(remove_btn)
        stack_buttons.addWidget(up_btn)
        stack_buttons.addWidget(down_btn)
        middle_panel.addLayout(stack_buttons)

        stack_controls = QFormLayout()
        self.filter_blend_combo = QComboBox()
        for mode in FILTER_BLEND_MODE_MAP:
            self.filter_blend_combo.addItem(mode)
        self.filter_blend_combo.currentTextChanged.connect(self._on_stack_blend_changed)
        stack_controls.addRow("Filter Blend", self.filter_blend_combo)

        self.filter_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.filter_opacity_slider.setRange(0, 100)
        self.filter_opacity_slider.setValue(100)
        self.filter_opacity_slider.valueChanged.connect(self._on_stack_opacity_changed)
        stack_controls.addRow("Filter Opacity", self.filter_opacity_slider)
        middle_panel.addLayout(stack_controls)

        self.preview = QLabel("Import images to begin")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(600, 600)
        self.preview.setStyleSheet("background: #1b1b1b; color: #ddd;")
        root_layout.addWidget(self.preview, 3)

        self._populate_available_filters()

    def _populate_available_filters(self) -> None:
        self.available_filters.clear()
        for image_filter in self._filters.all():
            item = QListWidgetItem(image_filter.meta.display_name)
            item.setData(Qt.ItemDataRole.UserRole, image_filter.meta.key)
            self.available_filters.addItem(item)

    def _active_layer(self) -> ImageLayer | None:
        idx = self.layer_list.currentRow()
        if idx < 0 or idx >= len(self._layers):
            return None
        return self._layers[idx]

    def _active_branch(self) -> LayerBranch | None:
        layer = self._active_layer()
        if layer is None:
            return None
        if not layer.branches:
            return None
        return layer.branches[0]

    def _active_stack_item(self) -> FilterStackItem | None:
        branch = self._active_branch()
        if branch is None:
            return None
        idx = self.stack_list.currentRow()
        if idx < 0 or idx >= len(branch.filter_stack):
            return None
        return branch.filter_stack[idx]

    def _rebuild_layer_list(self, selected_index: int | None = None) -> None:
        self.layer_list.blockSignals(True)
        self.layer_list.clear()
        for layer in self._layers:
            item = QListWidgetItem(layer.name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if layer.visible else Qt.CheckState.Unchecked)
            self.layer_list.addItem(item)
        self.layer_list.blockSignals(False)
        self._refresh_source_images_list()

        if not self._layers:
            return
        if selected_index is None:
            selected_index = min(len(self._layers) - 1, self.layer_list.currentRow())
        selected_index = max(0, min(selected_index, len(self._layers) - 1))
        self.layer_list.setCurrentRow(selected_index)

    def _refresh_source_images_list(self) -> None:
        self.source_images_list.clear()
        for index, layer in enumerate(self._layers, start=1):
            source_path = str(layer.source_path) if str(layer.source_path) else "Untitled"
            self.source_images_list.addItem(f"{index}. {layer.name} — {source_path}")

    def _import_images(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Select images", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        for file in files:
            path = Path(file)
            image = QImage(str(path))
            if image.isNull():
                continue
            layer = ImageLayer(name=path.name, source_path=path, image=image)
            self._layers.append(layer)
        self._rebuild_layer_list(selected_index=len(self._layers) - 1)
        self._render()

    def _remove_layer(self) -> None:
        idx = self.layer_list.currentRow()
        if idx < 0 or idx >= len(self._layers):
            return
        self._layers.pop(idx)
        self._rebuild_layer_list(selected_index=max(0, idx - 1))
        if not self._layers:
            self.stack_list.clear()
        self._render()

    def _duplicate_layer(self) -> None:
        layer = self._active_layer()
        if layer is None:
            return

        source_to_new_id: dict[str, str] = {}
        cloned_branches: list[LayerBranch] = []
        for branch in layer.branches:
            clone = LayerBranch(
                name=branch.name,
                enabled=branch.enabled,
                opacity=branch.opacity,
                blend_mode=branch.blend_mode,
                source_branch_id=branch.source_branch_id,
                filter_stack=[
                    FilterStackItem(
                        filter_key=stack_item.filter_key,
                        enabled=stack_item.enabled,
                        opacity=stack_item.opacity,
                        blend_mode=stack_item.blend_mode,
                    )
                    for stack_item in branch.filter_stack
                ],
            )
            source_to_new_id[branch.branch_id] = clone.branch_id
            cloned_branches.append(clone)

        for clone in cloned_branches:
            if clone.source_branch_id in source_to_new_id:
                clone.source_branch_id = source_to_new_id[clone.source_branch_id]

        self._layers.append(
            ImageLayer(
                name=f"{layer.name} Copy",
                source_path=layer.source_path,
                image=QImage(layer.image),
                visible=layer.visible,
                opacity=layer.opacity,
                blend_mode=layer.blend_mode,
                branches=cloned_branches,
            )
        )
        self._rebuild_layer_list(selected_index=len(self._layers) - 1)
        self._render()

    def _move_layer(self, offset: int) -> None:
        idx = self.layer_list.currentRow()
        if idx < 0 or idx >= len(self._layers):
            return
        new_idx = idx + offset
        if not (0 <= new_idx < len(self._layers)):
            return
        self._layers[idx], self._layers[new_idx] = self._layers[new_idx], self._layers[idx]
        self._rebuild_layer_list(selected_index=new_idx)
        self._render()

    def _on_layer_enabled_changed(self, row_item: QListWidgetItem) -> None:
        idx = self.layer_list.row(row_item)
        if idx < 0 or idx >= len(self._layers):
            return
        checked = row_item.checkState() == Qt.CheckState.Checked
        self._layers[idx].visible = checked
        if idx == self.layer_list.currentRow():
            self.layer_visible_checkbox.blockSignals(True)
            self.layer_visible_checkbox.setChecked(checked)
            self.layer_visible_checkbox.blockSignals(False)
        self._render()

    def _on_layer_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._layers):
            return
        layer = self._layers[row]
        self.layer_blend_combo.setCurrentText(layer.blend_mode)
        self.layer_opacity_slider.setValue(int(layer.opacity * 100))
        self.layer_visible_checkbox.setChecked(layer.visible)
        base_branch = self._active_branch()
        if base_branch is None:
            self.stack_list.clear()
        else:
            self._populate_stack(base_branch)
        self._render()

    def _populate_stack(self, branch: LayerBranch) -> None:
        self.stack_list.blockSignals(True)
        self.stack_list.clear()
        for item in branch.filter_stack:
            filter_obj = self._filters.get(item.filter_key)
            name = filter_obj.meta.display_name if filter_obj else item.filter_key
            row_item = QListWidgetItem(name)
            row_item.setData(Qt.ItemDataRole.UserRole, item.filter_key)
            row_item.setFlags(row_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row_item.setCheckState(Qt.CheckState.Checked if item.enabled else Qt.CheckState.Unchecked)
            self.stack_list.addItem(row_item)
        self.stack_list.blockSignals(False)
        if branch.filter_stack:
            self.stack_list.setCurrentRow(0)

    def _on_layer_blend_changed(self, value: str) -> None:
        layer = self._active_layer()
        if layer is None:
            return
        layer.blend_mode = value
        self._render()

    def _on_layer_opacity_changed(self, value: int) -> None:
        layer = self._active_layer()
        if layer is None:
            return
        layer.opacity = value / 100.0
        self._render()

    def _on_layer_visible_changed(self, checked: bool) -> None:
        layer = self._active_layer()
        if layer is None:
            return
        layer.visible = checked
        current_item = self.layer_list.item(self.layer_list.currentRow())
        if current_item is not None:
            current_item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self._render()

    def _on_add_filter(self, item: QListWidgetItem) -> None:
        branch = self._active_branch()
        if branch is None:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        branch.filter_stack.append(FilterStackItem(filter_key=key))
        self._populate_stack(branch)
        self.stack_list.setCurrentRow(len(branch.filter_stack) - 1)
        self._render()

    def _remove_stack_item(self) -> None:
        branch = self._active_branch()
        idx = self.stack_list.currentRow()
        if branch is None or idx < 0:
            return
        branch.filter_stack.pop(idx)
        self._populate_stack(branch)
        if branch.filter_stack:
            self.stack_list.setCurrentRow(min(idx, len(branch.filter_stack) - 1))
        self._render()

    def _move_stack_item(self, offset: int) -> None:
        branch = self._active_branch()
        idx = self.stack_list.currentRow()
        if branch is None or idx < 0:
            return
        new_idx = idx + offset
        if not (0 <= new_idx < len(branch.filter_stack)):
            return
        branch.filter_stack[idx], branch.filter_stack[new_idx] = branch.filter_stack[new_idx], branch.filter_stack[idx]
        self._populate_stack(branch)
        self.stack_list.setCurrentRow(new_idx)
        self._render()

    def _on_stack_item_selected(self, row: int) -> None:
        branch = self._active_branch()
        if branch is None or row < 0 or row >= len(branch.filter_stack):
            return
        item = branch.filter_stack[row]
        self.filter_blend_combo.setCurrentText(item.blend_mode)
        self.filter_opacity_slider.setValue(int(item.opacity * 100))

    def _on_stack_enabled_changed(self, row_item: QListWidgetItem) -> None:
        branch = self._active_branch()
        if branch is None:
            return
        idx = self.stack_list.row(row_item)
        if idx < 0 or idx >= len(branch.filter_stack):
            return
        branch.filter_stack[idx].enabled = row_item.checkState() == Qt.CheckState.Checked
        self._render()

    def _on_stack_blend_changed(self, value: str) -> None:
        item = self._active_stack_item()
        if item is None:
            return
        item.blend_mode = value
        self._render()

    def _on_stack_opacity_changed(self, value: int) -> None:
        item = self._active_stack_item()
        if item is None:
            return
        item.opacity = value / 100.0
        self._render()

    def _render(self) -> None:
        image = self._compositor.composite(self._layers)
        if image is None:
            self.preview.setText("Import images to begin")
            self.preview.setPixmap(QPixmap())
            return

        pixmap = QPixmap.fromImage(image)
        scaled = pixmap.scaled(
            self.preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setPixmap(scaled)
