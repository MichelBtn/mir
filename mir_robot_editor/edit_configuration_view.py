from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QToolBar,
    QTreeWidget, QTreeWidgetItem, QWidget
)
import dataclasses
from enum import Enum
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from pathlib import Path
from mir_utils.ui.widgets import DialogBase, IconFinder, ToolButton
from mir_utils.ui.code_editor import CodeEditorWidget
from mir_robot_editor.edit_configuration_view_model import EditConfigurationViewModel, EditConfigurationVMAction
from mir_robot_editor.view_base import ViewBase
from mir_devices.mir_feetech_motor_bus import mirMotorBusConfiguration, mirMotor

class EditConfigurationView(DialogBase, ViewBase[EditConfigurationViewModel, EditConfigurationVMAction]):
    def __init__(self, parent, view_model:EditConfigurationViewModel):
        super().__init__(parent, view_model = view_model, disable_esc=True)
        self.setWindowTitle("Edition configuration")
        self._view_model.config_changed.connect(self.on_config_changed)        
        self._view_model.closed.connect(lambda : self.close())

        main_layout = QVBoxLayout(self)
        
        editors_layout = QHBoxLayout()
        self._code_editor = CodeEditorWidget(parent)
        self._code_editor.setTheme("light")
        self._code_editor.validationChanged.connect(self.on_validation_changed)
        editors_layout.addWidget(self._code_editor)
        self._config_tree = RobotConfigurationTreeWidget(title="Configuration robot")
        editors_layout.addWidget(self._config_tree)
        main_layout.addLayout(editors_layout)
        
        toolbar = QToolBar()
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._action_apply =   self._make_action(EditConfigurationVMAction.APPLY, self.on_apply, "apply", toolbar=toolbar)
        self._action_save = self._make_action(EditConfigurationVMAction.SAVE_AND_CLOSE, self.on_save_and_close, "save", toolbar=toolbar)
        self._action_cancel = self._make_action(EditConfigurationVMAction.CANCEL,  self.on_cancel, "close", toolbar=toolbar)
        
        main_layout.addWidget(toolbar)

        self._code_editor.setPlainText(self._view_model.get_current_configuration_json())
        self._code_editor.format_json()

        self._config_tree.refresh(self._view_model.get_current_configuration()) 

    def on_validation_changed(self, is_valid):
        self._view_model.on_validation_changed(is_valid)

    def on_save_and_close(self):
        self._view_model.save_and_close(self._code_editor.toPlainText())

    def on_apply(self):
        self._view_model.apply(self._code_editor.toPlainText())

    def on_cancel(self):
        self._view_model.cancel()

    def on_config_changed(self, config):
        self._config_tree.refresh(config)

class RobotConfigurationTreeWidget(QWidget):

    def __init__(self, obj: object = None, parent=None, title: str | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        btn_expand_all = ToolButton("expand_all", lambda: self.on_expand_all_clicked(True), True, "Etendre tout", size=20)
        toolbar.addWidget(btn_expand_all)
        btn_collapse_all = ToolButton("collapse_all", lambda: self.on_expand_all_clicked(False), True, "Réduire tout", size=20)
        toolbar.addWidget(btn_collapse_all)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(2)
        self._tree.setHeaderHidden(True)
        self._tree.setColumnWidth(0, 220)
        self._tree.setAlternatingRowColors(True)
        self._tree.setAnimated(True)
        layout.addWidget(self._tree)
        self._title = title
        self.refresh(obj)

    def on_expand_all_clicked(self, expand: bool):
        self._tree.expandToDepth(3 if expand else 0)

    def populate_tree(self, parent_item: QTreeWidgetItem, obj, name: str = ""):
        """Remplit récursivement un QTreeWidgetItem depuis n'importe quel dataclass."""
        
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            item = QTreeWidgetItem(parent_item, [name, type(obj).__name__])
            if isinstance(obj, mirMotorBusConfiguration):
                item.setIcon(0, IconFinder.find_icon("motors"))
            for f in dataclasses.fields(obj):
                self.populate_tree(item, getattr(obj, f.name), f.name)

        elif isinstance(obj, dict):
            item = QTreeWidgetItem(parent_item, [name, f"{len(obj)}"])
            item.setIcon(0, IconFinder.find_icon(name))
            for k, v in obj.items():
                self.populate_tree(item, v, str(k))

        elif isinstance(obj, (list, tuple)):
            item = QTreeWidgetItem(parent_item, [name, f"{type(obj).__name__} ({len(obj)})"])
            for i, v in enumerate(obj):
                self.populate_tree(item, v, str(i))

        elif isinstance(obj, Enum):
            item = QTreeWidgetItem(parent_item, [name, obj.name])
            item.setForeground(1, Qt.darkMagenta) # type: ignore

        elif isinstance(obj, Path):
            item = QTreeWidgetItem(parent_item, [name, str(obj)])
        else:
            item = QTreeWidgetItem(parent_item, [name, repr(obj)])
            item.setIcon(0, IconFinder.find_icon(name))

        return item
        
    def refresh(self, obj: object) -> None:
        self._tree.clear()
        if obj is None:
            return
        root = QTreeWidgetItem(self._tree, [self._title or type(obj).__name__,  type(obj).__name__])
        root.setIcon(0, IconFinder.find_icon("robot"))
        root.setExpanded(True)
        for f in dataclasses.fields(obj): # type: ignore
            self.populate_tree(root, getattr(obj, f.name), f.name)
        self._tree.expandToDepth(0)