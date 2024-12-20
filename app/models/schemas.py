from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ProcessingRequest(BaseModel):
    audio_folder_id: str
    summary_folder_id: str
    access_token: str

class ProcessingStatus(BaseModel):
    type: str = Field(..., description="Type of status update")
    message: str = Field(..., description="Status message")
    data: Optional[Dict] = Field(default=None, description="Additional data")

class WebSocketMessage(BaseModel):
    type: str
    data: Dict[str, Any]