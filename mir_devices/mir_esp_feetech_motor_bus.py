from lerobot.motors.motors_bus import MotorNormMode
from mir_devices.mir_device import (mirDevice, 
                                    ActionValue, 
                                    ObservableProperty, 
                                    ObservationValue, 
                                    ObservablePropertyFloat, 
                                    ImirFeetechMotorBus, 
                                    DeviceAction,
                                    mirMotorCalibration)
from mir_devices.mir_feetech_motor_bus import (
    mirMotorBusConfiguration,
    mirMotor,
    OperatingMode,
    Event_,
    sts3215_registers
)
from loguru import logger
import struct
import socket
from enum import Enum
from typing_extensions import override
from typing import cast, TypeAlias

RegValue : TypeAlias = int|float

POSITION_SUFFIX = "position"
VELOCITY_SUFFIX = "velocity"
CURRENT_SUFFIX = "current"
TEMPERATURE_SUFFIX = "temperature"
LOAD_SUFFIX = "load"
ACTION_POSITION_SUFFIX = "position"
ACTION_VELOCITY_SUFFIX = "velocity"

class MotorBusError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)

class MotorBusCommands(Enum):
    CMD_STATUS = 0x01,
    CMD_WRITE = 0x02,
    CMD_READ = 0x03,

class MotorBusErrors(Enum):
    OK =            0x00,
    NOT_CONNECTED = 0x01,
    UNKNOWN_CMD =   0x02,
    BAD_LEN =       0x03,
    BAD_FRAME =     0x04,
    STS_NACK =      0x05,
    BAD_ARG =       0x06  

class MotorBusInitStatus(Enum):
    OK = 0,          
    UART_ERROR = 1,  
    NO_RESPONSE = 2, 

class Esp32MotorBusProxy:
    def __init__(self, ip:str, port:int=5002):
        self.ip = ip
        self.port = port
        self.sock:socket.socket | None = None

    def connect(self):
        self.sock = socket.create_connection((self.ip, self.port))
        response = self.send(b'\x01')
        if response[0] != MotorBusErrors.OK.value:
            raise MotorBusError(f"CMD_STATUS Error code : {response[0]}")
        if response[1] != MotorBusInitStatus.OK.value:
            raise MotorBusError(f"CMD_STATUS Init status : {response[1]}")

    def disconnect(self):
        if self.sock is not None:
            self.sock.close()
        self.sock = None

    def recv_exact(self, size):
        if self.sock is None:
            raise ConnectionError("Connexion TCP fermée")
        data = b""
        while len(data) < size:
            chunk = self.sock.recv(size - len(data))
            if not chunk:
                raise ConnectionError("Connexion TCP fermée")
            data += chunk
        return data

    def send(self, payload:bytes):
        if self.sock is None:
            raise ConnectionError("Connexion TCP fermée")
        # Protocole : longueur uint16 big-endian + payload
        frame = struct.pack(">H", len(payload)) + payload
        self.sock.sendall(frame)
        # Réception de la longueur de réponse
        response_len = struct.unpack(">H", self.recv_exact(2))[0]
        # Réception de la réponse
        response = self.recv_exact(response_len)
        return response
    

    def read_reg(self, id: int, addr: int, count: int) -> int:
        try:
            if not 0 <= id <= 0xFD:
                raise ValueError(f"ID servo invalide : {id:#x}")
            if not 1 <= count <= 255:
                raise ValueError(f"count invalide : {count}")
            payload = struct.pack("<BBBB", MotorBusCommands.CMD_READ.value, id, addr, count)
            response = self.send(payload)
            if len(response) < 1:
                raise MotorBusError("réponse vide")
            status = response[0]
            if status != MotorBusErrors.OK.value:
                raise MotorBusError(f"CMD_READ id={id} addr={addr:#x} : {status} (0x{status:02X})")
            if len(response) != 1 + count:
                raise MotorBusError(
                    f"trame non conforme : {len(response)} octet(s) reçu(s), {1 + count} attendu(s)"
                )
            return int.from_bytes(response[1:], "little")
        except Exception as e:
            logger.exception(
                f"Failed to read @{addr=} ({count=}) on {id=}): {e}"
            )            
            raise

class mirEspFeetechMotorBus(ImirFeetechMotorBus):
   
    _bus_connected : dict[str, bool] = {}
    
    def __init__(self, config: mirMotorBusConfiguration):
        mirDevice.__init__(self)
        self._is_connected = False
        self._config = config
        self._mir_motors = config.motors
        self._id_to_name_dict = {motor_cfg.id: motor_name for motor_name, motor_cfg in self._mir_motors.items()}
        self._port = config.motor_port
        self._mir_calibration:dict[str, mirMotorCalibration] = config.calibration
        self._mir_is_calibrated_changed = Event_[[bool]]()
        self._mir_is_calibrated = False
        self._mir_is_ready = False
        for motor_name, motor_cfg in self._mir_motors.items():
            if motor_cfg.operating_mode == OperatingMode.POSITION:
                self._actions[f"{motor_name}.{ACTION_POSITION_SUFFIX}"] = DeviceAction(motor_name, ACTION_POSITION_SUFFIX, 0.0,'float', '°', None)
            elif motor_cfg.operating_mode == OperatingMode.VELOCITY:                        
                self._actions[f"{motor_name}.{ACTION_VELOCITY_SUFFIX}"] = DeviceAction(motor_name, ACTION_VELOCITY_SUFFIX, 0,'int', '°/s', None)
        self._proxy = Esp32MotorBusProxy(config.motor_port)
        self._encoding_table = {
            "Present_Load": 10,
            "Homing_Offset": 11,
            "Goal_Position": 15,
            "Goal_Velocity": 15,
            "Goal_Speed": 15,
            "Present_Position": 15,
            "Present_Velocity": 15,
            "Present_Speed": 15,
        }
        self._normalized_data = ["Goal_Position", "Present_Position"]

    def decode_sign_magnitude(self, encoded_value: int, sign_bit_index: int):
        direction_bit = (encoded_value >> sign_bit_index) & 1
        magnitude_mask = (1 << sign_bit_index) - 1
        magnitude = encoded_value & magnitude_mask
        return -magnitude if direction_bit else magnitude
    
    def _decode_sign(self, data_name: str, ids_values: dict[int, int]) -> dict[int, int]:
        for id_ in ids_values:
            if data_name in self._encoding_table:
                sign_bit = self._encoding_table[data_name]
                ids_values[id_] = self.decode_sign_magnitude(ids_values[id_], sign_bit)
        return ids_values
    
    def _normalize(self, ids_values: dict[int, int]) -> dict[int, float]:
        if not self.calibration:
            raise RuntimeError(f"{self} has no calibration registered.")

        normalized_values = {}
        for id_, val in ids_values.items():
            motor = self._id_to_name_dict[id_]
            min_ = self.calibration[motor].range_min
            max_ = self.calibration[motor].range_max
            drive_mode = self.calibration[motor].drive_mode
            if max_ == min_:
                raise ValueError(f"Invalid calibration for motor '{motor}': min and max are equal.")

            bounded_val = min(max_, max(min_, val))
            if self._mir_motors[motor].norm_mode is MotorNormMode.RANGE_M100_100:
                norm = (((bounded_val - min_) / (max_ - min_)) * 200) - 100
                normalized_values[id_] = -norm if drive_mode else norm
            elif self._mir_motors[motor].norm_mode is MotorNormMode.RANGE_0_100:
                norm = ((bounded_val - min_) / (max_ - min_)) * 100
                normalized_values[id_] = 100 - norm if drive_mode else norm
            elif self._mir_motors[motor].norm_mode is MotorNormMode.DEGREES:
                mid = (min_ + max_) / 2
                max_res = 4095
                normalized_values[id_] = (val - mid) * 360 / max_res
            else:
                raise NotImplementedError

        return normalized_values

    def write(
        self, data_name: str, motor: str, value: RegValue, *, normalize: bool = True, num_retry: int = 0
    ) -> None:

        id_ = self.motors[motor].id
        model = self.motors[motor].model
        addr, length = get_address(self.model_ctrl_table, model, data_name)

        # TODO: remove me (debug)
        norm_value = value

        if normalize and data_name in self.normalized_data:
            value = self._unnormalize({id_: value})[id_]

        value = self._encode_sign(data_name, {id_: value})[id_]

        # TODO: remove me (debug)
        logger.debug(f"[MOTOR_BUS] {data_name=}, {id_=}, {value=}, {norm_value=}")

        err_msg = f"Failed to write '{data_name}' on {id_=} with '{value}' after {num_retry + 1} tries."
        self._write(addr, length, id_, value, num_retry=num_retry, raise_on_error=True, err_msg=err_msg)

    def _write(
        self,
        addr: int,
        length: int,
        motor_id: int,
        value: int,
        *,
        num_retry: int = 0,
        raise_on_error: bool = True,
        err_msg: str = "",
    ) -> tuple[int, int]:
        data = self._serialize_data(value, length)
        for n_try in range(1 + num_retry):
            comm, error = self.packet_handler.writeTxRx(self.port_handler, motor_id, addr, length, data)
            if self._is_comm_success(comm):
                break
            logger.debug(
                f"Failed to sync write @{addr=} ({length=}) on id={motor_id} with {value=} ({n_try=}): "
                + self.packet_handler.getTxRxResult(comm)
            )

        if not self._is_comm_success(comm) and raise_on_error:
            raise ConnectionError(f"{err_msg} {self.packet_handler.getTxRxResult(comm)}")
        elif self._is_error(error) and raise_on_error:
            raise RuntimeError(f"{err_msg} {self.packet_handler.getRxPacketError(error)}")

        return comm, error

    def _read(
        self,
        data_name: str,
        motor: str,
        *,
        normalize: bool = True,
    ) -> RegValue:
        addr = sts3215_registers[data_name].address
        length = sts3215_registers[data_name].size
        return self._read_by_id(data_name, addr, length, self._mir_motors[motor].id, normalize=normalize)

    def _read_by_id(
        self,
        data_name: str,
        addr: int,
        length: int,
        id_: int,
        normalize: bool = True,
    ) -> RegValue:

        if length not in [1,2]:   
            raise ValueError(length)

        value = self._proxy.read_reg(id_, addr, length)
        id_value = self._decode_sign(data_name, {id_: value})

        if normalize and data_name in self._normalized_data:
            id_value = self._normalize(id_value)

        return id_value[id_]

    def _read_calibration(self) -> dict[str, mirMotorCalibration]:
        offsets, mins, maxes = {}, {}, {}
        for motor in self._mir_motors:
            mins[motor] = self._read("Min_Position_Limit", motor, normalize=False)
            maxes[motor] = self._read("Max_Position_Limit", motor, normalize=False)
            offsets[motor] = (
                self._read("Homing_Offset", motor, normalize=False)
            )

        calibration = {}
        for motor, m in self._mir_motors.items():
            calibration[motor] = mirMotorCalibration(
                id=m.id,
                drive_mode=0,
                homing_offset=offsets[motor],
                range_min=mins[motor],
                range_max=maxes[motor],
            )

        return calibration

    @property
    def mir_is_calibrated_changed(self) -> Event_[bool]:
        """Implémentation de la propriété requise par l'interface ImirFeetechMotorBus"""
        return self._mir_is_calibrated_changed
    
    def mir_is_calibrated(self):
        return self._mir_is_calibrated

    def _set_is_calibrated(self, calibrated:bool):
        self._mir_is_calibrated = calibrated 
        self.mir_is_calibrated_changed.fire(self._mir_is_calibrated)         

    def mir_uncalibrated_reason(self)->str:
        return self._mir_uncalibrated_reason if hasattr(self, "_mir_uncalibrated_reason") else "" # type: ignore
    
    def mir_get_motors(self)->dict[str, mirMotor]:
        return self._mir_motors


    @override
    def mir_read_calibration_from_motors(self) -> dict[str, mirMotorCalibration] | None:
        calibration = {key: mirMotorCalibration(id=cal.id, drive_mode=cal.drive_mode, homing_offset=cal.homing_offset, range_min=cal.range_min, range_max=cal.range_max) 
                for key, cal in self._read_calibration().items()}
        for c in calibration.values():
            if c.range_max <= c.range_min:
                return None
        return calibration                

    
    def is_calibrated(self) -> bool:
        """
        surcharge is_calibrated de FeetechMotorBus
        car sa fonction ne testait pas les IDs
        """
        motors_calibration = self._read_calibration()
        if set(motors_calibration) != set(self.calibration):
            return False

        same_ranges = all(
            self.calibration[motor].range_min == cal.range_min
            and self.calibration[motor].range_max == cal.range_max
            for motor, cal in motors_calibration.items()
        )
        same_ids = all(
            self.calibration[motor].id == cal.id
            for motor, cal in motors_calibration.items()
        )

        same_offsets = all(
            self.calibration[motor].homing_offset == cal.homing_offset
            for motor, cal in motors_calibration.items()
        )
        return same_ranges and same_offsets and same_ids
    
    def mir_connect(self):
        if mirEspFeetechMotorBus._bus_connected.get(self._config.motor_port, False):
            raise ConnectionError("Le bus est déjà connecté")
        try :
            self._proxy.connect()
            self._mir_is_ready = True
            self._is_connected = True
            mirEspFeetechMotorBus._bus_connected[self._config.motor_port] = True
            positions = self.mir_read_positions()
            velocities = self.mir_read_velocities()
            for motor_name, motor_cfg in self._mir_motors.items():
                if motor_cfg.operating_mode == OperatingMode.POSITION:
                    self._actions[f"{motor_name}.{ACTION_POSITION_SUFFIX}"].set_value(positions[motor_name])
                    range = self.mir_get_motor_position_range(motor_name)
                    self._actions[f"{motor_name}.{ACTION_POSITION_SUFFIX}"].set_range(range)
                elif motor_cfg.operating_mode == OperatingMode.VELOCITY:                        
                    self._actions[f"{motor_name}.{ACTION_VELOCITY_SUFFIX}"].set_value(velocities[motor_name])
                    range = self.mir_get_motor_velocity_range(motor_name)
                    self._actions[f"{motor_name}.{ACTION_VELOCITY_SUFFIX}"].set_range(range)
        except BaseException as e:
            self._mir_is_ready = False
            raise e
        self._set_is_calibrated(self.is_calibrated())
               
    def mir_disconnect(self):
        if self._is_connected:
            self._proxy.disconnect()
            self._is_connected = False
        mirEspFeetechMotorBus._bus_connected[self._config.motor_port] = False

    def mir_is_connected(self) -> bool:
        return self._is_connected
    
    def _check_mir_is_ready(self):
        if not self._mir_is_ready:
            raise RuntimeError("Opération impossible, car le bus n'est pas prêt (non connecté ou la liste des moteurs n'est pas conforme)")

    def mir_read_register(self, data_name: str, motor: str, num_retry: int = 0) ->int:
        return int(self._read(data_name, motor, normalize=False))
    
    def mir_read_register_by_id(self, data_name: str, motor_id: int, num_retry: int = 0) ->int:
        reg = sts3215_registers[data_name]
        value = int(self._read_by_id(data_name, reg.address, reg.size,  motor_id))
        return value
    
    def mir_write_register_by_id(self, data_name: str, motor_id: int, value: int, num_retry: int = 0) ->None:
        reg = sts3215_registers[data_name]
        self._write(reg.address, reg.size,  motor_id, value, num_retry=num_retry)

    def mir_set_operating_mode(self, motor:str, operating_mode:OperatingMode):
        self._check_mir_is_ready()
        self.write("Operating_Mode", motor, operating_mode.value)
        self._mir_motors[motor].operating_mode = operating_mode
        

    def mir_disable_torques(self, motors: list[str] | None=None)->None:
        if motors is None:
            self.sync_write("Torque_Enable", 0)
        else:
            self.sync_write("Torque_Enable", {motor:0 for motor in motors})                        
        

    def mir_get_position_unit(self, motor: str) -> str:
        if self.mir_is_calibrated and self._mir_motors[motor].operating_mode == OperatingMode.POSITION:
            return "degrés"
        return "pas"
    
    def mir_get_velocity_unit(self) -> str:
        return 'RPM'

    def mir_emergency_stop(self) -> None:
        self.mir_disable_torques()
        self.mir_goal_velocities(0)
        positions = self.mir_read_positions()
        self.mir_goal_positions(positions, None)
        self.mir_disable_torques()

    def mir_stop(self, name:str|list[str]|None):
        if name is None:
            self.mir_goal_velocities(0)
            positions = self.mir_read_positions()
            self.mir_goal_positions(positions, None)
        elif isinstance(name, str):
            self.mir_goal_velocities({name:0})
            positions = self.mir_read_positions([name])
            self.mir_goal_positions(positions, None)
        else:         
            self.mir_goal_velocities({name:0 for name in name})
            positions = self.mir_read_positions(name)
            self.mir_goal_positions(positions, None)

    def mir_goal_position(self, name: str, pos:int|float, vel:int|float):
        self._check_mir_is_ready()
        #self.mir_goal_velocity(name, vel)
        velocities : dict[str, int|float] = {name: vel}
        self.mir_goal_velocities(velocities)
        time.sleep(0.001)
        if self._mir_is_calibrated:
            self.write("Goal_Position", name, pos, normalize=True)
        else:
            self.write("Goal_Position", name, int(pos), normalize=False)
    
    def mir_goal_velocities(self, velocities:  int | dict[str, int|float]) -> None:
        """
        Déplace un ou plusieurs moteurs à des vitesses données.
        
        Args:
        dictionnaire ou valeur, les valeurs sont en RPM
        """
        self._check_mir_is_ready()
        #Les vitesses sont en RPM. Avec Phase=0 (forcé à dans configure), l'unité de vitesse est de 0.732RPM
        if isinstance(velocities, dict):
            velocities = {key: int(val / RPM_PER_UNIT + 0.5) for key, val in velocities.items()}
        else:
            velocities = int(velocities / RPM_PER_UNIT + 0.5)
        """Déplace un ou plusieurs moteurs à des vitesses données."""
        self.sync_write("Goal_Velocity", velocities, normalize=False)

    def mir_goal_positions(self, positions:dict[str, int|float] | int | float, velocities: dict[str, int|float]|None):
        self._check_mir_is_ready()
        if velocities is not None:
            self.mir_goal_velocities(velocities)
            time.sleep(0.001)            
        if self._mir_is_calibrated:
            self.sync_write("Goal_Position", positions, normalize=True)
        else:
            self.sync_write("Goal_Position", positions, normalize=True)
    
    def mir_goal_velocity(self, name: str, velocity: int|float) -> None:
        self._check_mir_is_ready()
        velocity = int(velocity / RPM_PER_UNIT + 0.5)
        self.write("Goal_Velocity", name, velocity)

    @staticmethod
    def mir_normalize_motor_pos_for_velocity_mode(raw_position:int, calibration: mirMotorCalibration) -> float:
        raw_position -= calibration.homing_offset
        if raw_position < 0:
            raw_position = 4095 + raw_position
        elif raw_position > 4095:
            raw_position = raw_position - 4095
        mid = (calibration.range_min + calibration.range_max) / 2
        return (raw_position - mid) * 360 / 4095

    def mir_read_positions(self, motors: list[str]|None = None) -> dict[str, int|float]:
        self._check_mir_is_ready()
        if not self._mir_is_calibrated or self._mir_calibration is None:
            return self.sync_read("Present_Position", motors, normalize=False)
        if motors is None:
            motors_velocity = [motor for motor in self._mir_motors if self._mir_motors[motor].operating_mode == OperatingMode.VELOCITY]
            motors_positions = [motor for motor in self._mir_motors if self._mir_motors[motor].operating_mode == OperatingMode.POSITION]
        else:
            motors_velocity = [motor for motor in motors if self._mir_motors[motor].operating_mode == OperatingMode.VELOCITY]
            motors_positions = [motor for motor in motors if self._mir_motors[motor].operating_mode == OperatingMode.POSITION]
        if motors_positions is None or len(motors_positions) == 0:
            positions = {}
        else:
            positions = self.sync_read("Present_Position", motors_positions, normalize=True)
        if motors_velocity is not None and len(motors_velocity) > 0:            
            positions_velocity = self.sync_read("Present_Position", motors_velocity, normalize=False)
            for motor, pos in positions_velocity.items():
                positions[motor] = mirFeetechMotorsBus.mir_normalize_motor_pos_for_velocity_mode(
                                                        int(pos), 
                                                        self._mir_calibration[motor]
                                                    )            
        return positions

    def mir_read_raw_positions(self, motors: list[str]|None = None) -> dict[str, int|float]:
        self._check_mir_is_ready()
        return self.sync_read("Present_Position", motors, normalize=False)

    def mir_read_velocities(self, motors: list[str]|None = None) -> dict[str, int|float]:
        self._check_mir_is_ready()
        result = self.sync_read("Present_Velocity", motors)
        return {key: int(val * RPM_PER_UNIT + 0.5) for key, val in result.items()}

    def mir_read_currents(self, motors: list[str]|None = None) -> dict[str, int|float]:            
        self._check_mir_is_ready()
        raw_currents = self.sync_read("Present_Current", motors)
        return {key: int(val * 6.5 + 0.5) for key, val in raw_currents.items()}
    
    def mir_read_loads(self, motors: list[str]|None = None) -> dict[str, int|float]:
        self._check_mir_is_ready()
        raw_loads = self.sync_read("Present_Load", motors)
        return {key: int(val / 10.0) for key, val in raw_loads.items()}
    
    def mir_read_temperatures(self, motors: list[str]|None = None) -> dict[str, int|float]:            
        self._check_mir_is_ready()
        return self.sync_read("Present_Temperature", motors)

    def mir_is_moving(self, motors:list[str]|None=None) -> bool:
        velocities = self.sync_read("Present_Velocity", motors)
        return any(v != 0 for v in velocities.values())

    def mir_reset_calibration(self, motors = None):
        self._check_mir_is_ready()
        super().reset_calibration(motors) 
        self._set_is_calibrated(False)    

    def mir_calibrate(self, homing_offsets: dict, range_mins: dict, range_maxes:dict) -> None: 
        self._check_mir_is_ready()
        self._mir_calibration = {}
        for motor, m in self.motors.items():
            self._mir_calibration[motor] = mirMotorCalibration(
                id=m.id,
                drive_mode=0,
                homing_offset=homing_offsets[motor],
                range_min=range_mins[motor],
                range_max=range_maxes[motor],
            )
        self.calibration = self._mir_calibration
        self.write_calibration(cast(dict[str, MotorCalibration], self.calibration))
        self._set_is_calibrated(self.is_calibrated)
        self._config.calibration = self._mir_calibration
        if not self._mir_is_calibrated:
            raise Exception("La calibration des moteurs ne correspond pas à la calibration réalisée")           
    
    def mir_calibrate_from_motors(self):
        self._check_mir_is_ready()
        cal_from_motors = self.mir_read_calibration_from_motors()
        if cal_from_motors is None:
            raise Exception("La calibration des moteurs n'est pas valide")
        self._mir_calibration = cal_from_motors
        self.calibration = self._mir_calibration
        self._set_is_calibrated(self.is_calibrated)
        self._config.calibration = self._mir_calibration
        if not self._mir_is_calibrated:
            raise Exception("La calibration des moteurs ne correspond pas à la calibration appliquée")           

    def mir_store_calibration(self):
        self._check_mir_is_ready()
        if not self.is_calibrated:
            self._stored_calibration = None
            return
        self._stored_calibration = self.calibration.copy()

    def mir_restore_calibration(self):
        self._check_mir_is_ready()
        if self._stored_calibration is None:
            return
        self.calibration = self._stored_calibration
        self.write_calibration(cast(dict[str, MotorCalibration], self.calibration))
        self._set_is_calibrated(self.is_calibrated)

    #TODO ajouter MotorNormMode
    def mir_configure_motors(self):
        self._check_mir_is_ready()
        super().configure_motors(return_delay_time=0)
        for motor_name, motor in self._mir_motors.items():
            self.write("Torque_Enable", motor_name, 0)
            self.write("Operating_Mode", motor_name, motor.operating_mode.value)
            self.write("P_Coefficient", motor_name, motor.P)
            self.write("I_Coefficient", motor_name, motor.I)
            self.write("D_Coefficient", motor_name, motor.D)
            self.write("Moving_Velocity_Threshold", motor_name, 0)
            self.write("Goal_Velocity", motor_name, 0)
            self.write("Torque_Limit", motor_name, motor.torque_limit)
            phase = self.read("Phase", motor_name)
            if phase != 0:
                logger.warning(f"Remise à 0 du registre Phase du moteur {motor_name} qui était sur {phase}")
                self.write("Lock", motor_name, 0)
                self.write("Phase", motor_name, 0)
                self.write("Lock", motor_name, 1)
    
    def mir_get_motor_position_range(self, motor:str)->tuple[float, float]:
        if not self._mir_is_calibrated or self._mir_calibration is None:
            return (0, 4095)
        if self._mir_motors[motor].operating_mode == OperatingMode.VELOCITY:
            return (-180, 180)
        raw_values = {
            self._mir_motors[motor].id: self._mir_calibration[motor].range_min
        }
        res = self._normalize(raw_values)
        min_ = res[self._mir_motors[motor].id]
        raw_values = {
            self._mir_motors[motor].id: self._mir_calibration[motor].range_max
        }
        res = self._normalize(raw_values)
        max_ = res[self._mir_motors[motor].id]
                
        return (min_, max_)
    
    def mir_get_motor_velocity_range(self, motor:str)->tuple[float, float]:
        max_ = self.mir_read_register("Maximum_Velocity_Limit", motor)
        return (-max_, max_)
    
    def get_observation(self) -> dict[str, ObservationValue]:
        observation : dict[str, ObservationValue]= {}
        if len(self.subscribed_observations) > 0:
            positions_features = [feature.split(".")[0] for feature in self.subscribed_observations if feature.endswith(f".{POSITION_SUFFIX}")]
            if len(positions_features) > 0:
                positions = {f"{key}.{POSITION_SUFFIX}":value for key, value in self.mir_read_positions(positions_features).items()}
                observation.update(positions)
            velocities_features = [feature.split(".")[0] for feature in self.subscribed_observations if feature.endswith(f".{VELOCITY_SUFFIX}")]                
            if len(velocities_features) > 0:
                velocities = {f"{key}.{VELOCITY_SUFFIX}":value for key, value in self.mir_read_velocities(velocities_features).items()}
                observation.update(velocities)
            currents_features = [feature.split(".")[0] for feature in self.subscribed_observations if feature.endswith(f".{CURRENT_SUFFIX}")]
            if len(currents_features) > 0:
                currents = {f"{key}.{CURRENT_SUFFIX}":value for key, value in self.mir_read_currents(currents_features).items()}
                observation.update(currents)
            temperatures_features = [feature.split(".")[0] for feature in self.subscribed_observations if feature.endswith(TEMPERATURE_SUFFIX)]
            if len(temperatures_features) > 0:
                temperatures = {f"{key}.{TEMPERATURE_SUFFIX}":value for key, value in self.mir_read_temperatures(temperatures_features).items()}
                observation.update(temperatures)
            loads_features = [feature.split(".")[0] for feature in self.subscribed_observations if feature.endswith(LOAD_SUFFIX)]
            if len(loads_features) > 0:
                loads = {f"{key}.{LOAD_SUFFIX}":value for key, value in self.mir_read_loads(loads_features).items()}
                observation.update(loads)
        return observation
    
    def get_observables(self) -> dict[str, ObservableProperty]:
        try:
            should_disconnect = False
            if not self.mir_is_connected():
                self.mir_connect()
                should_disconnect = True
            observables : dict[str, ObservableProperty] = {}
            for key, motor in self._mir_motors.items():
                min_pos, max_pos = self.mir_get_motor_position_range(key)
                observables[f"{key}.{POSITION_SUFFIX}"] = ObservablePropertyFloat(min_pos, max_pos, "deg")
                min_vel, max_vel = self.mir_get_motor_velocity_range(key)
                observables[f"{key}.{VELOCITY_SUFFIX}"] = ObservablePropertyFloat(min_vel, max_vel, "rpm")
                observables[f"{key}.{CURRENT_SUFFIX}"] = ObservablePropertyFloat(0, 2700, "mA")
                observables[f"{key}.{TEMPERATURE_SUFFIX}"] = ObservablePropertyFloat(0, 100, "°C")
                observables[f"{key}.{LOAD_SUFFIX}"] = ObservablePropertyFloat(-100, 100, "%")
            return observables
        finally:
            if should_disconnect and self.mir_is_connected():
                self.mir_disconnect()
    
    def send_action(self, actions:dict[str, ActionValue]) -> dict[str, ActionValue]:
        goal_positions = {key.split(".")[0]: val for key, val in actions.items() if key.endswith(f".{POSITION_SUFFIX}")}
        goal_velocities = {key.split(".")[0]: val for key, val in actions.items() if key.endswith(f".{VELOCITY_SUFFIX}")}
        if len(goal_velocities) > 0:
            self.mir_goal_velocities(goal_velocities)
        if len(goal_positions) > 0:
            goal_positions_velocities:dict[str, float] = {}
            for motor in goal_positions:
                goal_positions_velocities[motor] = self._config.motors[motor].position_mode_velocity
            self.mir_goal_positions(goal_positions, goal_positions_velocities)
        return actions
                    
    @staticmethod
    def mir_make_empty_bus(port : str) -> mirEspFeetechMotorBus:
        return mirEspFeetechMotorBus(mirMotorBusConfiguration(motor_port=port, motors={}, calibration={}))

    @staticmethod
    def mir_make_bus_from_motors(port: str, motors: dict[str, mirMotor]) -> mirEspFeetechMotorBus:
        return mirEspFeetechMotorBus(mirMotorBusConfiguration(motor_port=port, motors=motors, calibration={}))

    @staticmethod
    def mir_scan_motors(port:str) -> list[int]:
        if mirEspFeetechMotorBus._bus_connected.get(port, False):
            raise ConnectionError("Le bus est déjà connecté")

        bus: mirEspFeetechMotorBus | None = None
        try :
            bus = mirEspFeetechMotorBus.mir_make_empty_bus(port)
            bus.mir_connect()
            ping_res = bus.broadcast_ping()
            return list(result) if (result := ping_res) else []
        except Exception as e:
            logger.error(f"Erreur lors du scan des moteurs: {e}")
            raise ConnectionError()
        finally:    
            if bus is not None:
                bus.disconnect()

    @staticmethod
    def mir_scan_motors_on_all_ports() -> tuple[str, list[int]] | tuple[None, None]:
        """
        Scanne tous les ports série ACM disponibles pour chercher un bus Feetech 
        Retourne le premier port trouvé avec les IDs des moteurs, 
        sinon retourne (None, None)
        """
        ports = find_acm_serial_ports()
        print(ports)
        for port in ports:
            print(f"scanning port {port}...")
            try:
                motors_ids = mirFeetechMotorsBus.mir_scan_motors(port)
                return (port, motors_ids)
            except ConnectionError:
                continue
        return (None, None)

        
