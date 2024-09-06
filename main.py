from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import ts_orders
import ts_connection
import json
import logging
import traceback
from functools import wraps
from datetime import timedelta
from ts_connection import start_streaming, get_latest_data


# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', 
                    handlers=[logging.StreamHandler()])

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)  # Set session lifetime to 8 hours

supabase: Client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_ANON_KEY'))

# Start the market data streaming
ts_connection.start_streaming()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            logging.warning("Unauthenticated access attempt")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def api_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            logging.warning(f"Unauthenticated API access attempt. Session: {session}")
            return jsonify({'error': 'Not authenticated', 'redirect': url_for('login')}), 401
        logging.info(f"Authenticated API access. User ID: {session['user_id']}")
        return f(*args, **kwargs)
    return decorated_function

@app.route('/register', methods=['GET', 'POST'])
def register():
    logging.info("Register route accessed")
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        logging.info(f"Registration attempt for username: {username}")
        
        try:
            existing_user = supabase.table('users').select('*').eq('username', username).execute()
            if existing_user.data:
                logging.warning(f"Registration failed: Username {username} already exists")
                flash('Username already exists. Please choose a different one.')
                return redirect(url_for('register'))

            new_user = supabase.table('users').insert({
                'username': username,
                'password': password,
                'balance': 100000.0
            }).execute()
            logging.info(f"New user registered: {username}")

            flash('Registered successfully. Please log in.')
            return redirect(url_for('login'))
        except Exception as e:
            logging.error(f"Registration failed: {str(e)}")
            flash(f'Registration failed: {str(e)}')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    logging.info("Login route accessed")
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        logging.info(f"Login attempt for username: {username}")
        
        try:
            user = supabase.table('users').select('*').eq('username', username).eq('password', password).execute()
            if user.data:
                session.permanent = True
                session['user_id'] = user.data[0]['id']
                logging.info(f"User logged in: {username}")
                flash('Logged in successfully.')
                return redirect(url_for('trading'))
            else:
                logging.warning(f"Login failed: Invalid credentials for username {username}")
                flash('Invalid username or password')
        except Exception as e:
            logging.error(f"Login failed: {str(e)}")
            flash(f'Login failed: {str(e)}')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    logging.info(f"User logged out: {session.get('user_id')}")
    session.clear()
    flash('Logged out successfully.')
    return redirect(url_for('login'))

@app.route('/')
@app.route('/trading')
@login_required
def trading():
    logging.info(f"Trading page accessed by user {session['user_id']}")
    user = supabase.table('users').select('username').eq('id', session['user_id']).execute()
    username = user.data[0]['username'] if user.data else 'Trader'
    logging.info(f"User {username} accessed trading page")
    return render_template('trading.html', username=username)

@app.route('/api/market_data')
@api_login_required
def get_market_data():
    latest_data = get_latest_data()
    logging.info(f"Market data request: {latest_data}")
    return jsonify(latest_data)

@app.route('/api/account_summary')
@api_login_required
def get_account_summary():
    logging.info(f"Fetching account summary for user {session['user_id']}")
    try:
        account_id = os.getenv('TRADESTATION_ACCOUNT_ID_SIM')
        account_summary = ts_orders.get_account_summary(account_id)
        logging.info(f"Account summary for user {session['user_id']}: {account_summary}")
        return jsonify(account_summary)
    except Exception as e:
        logging.error(f"Error fetching account summary: {str(e)}")
        return jsonify({'error': 'Unable to fetch account summary at this time'}), 500

@app.route('/api/positions')
@api_login_required
def get_positions():
    logging.info(f"Fetching positions for user {session['user_id']}")
    try:
        account_id = os.getenv('TRADESTATION_ACCOUNT_ID_SIM')
        positions = ts_orders.get_positions(account_id)
        latest_data = ts_connection.get_latest_data()
        
        position_data = []
        for position in positions:
            current_price = float(latest_data.get('Close', 0))
            unrealized_pl = (current_price - position['AveragePrice']) * position['Quantity']
            
            position_data.append({
                'symbol': position['Symbol'],
                'quantity': position['Quantity'],
                'average_price': position['AveragePrice'],
                'current_value': current_price * abs(position['Quantity']),
                'unrealized_pl': unrealized_pl
            })
        
        logging.info(f"Positions data for user {session['user_id']}: {position_data}")
        return jsonify({'positions': position_data})
    except Exception as e:
        logging.error(f"Error fetching positions: {str(e)}")
        return jsonify({'error': 'Unable to fetch positions at this time'}), 500

@app.route('/api/trade', methods=['POST'])
@api_login_required
def place_trade():
    data = request.json
    logging.info(f"Trade request received: {data}")
    
    action = data.get('action')
    quantity = data.get('quantity')
    symbol = data.get('symbol', 'NQU24')  # Changed from '@NQU24' to 'NQU24'
    account_id = os.getenv('TRADESTATION_ACCOUNT_ID_SIM')
    
    if not all([action, quantity, symbol, account_id]):
        logging.error(f"Invalid trade request: Missing required fields. Data: {data}")
        return jsonify({'success': False, 'message': 'Invalid trade request: Missing required fields'}), 400
    
    try:
        quantity = int(quantity)
    except ValueError:
        logging.error(f"Invalid quantity: {quantity}. Must be an integer.")
        return jsonify({'success': False, 'message': 'Invalid quantity: Must be an integer'}), 400
    
    trade_action = action.upper()
    
    logging.info(f"Placing trade: User {session['user_id']} - {trade_action} {quantity} {symbol}")
    
    try:
        order_result = ts_orders.place_order(
            account_id=account_id,
            symbol=symbol,
            quantity=quantity,
            order_type="Market",
            trade_action=trade_action
        )
        logging.info(f"Order result: {order_result}")
        
        if 'Orders' in order_result and len(order_result['Orders']) > 0:
            if order_result['Orders'][0].get('Status') == 'OK':
                return jsonify({
                    'success': True,
                    'message': f"{action.capitalize()} order for {quantity} {symbol} placed successfully.",
                    'order_details': order_result['Orders'][0]
                })
            else:
                error_message = order_result['Orders'][0].get('Message', 'Unknown error occurred')
                return jsonify({'success': False, 'message': f'Failed to place order: {error_message}'}), 400
        else:
            logging.error(f"Unexpected order result: {order_result}")
            return jsonify({'success': False, 'message': f'Failed to place order: Unexpected response'}), 500
    except Exception as e:
        logging.error(f"Error placing order: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({'success': False, 'message': f'Failed to place order: {str(e)}'}), 500

@app.route('/api/reset/<username>', methods=['GET', 'POST'])
@api_login_required
def reset_user(username):
    logging.info(f"Reset request for user: {username}")
    try:
        # Check if the user exists
        user = supabase.table('users').select('*').eq('username', username).execute()
        if not user.data:
            logging.warning(f"Reset attempted for non-existent user: {username}")
            return jsonify({'success': False, 'message': 'User not found'}), 404

        user_id = user.data[0]['id']

        # Reset user balance in Supabase
        supabase.table('users').update({'balance': 100000.0}).eq('id', user_id).execute()
        logging.info(f"Balance reset for user {username} in Supabase")
        
        # Note: We can't reset the TradeStation account balance directly
        # You might want to add a note here about manually resetting the TradeStation sim account if needed
        
        logging.info(f"User data reset successfully for user {username}")
        return jsonify({'success': True, 'message': f'User data reset successfully for {username} in Supabase. TradeStation account may need manual reset.'})
    except Exception as e:
        logging.error(f"Failed to reset user data for {username}: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to reset user data'}), 500

if __name__ == '__main__':
    app.run(debug=True)