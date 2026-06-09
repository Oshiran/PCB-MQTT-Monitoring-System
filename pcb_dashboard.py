import streamlit as st
import paho.mqtt.client as mqtt_client
import time
import random
import os
from dotenv import load_dotenv

load_dotenv()

#! Config System (Change when in lab/home)
TESTING_AT_HOME = True 

BROKER = 'broker.emqx.io' if TESTING_AT_HOME else os.getenv("PRIVATE_MQTT_BROKER")
PORT = int(os.getenv("MQTT_PORT"))
ID = os.getenv("MQTT_USERNAME")
CLIENT_ID = f'pcb-dashboard-{ID}'

#! MQTT TOPICS
TOPIC_PRIVATE_WILD = f"{ID}/factory/#" #? Subscribe to all factory-related topics 
TOPIC_COMMANDS = f"{ID}/factory/processing/conveyor/commands" #? Publish control commands to the conveyor subsystem

TOPIC_PUB_WILD = f"public/{ID}/factory/#" #? Subscribe to all public factory-related topics
TOPIC_PUB_ALERT = f"public/{ID}/factory/supply/order_alert" #? Subscribe to order alert messages
TOPIC_PUB_CONFIRM = f"public/{ID}/factory/supply/order_confirmed" #? Subscribe to order confirmation messages

#! MQTT Client Initialization and State Management
@st.cache_resource #? Cache the MQTT client to maintain state across Streamlit reruns since streamlit's works by re-running the script on every interaction. This ensures we don't lose our MQTT connection or logs

def init_mqtt():
    client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION1, CLIENT_ID)
    if not TESTING_AT_HOME:
        client.username_pw_set(ID, ID) #? Use student ID as both username and password for authentication in the lab
        
    #TODO Initialize logs and state variables storage on the client side since MQTT client object persists across Streamlit reruns due to caching and we need a place to store our logs and state that is accessible in the callback functions. Furthermore, we maintain the history of events of up to 15 past logs

    client.logistics_log = []
    client.finance_log = []
    client.b2b_log = [] 
    
    #? Initial state values for telemetry
    client.wafer_history = [500] 
    client.temp_history = [240.0]  
    client.is_connected = False
    
    #? Initial state of the conveyor and oven for display purposes
    client.conveyor_status = "RUNNING"       
    client.conveyor_speed = 1  
    client.oven_temp = "240.0°C"
    
    #? To prevent multiple restock triggers when inventory is low, we use a flag to track if we've already triggered a restock action
    client.restock_triggered = False

    #? Since we are connceting to a public broker, we need to handle the possibility of receiving messages from other clients that are not part of our factory. We will filter messages based on the topic and expected payload format in the on_message callback to ensure we only process relevant messages for our dashboard, and to prevent accidently DOSing myself
    def on_connect(c, _userdata, _flags, rc, _properties=None):
        print(f"Result Code: {rc}")
        if rc == 0:
            c.is_connected = True
            if TESTING_AT_HOME:
                c.subscribe([(TOPIC_PRIVATE_WILD, 0), (TOPIC_PUB_ALERT, 0)])
            else:
                c.subscribe([(TOPIC_PRIVATE_WILD, 0), (TOPIC_PUB_WILD, 0)])

    #? Handles all MQTT messages received by client, different logic is implmented based on the topic of the message
    def on_message(c, _userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode()
        timestamp = time.strftime("%H:%M:%S")
        
        #! Based on the requirement: "Automatically generate messages based on the messages from <Topic 1> and post messages to <Topic 2> in a public channel"
        #TODO 1) Client 1: "pcb_finance.py" publishes to the public "factory/supply/order_alert" when 3rd Party inventory is low and needs restocking 
        #TODO 2) Client 2: "pcb_dashboard.py" listens for this message, extracts the incoming payload, and dynamically formulates a response (injecting the original message) to confirm receipt.
        #TODO 3) Recipt is published to the public "factory/supply/order_confirmed" for the finance system to receive and log. This simulates an automated B2B communication where the dashboard acts as an intermediary that acknowledges supply chain alerts from the finance system and confirms them back to ensure smooth coordination between the two systems.
        if topic == TOPIC_PUB_ALERT:
            #? Incoming message logged
            c.b2b_log.insert(0, f" `[{timestamp}]` **[ERP REQUEST]** {payload}")
            
            #? Formatting of automated response with the original message injected for context
            auto_response = f"B2B Verification: Dashboard acknowledges '{payload}'"
            c.publish(TOPIC_PUB_CONFIRM, auto_response)
            
            #? Log outgong response
            c.b2b_log.insert(0, f" `[{timestamp}]` **[B2B AUTO-REPLY]** {auto_response}")
            c.b2b_log = c.b2b_log[:15]
            return

        #? Oven Temperature Message Handling with Autonomous Safety Logic
        #TODO 1) Extract temperature value from incoming messages and update the dashboard state to reflect the current oven temperature
        #TODO 2) If the temperature exceeds 260°C, automatically publish a "HALT" Command to the conveyor commands topic to simulate an emergency shutdown of the production line to prevent damage or safety hazards. This automates safety without human intervention.
        if "oven/temp" in topic:
            c.oven_temp = payload.replace("Oven Temp: ", "")
            
            try:
                clean_str = c.oven_temp.replace("COOLING", "").replace("(", "").replace(")", "").replace("°C", "").strip()
                raw_temp = float(clean_str)
                
                c.temp_history.append(raw_temp)
                if len(c.temp_history) > 50: c.temp_history.pop(0)
                
                #! Auto shutdown lopic based on temperature threshold of 260°C, anything higher will shutdown the production line
                if raw_temp > 260.0 and c.conveyor_status == "RUNNING":
                    c.publish(TOPIC_COMMANDS, "HALT")
                    c.logistics_log.insert(0, f"`[{timestamp}]` [AUTO] Critical Heat: ({raw_temp}°C). Motor Halted")
                    c.logistics_log = c.logistics_log[:15]
            except:
                pass
        
        #? Conveyor status message handling to update the dashboard state and display
        if "conveyor/status" in topic:
            c.conveyor_status = "RUNNING" if "RUNNING" in payload else "HALTED"

        #? Wafer Inventory Message Handling with Autonomous Stock Logic
        #TODO When wafer numbers drop below 50, we automatically trigger a restock command to simulate a refill to the stock 
        #TODO To prevent multiple triggers, we use the "restock_triggered" flag to ensure we only send one restock command until the inventory is sufficiently replenished (above 100).
        if "inventory/wafers" in topic:
            try:
                stock_val = int(payload.split(": ")[1].split(" ")[0])
                c.wafer_history.append(stock_val)
                if len(c.wafer_history) > 50: c.wafer_history.pop(0)
                
                #! Auto Restocking
                if stock_val < 50 and not c.restock_triggered:
                    c.publish(TOPIC_COMMANDS, "RESTOCK")
                    c.logistics_log.insert(0, f"`[{timestamp}]` [AUTO] Stock critical: {stock_val} units. Restocking")
                    c.logistics_log = c.logistics_log[:15]
                    c.restock_triggered = True

                elif stock_val > 100:
                    c.restock_triggered = False
            except:
                pass
            
            if c.conveyor_status == "RUNNING":
                status_txt = f":green[RUNNING ({c.conveyor_speed}x)]"
            else:
                status_txt = ":red[HALTED]" 
                
            formatted_msg = f"`[{timestamp}]` **{payload}** | Motor: **{status_txt}** | Temp: **{c.oven_temp}**"
            c.logistics_log.insert(0, formatted_msg)
            c.logistics_log = c.logistics_log[:15]

        #? Sales Receipt Message Handling to log financial transactions in the dashboard
        if "sales/receipts" in topic:
            c.finance_log.insert(0, f"`[{timestamp}]` {payload}")
            c.finance_log = c.finance_log[:15] 

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT)
    client.loop_start() 
    return client

client = init_mqtt()

#! Streamlit Dashboard Layout and Logic

st.set_page_config(page_title="PCB Smart Factory", layout="wide")
st.title("PCB Smart Factory Dashboard")

if client.is_connected:
    st.success(f"Connected to Broker: {BROKER}")
else:
    st.error(f"Attempting to connect to Broker {BROKER}")

st.subheader("Factory Floor Telemetry")
m1, m2, m3 = st.columns(3)

current_wafers = client.wafer_history[-1] if client.wafer_history else 500

with m1:
    st.subheader("Raw Silicon Wafer (Max 500)")
    st.metric(label="Current Stock", value=f"{current_wafers} units")
    st.progress(max(0, min(current_wafers / 500.0, 1.0)))

with m2:
    st.subheader("Conveyor Belt Status")
    n1,n2 = st.columns(2)
    with n1:
        st.metric(label="Current Status", value=client.conveyor_status)
    with n2:
        st.metric(label="Speed Multiplier", value=f"{client.conveyor_speed}x")
    st.progress(1.0 if client.conveyor_status == "RUNNING" else 0.0)
    if client.conveyor_status == "HALTED":
        st.error(f"Conveyor Offline")
    else:
        st.success(f"Running at speed: {client.conveyor_speed}x")
    
with m3:
    st.subheader("Reflow Oven Temperature")    
    st.metric(label="Current Temperature", value=client.oven_temp)
    n1, n2 = st.columns(2)
    with n1:
        st.badge("Warning Trigger at 250°C", color="yellow")
    with n2:
        st.badge("Safety Trigger at 260°C",color="red")
    if "COOLING" in client.oven_temp:
        st.info(f"Cooling Mode Active")
    else:
        try:
            temp_float = float(client.oven_temp.replace("°C", ""))
            if temp_float > 250.0:
                st.warning(f"Warning: High Heat detected:{client.oven_temp}")
            else:
                st.info(f"Oven Active: {client.oven_temp}")
        except:
            st.warning(f"Reflow Oven Active: {client.oven_temp} (Unable to parse temperature)")

tab1, tab2 = st.tabs(["Telemetry & Controls", "Logs"])

with tab1:
    st.header("Factory Controls")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Conveyor Stop", use_container_width=True, type="primary"):
            client.publish(TOPIC_COMMANDS, "HALT")
    with c2:
        if st.button("Conveyor Resume", use_container_width=True):
            client.publish(TOPIC_COMMANDS, "RESUME")
    with c3:
        if st.button("Restock Wafers (Back to 500)", use_container_width=True):
            client.publish(TOPIC_COMMANDS, "RESTOCK")
            
    st.subheader("Coneyor Speed Control")
    new_speed = st.slider("Conveyor Speed Multiplier", 1, 5, client.conveyor_speed)
    if new_speed != client.conveyor_speed:
        client.conveyor_speed = new_speed
        client.publish(TOPIC_COMMANDS, f"SPEED:{new_speed}")

    st.header("Current Silicon Wafer Inventory & Oven Temperature")
    n1, n2 = st.columns(2)
    with n1:
        st.metric(label="Current Silicon Wafers", value=f"{client.wafer_history[-1]} units", delta="- Depleting" if client.wafer_history[-1] < 100 else "+ Stable", delta_color="inverse" if client.wafer_history[-1] < 100 else "normal")
        st.caption("Silicon Wafer Depletion Rate")
        st.line_chart(client.wafer_history, height=200,x_label="Time (s)", y_label="Wafers in Stock")
        

    with n2:
        st.metric(label="Current Oven Temperature", value=client.oven_temp, delta="Auto-Safety at 260°C", delta_color="inverse")
        st.caption("Reflow Oven Temperature (°C)")
        st.line_chart(client.temp_history, height=200,x_label="Time (s)", y_label="Temperature (°C)")
    
with tab2:
    st.header("Factory Logs")
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("Factory Operations")
        for log in client.logistics_log:
            st.markdown(log)
            
    with c2:
        st.subheader("Financial & Business Transactions")
        for log in client.finance_log:
            st.markdown(log)
                
    with c3:
        st.subheader("Business-to-Business Communications")
        for log in client.b2b_log:
            st.markdown(log)

time.sleep(1.5)
st.rerun()