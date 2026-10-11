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


class FacilitySchema(BaseModel):
    """Emergency facility schema used in routing, database and dispatch tests."""
    facility_id: Optional[str] = None
    id: Optional[str] = None
    name: str
    type: str
    latitude: float
    longitude: float
    phone_contact: Optional[str] = ""
    phone: Optional[str] = ""
    status: Optional[str] = "active"
    available: bool = True
    is_simulated: bool = True
    distance_km: Optional[float] = None

    model_config = ConfigDict(from_attributes=True, extra="allow")

    def __init__(self, **data):
        if "facility_id" not in data and "id" in data:
            data["facility_id"] = data["id"]
        elif "id" not in data and "facility_id" in data:
            data["id"] = data["facility_id"]
        if "phone" in data and "phone_contact" not in data:
            data["phone_contact"] = data["phone"]
        elif "phone_contact" in data and "phone" not in data:
            data["phone"] = data["phone_contact"]
        super().__init__(**data)

