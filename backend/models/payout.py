from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from backend.database import Base
from backend.models.user import get_moscow_time

class PayoutDB(Base):
    __tablename__ = "payouts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    amount = Column(Float, nullable=False)
    requisites = Column(String, nullable=False) # e.g. Card number or phone
    status = Column(String, default="pending") # pending, completed, rejected
    check_file_path = Column(String, nullable=True) # path to receipt/check uploaded by admin
    created_at = Column(DateTime, default=get_moscow_time)
