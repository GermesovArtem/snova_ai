import httpx
import os
import json
import logging

logger = logging.getLogger(__name__)

KIE_BASE_URL = os.getenv("KIE_BASE_URL", "https://api.kie.ai").rstrip('/').replace("/api/v1", "").replace("/v1", "")

def get_headers():
    # Remove any extra quotes or spaces from .env value
    token = os.getenv("KIE_API_KEY", "").strip(' "\'')
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

from typing import Optional, List, Any

async def create_task(model: str, prompt: str, image_urls: Optional[List[str]] = None, 
                      aspect_ratio: str = "auto", resolution: str = "1K", 
                      output_format: str = "png"):
    url = f"{KIE_BASE_URL}/api/v1/jobs/createTask"
    # KIE API expects base model name without resolution suffixes
    api_model = model.replace("-1k", "").replace("-2k", "").replace("-4k", "")
    payload: dict[str, Any] = {
        "model": api_model, 
        "input": {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "output_format": output_format
        }
    }
    if image_urls:
        # According to official Nano Banana 2 / Pro documentation:
        # 1. Field name MUST be 'image_input' (array of strings)
        # 2. It supports up to 14 images
        if "nano-banana" in model.lower():
            payload["input"]["image_input"] = image_urls
        else:
            # Fallback for legacy or other KIE models
            payload["input"]["image_url"] = image_urls[0]
            payload["input"]["image_urls"] = image_urls
            payload["input"]["image"] = image_urls[0]
            payload["input"]["input_image"] = image_urls[0]


        
    logger.info(f"Kie API createTask: payload={json.dumps(payload, ensure_ascii=False)}")
    async with httpx.AsyncClient() as client:


        try:
            resp = await client.post(url, json=payload, headers=get_headers(), timeout=10.0)
            data = resp.json()
            
            # 1. Error Handling Check: code 402 or 422
            if resp.status_code != 200 or data.get("code") not in [0, 200, 201]:
                err_msg = data.get("msg") or data.get("error") or str(data)
                logger.error(f"Kie API Error (Code {data.get('code')}): {err_msg}")
                if data.get("code") == 402:
                    return {"success": False, "error": "insufficient_funds"}
                return {"success": False, "error": err_msg}
            
            # 2. Extract TaskID
            task_data = data.get("data", {})
            if task_data and task_data.get("taskId"):
                return {"success": True, "taskId": task_data["taskId"]}
            else:
                logger.error(f"Kie API: No taskId in success response: {data}")
                return {"success": False, "error": "No taskId returned from API"}
        except Exception as e:
            logger.error(f"Kie API createTask exception: {e}")
            return {"success": False, "error": str(e)}

async def get_task_info(task_id: str):
    # Endpoint must be recordInfo, with taskId as query parameter
    url = f"{KIE_BASE_URL}/api/v1/jobs/recordInfo"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params={"taskId": task_id}, headers=get_headers(), timeout=10.0)
            data = resp.json()
            
            # Check for API-level errors (like 422 recordInfo is null)
            if data.get("code") and data.get("code") != 200:
                err_msg = data.get("msg") or "Unknown KIE error"
                logger.warning(f"Kie API recordInfo error (Task {task_id}): {err_msg}")
                return {"success": False, "state": "failed", "error": err_msg}

            # JSON Parsing Check (NoneType)
            if not data or data.get("data") is None:
                logger.warning(f"Kie API recordInfo: 'data' field is null for task {task_id}")
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
                        
            # Достаем текст ошибки, если KIE его отдает (может быть в failReason, errorMsg и тд)
            error_msg = job_data.get("failReason") or job_data.get("errorMsg") or job_data.get("error") or job_data.get("msg")
            
            return {"success": True, "state": state, "image_url": image_url, "error": error_msg}
        except Exception as e:
            logger.error(f"Kie API queryTask exception: {e}")
            return {"success": False, "state": "error", "error": str(e)}
