import os
from pathlib import Path
from dotenv import load_dotenv
import certifi
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ.get('MONGO_URL') or os.environ.get('MONGODB_URI')
db_name = os.environ.get('DB_NAME', 'syncoop')

if not mongo_url:
    raise RuntimeError(
        "MongoDB connection is not configured. Set MONGO_URL in backend/.env "
        "to your MongoDB Atlas URI or local MongoDB URI."
    )

client_options = {
    "serverSelectionTimeoutMS": 10000,
}

if mongo_url.startswith("mongodb+srv://"):
    client_options["tlsCAFile"] = certifi.where()

client = AsyncIOMotorClient(mongo_url, **client_options)
db = client[db_name]

# Collections
users = db.users
sessions = db.user_sessions
vessels = db.vessels
transactions = db.transactions
fish_prices = db.fish_prices
fish_calcs = db.fish_calcs
fish_sales = db.fish_sales
notifications = db.notifications
settings = db.settings
savings_entries = db.savings_entries
loans = db.loans
loan_payments = db.loan_payments
inventory_items = db.inventory_items
inventory_movements = db.inventory_movements
service_tickets = db.service_tickets
ticket_messages = db.ticket_messages
announcements = db.announcements
