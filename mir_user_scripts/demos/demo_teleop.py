from mir_robot.mir_robot import mirRobot
from mir_robot.mir_robot_config import mirRobotConfig
from mir_utils.period_waiters import PeriodWaiterExact
from os import path
from mir_utils.keyboard_listener import KeyboardListener, Key
from typing import Any

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
try:
    dir = path.dirname(__file__)
    config = mirRobotConfig.load(f"{dir}/config_motors_position.json")   
    robot = mirRobot(config)
    robot.connect()
    robot.configure()

    if not robot.is_calibrated:
        r= input("Le robot n'est pas calibré. Voulez-vous continuer ??? (o/n)")
        if r != 'o' and r != 'O':
            raise KeyboardInterrupt()

    teleop = TeleopKeyboard()
    teleop.connect()

    print("Téléopérateur connecté.\r\nFlèche gauche : -50°\r\nFlèche droite : +50°\r\nFlèche haut : 0°\r\nESC pour terminer.\r\n")
    period_waiter = PeriodWaiterExact(1/20) #20 Hz
    while True:
        action = teleop.get_action()
        if action is None:
            break
        robot.send_action(action)
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
    print("\r\n")
