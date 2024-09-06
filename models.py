from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

supabase: Client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_ANON_KEY'))

def create_tables():
    # Create users table
    supabase.table('users').create({
        'id': {'type': 'uuid', 'primaryKey': True},
        'username': {'type': 'text', 'unique': True},
        'email': {'type': 'text', 'unique': True},
        'balance': {'type': 'float', 'default': 100000.0}
    })

    # Create positions table
    supabase.table('positions').create({
        'id': {'type': 'uuid', 'primaryKey': True},
        'user_id': {'type': 'uuid', 'foreignKey': 'users.id'},
        'symbol': {'type': 'text'},
        'quantity': {'type': 'integer'},
        'average_price': {'type': 'float'}
    })

    # Create transactions table
    supabase.table('transactions').create({
        'id': {'type': 'uuid', 'primaryKey': True},
        'user_id': {'type': 'uuid', 'foreignKey': 'users.id'},
        'action': {'type': 'text'},
        'symbol': {'type': 'text'},
        'quantity': {'type': 'integer'},
        'price': {'type': 'float'},
        'timestamp': {'type': 'timestamp', 'default': {'type': 'now'}}
    })

if __name__ == "__main__":
    create_tables()
    print("Tables created successfully")