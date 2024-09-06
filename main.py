from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import ts_connection
import nt_connection
import json
import logging
import time
from functools import wraps
from datetime import timedelta

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', 
                    handlers=[logging.StreamHandler()])

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)  # Set session lifetime to 8 hours

supabase: Client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_ANON_KEY'))

# Start the TradeStation data streaming
ts_connection.start_streaming()

# Start NinjaTrader monitoring
nt_connection.start_monitoring()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            logging.warning("Unauthenticated access attempt")
            return jsonify({'error': 'Not authenticated'}), 401
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
    session.pop('user_id', None)
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

@app.route('/api/balance')
@login_required
def get_balance():
    logging.info(f"Balance request for user {session['user_id']}")
    user = supabase.table('users').select('balance').eq('id', session['user_id']).execute()
    balance = user.data[0]['balance'] if user.data else 0
    logging.info(f"Balance for user {session['user_id']}: {balance}")
    return jsonify({'balance': balance})

@app.route('/api/positions')
@login_required
def get_positions():
    logging.info(f"Fetching positions for user {session['user_id']}")
    try:
        position = nt_connection.get_current_position()
        logging.info(f"Retrieved position: {position}")
        
        latest_data = ts_connection.get_latest_data()
        logging.info(f"Latest market data: {latest_data}")
        
        current_price = float(latest_data.get('Close', 0))
        logging.info(f"Current price: {current_price}")
        
        unrealized_pl = (current_price - position['average_price']) * position['quantity']
        logging.info(f"Calculated unrealized P/L: {unrealized_pl}")
        
        position_data = {
            'symbol': nt_connection.SYMBOL,
            'quantity': position['quantity'],
            'average_price': position['average_price'],
            'current_value': current_price * abs(position['quantity']),
            'unrealized_pl': unrealized_pl
        }
        
        logging.info(f"Final position data: {position_data}")
        return jsonify({'positions': [position_data] if position_data['quantity'] != 0 else []})
    except Exception as e:
        logging.error(f"Error fetching positions: {str(e)}")
        return jsonify({'error': 'Unable to fetch positions at this time'}), 500

@app.route('/api/trade', methods=['POST'])
@login_required
def place_trade():
    data = request.json
    logging.info(f"Trade request received: {data}")
    
    action = data['action']
    quantity = int(data['quantity'])
    
    logging.info(f"Trade request: User {session['user_id']} - {action} {quantity} contracts")
    
    order_result = nt_connection.place_order(action, quantity)
    
    if order_result['status'] == 'FILLED':
        logging.info(f"Order filled: {order_result}")
        
        # Update the position
        current_position = nt_connection.update_position(action, quantity, order_result['fill_price'])
        logging.info(f"Updated position after trade: {current_position}")
        
        return jsonify({
            'success': True, 
            'message': f'{action.capitalize()} order for {quantity} contracts filled at {order_result["fill_price"]}.', 
            'current_position': current_position
        })
    elif order_result['status'] == 'PLACED':
        logging.info(f"Order placed: {order_result}")
        return jsonify({
            'success': True, 
            'message': f'{action.capitalize()} order for {quantity} contracts placed. Order ID: {order_result["order_id"]}',
        })
    else:
        logging.error(f"Failed to place order: {order_result}")
        return jsonify({'success': False, 'message': 'Failed to place order'})

@app.route('/api/market_data')
@login_required
def get_market_data():
    market_data = ts_connection.get_latest_data()
    logging.info(f"Market data request: {market_data}")
    return jsonify(market_data)

@app.route('/api/account_summary')
@login_required
def get_account_summary():
    logging.info(f"Fetching account summary for user {session['user_id']}")
    try:
        user = supabase.table('users').select('balance').eq('id', session['user_id']).execute().data[0]
        balance = user['balance']
        
        position = nt_connection.get_current_position()
        latest_data = ts_connection.get_latest_data()
        current_price = float(latest_data.get('Close', 0))
        
        unrealized_pl = (current_price - position['average_price']) * position['quantity']
        equity = balance + unrealized_pl
        
        account_summary = {
            'balance': balance,
            'equity': equity,
            'unrealized_pl': unrealized_pl,
            'realized_pl': 0,  # Placeholder
            'daily_pl': 0  # Placeholder
        }
        
        logging.info(f"Account summary for user {session['user_id']}: {account_summary}")
        return jsonify(account_summary)
    except Exception as e:
        logging.error(f"Error fetching account summary: {str(e)}")
        return jsonify({'error': 'Unable to fetch account summary at this time'}), 500

@app.route('/api/reset/<username>', methods=['GET', 'POST'])
@login_required
def reset_user(username):
    logging.info(f"Reset request for user: {username}")
    try:
        # Check if the user exists
        user = supabase.table('users').select('*').eq('username', username).execute()
        if not user.data:
            logging.warning(f"Reset attempted for non-existent user: {username}")
            return jsonify({'success': False, 'message': 'User not found'}), 404

        user_id = user.data[0]['id']

        # Reset user balance
        supabase.table('users').update({'balance': 100000.0}).eq('id', user_id).execute()
        logging.info(f"Balance reset for user {username}")
        
        # Reset position
        nt_connection.reset_position()
        logging.info(f"Position reset for user {username}")
        
        logging.info(f"User data reset successfully for user {username}")
        return jsonify({'success': True, 'message': f'User data reset successfully for {username}'})
    except Exception as e:
        logging.error(f"Failed to reset user data for {username}: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to reset user data'}), 500

if __name__ == '__main__':
    app.run(debug=True)