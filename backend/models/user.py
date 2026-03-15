from sqlalchemy import Column, Integer, String, Float, DateTime
from backend.database import Base
from datetime import datetime
import pytz

def get_moscow_time():
    moscow_tz = pytz.timezone('Europe/Moscow')
    return datetime.now(moscow_tz)

class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String, nullable=True)
    balance = Column(Float, default=10.0)
    frozen_balance = Column(Float, default=0.0)
    referrer_id = Column(String, nullable=True) # ID of the user who referred them
    role = Column(String, default="USER") # USER, SUPPORT, SUPERADMIN
    created_at = Column(DateTime, default=get_moscow_time)
