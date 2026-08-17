import traci
import os
import time
import sys
from sumolib import checkBinary
import pickle

if "SUMO_HOME" in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'],'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

show_gui = True
sumoconfig_path = os.environ.get("IRPP_SUMO_CONFIG")
if not sumoconfig_path:
    sys.exit("set IRPP_SUMO_CONFIG to the SUMO .sumocfg file")
if not show_gui:
    sumoBinary = checkBinary('sumo')
else:
    sumoBinary = checkBinary('sumo-gui')

traci.start([sumoBinary, '-c', sumoconfig_path])
# with open('list.pkl', 'wb') as file:
#   for step in range(0,1000):
#     time.sleep(0.1)
#     #操控时间
#     traci.simulationStep(step*100 + 100)
#     simulation_current_time=traci.simulation.getTime()
#     print("仿真时间是",simulation_current_time)
#     #获取所有车的ID
#     all_vehicle_id = traci.vehicle.getIDList()
#     #获取所有车的position
#     all_vehicle_position = [(i,traci.vehicle.getPosition(i))for i in all_vehicle_id]
#     pickle.dump(all_vehicle_position, file)
#     #获取所有车是否经过过车线
#     # print(all_vehicle_position)

with open('trace.pkl', 'wb') as file:
      for step in range(0, 10):
            time.sleep(0.1)
            # 操控时间
            traci.simulationStep(step*100 + 100)
            simulation_current_time = traci.simulation.getTime()
            print("仿真时间是", simulation_current_time)
            # 获取所有车的ID
            all_vehicle_id = traci.vehicle.getIDList()
            # 获取所有车的position
            all_vehicle_position = [(i, traci.vehicle.getPosition(i))for i in all_vehicle_id]
            pickle.dump(all_vehicle_position, file)
            # 获取所有车是否经过过车线
            # print(all_vehicle_position)

traci.close()
