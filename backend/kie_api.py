import httpx
import os
import json
import logging

logger = logging.getLogger(__name__)

KIE_BASE_URL = os.getenv("KIE_BASE_URL", "https://api.kie.ai").rstrip('/')

def get_headers():
    # Remove any extra quotes or spaces from .env value
    token = os.getenv("KIE_API_KEY", "").strip(' "\'')
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

from typing import Optional, List, Any

async def create_task(model: str, prompt: str, image_urls: Optional[List[str]] = None):
    url = f"{KIE_BASE_URL}/api/v1/jobs/createTask"
    payload: dict[str, Any] = {
        "model": model, 
        "input": {
            "prompt": prompt,
            "aspect_ratio": "1:1"
        }
    }
    if image_urls:
        payload["input"]["image_urls"] = image_urls
        payload["input"]["image_url"] = image_urls[0]
        payload["input"]["image"] = image_urls[0]

        
    logger.info(f"Kie API createTask: model={model}, prompt='{prompt[:50]}...', payload={json.dumps(payload)}")
    async with httpx.AsyncClient() as client:

        try:
            resp = await client.post(url, json=payload, headers=get_headers(), timeout=10.0)
            data = resp.json()
            
            # 1. Error Handling Check: code 402
            if resp.status_code == 402 or data.get("code") == 402:
                logger.error("Kie.ai Error: Credits insufficient (402)")
                return {"success": False, "error": "insufficient_funds"}
            
            # 2. Extract TaskID
            task_data = data.get("data", {})
            if task_data and task_data.get("taskId"):
                return {"success": True, "taskId": task_data["taskId"]}
            else:
                return {"success": False, "error": str(data)}
        except Exception as e:
            logger.error(f"Kie API createTask error: {e}")
            return {"success": False, "error": str(e)}

async def get_task_info(task_id: str):
    # Endpoint must be recordInfo, with taskId as query parameter
    url = f"{KIE_BASE_URL}/api/v1/jobs/recordInfo"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params={"taskId": task_id}, headers=get_headers(), timeout=10.0)
            data = resp.json()
            
            # JSON Parsing Check (NoneType)
            if not data or data.get("data") is None:
                return {"success": False, "state": "failed", "error": "No data in response"}
            
            job_data = data["data"]
            # Different status fields
            state = job_data.get("state") or job_data.get("status") or job_data.get("task_status")
            if state:
                state = str(state).lower()
            
            # Finding result URL
            image_url = None
            if state in ["success", "completed"]:
                if "url" in job_data:
                    image_url = job_data["url"]
                elif "resultJson" in job_data:
                    try:
                        res_json = json.loads(job_data["resultJson"])
                        urls = res_json.get("resultUrls", [])
                        if urls:
                            image_url = urls[0]
                    except json.JSONDecodeError:
                        pass
                        
            return {"success": True, "state": state, "image_url": image_url}
        except Exception as e:
            logger.error(f"Kie API queryTask error: {e}")
            return {"success": False, "state": "error", "error": str(e)}
