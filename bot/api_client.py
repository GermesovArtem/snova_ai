import asyncio
import aiohttp
from typing import Tuple, Optional, Any
import logging

BACKEND_URL = "http://api:8000"

async def add_balance(telegram_id: int, amount: float) -> Optional[float]:
    async with aiohttp.ClientSession() as session:
        url = f"{BACKEND_URL}/users/{telegram_id}/add_balance"
        async with session.post(url, json={"amount": amount}) as response:
            if response.status == 200:
                return await response.json()
            else:
                logging.error(f"Error adding balance: {await response.text()}")
                return None

async def create_payment_link(telegram_id: int, amount: float, description: str) -> Optional[str]:
    async with aiohttp.ClientSession() as session:
        url = f"{BACKEND_URL}/payments/create"
        payload = {"telegram_id": telegram_id, "amount": amount, "description": description}
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("url")
            else:
                logging.error(f"Error creating payment link: {await response.text()}")
                return None

async def get_or_create_user(telegram_id: int, username: Optional[str] = None, referrer_id: Optional[str] = None) -> Any:
    async with aiohttp.ClientSession() as session:
        url = f"{BACKEND_URL}/users/"
        payload = {"telegram_id": telegram_id, "username": username, "referrer_id": referrer_id}
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                return await response.json()
            else:
                logging.error(f"Error creating user: {await response.text()}")
                return None

async def get_referral_stats(telegram_id: int) -> dict:
    async with aiohttp.ClientSession() as session:
        url = f"{BACKEND_URL}/users/{telegram_id}/referrals"
        async with session.get(url) as response:
            if response.status == 200:
                return await response.json()
            else:
                logging.error(f"Error fetching referral stats: {await response.text()}")
                return {"referral_count": 0, "referral_link": ""}

async def get_balance(telegram_id: int) -> float:
    async with aiohttp.ClientSession() as session:
        url = f"{BACKEND_URL}/users/{telegram_id}/balance"
        async with session.get(url) as response:
            if response.status == 200:
                return await response.json()
            else:
                logging.error(f"Error fetching balance: {await response.text()}")
                return 0.0

async def generate_image(telegram_id: int, prompt: str, model: str, cost: float) -> Tuple[Optional[str], str]:
    async with aiohttp.ClientSession() as session:
        url = f"{BACKEND_URL}/generate/"
        payload = {
            "telegram_id": telegram_id,
            "prompt": prompt,
            "model": model,
            "cost": cost
        }
        try:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("image_url"), "Успешно"
                elif response.status == 402:
                    data = await response.json()
                    return None, f"Недостаточно баланса: {data.get('detail')}"
                else:
                    error_text = await response.text()
                    logging.error(f"Generation API error: {error_text}")
                    return None, f"Ошибка API: {response.status}"
        except asyncio.TimeoutError:
             return None, "Превышено время ожидания сервера Backend"
        except Exception as e:
            return None, f"Внутренняя ошибка: {str(e)}"
