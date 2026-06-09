import time
import random
from paho.mqtt import client as mqtt_client
import os
from dotenv import load_dotenv

load_dotenv()

#! Config System (Change when in lab/home)
TESTING_AT_HOME = True 

BROKER = 'broker.emqx.io' if TESTING_AT_HOME else os.getenv("PRIVATE_MQTT_BROKER")
PORT = int(os.getenv("MQTT_PORT"))
ID = os.getenv("MQTT_USERNAME")
CLIENT_ID = f'pcb-finance-{ID}'


#! MQTT TOPICS (Some here are private for internal finance/sales telemetry, some are public to simulate 3rd party interactions )
#? Internal Finance/Sales Topics
TOPIC_SALES = f"{ID}/factory/sales/receipts"

#? Public 3rd Party Supply Chain Topics
TOPIC_PUB_ALERT = f"public/{ID}/factory/supply/order_alert"       #* This is the <Topic 1> where user 1 Posts
TOPIC_PUB_CONFIRM = f"public/{ID}/factory/supply/order_confirmed" #* This is the <Topic 2> where user 2 Replies

def connect_mqtt():
    def on_connect(client, _userdata, _flags, rc, _properties=None):
        if rc == 0:
            print("Finance Node Online")
            client.subscribe(TOPIC_PUB_CONFIRM, 0) 
        else:
            print(f"Connection failed with code {rc}")

    client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION1, CLIENT_ID)
    if not TESTING_AT_HOME:
        client.username_pw_set(ID, ID)
        
    client.on_connect = on_connect
    client.connect(BROKER, PORT)
    return client

#? MQTT Handler for receiving confirmations from the supplier network (User 2) regarding the orders coming in and confirming said orders
def on_message(_client, _userdata, msg):
    timestamp = time.strftime("%H:%M:%S")
    topic = msg.topic
    payload = msg.payload.decode()
    
    if topic == TOPIC_PUB_CONFIRM:
        print(f"\n[{timestamp}] 3rd Party Request | Dashboard Replied: {payload}")

#!  Finance simulation loop and MQTT Client sits here
#TODO We simulate random sales of PCB batches every few seconds and publish receipts to the private sales topic
def run_enterprise():
    client = connect_mqtt()
    client.on_message = on_message
    client.loop_start()
    
    time.sleep(2)

    while True:
        #? Simulate random sales of PCB batches and publish receipts to the private sales topic (60% chance every 5 seconds)
        timestamp = time.strftime("%H:%M:%S")
        if random.random() > 0.4: 
            batch_size = random.randint(50, 200)
            price_per_unit = 25.50
            total = batch_size * price_per_unit
            
            #? Publish the sales receipt to the private sales topic for the Dashboard
            receipt = f"Sold batch of {batch_size} PCBs at ${price_per_unit:.2f} | Total: ${total:.2f}"
            client.publish(TOPIC_SALES, receipt)
            
            print(f"\n[{timestamp}] {receipt}")
            
        #? We publish a message to the public alert topic to simulate a 3rd party requesting more silicon wafers from the supplier network (User 1 -> User 2 interaction) (30% chance every 5 seconds)

        if random.random() > 0.7:
            batch_size = random.randint(50, 200)
            alert_msg = f"User1_Alert: 3rd party requests {batch_size} new silicon wafers from Supplier Network."
            client.publish(TOPIC_PUB_ALERT, alert_msg)
            
            print(f"[{timestamp}] Published to Public 'order_alert': {alert_msg}")
            
        time.sleep(5)

if __name__ == '__main__':
    run_enterprise()