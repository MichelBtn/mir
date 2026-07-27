
from typing_extensions import override
from PySide6.QtCore import Signal, QTimer
from lerobot.motors.feetech import OperatingMode
from dataclasses import dataclass
from mir_robot_editor.motor_configuration.registers_viewmodel import RegistersViewModel
from mir_robot_editor.motor_configuration.calibration_viewmodel import CalibrationViewModel
from mir_utils.ui.dialogs import IDialogProvider
from mir_devices.mir_feetech_motor_bus import mirFeetechMotorsBus, mirMotor
from mir_robot_editor.view_model_base import ViewModelBase
from mir_robot.mir_robot_config import mirRobotConfig

@dataclass
class MotorConfigurationViewModel_MotorData():
    motor : mirMotor
    pos : float | int
    vel : int
    def can_set_pos(self) -> bool:
        return self.motor.operating_mode == OperatingMode.POSITION

class MotorConfigurationViewModel(ViewModelBase):
    property_changed = Signal(str, object)

    def __init__(self, dialogProvider : IDialogProvider, config:mirRobotConfig):
        super().__init__(dialogProvider)
        self._motors = config.motor_bus.motors
        self._temp_bus = mirFeetechMotorsBus(config.motor_bus)
        self._motors_data: dict[str, MotorConfigurationViewModel_MotorData] = {}
        self._temp_bus.mir_connect()
        self._temp_bus.mir_configure_motors()
        self._motors_data = {
            key: MotorConfigurationViewModel_MotorData(value, 0, 0)
            for key, value in self._motors.items()
        }
        motors_pos = self._temp_bus.mir_read_positions()
        for key in self._motors_data:
            pos = motors_pos[key]
            if pos is float:
                self._motors_data[key].pos = round(pos, 2)
            else:
                self._motors_data[key].pos = int(pos)
        self._is_calibration_done = False

    @property
    def motors_data(self)-> dict[str, MotorConfigurationViewModel_MotorData]:
        return self._motors_data    

    @property
    def is_calibrated(self) -> bool:
        return self._temp_bus.mir_is_calibrated()
            
    @override
    def _enter_context(self):
        self._temp_bus.mir_is_calibrated_changed.subscribe(self._on_bus_is_calibrated_changed)
        self._timer = QTimer()
        self._timer.timeout.connect(self._on_timer)
        self._timer.start(250)
    
    @override
    def _exit_context(self, exc_type, exc_value, traceback):
        if self._temp_bus is not None:
            self._temp_bus.mir_is_calibrated_changed.unsubscribe(self._on_bus_is_calibrated_changed)        
            self._temp_bus.mir_disconnect()
            self._temp_bus = None

    def _on_bus_is_calibrated_changed(self, is_calibrated :bool):
        self.property_changed.emit("is_calibrated", is_calibrated)

    def get_port(self):
        self._check_initialized()
        return self._port
    
    def set_port(self, port:str):
        self._check_initialized()
        self._port = port

    def execute_registers_viewmodel(self, open_view,  motor_name:str):
        try :
            self._check_initialized()
            if self._temp_bus is None:
                raise RuntimeError("Bus is not initialized")
            vm =  RegistersViewModel(self._temp_bus, motor_name)
            with vm:
                open_view(vm)
        except BaseException as e:
            self._dialogProvider.exception(e)    

    def execute_calibration_view_model(self, open_view):
        try :
            self._check_initialized()
            if self._temp_bus is None:
                raise RuntimeError("Bus is not initialized")
            vm =  CalibrationViewModel(self._temp_bus, self._dialogProvider)
            with vm:
                open_view(vm)
            self._is_calibration_done = vm._is_calibration_done
        except BaseException as e:
            self._dialogProvider.exception(e)            

    def move_motor(self, name, pos, vel):
        self._check_initialized()
        
        if self._temp_bus is not None:
            if self._motors[name].operating_mode == OperatingMode.POSITION:
                self._temp_bus.mir_goal_position(name, pos, vel)
            else:
                self._temp_bus.mir_goal_velocity(name, vel)

    def stop_motor(self, name):
        self._check_initialized()
        if self._temp_bus is not None:
            self._temp_bus.mir_stop(name)

    def emergency_stop(self, motor:str|None = None):
        if self._temp_bus is not None:
            self._temp_bus.mir_emergency_stop()

    def _on_timer(self):
        if self._temp_bus is None:
            return
        motors_pos = self._temp_bus.mir_read_positions()
        for key, value in self._motors.items():
            self._motors_data[key].pos = round(motors_pos[key], 2)
        self.property_changed.emit("motors_data", self._motors_data)

