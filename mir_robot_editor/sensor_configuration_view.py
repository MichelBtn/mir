from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QToolButton,
    QLabel,
    QGridLayout,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QLineEdit,
    QComboBox,
    QWidget    
)
from PySide6.QtCore import Qt, QSize, QTimer
from loguru import logger
from mir_utils.ui.view_base import ViewBase
from mir_robot_editor.sensor_configuration_view_model import SensorConfigurationViewModel
from mir_utils.ui.widgets import DialogBase
from mir_devices.mir_sensor import SensorProperty
from mir_robot_editor.observations_widget import VideoWidget, PlotWidget
from mir_devices.mir_device import ObservablePropertyBitmap

class SensorConfigurationView(DialogBase, ViewBase):
    def __init__(self, parent, view_model: SensorConfigurationViewModel):
        super().__init__(parent, view_model=view_model)
        self.setWindowTitle(f"Configuration - {view_model.get_sensor_key()}")

        main_layout = QHBoxLayout(self)
        left_layout = QVBoxLayout()

        # Récupère les propriétés configurables
        properties = view_model.get_configurable_properties()
        view_model.close_required.connect(self.close)
        if not properties:
            label = QLabel("Aucune propriété configurable disponible")
            left_layout.addWidget(label)
        else:
            grid = QGridLayout()
            left_layout.addLayout(grid)

            # Stocke les widgets pour récupérer les valeurs plus tard
            self._property_widgets = {}

            for r, (key, prop) in enumerate(properties.items()):
                label = QLabel(prop.label)
                label.setToolTip(prop.tooltip)
                grid.addWidget(label, r, 0)

                widget = self._create_widget_for_property(key, prop)
                widget.setEnabled(not prop.read_only)
                widget.setToolTip(str(prop.current_value))
                if widget is not None:
                    self._property_widgets[key] = (widget, prop)
                    grid.addWidget(widget, r, 1)
                else:
                    label_value = QLabel(str(prop.current_value))
                    grid.addWidget(label_value, r, 1)

                if prop.immediate:
                    btn_apply_prop = QToolButton()
                    btn_apply_prop.setIcon(self._icon("enter"))
                    btn_apply_prop.setIconSize(QSize(20,20))
                    btn_apply_prop.clicked.connect(lambda _, k = key, w = widget: self._view_model.set_property(k, self._get_widget_value(w)))
                    grid.addWidget(btn_apply_prop, r, 2)

            grid.setColumnStretch(1, 1)
            left_layout.addStretch()

            right_layout = QVBoxLayout()
            self._observation_widget = self._create_observation_widget()
            if self._observation_widget is not None:
                right_layout.addWidget(self._observation_widget)

            main_layout.addLayout(left_layout, 1)
            main_layout.addLayout(right_layout, 1)

        # Bottom buttons
        bottom = QHBoxLayout()

        btn_apply = QToolButton()
        btn_apply.setText("Appliquer")
        btn_apply.clicked.connect(self.btn_apply_clicked)
        bottom.addWidget(btn_apply)

        btn_cancel = QToolButton()
        btn_cancel.setText("Annuler")
        btn_cancel.clicked.connect(self.btn_cancel_clicked)
        bottom.addWidget(btn_cancel)

        bottom.addStretch()
        left_layout.addLayout(bottom)
        self.adjustSize()

        self._view_model.observation_ready.connect(self._on_observation_ready)

    def _on_observation_ready(self, data):
        if self._observation_widget is not None:
            self._observation_widget.update_plot(data)

    def _create_observation_widget(self) -> PlotWidget|None:
        observable = self._view_model.get_observable()
        if isinstance(observable, ObservablePropertyBitmap):
            return VideoWidget("", width=320, height=240)
        return None                

    def _create_widget_for_property(self, key, prop: SensorProperty):
        """Crée le widget approprié selon le type de propriété"""
        MIN_WIDTH = 100
        try:
            if prop.property_type == "int":
                spinbox = QSpinBox()
                spinbox.setMinimumWidth(MIN_WIDTH)
                spinbox.setValue(int(prop.current_value))
                spinbox.setAlignment(Qt.AlignmentFlag.AlignRight)
                if prop.min_value is not None:
                    spinbox.setMinimum(int(prop.min_value))
                if prop.max_value is not None:
                    spinbox.setMaximum(int(prop.max_value))
                if prop.step is not None:
                    spinbox.setSingleStep(int(prop.step))
                return spinbox

            elif prop.property_type == "float":
                spinbox = QDoubleSpinBox()
                spinbox.setMinimumWidth(MIN_WIDTH)
                spinbox.setAlignment(Qt.AlignmentFlag.AlignRight)
                spinbox.setValue(float(prop.current_value))
                if prop.min_value is not None:
                    spinbox.setMinimum(float(prop.min_value))
                if prop.max_value is not None:
                    spinbox.setMaximum(float(prop.max_value))
                if prop.step is not None:
                    spinbox.setSingleStep(float(prop.step))
                return spinbox

            elif prop.property_type == "bool":
                checkbox = QCheckBox()
                checkbox.setChecked(bool(prop.current_value))
                return checkbox

            elif prop.property_type == "str":
                lineedit = QLineEdit()
                lineedit.setMinimumWidth(MIN_WIDTH)
                lineedit.setText(str(prop.current_value))
                return lineedit

            elif prop.property_type == "list":
                combobox = QComboBox()
                combobox.setMinimumWidth(MIN_WIDTH)
                if prop.options is not None:
                    combobox.addItems(prop.options)
                combobox.setCurrentText(str(prop.current_value))
                return combobox

            else:
                logger.warning(f"Unknown property type: {prop.property_type}")
                return None
        except Exception as e:
            logger.error(f"Failed to create widget for property {key}: {e}")
            return None

    def _get_widget_value(self, widget):
        """Récupère la valeur du widget selon son type"""
        if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            return widget.value()
        elif isinstance(widget, QCheckBox):
            return widget.isChecked()
        elif isinstance(widget, QLineEdit):
            if not widget.isReadOnly():
                return widget.text()
        elif isinstance(widget, QComboBox):
            return widget.currentText()
        return None

    def btn_apply_clicked(self):
        properties = {key: self._get_widget_value(widget) for key, (widget, prop) in self._property_widgets.items()}
        self._view_model.set_properties_and_close(properties)

    def btn_cancel_clicked(self):
        self._view_model.cancel_and_close()
