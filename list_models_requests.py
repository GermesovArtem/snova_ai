import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("KIE_API_KEY")
base_url = "https://api.kie.ai/v1"

try:
    resp = requests.get(f"{base_url}/models", headers={"Authorization": f"Bearer {api_key}"})
    data = resp.json()
    # Looking at the possible structure of the response
    if isinstance(data, dict) and "data" in data:
         models = [m["id"] for m in data.get("data", [])]
    else:
         print("Unexpected response structure:", data)
         models = []
         
    for m in models:
        print(f"- {m}")
except Exception as e:
    import traceback
    traceback.print_exc()
