from mir_devices.cameras import PiCamera
from PySide6.QtCore import Signal, QTimer
from typing_extensions import override
from loguru import logger
from typing import Any
from mir_devices.mir_devices_factory import DefaultSensorsFactory, ObservableProperty
from mir_devices.mir_sensor import mirSensorConfiguration, SensorProperty, mirSensor
from mir_utils.ui.view_model_base import ViewModelBase
from mir_utils.ui.dialogs import IDialogProvider

class SensorConfigurationViewModel(ViewModelBase):
    close_required = Signal()
    observation_ready = Signal(object)

    def __init__(self, dialogProvider: IDialogProvider, sensor_key:str, config: mirSensorConfiguration):
        super().__init__(dialogProvider)
        self._configuration = config
        self._sensor_key = sensor_key
        self._sensor: mirSensor | None = None
        self._sensor_factory = DefaultSensorsFactory()
        self._reset_required = False
        self._observation_timer = QTimer()
        self._observation_timer.timeout.connect(self._on_timer_tick)

    @override
    def _enter_context(self):
        self.connect_sensor()
            
    @override
    def _exit_context(self, exc_type, exc_value, traceback):
        self._observation_timer.stop()
        self.disconnect_sensor()

    def get_sensor_key(self):
        return self._sensor_key

    def disconnect_sensor(self):
        if self._sensor is not None and self._sensor.mir_is_connected():
            logger.info("disconnect sensor")
            self._sensor.mir_disconnect()                
            self._sensor = None    

    def connect_sensor(self):
        if self._sensor is not None:
            if self._sensor.mir_is_connected():
                return 
        logger.info("create sensor")                
        self._sensor = self._sensor_factory.create_sensor(self._sensor_key, self._configuration)
        logger.info("connect sensor")                
        self._sensor.mir_connect()
        self._observable = None
        if isinstance(self._sensor,PiCamera):
            self._observable = self._sensor.get_observables()[self._sensor_key]
            self._sensor.subscribe(self._sensor_key)
            self._observation_timer.start(50) 

    def get_observable(self) -> ObservableProperty|None:
        return self._observable

    def get_configurable_properties(self) -> dict[str, SensorProperty]:
        if self._sensor is None:
            return {}
        self._configurable_properties = self._sensor.get_configurable_properties()
        return self._configurable_properties
    
    def set_property(self, key: str, value) -> bool:
        if self._sensor is None or not self._sensor.mir_is_connected():
            logger.error("Sensor not connected")
            return False
        return self._sensor.set_property(key, value)

    def set_properties_and_close(self, properties: dict[str, Any]):
        self._reset_required = False
        for key, value in properties.items():
            if value != self._configurable_properties[key].current_value:
                self.set_property(key, value)
                if self._configurable_properties[key].requires_reboot:
                    self._reset_required = True
        self.close_required.emit()            

    def cancel_and_close(self):
        self.close_required.emit()            

    def sensor_reset_required(self):
        return self._reset_required

    def _on_timer_tick(self):
        if self._sensor is not None and self._sensor.mir_is_connected():
            data = self._sensor.get_observation()[self._sensor_key]
            self.observation_ready.emit(data)
