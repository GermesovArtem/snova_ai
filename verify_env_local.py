import os
from dotenv import load_dotenv
import json

load_dotenv()

print(f"BOT_TOKEN: {os.getenv('BOT_TOKEN')[:10]}...")
print(f"AVAILABLE_MODELS: {os.getenv('AVAILABLE_MODELS')}")
print(f"CREDITS_PER_MODEL: {os.getenv('CREDITS_PER_MODEL')}")
print(f"CREDIT_PACKS: {os.getenv('CREDIT_PACKS')}")
print(f"STARTING_BALANCE: {os.getenv('STARTING_BALANCE')}")
