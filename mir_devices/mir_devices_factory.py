from dataclasses import field
from typing import Callable
from abc import ABC, abstractmethod
from mir_devices.mir_sensor import mirSensorConfiguration, mirSensor
from mir_devices.mir_feetech_motor_bus import mirMotorBusConfiguration, ImirFeetechMotorBus, mirFeetechMotorsBus
from mir_devices.cameras import PiCamera
from mir_devices.esp_sensors import (EspSensorWheather, 
                                    EspSensorLidar, 
                                    EspSensorSimulation, 
                                    EspSensorLidarConfiguration,
                                    EspSensorSimulationConfiguration,
                                    EspSensorWheatherConfiguration)
from mir_devices.mir_device import mirDevice, mirDevices
from mir_robot.mir_robot_config import mirRobotConfig
from mir_devices.mir_sensor import mirPiCameraConfiguration
from mir_devices.mir_device import ObservableProperty

import time

class mirSensorsConfig:
    sensors : dict[str, mirSensorConfiguration] = field(default_factory=lambda: { })

class ImirSensorsFactory(ABC):
   
    @abstractmethod
    def create_sensors(self, sensors_config: dict[str, mirSensorConfiguration]) -> dict[str, mirSensor]:
        pass

class DefaultSensorsFactory(ImirSensorsFactory):
    def create_sensors(self, sensors_config: dict[str, mirSensorConfiguration]) -> dict[str, mirSensor]:
        sensors = {}
        for sensor_id, cfg in sensors_config.items():
            sensors[sensor_id] = self.create_sensor(sensor_id, cfg)
        return sensors

    def create_sensor(self, sensor_key:str, cfg: mirSensorConfiguration) -> mirSensor:
        if isinstance(cfg, mirPiCameraConfiguration):
            return PiCamera(sensor_key, cfg)
        elif isinstance(cfg, EspSensorWheatherConfiguration):
            return EspSensorWheather(sensor_key, cfg)
        elif isinstance(cfg, EspSensorLidarConfiguration):
            return EspSensorLidar(sensor_key, cfg)
        elif isinstance(cfg, EspSensorSimulationConfiguration):
            return EspSensorSimulation(sensor_key, cfg)
        raise ValueError(f"Unknown sensor type: {cfg.sensor_type}")


def reset_sensors(
    sensors_configurations: dict[str, mirSensorConfiguration],
    initial_delay: float = 1.0,
    retry_interval: float = 1.0,
    timeout: float = 30.0,
    on_progress: Callable[[str], None] | None = None,
) -> None:
    """
    Réinitialise un ensemble de capteurs en parallèle.

    Args:
        sensors:  dict des capteurs à réinitialiser {sensor_id: mirSensor}.

    Étapes :
      0. Connexion préalable des capteurs non connectés.
      1. Envoi de la commande de reboot à tous.
      2. Attente d'un délai de boot initial commun.
      3. Tentatives de reconnexion en boucle jusqu'à ce que tous
         répondent ou que le timeout global soit dépassé.

    Raises:
        TimeoutError: si un ou plusieurs capteurs n'ont pas redémarré
                      dans le délai imparti.
    """
   
    def notify(msg: str) -> None:
        if on_progress is not None:
            on_progress(msg)

    #réinitialiser tous les capteurs
    sensor_factory = DefaultSensorsFactory()
    sensors = sensor_factory.create_sensors(sensors_configurations)
    for key, sensor in sensors.items():
        if sensor.mir_is_connected():
            raise RuntimeError(f"un capteur est en cours d'utilisation : {key}")
        notify(f"Reset du capteur {key}...")
        sensor.reset_sensor()
        

    # Phase 2 : délai de boot initial (une seule fois pour tous)
    time.sleep(initial_delay)
    notify("attente reconnexion capteurs..")
    # Phase 3 : boucle de reconnexion commune
    pending = sensors 
    t0 = time.time()
    while pending:
        if time.time() - t0 > timeout:
            ids = ", ".join(pending.keys())
            raise TimeoutError(
                f"Les capteurs suivants n'ont pas redémarré "
                f"dans le délai imparti ({timeout:.0f}s) : {ids}"
            )
        time.sleep(retry_interval)
        reconnected = []
        for sensor_id, sensor in pending.items():
            try:
                if sensor.test_connection():
                    reconnected.append(sensor_id)
            except Exception:
                pass   
        for sid in reconnected:
            notify(f"Capteur {sid} redémarré")
            del pending[sid]    
    notify("Tous les capteurs ont été redémarrés avec succès.")            

class ImirFeetechMotorBusFactory(ABC):
    """Interface pour la fabrique de bus de moteurs Feetech."""
    
    @abstractmethod
    def create_bus(self, config: mirMotorBusConfiguration) -> ImirFeetechMotorBus:
        """
        Crée et retourne une instance de bus de moteurs.
        
        Args:
            motor_config_provider: Le fournisseur de configuration des moteurs.
        """
        pass

class DefaultFeetechMotorBusFactory(ImirFeetechMotorBusFactory):
    """Implémentation par défaut de la fabrique de bus."""

    def create_bus(self, config: mirMotorBusConfiguration) -> ImirFeetechMotorBus:
        """Instancie mirFeetechMotorsBus avec le provider requis."""
        return mirFeetechMotorsBus(config)    


class ImirDevicesFactory(ABC):
    @abstractmethod
    def create_devices(self, config: mirRobotConfig) -> mirDevices:
        pass

class DefaultDevicesFactory(ImirDevicesFactory):
    def create_devices(self, config: mirRobotConfig) -> mirDevices:
        """
        Crée les devices (sensors et motor_bus selon la configuration)
        ainsi que le liste des observables selon la configuration
        souscrit aux observables sur les capteurs
        """

        #créer et ajouter les capteurs
        sensors_factory = DefaultSensorsFactory()
        sensors = sensors_factory.create_sensors(config.sensors)
        devices: dict[str, mirDevice] = {k: v for k, v in sensors.items()}

        #créer et ajouter le bus moteur
        if config.motor_bus is not None:
            motor_bus_factory = DefaultFeetechMotorBusFactory()
            motor_bus = motor_bus_factory.create_bus(config.motor_bus)
            devices['motor_bus'] = motor_bus

        #souscrire aux observables qui sont dans la liste des observations de la configuration
        observables : dict[str, ObservableProperty] = {}
        for device in devices.values():
            device_observables = device.get_observables_in(list(config.observations.keys()))
            observables.update(device_observables)
        return mirDevices(devices, observables)


