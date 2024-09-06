import requests
import os
from dotenv import load_dotenv
import logging

load_dotenv()

API_KEY = os.getenv('TRADESTATION_API_KEY_SIM')
API_SECRET = os.getenv('TRADESTATION_API_SECRET_SIM')
REDIRECT_URI = os.getenv('TRADESTATION_REDIRECT_URI')
ACCESS_TOKEN = os.getenv('TRADESTATION_ACCESS_TOKEN')

BASE_URL = "https://sim-api.tradestation.com/v2"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_headers():
    return {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

def place_order(account_id, symbol, action, quantity):
    url = f"{BASE_URL}/accounts/{account_id}/orders"
    headers = get_headers()
    
    payload = {
        "AccountID": account_id,
        "Symbol": symbol,
        "Quantity": quantity,
        "OrderType": "Market",
        "TradeAction": action.upper(),
        "TimeInForce": "DAY"
    }
    
    logging.info(f"Placing order: {payload}")
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        order_data = response.json()
        logging.info(f"Order placed successfully: {order_data}")
        
        if 'Orders' in order_data and len(order_data['Orders']) > 0:
            order_id = order_data['Orders'][0].get('OrderID')
            if order_id:
                return check_order_status(account_id, order_id)
            else:
                return {"status": "Error", "message": "Order ID not found in response"}
        else:
            return {"status": "Error", "message": "Unexpected response format"}
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {str(e)}")
        return {"status": "Error", "message": f"Request failed: {str(e)}"}

def check_order_status(account_id, order_id):
    url = f"{BASE_URL}/accounts/{account_id}/orders/{order_id}"
    headers = get_headers()
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        order_data = response.json()
        logging.info(f"Order status: {order_data}")
        
        return {
            "status": order_data.get('Status'),
            "order_id": order_id,
            "fill_price": order_data.get('FilledPrice'),
            "filled_quantity": order_data.get('FilledQuantity')
        }
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to check order status: {str(e)}")
        return {"status": "Error", "message": f"Failed to check order status: {str(e)}"}

def get_positions(account_id):
    url = f"{BASE_URL}/accounts/{account_id}/positions"
    headers = get_headers()
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        positions = response.json()
        return [{
            "symbol": pos['Symbol'],
            "quantity": pos['Quantity'],
            "average_price": pos['AveragePrice']
        } for pos in positions]
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get positions: {str(e)}")
        return []

def get_account_balance(account_id):
    url = f"{BASE_URL}/accounts/{account_id}/balances"
    headers = get_headers()
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        balance_data = response.json()
        return balance_data.get('CashBalance', 0)
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get account balance: {str(e)}")
        return 0

def get_account_summary(account_id):
    url = f"{BASE_URL}/accounts/{account_id}"
    headers = get_headers()
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        account_data = response.json()
        return {
            'balance': account_data.get('CashBalance', 0),
            'equity': account_data.get('Equity', 0),
            'buying_power': account_data.get('BuyingPower', 0),
            'unrealized_pl': account_data.get('UnrealizedProfitLoss', 0),
            'realized_pl': account_data.get('RealizedProfitLoss', 0),
        }
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get account summary: {str(e)}")
        return {}