import os
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

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
