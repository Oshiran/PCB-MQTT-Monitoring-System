import time
import random
from paho.mqtt import client as mqtt_client
import os
from dotenv import load_dotenv

load_dotenv()

#! Config System (Change when in lab/home)
TESTING_AT_HOME = True 

BROKER = 'broker.emqx.io' if TESTING_AT_HOME else os.getenv("PRIVATE_MQTT_BROKER")
PORT = int(os.getenv("MQTT_PORT", "1883"))
ID = os.getenv("MQTT_USERNAME")
CLIENT_ID = f'pcb-hardware-{ID}'


#! MQTT TOPICS (All Private as this node is considered "internal telemetry")
TOPIC_CMD = f"{ID}/factory/processing/conveyor/commands"
TOPIC_STATUS = f"{ID}/factory/processing/conveyor/status"
TOPIC_TEMP = f"{ID}/factory/processing/oven/temp"
TOPIC_INVENTORY = f"{ID}/factory/inventory/wafers"

#! Global State Variables for the Hardware Simulation
conveyor_running = True
wafer_stock = 500
motor_speed = 1
base_temp = 240.0

def connect_mqtt():
    def on_connect(client, _userdata, _flags, rc, _properties=None):
        if rc == 0:
            print("Factory Node Online")
            client.subscribe(TOPIC_CMD, 0)
        else:
            print(f"Connection failed with code {rc}")

    client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION1, CLIENT_ID)
    if not TESTING_AT_HOME:
        client.username_pw_set(ID, ID)
    client.on_connect = on_connect
    client.connect(BROKER, PORT)
    return client

#! MQTT Message Handler for receiving commands from the Dashboard and updating internal state accordingly
def on_message(_client, _userdata, msg):
    global conveyor_running, wafer_stock, motor_speed 
    command = msg.payload.decode()
    timestamp = time.strftime("%H:%M:%S")

    print(f"\n[{timestamp}] Command Received: {command}")
    
    if command == "HALT":
        conveyor_running = False
    elif command == "RESUME":
        conveyor_running = True
    elif command == "RESTOCK":
        wafer_stock = 500
        print(f"[{timestamp}] Inventory restocked to 500")
    elif command.startswith("SPEED:"):
        try:
            motor_speed = int(command.split(":")[1])
            print(f"[{timestamp}] Speed adjusted to {motor_speed}x")
        except:
            pass

def run():
    global wafer_stock, conveyor_running, motor_speed
    client = connect_mqtt()
    client.on_message = on_message
    client.loop_start()
    time.sleep(2)
    
    current_temp = base_temp 

    #! Factory Simulation Loop sits here
    #TODO Our values are randomized for demonstration but could also be replaces with real sensor readings if this were connected to actual hardware
    while True:
        timestamp = time.strftime("%H:%M:%S")
        if conveyor_running:
            
            #? Simulate Conveyor Belt random amounts of wafers from 1-5
            items_picked = random.randint(1, 5)
            wafer_stock = max(0, wafer_stock - items_picked) #* Ensure we don't go negative on stock
            
            #? Simulate the oven temperature fluctuating based on motor speed and some random noise
            current_temp = base_temp + (motor_speed * 4.5) + random.uniform(-1.5, 1.5)
            
            #? Publish the current status, inventory, and temperature to the Dashboard
            status_msg = "Belt Status: RUNNING"
            stock_msg = f"Silicon Wafers: {wafer_stock} units"
            temp_msg = f"Oven Temp: {current_temp:.1f}°C"
            
            client.publish(TOPIC_STATUS, status_msg)
            client.publish(TOPIC_INVENTORY, stock_msg)
            client.publish(TOPIC_TEMP, temp_msg)
            
            print(f"[{timestamp}] {stock_msg} | {temp_msg} | Speed: {motor_speed}x")
            
            time.sleep(5.0 / motor_speed) #? Conveyor speed affects how often we publish updates (faster speed = more frequent updates)
            
        else:
            #? If we aren't processing, we simulate a drop in the temperature to cool the oven till it hits room temp)
            if current_temp > 25.0: 
                current_temp -= 2.5
                
            #? Publish the halted status and current inventory/temp to the Dashboard    
            status_msg = "Belt Status: HALTED"
            stock_msg = f"Silicon Wafers: {wafer_stock} units"
            temp_msg = f"Oven Temp: COOLING ({current_temp:.1f}°C)"
            
            client.publish(TOPIC_STATUS, status_msg)
            client.publish(TOPIC_INVENTORY, stock_msg)
            client.publish(TOPIC_TEMP, temp_msg)
            
            print(f"[{timestamp}] Published -> {stock_msg} | {temp_msg}")
            
            time.sleep(5) #? When halted, we publish less frequently as there is no active processing happening

if __name__ == '__main__':
    run()