from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base
import uuid

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True) # Telegram User ID
    name = Column(String, nullable=True)
    role = Column(String, default="user")
    balance = Column(Float, default=10.0) # Default balance
    frozen_balance = Column(Float, default=0.0)
    model_preference = Column(String, default="nanobanana")
    email_verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

class GenerationTask(Base):
    __tablename__ = "generation_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    task_uuid = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"))
    tool = Column(String, default="image")
    model = Column(String, default="nanobanana")
    status = Column(String, default="processing") # processing, completed, failed
    prompt = Column(String, nullable=True)
    image_url = Column(String, nullable=True) # Result URL
    credits_cost = Column(Integer, default=1)
    prompt_image_url = Column(String, nullable=True) # If it was image-to-image
    created_at = Column(DateTime, server_default=func.now())

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount_rub = Column(Float, nullable=False)
    status = Column(String, default="pending") # pending, succeeded, canceled
    payment_url = Column(String, nullable=True)
    provider_payment_id = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    
class Referral(Base):
    __tablename__ = "referrals"
    
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    invited_count = Column(Integer, default=0)
    available_to_convert = Column(Integer, default=0)
    total_earned = Column(Integer, default=0)
