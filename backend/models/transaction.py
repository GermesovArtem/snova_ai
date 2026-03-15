from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from backend.database import Base
from backend.models.user import get_moscow_time

class TransactionDB(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    amount = Column(Float, nullable=False)
    type = Column(String, nullable=False) # pay, gen, ref
    status = Column(String, default="completed") # pending, completed, failed
    created_at = Column(DateTime, default=get_moscow_time)
