# Install Instructions

1) Before running the code, ensure you have the libraries detailed in requirements.txt installed

You can manually install these libraries using pip install. Do note that you can automatically install these using

``
pip install -r requirements.txt
``

2) After installing libraries, use the .env.example and check the requirements and fill them up accordingly

3) Run each Python file in separate files, starting with the hardware and finance node

4) Run the dashboard using the following command

"streamlit run pcb_dashboard.py"


# Understanding the System

## Private Network (The Factory Floor)

This is where internal telemetry and filing gets broadcasted,  we keep this private as these are senstive information

* ID
  * Factory
    * processing
      * conveyor/commands (Receives SPEED:x, HALT, RESUME, RESTOCK)
      * conveyor/status (Broadcasts RUNNING or HALTED)
      * oven/temp (Broadcasts the thermal float value (e.g., 245.5C))
    * inventory 
      * wafers (Broadcasts the raw silicon count)
    * sales
      * receipts (Broadcasts the revenue data)
       
All Private Topics
```
ID/factory/processing/conveyor/commands
ID/factory/processing/conveyor/status
ID/factory/processing/oven/temp

ID/factory/inventory/wafers
ID/factory/sales/receipts
```

## Public Network 
This public network simuates communication betwee 3rd parties and the PCB factory 
[Purpose: External B2B cross-talk and supply chain]

* public/ID/factory/supply/
  * order_alert (Topic 1) 3rd party publishes supply requesth
  * order_confirmed (Topic 2) Dashboard publishes verification handshake


All Public Tools
``
public/ID/factory/supply/order_alert
public/ID/factory/supply/order_confirmed
``


## How all files wire together

pcb_hardware.py: Strictly lives in the Private network. It listens to `processing/conveyor/commands` and publishes to the other `processing/` and `inventory/` topics.

pcb_enterprise.py: Straddles both networks. It publishes internal receipts to the **Private** `sales/` folder, but broadcasts its supply needs to the **Public** `supply/order_alert` topic.

pcb_dashboard.py: The ultimate overseer. It subscribes to **every single topic** in this list (using the `#` wildcard) so it can render the UI, and it actively publishes the handshake back to the **Public** `supply/order_confirmed` topic.
