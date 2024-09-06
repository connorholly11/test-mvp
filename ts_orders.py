import requests
import json
import os
import time
import logging
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('TRADESTATION_API_KEY_SIM')
API_SECRET = os.getenv('TRADESTATION_API_SECRET_SIM')
REFRESH_TOKEN = os.getenv('TRADESTATION_REFRESH_TOKEN_SIM')
ACCOUNT_ID = os.getenv('TRADESTATION_ACCOUNT_ID_SIM')
BASE_URL = "https://sim-api.tradestation.com/v3"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

ACCESS_TOKEN = None
TOKEN_EXPIRY = 0

def get_access_token():
    global ACCESS_TOKEN, TOKEN_EXPIRY
    current_time = time.time()
    
    if ACCESS_TOKEN and current_time < TOKEN_EXPIRY:
        return ACCESS_TOKEN
    
    url = "https://signin.tradestation.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": API_KEY,
        "client_secret": API_SECRET,
        "refresh_token": REFRESH_TOKEN
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    try:
        response = requests.post(url, data=payload, headers=headers)
        response.raise_for_status()
        token_data = response.json()
        ACCESS_TOKEN = token_data['access_token']
        TOKEN_EXPIRY = current_time + token_data.get('expires_in', 1800)
        logging.info("New access token obtained")
        return ACCESS_TOKEN
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get access token: {str(e)}")
        raise

def get_headers():
    return {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }

def place_order(account_id, symbol, quantity, order_type, trade_action, **kwargs):
    url = f"{BASE_URL}/orderexecution/orders"
    headers = get_headers()
    
    payload = {
        "AccountID": account_id,
        "Symbol": symbol,
        "Quantity": str(quantity),
        "OrderType": order_type,
        "TradeAction": trade_action,
        "TimeInForce": {"Duration": "DAY"},
        "Route": "Intelligent"
    }

    if "LimitPrice" in kwargs:
        payload["LimitPrice"] = str(kwargs["LimitPrice"])
    if "StopPrice" in kwargs:
        payload["StopPrice"] = str(kwargs["StopPrice"])

    logging.info(f"Placing order: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        order_data = response.json()
        logging.info(f"Order placed successfully: {json.dumps(order_data, indent=2)}")
        
        return order_data
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to place order: {str(e)}")
        logging.error(f"Response content: {e.response.content if e.response else 'No response'}")
        raise

def get_account_balance(account_id):
    url = f"{BASE_URL}/brokerage/accounts/{account_id}/balances"
    headers = get_headers()
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        balance_data = response.json()
        if isinstance(balance_data, list) and len(balance_data) > 0:
            return balance_data[0].get('TotalTradingValue', 0)
        else:
            raise ValueError("Unexpected balance data format")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get account balance: {str(e)}")
        return 0

def get_positions(account_id):
    url = f"{BASE_URL}/brokerage/accounts/{account_id}/positions"
    headers = get_headers()
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        positions = response.json()
        return positions
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get positions: {str(e)}")
        return []

def get_account_summary(account_id):
    url = f"{BASE_URL}/brokerage/accounts/{account_id}/balances"
    headers = get_headers()
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        balance_data = response.json()
        if isinstance(balance_data, list) and len(balance_data) > 0:
            return {
                "balance": balance_data[0].get('TotalTradingValue', 0),
                "equity": balance_data[0].get('TotalEquity', 0),
                "realized_pl": balance_data[0].get('RealTimeRealizedProfitLoss', 0),
                "unrealized_pl": balance_data[0].get('RealTimeUnrealizedProfitLoss', 0),
                "daily_pl": balance_data[0].get('TodaysRealTimeRealizedProfitLoss', 0) + balance_data[0].get('TodaysRealTimeUnrealizedProfitLoss', 0)
            }
        else:
            raise ValueError("Unexpected balance data format")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get account summary: {str(e)}")
        return {}

def get_latest_quote(symbol):
    url = f"{BASE_URL}/marketdata/quotes/{symbol}"
    headers = get_headers()
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        quote_data = response.json()
        if isinstance(quote_data, list) and len(quote_data) > 0:
            return quote_data[0]
        else:
            raise ValueError("Unexpected quote data format")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get latest quote: {str(e)}")
        return {}