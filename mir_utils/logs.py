from loguru import logger
from pathlib import Path

MIR_DIR = Path(__file__).parent.parent

def enable_logging():
    logger.enable("mir_robot")
    logger.enable("mir_utils")
    logger.enable("mir_devices")
    logger.enable("mir_robot_editor")

    logger.add(
        MIR_DIR / "logs" / "mir.log",
        format="{time} - {name} - {level} - {message}",
        filter=lambda r: r["name"].startswith("mir_"), # type: ignore
        level="DEBUG"
    )

def disable_logging():
    logger.disable("mir_robot")
    logger.disable("mir_utils")
    logger.disable("mir_devices")
    logger.disable("mir_robot_editor")