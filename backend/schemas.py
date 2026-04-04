from pydantic import BaseModel
from typing import Optional, List

class TelegramAuth(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str

class ModelUpdate(BaseModel):
    model_id: str

class GenerationRequest(BaseModel):
    prompt: str
    aspect_ratio: Optional[str] = "1:1"
    resolution: Optional[str] = "1K"
    output_format: Optional[str] = "jpg"
