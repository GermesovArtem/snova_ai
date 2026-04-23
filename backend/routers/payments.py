from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import os
import aiohttp
from backend.database import get_db
from backend import models, services

router = APIRouter(prefix="/payments", tags=["payments"])
logger = logging.getLogger(__name__)

@router.post("/webhook")
async def yookassa_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handles Yookassa payment notifications"""
    try:
        data = await request.json()
        event = data.get("event")
        payment_data = data.get("object", {})
        
        payment_id = payment_data.get("id")
        status = payment_data.get("status")
        
        logger.info(f"YooKassa Webhook: event={event}, payment_id={payment_id}, status={status}")
        
        if event == "payment.succeeded":
            # 1. Verify with Yookassa API for security
            shop_id = os.getenv("YOOKASSA_SHOP_ID")
            secret_key = os.getenv("YOOKASSA_SECRET_KEY")
            
            async with aiohttp.ClientSession() as session:
                auth = aiohttp.BasicAuth(shop_id, secret_key)
                async with session.get(f"https://api.yookassa.ru/v3/payments/{payment_id}", auth=auth) as resp:
                    if resp.status == 200:
                        verified_data = await resp.json()
                        if verified_data.get("status") == "succeeded":
                            # Use centralized atomic service function
                            success = await services.process_successful_payment(db, payment_id)
                            if success:
                                logger.info(f"Webhook processed payment {payment_id}")
                        else:
                            logger.error(f"YooKassa verification failed: Status is {verified_data.get('status')}")
                    else:
                        logger.error(f"YooKassa verification API error: {resp.status}")
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
