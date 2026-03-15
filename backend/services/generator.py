import aiohttp
import asyncio
from backend.settings import settings

KIE_AI_URL = "https://api.kie.ai/v1/images/generations"

async def generate_image(prompt: str, model: str = "nano-banana") -> str:
    """
    Генерирует изображение через Kie.ai API и возвращает URL
    """
    headers = {
        "Authorization": f"Bearer {settings.kie_api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024" # Стандартный размер, если не поддерживаются другие параметры
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(KIE_AI_URL, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    # Обычно OpenAI совместимые API возвращают {"data": [{"url": "http..."}]}
                    if "data" in data and len(data["data"]) > 0:
                        return data["data"][0]["url"]
                    else:
                        raise Exception(f"Неожиданный формат ответа: {data}")
                else:
                    error_text = await response.text()
                    raise Exception(f"Ошибка API Kie.ai: {response.status} - {error_text}")
    except Exception as e:
        print(f"Error generating image: {e}")
        raise e
