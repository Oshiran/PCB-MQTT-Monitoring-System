1) Before running the code, ensure you have the libraries detailed in requirements.txt installed

You can manually install these libraries using pip install, however do note that you can automatically install these using

"pip install -r requirements.txt"

2) After installing libraries, use the .env.example and check the requuiremnts and fill them up accordingly

3) Run each python file in seperate files, startting with the hardware and finance node

4) Run the dashboard using the following command

"streamlit run pcb_dashboard.py"


Understanding the System

PRIVATE OT NETWORK (The Factory Floor)
---------------------------------------------------------
[Purpose: Internal mechatronics, sensors, and internal ERP]

ID/
  └── factory/
      ├── processing/
      │   ├── conveyor/commands   -> Receives SPEED:x, HALT, RESUME, RESTOCK
      │   ├── conveyor/status     -> Broadcasts RUNNING or HALTED
      │   └── oven/temp           -> Broadcasts the thermal float value (e.g., 245.5C)
      │
      ├── inventory/
      │   └── wafers              -> Broadcasts the raw silicon count
      │
      └── sales/
          └── receipts            -> Broadcasts the revenue data

Private

ID/factory/processing/conveyor/commands
ID/factory/processing/conveyor/status
ID/factory/processing/oven/temp

ID/factory/inventory/wafers
ID/factory/sales/receipts


PUBLIC IT NETWORK (The B2B Gateway)
---------------------------------------------------------
[Purpose: External B2B cross-talk and supply chain]

public/
  └── ID/
      └── factory/
          └── supply/
              ├── order_alert     -> (Topic 1) 3rd party publishes supply request
              └── order_confirmed -> (Topic 2) Dashboard publishes verification handshake

Public

public/ID/factory/supply/order_alert
public/ID/factory/supply/order_confirmed



How They Wire Together

pcb_hardware.py: Strictly lives in the Private network. It listens to `processing/conveyor/commands` and publishes to the other `processing/` and `inventory/` topics.

pcb_enterprise.py: Straddles both networks. It publishes internal receipts to the **Private** `sales/` folder, but broadcasts its supply needs to the **Public** `supply/order_alert` topic.

pcb_dashboard.py: The ultimate overseer. It subscribes to **every single topic** in this list (using the `#` wildcard) so it can render the UI, and it actively publishes the handshake back to the **Public** `supply/order_confirmed` topic.