# dans chaque __init__.py de sous-package
import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.propagate = False  # ← silence même si lerobot configure le root