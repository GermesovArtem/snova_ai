from pydantic import BaseModel
from typing import Optional, List
import datetime

class TelegramAuth(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: Optional[int] = None
    hash: Optional[str] = None
    auth_type: str = "widget" # "widget" or "twa"
    initData: Optional[str] = None

class ModelUpdate(BaseModel):
    model_id: str

class GenerationRequest(BaseModel):
    prompt: str
    aspect_ratio: Optional[str] = "1:1"
    resolution: Optional[str] = "1K"
    output_format: Optional[str] = "jpg"

class MessageCreate(BaseModel):
    role: str
    text: Optional[str] = None
    image_url: Optional[str] = None
    meta: Optional[dict] = None

class MessageUpdate(BaseModel):
    text: Optional[str] = None
    meta: Optional[dict] = None

class MessageRead(BaseModel):
    id: int
    role: str
    text: Optional[str] = None
    image_url: Optional[str] = None
    meta: Optional[str] = None # JSON string
    timestamp: datetime.datetime
