import os
import httpx
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("KIE_API_KEY")
base_url = "https://api.kie.ai/v1"

try:
    with httpx.Client() as client:
        resp = client.get(f"{base_url}/models", headers={"Authorization": f"Bearer {api_key}"})
        data = resp.json()
        models = [m["id"] for m in data.get("data", [])]
        for m in models:
            print(f"- {m}")
except Exception as e:
    import traceback
    traceback.print_exc()
