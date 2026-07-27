# MIR (Modular Intelligent Robot) Copilot Instructions

This repository contains a modular robotics framework built on [LeRobot](https://github.com/huggingface/lerobot) with a PyQt/PySide6 GUI editor for configuration and monitoring.

## Environment Setup

**Always use the conda environment specified in `.agent/rules.md`:**
```bash
/home/michel/miniforge3/envs/lerobot/bin/python
```

The project is configured via `pyrefly.toml` to use the `lerobot` conda environment for dependency resolution.

## Installation & Build

Install all packages in development mode from the project root:
```bash
./install.sh
```

This editable-installs these packages in dependency order:
1. `mir_utils` — Shared utilities (logging, UI base, keyboard listeners, concurrency)
2. `mir_devices` — Hardware abstraction layer
3. `mir_robot` — Main robot class extending LeRobot
4. `mir_robot_editor` — PyQt/PySide6 GUI application

## High-Level Architecture

### Package Structure

- **mir_utils/** — Reusable utilities:
  - `logs.py` — Loguru configuration with filters for mir_* modules
  - `ui/` — PyQt/PySide6 base widgets (MainWindowBase, DialogBase, etc.)
  - `keyboard_listener.py`, `concurrency.py`, `metrics.py`, `period_waiters.py`

- **mir_devices/** — Hardware abstraction:
  - `mir_feetech_motor_bus.py` — Feetech STS3215 motor bus control (operating modes 0/1/4)
  - `cameras.py`, `lidar.py`, `esp_sensors.py` — Sensor drivers
  - `mir_sensor_factory.py` — Factory pattern for sensor instantiation
  - `discovery_scanner.py` — Device discovery on network

- **mir_robot/** — Robot core:
  - `mir_robot.py` — Main `mirRobot` class extending LeRobot's `Robot`
  - `mir_robot_config.py` — Configuration dataclass with dacite-based JSON deserialization
  - `robot_configurations/` — Pre-built robot config files

- **mir_robot_editor/** — GUI application:
  - `main.py` — Entry point
  - `main_view.py` + `main_viewmodel.py` — Main window (MVC pattern)
  - `motor_configuration/` — Motor setup UI (calibration, ID assignment, register config)
  - `scan_devices_view.py` — Device discovery interface
  - `robot_monitor_view.py` — Real-time monitoring and manual control

### Data Flow

1. **Configuration**: JSON-based robot config → deserialized via `dacite` → `mirRobotConfig` dataclass
2. **Robot instantiation**: `mirRobotConfig` → `mirRobot` (extends LeRobot) → observation/action schemas
3. **Motor control**: Motor actions → `mirFeetechMotorBus` → serial communication
4. **Observations**: Sensors (lidar, cameras, ESP32) → aggregated observations from LeRobot
5. **GUI**: Views bind to ViewModels; ViewModels manage state and communicate with robot/devices

## Key Conventions

### Configuration Format (JSON)

Robot configs are stored in `mir_robot/robot_configurations/` as JSON files with this structure:

```json
{
  "id": "mir_robot",
  "calibration_dir": null,
  "motor_port": "/dev/ttyACM0",
  "motors": {
    "joint_1": {
      "id": 2,
      "model": "sts3215",
      "norm_mode": "degrees",
      "operating_mode": 0,
      "P": 16, "I": 0, "D": 32,
      "position_mode_velocity": 100
    }
  },
  "sensors": {
    "camera_top": {
      "type": "pi_camera",
      "ip_address": "192.168.1.22",
      "width": 640, "height": 480, "fps": 30
    }
  },
  "observations": { ... },
  "actions": { ... },
  "calibration": { ... }
}
```

Supported sensor types:
- Cameras: `pi_camera`, `usb_camera`
- LIDAR: `pi_lidar`, `usb_lidar`, `esp_lidar`
- ESP: `esp_sensors`, `esp_simulation`, `esp_wheather`

For details, see `doc/configuration_format.md`.

### Logging

Always use `loguru` for logging:

```python
from loguru import logger

logger.debug("message")
logger.info("message")
logger.warning("message")
```

Enable logging in main application entry points:
```python
from mir_utils.logs import enable_logging
enable_logging()
```

Logs are written to `logs/mir.log` with DEBUG level. Filters ensure only mir_* modules log.

### Motor Control

Motor operating modes (set in config or at runtime):
- **Mode 0**: Position control (motor moves to target position)
- **Mode 1**: Velocity control (motor maintains velocity)
- **Mode 4**: Extended position control

Each motor has:
- `id` — hardware ID on bus
- `model` — e.g., "sts3215"
- `norm_mode` — "degrees" or other units
- PID gains (`P`, `I`, `D`)
- `position_mode_velocity` — velocity when in position mode

### Configuration Deserialization

Use `dacite` + `JsonParseHelper` for robust JSON → dataclass conversion:

```python
from mir_robot.mir_robot_config import mirRobotConfig

config = mirRobotConfig.load("path/to/config.json")
config.save("path/to/output.json")
config_dict = config.to_dict()
```

### UI (MVC Pattern)

- **View**: PyQt/PySide6 widgets inheriting from `ViewBase` or `MainWindowBase`
- **ViewModel**: Business logic, state management (no direct LeRobot interaction in views)
- **Model**: Robot, sensors, configuration

Example pattern:
```python
class MyViewModel:
    def __init__(self, robot: mirRobot):
        self.robot = robot
        self.my_value = 0  # Observable state
    
    def update_motor(self, motor_id: int, position: float):
        self.robot.send_action(motor_id, position)

class MyView(ViewBase):
    def __init__(self, view_model: MyViewModel):
        self.view_model = view_model
        # Connect signals to view_model slots
```

### Device Discovery

Use `DiscoveryScanner` from `mir_devices.discovery_scanner` to find sensors on network (IP/port broadcast).

### Error Handling

Wrap configuration loading and device communication in try-except:

```python
try:
    config = mirRobotConfig.load(path)
except ValueError as e:
    logger.error(f"Config load failed: {e}")
    # Show user-facing error via QtDialogProvider
```

## Testing Notes

Currently, no automated test suite exists in the repository. Manual testing focuses on:
- Configuration loading/saving
- Motor communication on serial port
- Sensor data acquisition (cameras, LIDAR)
- GUI responsiveness and state sync

## Common Tasks

### Run the GUI Editor

```bash
/home/michel/miniforge3/envs/lerobot/bin/python -m mir_robot_editor.main
```

### Load a Robot Configuration

```python
from mir_robot.mir_robot_config import mirRobotConfig
config = mirRobotConfig.load("mir_robot/robot_configurations/my_robot.json")
```

### Access Robot Observations

```python
robot = mirRobot(config)
observations = robot.get_observations()  # Dict with sensor data
# Keys: "camera_top", "joint_1.position", "lidar_front", etc.
```

### Send Motor Commands

```python
robot.send_action({"joint_1": 90, "joint_2": 45})  # Positions in degrees
```

## File Locations

- **Logs**: `logs/mir.log`
- **Robot configs**: `mir_robot/robot_configurations/`
- **Documentation**: `doc/` (configuration_format.md, calibration guides, etc.)
- **Sensor Pi code**: `mir_pi_sensors/` (camera_server.py, lidar_server.py)
- **User scripts/demos**: `mir_user_scripts/demos/`

## External Dependencies

- **LeRobot** (HuggingFace) — Robot control framework
- **PyQt/PySide6** — GUI framework
- **loguru** — Structured logging
- **dacite** — Dataclass JSON deserialization
- **pyqtgraph** — Real-time plotting in GUI

## Language

The codebase is primarily in English, with some comments and docstrings in French. Function/class names follow English conventions.
