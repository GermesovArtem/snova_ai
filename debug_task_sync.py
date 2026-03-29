import os
import httpx
import json
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("KIE_API_KEY")
task_id = "16fb0c4a86ffe717f0533fbed05ed42b"
base_url = "https://api.kie.ai/api/v1/jobs/recordInfo"

headers = {"Authorization": f"Bearer {api_key}"}
params = {"taskId": task_id}

def check():
    with httpx.Client() as client:
        try:
            resp = client.get(base_url, params=params, headers=headers)
            print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    check()
