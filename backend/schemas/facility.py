from typing import Optional
from pydantic import BaseModel, ConfigDict


class FacilityResponse(BaseModel):
    id: str
    name: str
    type: str
    latitude: float
    longitude: float
    phone: str
    status: str
    distance_km: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)
