#!/bin/bash
cd /home/pi/mir_sensors_servers
source .venv/bin/activate
exec python lidar_server.py



