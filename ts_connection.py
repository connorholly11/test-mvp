import requests
import json
import os
import time
import threading
from dotenv import load_dotenv
import logging

load_dotenv()

# Set up logging to file
logging.basicConfig(filename='ts_connection.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# TradeStation API credentials
API_KEY = os.getenv('TRADESTATION_API_KEY_SIM')
API_SECRET = os.getenv('TRADESTATION_API_SECRET_SIM')
REFRESH_TOKEN = os.getenv('TRADESTATION_REFRESH_TOKEN_SIM')
BASE_URL = "https://sim-api.tradestation.com"

SYMBOL = '@MNQ'  # Fixed symbol for Micro E-mini Nasdaq-100 futures

# Global variable to store the latest data
latest_data = {}

def get_access_token():
    url = "https://signin.tradestation.com/oauth/token"
    payload = f'grant_type=refresh_token&client_id={API_KEY}&client_secret={API_SECRET}&refresh_token={REFRESH_TOKEN}'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(url, headers=headers, data=payload)
    response_data = response.json()
    if 'access_token' in response_data:
        return response_data['access_token']
    else:
        raise Exception(f"Error obtaining access token: {response_data}")

def stream_data(access_token):
    global latest_data
    url = f"{BASE_URL}/v3/marketdata/stream/barcharts/{SYMBOL}?interval=1&unit=Minute"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    with requests.get(url, headers=headers, stream=True) as response:
        if response.status_code != 200:
            latest_data = {"error": f"Stream request failed: {response.status_code} - {response.text}"}
            logging.error(f"Error: {latest_data['error']}")
            return

        buffer = ""
        for chunk in response.iter_content(chunk_size=1):
            if chunk:
                buffer += chunk.decode('utf-8')
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    try:
                        data = json.loads(line)
                        latest_data = data
                        logging.info(f"Received new data: {json.dumps(data, indent=2)}")
                    except json.JSONDecodeError:
                        logging.error(f"Error: Invalid JSON: {line}")

def run_stream():
    while True:
        try:
            access_token = get_access_token()
            stream_data(access_token)
        except Exception as e:
            logging.error(f"Error in run_stream: {str(e)}")
            time.sleep(5)  # Wait for 5 seconds before retrying

def start_streaming():
    threading.Thread(target=run_stream, daemon=True).start()

def get_latest_data():
    return latest_data