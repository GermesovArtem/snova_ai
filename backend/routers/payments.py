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
                            # 2. Update DB Payment with FOR UPDATE to prevent race conditions
                            from sqlalchemy import select, update
                            
                            # Lock the payment row until the transaction is committed
                            res = await db.execute(
                                select(models.Payment)
                                .filter_by(provider_payment_id=payment_id)
                                .with_for_update()
                            )
                            db_payment = res.scalars().first()
                            
                            if db_payment and db_payment.status != "succeeded":
                                # Mark as succeeded immediately
                                db_payment.status = "succeeded"
                                
                                # 3. Credit User Balance
                                user_id = db_payment.user_id
                                amount = db_payment.amount_rub
                                
                                # Determine how many credits to give
                                packs_str = os.getenv("CREDIT_PACKS", '{"149": 30, "299": 65, "990": 270}')
                                import json
                                try:
                                    packs = json.loads(packs_str)
                                except:
                                    packs = {"149": 30, "299": 65, "990": 270}
                                
                                credits_to_add = 0
                                for p_str, cr in packs.items():
                                    if abs(float(p_str) - amount) < 1.0:
                                        credits_to_add = cr
                                        break
                                
                                if credits_to_add == 0:
                                    # Fallback: calculate using the best ratio from available packs
                                    ratios = [cr/float(p) for p, cr in packs.items() if float(p) > 0]
                                    best_ratio = max(ratios) if ratios else 0.2
                                    credits_to_add = int(amount * best_ratio)
                                
                                # Atomic update of user balance WITHOUT calling services.update_user_balance
                                # to ensure the whole operation is within a single transaction
                                await db.execute(
                                    update(models.User)
                                    .where(models.User.id == user_id)
                                    .values(balance=models.User.balance + credits_to_add)
                                )
                                
                                logger.info(f"Verified payment {payment_id} succeeded. Added {credits_to_add} credits to user {user_id}")
                                await db.commit()
                            else:
                                logger.warning(f"Payment {payment_id} already processed or not found in DB")
                        else:
                            logger.error(f"YooKassa verification failed: Status is {verified_data.get('status')}")
                    else:
                        logger.error(f"YooKassa verification API error: {resp.status}")
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
