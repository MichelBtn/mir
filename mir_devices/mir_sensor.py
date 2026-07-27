from typing import Literal
from abc import abstractmethod
from typing import Any
import dacite
from dataclasses import dataclass
from mir_devices.mir_device import mirDevice

PropertyType = Literal["int", "float", "bool", "str", "list"]

@dataclass
class SensorProperty:
    label: str
    property_type: PropertyType
    current_value: Any
    min_value: int | float | None = None
    max_value: int | float | None = None
    step: int | float | None = None
    options: list[str] | None = None
    immediate: bool = False
    requires_reboot: bool = False
    read_only: bool = False
    tooltip: str = ""

@dataclass
class mirSensorConfiguration:
    sensor_type: str

    @staticmethod
    def create_sensors_from_dict(sensors_config: dict[str, Any] | None, dacite_config: dacite.Config) -> dict[str, "mirSensorConfiguration"]:
        sensors: dict[str, "mirSensorConfiguration"] = {}
        if sensors_config is None:
            return sensors            
        for k, v in sensors_config.items():
            sensor_type = v.get("sensor_type", "")
            if sensor_type == mirPiCameraConfiguration.SENSOR_TYPE:
                target_class = mirPiCameraConfiguration
            elif sensor_type == EspSensorLidarConfiguration.SENSOR_TYPE:
                target_class = EspSensorLidarConfiguration
            elif sensor_type == EspSensorWheatherConfiguration.SENSOR_TYPE:
                target_class = EspSensorWheatherConfiguration
            elif sensor_type == EspSensorSimulationConfiguration.SENSOR_TYPE:
                target_class = EspSensorSimulationConfiguration
            else:
                raise ValueError(f"Unknown sensor type: {sensor_type}")
            sensors[k] = dacite.from_dict(target_class, v, dacite_config)
        return sensors    
   
@dataclass
class mirPiCameraConfiguration(mirSensorConfiguration):
    ip: str | None = None
    width: int | None = None
    height: int | None = None
    fps: int | None = None
    enable_stats: bool = False
    frame_stats_size: int = 0
    def __str__(self) -> str:
        return f"{self.ip}"
    SENSOR_TYPE = "pi_camera"

@dataclass
class EspSensorConfiguration(mirSensorConfiguration):
    ip: str
    def __str__(self) -> str:
        return f"{self.ip}"

@dataclass
class EspSensorLidarConfiguration(EspSensorConfiguration):
    SENSOR_TYPE = "esp_lidar"
   
@dataclass
class EspSensorWheatherConfiguration(EspSensorConfiguration):
    SENSOR_TYPE = "esp_wheather"

@dataclass
class EspSensorSimulationConfiguration(EspSensorConfiguration):
    SENSOR_TYPE = "esp_simulation"

class mirSensor(mirDevice):
    sensor_key:str

    def __init__(self, sensor_key:str):    
        super().__init__()    
        self.sensor_key = sensor_key
        
    @abstractmethod
    def test_connection(self) -> bool:
        pass

    @abstractmethod
    def get_configurable_properties(self) -> dict[str, SensorProperty]:
        """Retourne les propriétés configurables (à surcharger si configurable)"""
        return {}
    
    @abstractmethod
    def set_property(self, key: str, value: Any) -> bool:
        """Configure une propriété (à surcharger si configurable)"""
        return False

    @abstractmethod
    def reset_sensor(self):
        pass

    