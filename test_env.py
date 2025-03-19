# test_env.py
from dotenv import load_dotenv
import os

load_dotenv()  # Loads .env from the current directory
print("DB_HOST =", os.getenv("DB_HOST"))
