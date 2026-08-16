from click import Path
from mir_robot.mir_robot import mirRobot
from mir_robot.mir_robot_config import mirRobotConfig
from mir_utils.period_waiters import PeriodWaiterExact
from mir_utils.keyboard_listener import KeyboardListener, Key
from mir_utils.metrics import DataRecorder
from typing import Any
from os import path
from pathlib import Path

class TeleopKeyboard():
    def get_action(self) -> dict[str, Any] | None: 
        action = {}
        key = self._kbd.get_key()
        if key == Key.Left:
            pos = -50
        elif key == Key.Right:
            pos = 50
        elif key == Key.Up:
            pos = 0            
        elif key == Key.Esc:
            return None
        else:
            return action
        action["joint_1.position"] = pos
        action["joint_2.position"] = pos
        
        return action

    def connect(self):
        try:
            self._kbd = KeyboardListener()
            self._kbd.start()
        except Exception as e:
            print(f"Echec connexion keyboard : {e}")

    def disconnect(self) -> None:
        if self._kbd is not None:
            self._kbd.stop()
        

robot: mirRobot|None = None
teleop: TeleopKeyboard|None = None
recorder: DataRecorder|None = None
try:
    dir = path.dirname(__file__)
    config = mirRobotConfig.load(f"{dir}/motors_camera.json")   
    robot = mirRobot(config)
    robot.connect()
    robot.configure()
    robot.enable_all_observations()
    
    if not robot.is_calibrated:
        r= input("Le robot n'est pas calibré. Voulez-vous continuer ??? (o/n)")
        if r != 'o' and r != 'O':
            raise KeyboardInterrupt()

    teleop = TeleopKeyboard()
    teleop.connect()

    print("Téléopérateur connecté.\r\nFlèche gauche : -50°\r\nFlèche droite : +50°\r\nFlèche haut : 0°\r\nESC pour terminer.\r\n")
    recorder = DataRecorder(robot.get_enabled_observables(), 600*20) #600 secondes max
    period_waiter = PeriodWaiterExact(1/20) #20 Hz
    while True:
        action = teleop.get_action()
        if action is None:
            break
        robot.send_action(action)
        recorder.append(robot.get_observation())
        period_waiter.wait() #attend le temps nécessaire pour respecter le temps de boucle 

except KeyboardInterrupt:
    print("Téléopération annulée")
    pass
except BaseException as e:
    print(e)
finally:
    if robot is not None and robot.is_connected:
        robot.disconnect()
    if teleop is not None:
        teleop.disconnect()
    if recorder is not None:
        path = Path(__file__).parent / "rec.npz"
        recorder.save(path)
    print("\r\n")
