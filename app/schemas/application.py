from enum import Enum
from pydantic import BaseModel


class ApplicationEnum(str, Enum):
    OWL = "owl"
    HR_CORNER = "hr-corner"
    CINEKU = "cineku"
    FUTURE_APP = "future-app"


class ApplicationHealthResponse(BaseModel):
    application: str
    status: str
