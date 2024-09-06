import os
import time
import json
from datetime import datetime
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Update these paths to the correct NinjaTrader 8 folders
NT_INCOMING_FOLDER = r"C:\Users\connor holly\OneDrive\Documents\NinjaTrader 8\incoming"
NT_OUTGOING_FOLDER = r"C:\Users\connor holly\OneDrive\Documents\NinjaTrader 8\outgoing"
ACCOUNT_NAME = "Sim100"
SYMBOL = "NQ 09-24"  # Updated to match NinjaTrader's format

# In-memory position storage
current_position = {'quantity': 0, 'average_price': 0}

def generate_order_id():
    return int(time.time() * 1000)

def place_order(action, quantity):
    order_id = generate_order_id()
    
    # Reverse the action for NinjaTrader
    nt_action = "SELL" if action.upper() == "BUY" else "BUY"
    
    order_text = f"PLACE;{ACCOUNT_NAME};{SYMBOL};{nt_action};{quantity};MARKET;;;DAY;;{order_id};;"
    
    file_name = f"oif{order_id}.txt"
    file_path = os.path.join(NT_INCOMING_FOLDER, file_name)
    
    try:
        with open(file_path, 'w') as file:
            file.write(order_text)
        logging.info(f"Order placed: {file_name}")
        logging.info(f"Order details: {order_text}")
        return order_id
    except Exception as e:
        logging.error(f"Error placing order: {e}")
        return None

def verify_path():
    if not os.path.exists(NT_INCOMING_FOLDER):
        logging.warning(f"The specified NinjaTrader incoming folder does not exist: {NT_INCOMING_FOLDER}")
        return False
    if not os.path.exists(NT_OUTGOING_FOLDER):
        logging.warning(f"The specified NinjaTrader outgoing folder does not exist: {NT_OUTGOING_FOLDER}")
        return False
    return True

class NinjaTraderHandler(FileSystemEventHandler):
    def __init__(self):
        self.processed_files = set()

    def on_created(self, event):
        if event.is_directory:
            return
        self.process_file(event.src_path)

    def on_modified(self, event):
        if event.is_directory:
            return
        self.process_file(event.src_path)

    def process_file(self, file_path):
        if not file_path.endswith('.txt'):
            return
        
        file_name = os.path.basename(file_path)
        if not file_name.startswith(f"{ACCOUNT_NAME}_"):
            logging.debug(f"Skipping file: {file_name} (doesn't start with {ACCOUNT_NAME}_)")
            return
        
        if file_path in self.processed_files:
            logging.debug(f"Skipping already processed file: {file_name}")
            return

        logging.info(f"Processing file: {file_path}")
        try:
            with open(file_path, 'r') as file:
                content = file.read().strip()
                logging.info(f"File content: {content}")
                data_parts = content.split(';')
                if data_parts[0] == "FILLED":
                    self.update_position(data_parts)
                    self.processed_files.add(file_path)
                elif data_parts[0] == "REJECTED":
                    logging.error(f"Order rejected: {content}")
                    self.processed_files.add(file_path)
                else:
                    logging.info(f"Order status: {data_parts[0]}")
        except Exception as e:
            logging.error(f"Error processing file {file_path}: {str(e)}")

    def update_position(self, data_parts):
        global current_position
        if len(data_parts) != 3:
            logging.error(f"Unexpected data format: {data_parts}")
            return

        status, quantity, price = data_parts
        quantity = int(quantity)
        price = float(price)
        
        logging.info(f"Updating position: FILLED {quantity} at {price}")
        
        old_quantity = current_position['quantity']
        old_average_price = current_position['average_price']

        # NinjaTrader's perspective is reversed from our application's perspective
        app_quantity = -quantity

        new_quantity = old_quantity + app_quantity
        
        if new_quantity != 0:
            new_average_price = (old_average_price * old_quantity + price * abs(app_quantity)) / abs(new_quantity)
        else:
            new_average_price = 0
        
        current_position['quantity'] = new_quantity
        current_position['average_price'] = new_average_price
        
        logging.info(f"Position updated: {current_position}")

def start_monitoring():
    logging.info(f"Starting to monitor folder: {NT_OUTGOING_FOLDER}")
    event_handler = NinjaTraderHandler()
    observer = Observer()
    observer.schedule(event_handler, path=NT_OUTGOING_FOLDER, recursive=False)
    observer.start()
    return observer, event_handler

# Initialize monitoring
if verify_path():
    observer, handler = start_monitoring()
else:
    observer, handler = None, None
    logging.error("Failed to start monitoring due to invalid paths.")

def get_current_position():
    global current_position
    return current_position

def reset_position():
    global current_position
    current_position = {'quantity': 0, 'average_price': 0}
    logging.info("Position reset to zero")