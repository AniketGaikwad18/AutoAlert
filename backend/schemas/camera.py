from typing import Optional
from pydantic import BaseModel, ConfigDict


class CameraCreate(BaseModel):
    id: str
    name: str
    source: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_desc: Optional[str] = ""
    is_active: bool = True


class CameraResponse(BaseModel):
    id: str
    name: str
    source: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_desc: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
