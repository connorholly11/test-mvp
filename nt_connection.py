import os
import time
import json
from datetime import datetime
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', 
                    handlers=[logging.StreamHandler()])

# Update these paths to the correct NinjaTrader 8 folders
NT_INCOMING_FOLDER = r"C:\Users\connor holly\OneDrive\Documents\NinjaTrader 8\incoming"
NT_OUTGOING_FOLDER = r"C:\Users\connor holly\OneDrive\Documents\NinjaTrader 8\outgoing"
ACCOUNT_NAME = "Sim100"
SYMBOL = "NQ 09-24"  # Updated to match NinjaTrader's format

POSITION_FILE = 'current_position.json'

def generate_order_id():
    return int(time.time() * 1000)

def place_order(action, quantity):
    order_id = generate_order_id()
    
    # Reverse the action for NinjaTrader
    nt_action = "SELL" if action.upper() == "BUY" else "BUY"
    
    order_text = f"PLACE;{ACCOUNT_NAME};{SYMBOL};{nt_action};{quantity};MARKET;;;DAY;;{order_id};;"
    
    file_name = f"oif{order_id}.txt"
    file_path = os.path.join(NT_INCOMING_FOLDER, file_name)
    
    logging.info(f"Attempting to place order: {order_text}")
    try:
        with open(file_path, 'w') as file:
            file.write(order_text)
        logging.info(f"Order placed successfully: {file_name}")
        
        # Wait for the order to be filled (you might need to adjust the timeout)
        timeout = 10
        start_time = time.time()
        while time.time() - start_time < timeout:
            filled_order = check_for_filled_order(order_id)
            if filled_order:
                logging.info(f"Order filled: {filled_order}")
                return filled_order
            time.sleep(0.5)
        
        logging.warning(f"Order not filled within timeout period: {order_id}")
        return {'status': 'PLACED', 'order_id': order_id}
    except Exception as e:
        logging.error(f"Error placing order: {e}")
        return {'status': 'ERROR', 'message': str(e)}

def check_for_filled_order(order_id):
    for filename in os.listdir(NT_OUTGOING_FOLDER):
        if filename.startswith(f"{ACCOUNT_NAME}_") and filename.endswith('.txt'):
            file_path = os.path.join(NT_OUTGOING_FOLDER, filename)
            with open(file_path, 'r') as file:
                content = file.read().strip()
                data_parts = content.split(';')
                if data_parts[0] == "FILLED" and int(data_parts[-1]) == order_id:
                    return {
                        'status': 'FILLED',
                        'order_id': order_id,
                        'fill_price': float(data_parts[2]),
                        'filled_quantity': int(data_parts[1]),
                        'filled_action': "BUY" if data_parts[3] == "SELL" else "SELL"  # Invert the action
                    }
    return None

def update_position(action, quantity, fill_price):
    position = get_current_position()
    
    if action.upper() == 'BUY':
        new_quantity = position['quantity'] + quantity
        new_total_value = (position['quantity'] * position['average_price']) + (quantity * fill_price)
        new_average_price = new_total_value / new_quantity if new_quantity != 0 else 0
    else:  # SELL
        new_quantity = position['quantity'] - quantity
        if new_quantity > 0:
            # Maintain average price if still long
            new_average_price = position['average_price']
        elif new_quantity < 0:
            # Reset average price if going short
            new_average_price = fill_price
        else:
            # Reset average price to 0 if flat
            new_average_price = 0
    
    new_position = {'quantity': new_quantity, 'average_price': new_average_price}
    save_position(new_position)
    return new_position

def get_current_position():
    if os.path.exists(POSITION_FILE):
        with open(POSITION_FILE, 'r') as file:
            return json.load(file)
    return {'quantity': 0, 'average_price': 0}

def save_position(position):
    with open(POSITION_FILE, 'w') as file:
        json.dump(position, file)

def reset_position():
    save_position({'quantity': 0, 'average_price': 0})
    logging.info("Position reset to zero")

class NinjaTraderHandler(FileSystemEventHandler):
    def __init__(self):
        self.processed_files = set()

    def on_created(self, event):
        if event.is_directory:
            return
        logging.info(f"New file created: {event.src_path}")
        self.process_file(event.src_path)

    def on_modified(self, event):
        if event.is_directory:
            return
        logging.info(f"File modified: {event.src_path}")
        self.process_file(event.src_path)

    def process_file(self, file_path):
        if not file_path.endswith('.txt'):
            logging.debug(f"Ignoring non-txt file: {file_path}")
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
                    logging.info(f"Order FILLED: {content}")
                    self.update_position_from_fill(data_parts)
                    self.processed_files.add(file_path)
                elif data_parts[0] == "REJECTED":
                    logging.error(f"Order REJECTED: {content}")
                    self.processed_files.add(file_path)
                else:
                    logging.info(f"Order status: {data_parts[0]}")
        except Exception as e:
            logging.error(f"Error processing file {file_path}: {str(e)}")

    def update_position_from_fill(self, data_parts):
        if len(data_parts) < 4:
            logging.error(f"Unexpected data format: {data_parts}")
            return

        quantity = int(data_parts[1])
        price = float(data_parts[2])
        action = "BUY" if data_parts[3] == "SELL" else "SELL"  # Invert the action
        
        logging.info(f"Updating position from fill: {action} {quantity} at {price}")
        
        update_position(action, quantity, price)

def start_monitoring():
    logging.info(f"Starting to monitor folder: {NT_OUTGOING_FOLDER}")
    event_handler = NinjaTraderHandler()
    observer = Observer()
    observer.schedule(event_handler, path=NT_OUTGOING_FOLDER, recursive=False)
    observer.start()
    return observer, event_handler

def verify_path():
    logging.info("Verifying NinjaTrader folder paths")
    if not os.path.exists(NT_INCOMING_FOLDER):
        logging.warning(f"The specified NinjaTrader incoming folder does not exist: {NT_INCOMING_FOLDER}")
        return False
    if not os.path.exists(NT_OUTGOING_FOLDER):
        logging.warning(f"The specified NinjaTrader outgoing folder does not exist: {NT_OUTGOING_FOLDER}")
        return False
    logging.info("NinjaTrader folder paths verified successfully")
    return True

# Initialize monitoring
if verify_path():
    observer, handler = start_monitoring()
else:
    observer, handler = None, None
    logging.error("Failed to start monitoring due to invalid paths.")

# Ensure position file exists
if not os.path.exists(POSITION_FILE):
    reset_position()

