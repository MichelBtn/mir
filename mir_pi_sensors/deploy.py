#!/usr/bin/env python3
from fabric import Connection
import argparse
import sys
import subprocess
from pathlib import Path

PI_HOST = "pi2"
PI_USER = "pi"
PI_PATH = "/home/pi/mir_sensors_servers"
local_path = Path(__file__).parent
local_libs = local_path.parent / "mir_devices"
LOCAL_PATH = local_path.as_posix()
LOCAL_LIBS = local_libs.as_posix()

# ───────────────────────────────────────────────────────────────
# Couleurs
# ───────────────────────────────────────────────────────────────
GREEN      = "\033[1;32m"
YELLOW     = "\033[1;33m"
RED        = "\033[1;31m"
LIGHT_BLUE = "\033[1;34m"
RESET      = "\033[0m"

def info(msg):    print(f"{LIGHT_BLUE}{msg}{RESET}")
def success(msg): print(f"{GREEN}{msg}{RESET}")
def warn(msg):    print(f"{YELLOW}{msg}{RESET}")
def error(msg):   print(f"{RED}{msg}{RESET}")

# ───────────────────────────────────────────────────────────────
# Arguments
# ───────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Déploiement vers Raspberry Pi")
parser.add_argument("--camera", action="store_true", help="Déploie camera_server")
parser.add_argument("--lidar",  action="store_true", help="Déploie lidar_server")
parser.add_argument("--all",    action="store_true", help="Déploie les deux services")
args = parser.parse_args()

if args.all:
    args.camera = args.lidar = True

if not args.camera and not args.lidar:
    error("Aucun service spécifié. Utilisez --camera, --lidar ou --all.")
    parser.print_help()
    sys.exit(1)

services = [s for s, active in [("camera", args.camera), ("lidar", args.lidar)] if active]
info(f"Services à déployer : {' '.join(services)}")

# ───────────────────────────────────────────────────────────────
# Connexion SSH
# ───────────────────────────────────────────────────────────────
info(f"Connexion SSH vers {PI_USER}@{PI_HOST}...")
try:
    ssh_cnx = Connection(host=PI_HOST, user=PI_USER)
    ssh_cnx.run("true", hide=True)
    success("Connexion SSH OK.")
except Exception as e:
    error(f"Impossible de se connecter : {e}")
    sys.exit(1)

# ───────────────────────────────────────────────────────────────
# Synchronisation des fichiers (rsync)
# ───────────────────────────────────────────────────────────────
def rsync(src, dst, includes):
    include_args = [arg for f in includes for arg in ("--include", f)]
    cmd = ["rsync", "-av", "--delete", "--chmod=+x",
           *include_args, "--exclude=*", src, dst]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        error(f"Echec rsync (code {result.returncode}).")
        sys.exit(1)

info("Mise à jour des fichiers...")
ssh_cnx.run(f"mkdir -p {PI_PATH}")
rsync(
    src=f"{LOCAL_PATH}/",
    dst=f"{PI_USER}@{PI_HOST}:{PI_PATH}/",
    includes=["*.py", "camera_server.service", "run_camera_server.sh",
              "lidar_server.service", "run_lidar_server.sh",
              "setup_services.sh", "setup_python.sh", "requirements.in"]
)
rsync(
    src=f"{LOCAL_LIBS}/",
    dst=f"{PI_USER}@{PI_HOST}:{PI_PATH}/",
    includes=["lidar.py"]
)
success("Fichiers à jour.")

# ───────────────────────────────────────────────────────────────
# Setup Python
# ───────────────────────────────────────────────────────────────
info("Setup environnement Python...")
result = ssh_cnx.run(f"{PI_PATH}/setup_python.sh {PI_PATH}", warn=True)
if result.failed:
    error("Echec du setup Python.")
    sys.exit(1)
success("Environnement Python OK.")

# ───────────────────────────────────────────────────────────────
# Déploiement des services
# ───────────────────────────────────────────────────────────────
def deploy_service(service_name):
    info(f"Déploiement de {service_name}.service...")
    result = ssh_cnx.run(f"{PI_PATH}/setup_services.sh {service_name} {PI_PATH}", warn=True)
    if result.failed:
        error(f"Echec déploiement de {service_name}.service.")
        return False
    success(f"Service {service_name}.service déployé.")
    return True

for service in services:
    deploy_service(f"{service}_server")

success("Déploiement terminé.")
