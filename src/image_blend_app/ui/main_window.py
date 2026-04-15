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
    QMessageBox,
    QPushButton,
    QSlider,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from image_blend_app.filters.base import FilterRegistry
from image_blend_app.models import FilterStackItem, ImageLayer, LayerBranch
from image_blend_app.project_io import load_project, save_project
from image_blend_app.renderer.compositor import BLEND_MODE_MAP, FILTER_BLEND_MODE_MAP, LayerCompositor

NODE_TYPE_ROLE = int(Qt.ItemDataRole.UserRole)
LAYER_INDEX_ROLE = int(Qt.ItemDataRole.UserRole) + 1
EFFECT_INDEX_ROLE = int(Qt.ItemDataRole.UserRole) + 2


class MainWindow(QMainWindow):
    def __init__(self, filter_registry: FilterRegistry) -> None:
        super().__init__()
        self.setWindowTitle("Image Blend Studio")
        self.resize(1450, 860)

        self._layers: list[ImageLayer] = []
        self._filters = filter_registry
        self._compositor = LayerCompositor(filter_registry)

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)

        # Left: Structure tree (group -> image -> effects)
        left_panel = QVBoxLayout()
        root_layout.addLayout(left_panel, 2)

        left_panel.addWidget(QLabel("Structure (Group / Image / Effects)"))
        self.structure_tree = QTreeWidget()
        self.structure_tree.setColumnCount(4)
        self.structure_tree.setHeaderLabels(["Item", "Visible", "Blend", "Opacity"])
        self.structure_tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        self.structure_tree.itemChanged.connect(self._on_tree_item_changed)
        left_panel.addWidget(self.structure_tree)

        tree_buttons = QHBoxLayout()
        import_btn = QPushButton("Import")
        import_btn.clicked.connect(self._import_images)
        save_project_btn = QPushButton("Save")
        save_project_btn.clicked.connect(self._save_project)
        load_project_btn = QPushButton("Load")
        load_project_btn.clicked.connect(self._load_project)
        tree_buttons.addWidget(import_btn)
        tree_buttons.addWidget(save_project_btn)
        tree_buttons.addWidget(load_project_btn)
        left_panel.addLayout(tree_buttons)

        layer_buttons = QHBoxLayout()
        remove_layer_btn = QPushButton("Remove Image")
        remove_layer_btn.clicked.connect(self._remove_layer)
        up_layer_btn = QPushButton("Move Up")
        up_layer_btn.clicked.connect(lambda: self._move_layer(-1))
        down_layer_btn = QPushButton("Move Down")
        down_layer_btn.clicked.connect(lambda: self._move_layer(1))
        dup_layer_btn = QPushButton("Duplicate")
        dup_layer_btn.clicked.connect(self._duplicate_layer)
        layer_buttons.addWidget(remove_layer_btn)
        layer_buttons.addWidget(up_layer_btn)
        layer_buttons.addWidget(down_layer_btn)
        layer_buttons.addWidget(dup_layer_btn)
        left_panel.addLayout(layer_buttons)

        # Center: image preview
        center_panel = QVBoxLayout()
        root_layout.addLayout(center_panel, 3)
        self.preview = QLabel("Import images to begin")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(700, 700)
        self.preview.setStyleSheet("background: #1b1b1b; color: #ddd;")
        center_panel.addWidget(self.preview)

        # Right: three stacked sections
        right_panel = QVBoxLayout()
        root_layout.addLayout(right_panel, 2)

        right_panel.addWidget(QLabel("Import Area (thumbnails)"))
        self.source_images_list = QListWidget()
        self.source_images_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        right_panel.addWidget(self.source_images_list, 1)

        right_panel.addWidget(QLabel("Filters"))
        self.available_filters = QListWidget()
        self.available_filters.itemDoubleClicked.connect(self._on_add_filter)
        right_panel.addWidget(self.available_filters, 1)

        right_panel.addWidget(QLabel("Filter / Node Options"))
        options_layout = QVBoxLayout()
        right_panel.addLayout(options_layout, 1)

        self.options_target = QLabel("Select an image or effect in the tree")
        options_layout.addWidget(self.options_target)

        controls = QFormLayout()
        self.node_visible_checkbox = QCheckBox("Visible / Enabled")
        self.node_visible_checkbox.toggled.connect(self._on_selected_visibility_changed)
        controls.addRow(self.node_visible_checkbox)

        self.node_blend_combo = QComboBox()
        self.node_blend_combo.currentTextChanged.connect(self._on_selected_blend_changed)
        controls.addRow("Blend", self.node_blend_combo)

        self.node_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.node_opacity_slider.setRange(0, 100)
        self.node_opacity_slider.valueChanged.connect(self._on_selected_opacity_changed)
        controls.addRow("Opacity", self.node_opacity_slider)

        options_layout.addLayout(controls)

        effect_buttons = QHBoxLayout()
        remove_filter_btn = QPushButton("Remove Effect")
        remove_filter_btn.clicked.connect(self._remove_stack_item)
        up_filter_btn = QPushButton("Effect Up")
        up_filter_btn.clicked.connect(lambda: self._move_stack_item(-1))
        down_filter_btn = QPushButton("Effect Down")
        down_filter_btn.clicked.connect(lambda: self._move_stack_item(1))
        effect_buttons.addWidget(remove_filter_btn)
        effect_buttons.addWidget(up_filter_btn)
        effect_buttons.addWidget(down_filter_btn)
        options_layout.addLayout(effect_buttons)

        self._populate_available_filters()
        self._rebuild_structure_tree()

    def _populate_available_filters(self) -> None:
        self.available_filters.clear()
        for image_filter in self._filters.all():
            item = QListWidgetItem(image_filter.meta.display_name)
            item.setData(Qt.ItemDataRole.UserRole, image_filter.meta.key)
            self.available_filters.addItem(item)

    def _selected_tree_item(self) -> QTreeWidgetItem | None:
        selected = self.structure_tree.selectedItems()
        return selected[0] if selected else None

    def _active_layer(self) -> ImageLayer | None:
        selected_item = self._selected_tree_item()
        if selected_item is None:
            return self._layers[0] if self._layers else None

        layer_index = selected_item.data(0, LAYER_INDEX_ROLE)
        if layer_index is None and selected_item.parent() is not None:
            layer_index = selected_item.parent().data(0, LAYER_INDEX_ROLE)
        if not isinstance(layer_index, int):
            return None
        if not (0 <= layer_index < len(self._layers)):
            return None
        return self._layers[layer_index]

    def _active_branch(self) -> LayerBranch | None:
        layer = self._active_layer()
        if layer is None or not layer.branches:
            return None
        return layer.branches[0]

    def _selected_effect_index(self) -> int | None:
        selected_item = self._selected_tree_item()
        if selected_item is None:
            return None
        effect_index = selected_item.data(0, EFFECT_INDEX_ROLE)
        return effect_index if isinstance(effect_index, int) else None

    def _active_stack_item(self) -> FilterStackItem | None:
        branch = self._active_branch()
        effect_index = self._selected_effect_index()
        if branch is None or effect_index is None:
            return None
        if not (0 <= effect_index < len(branch.filter_stack)):
            return None
        return branch.filter_stack[effect_index]

    def _rebuild_structure_tree(self) -> None:
        self.structure_tree.blockSignals(True)
        self.structure_tree.clear()

        group_item = QTreeWidgetItem(["Main Group", "✓", "source_over", "100%"])
        group_item.setData(0, NODE_TYPE_ROLE, "group")
        group_item.setFlags(group_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.structure_tree.addTopLevelItem(group_item)

        for layer_index, layer in enumerate(self._layers):
            layer_item = QTreeWidgetItem([layer.name, "", layer.blend_mode, f"{int(layer.opacity * 100)}%"])
            layer_item.setData(0, NODE_TYPE_ROLE, "image")
            layer_item.setData(0, LAYER_INDEX_ROLE, layer_index)
            layer_item.setFlags(layer_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            layer_item.setCheckState(0, Qt.CheckState.Checked if layer.visible else Qt.CheckState.Unchecked)
            group_item.addChild(layer_item)

            branch = layer.branches[0] if layer.branches else None
            if branch is None:
                continue

            for effect_index, effect in enumerate(branch.filter_stack):
                filter_obj = self._filters.get(effect.filter_key)
                effect_name = filter_obj.meta.display_name if filter_obj else effect.filter_key
                effect_item = QTreeWidgetItem([
                    f"Effect: {effect_name}",
                    "",
                    effect.blend_mode,
                    f"{int(effect.opacity * 100)}%",
                ])
                effect_item.setData(0, NODE_TYPE_ROLE, "effect")
                effect_item.setData(0, LAYER_INDEX_ROLE, layer_index)
                effect_item.setData(0, EFFECT_INDEX_ROLE, effect_index)
                effect_item.setFlags(effect_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                effect_item.setCheckState(0, Qt.CheckState.Checked if effect.enabled else Qt.CheckState.Unchecked)
                layer_item.addChild(effect_item)

        group_item.setExpanded(True)
        for idx in range(group_item.childCount()):
            group_item.child(idx).setExpanded(True)

        self.structure_tree.blockSignals(False)
        self._refresh_source_images_list()

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
            self._layers.append(ImageLayer(name=path.name, source_path=path, image=image))
        self._rebuild_structure_tree()
        self._render()

    def _save_project(self) -> None:
        if not self._layers:
            QMessageBox.information(self, "Save Project", "There are no images to save.")
            return
        file, _ = QFileDialog.getSaveFileName(self, "Save project", "", "Image Blend Project (*.json)")
        if not file:
            return
        try:
            save_project(Path(file), self._layers)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Save Project Failed", str(exc))

    def _load_project(self) -> None:
        file, _ = QFileDialog.getOpenFileName(self, "Load project", "", "Image Blend Project (*.json)")
        if not file:
            return
        try:
            self._layers = load_project(Path(file))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Load Project Failed", str(exc))
            return
        self._rebuild_structure_tree()
        self._render()

    def _remove_layer(self) -> None:
        layer = self._active_layer()
        if layer is None:
            return
        self._layers.remove(layer)
        self._rebuild_structure_tree()
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
        self._rebuild_structure_tree()
        self._render()

    def _move_layer(self, offset: int) -> None:
        layer = self._active_layer()
        if layer is None:
            return
        idx = self._layers.index(layer)
        new_idx = idx + offset
        if not (0 <= new_idx < len(self._layers)):
            return
        self._layers[idx], self._layers[new_idx] = self._layers[new_idx], self._layers[idx]
        self._rebuild_structure_tree()
        self._render()

    def _on_add_filter(self, item: QListWidgetItem) -> None:
        branch = self._active_branch()
        if branch is None:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        branch.filter_stack.append(FilterStackItem(filter_key=str(key)))
        self._rebuild_structure_tree()
        self._render()

    def _remove_stack_item(self) -> None:
        branch = self._active_branch()
        effect_index = self._selected_effect_index()
        if branch is None or effect_index is None:
            return
        if not (0 <= effect_index < len(branch.filter_stack)):
            return
        branch.filter_stack.pop(effect_index)
        self._rebuild_structure_tree()
        self._render()

    def _move_stack_item(self, offset: int) -> None:
        branch = self._active_branch()
        idx = self._selected_effect_index()
        if branch is None or idx is None:
            return
        new_idx = idx + offset
        if not (0 <= new_idx < len(branch.filter_stack)):
            return
        branch.filter_stack[idx], branch.filter_stack[new_idx] = branch.filter_stack[new_idx], branch.filter_stack[idx]
        self._rebuild_structure_tree()
        self._render()

    def _on_tree_item_changed(self, item: QTreeWidgetItem, _column: int) -> None:
        node_type = item.data(0, NODE_TYPE_ROLE)
        layer = self._active_layer()
        if layer is None:
            return

        if node_type == "image":
            layer.visible = item.checkState(0) == Qt.CheckState.Checked
            item.setText(1, "✓" if layer.visible else "✕")
        elif node_type == "effect":
            effect = self._active_stack_item()
            if effect is None:
                return
            effect.enabled = item.checkState(0) == Qt.CheckState.Checked
            item.setText(1, "✓" if effect.enabled else "✕")

        self._render()

    def _on_tree_selection_changed(self) -> None:
        selected_item = self._selected_tree_item()
        if selected_item is None:
            self.options_target.setText("Select an image or effect in the tree")
            return

        node_type = selected_item.data(0, NODE_TYPE_ROLE)
        if node_type == "image":
            layer = self._active_layer()
            if layer is None:
                return
            self.options_target.setText(f"Image: {layer.name}")
            self.node_visible_checkbox.blockSignals(True)
            self.node_visible_checkbox.setChecked(layer.visible)
            self.node_visible_checkbox.blockSignals(False)
            self._set_blend_combo(BLEND_MODE_MAP.keys(), layer.blend_mode)
            self.node_opacity_slider.blockSignals(True)
            self.node_opacity_slider.setValue(int(layer.opacity * 100))
            self.node_opacity_slider.blockSignals(False)
        elif node_type == "effect":
            effect = self._active_stack_item()
            if effect is None:
                return
            self.options_target.setText("Effect")
            self.node_visible_checkbox.blockSignals(True)
            self.node_visible_checkbox.setChecked(effect.enabled)
            self.node_visible_checkbox.blockSignals(False)
            self._set_blend_combo(FILTER_BLEND_MODE_MAP.keys(), effect.blend_mode)
            self.node_opacity_slider.blockSignals(True)
            self.node_opacity_slider.setValue(int(effect.opacity * 100))
            self.node_opacity_slider.blockSignals(False)
        else:
            self.options_target.setText("Group")

    def _set_blend_combo(self, modes: object, selected_mode: str) -> None:
        self.node_blend_combo.blockSignals(True)
        self.node_blend_combo.clear()
        for mode in modes:
            self.node_blend_combo.addItem(str(mode))
        self.node_blend_combo.setCurrentText(selected_mode)
        self.node_blend_combo.blockSignals(False)

    def _on_selected_visibility_changed(self, checked: bool) -> None:
        selected_item = self._selected_tree_item()
        if selected_item is None:
            return
        node_type = selected_item.data(0, NODE_TYPE_ROLE)
        if node_type == "image":
            layer = self._active_layer()
            if layer is None:
                return
            layer.visible = checked
            selected_item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            selected_item.setText(1, "✓" if checked else "✕")
        elif node_type == "effect":
            effect = self._active_stack_item()
            if effect is None:
                return
            effect.enabled = checked
            selected_item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            selected_item.setText(1, "✓" if checked else "✕")
        self._render()

    def _on_selected_blend_changed(self, value: str) -> None:
        selected_item = self._selected_tree_item()
        if selected_item is None:
            return
        node_type = selected_item.data(0, NODE_TYPE_ROLE)
        if node_type == "image":
            layer = self._active_layer()
            if layer is None:
                return
            layer.blend_mode = value
        elif node_type == "effect":
            effect = self._active_stack_item()
            if effect is None:
                return
            effect.blend_mode = value
        selected_item.setText(2, value)
        self._render()

    def _on_selected_opacity_changed(self, value: int) -> None:
        selected_item = self._selected_tree_item()
        if selected_item is None:
            return
        node_type = selected_item.data(0, NODE_TYPE_ROLE)
        opacity = value / 100.0
        if node_type == "image":
            layer = self._active_layer()
            if layer is None:
                return
            layer.opacity = opacity
        elif node_type == "effect":
            effect = self._active_stack_item()
            if effect is None:
                return
            effect.opacity = opacity
        selected_item.setText(3, f"{value}%")
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
