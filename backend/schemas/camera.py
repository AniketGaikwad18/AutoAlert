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


class CameraSchema(BaseModel):
    """Camera schema used by camera registry and simulation controller."""
    camera_id: Optional[str] = None
    id: Optional[str] = None
    name: str
    source: Optional[str] = ""
    stream_url: Optional[str] = ""
    location_name: Optional[str] = ""
    location: Optional[str] = ""
    location_desc: Optional[str] = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    zone_id: Optional[str] = ""
    status: Optional[str] = "active"
    is_active: bool = True
    enabled: bool = True

    model_config = ConfigDict(from_attributes=True, extra="allow")

    def __init__(self, **data):
        if "camera_id" not in data and "id" in data:
            data["camera_id"] = data["id"]
        elif "id" not in data and "camera_id" in data:
            data["id"] = data["camera_id"]

        loc = data.get("location")
        if isinstance(loc, dict):
            if "latitude" not in data and "latitude" in loc:
                data["latitude"] = loc["latitude"]
            if "longitude" not in data and "longitude" in loc:
                data["longitude"] = loc["longitude"]
            desc = loc.get("description", "")
            data["location_desc"] = desc
            data["location_name"] = desc
            data["location"] = desc
        else:
            if "location" in data and "location_name" not in data:
                data["location_name"] = data["location"]
            if "location_name" in data and "location" not in data:
                data["location"] = data["location_name"]

        super().__init__(**data)

