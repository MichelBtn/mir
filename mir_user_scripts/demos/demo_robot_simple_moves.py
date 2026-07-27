from mir_robot.mir_robot import mirRobot, mirRobotConfig
from os import path
import time
robot: mirRobot|None = None
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
    r = input("Le robot va se déplacer. (o/n)")
    if r == 'o' or r == 'O':
        for pos in [-50, 0, 50]:
            robot.send_action({
                "joint_1.position":pos,
                "joint_2.position":pos,        
            })
            is_moving = True
            while is_moving:
                time.sleep(0.1) #la tempo (mini 0.05) est nécessaire au début, sinon robot.motor_is_moving() retourne False d'emblée (les registres 'Present_Velocity' sont encore à 0).
                obs = robot.get_observation()
                print(f"{obs['joint_1.position']:5.1f}, {obs['joint_2.position']:5.1f}")
                is_moving = robot.motor_is_moving()
            time.sleep(0.5)                        
            obs = robot.get_observation()                
            print(f"position atteinte : {obs['joint_1.position']:5.1f}, {obs['joint_2.position']:5.1f}")
                        

except BaseException as e:
    print(e)
finally:
    if robot is not None and robot.is_connected:
        robot.disconnect()
    print("si iou les teures")
