"""Pydantic schemas for the Homepage API."""
from pydantic import BaseModel, field_validator
from typing import Optional, List

VALID_SIZES = {"1x1", "2x1", "1x2", "2x2"}


class SettingsUpdate(BaseModel):
    background_image: Optional[str] = None
    blur_radius: Optional[int] = None
    dark_mode: Optional[bool] = None


class SettingsResponse(BaseModel):
    id: int
    background_image: Optional[str] = None
    blur_radius: int
    dark_mode: bool


class CardCreate(BaseModel):
    title: str
    url: Optional[str] = None
    icon_path: Optional[str] = None
    size: str = "1x1"
    grid_col: int = 1
    grid_row: int = 1

    @field_validator("size")
    @classmethod
    def validate_size(cls, v: str) -> str:
        if v not in VALID_SIZES:
            raise ValueError(f"Invalid size '{v}'. Allowed: {', '.join(sorted(VALID_SIZES))}")
        return v


class CardUpdate(BaseModel):
    title: Optional[str] = None
    url: Optional[str] = None
    icon_path: Optional[str] = None
    size: Optional[str] = None
    position: Optional[int] = None
    grid_col: Optional[int] = None
    grid_row: Optional[int] = None

    @field_validator("size")
    @classmethod
    def validate_size(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_SIZES:
            raise ValueError(f"Invalid size '{v}'. Allowed: {', '.join(sorted(VALID_SIZES))}")
        return v


class CardResponse(BaseModel):
    id: int
    title: str
    url: Optional[str] = None
    icon_path: Optional[str] = None
    size: str
    position: int
    grid_col: int
    grid_row: int


class CardsReorderRequest(BaseModel):
    card_ids: List[int]


class FetchIconRequest(BaseModel):
    url: str


class FetchIconResponse(BaseModel):
    icon_path: Optional[str] = None


class FullDataResponse(BaseModel):
    settings: SettingsResponse
    cards: List[CardResponse]


class ImportData(BaseModel):
    """Data for transactional import."""
    settings: Optional[SettingsUpdate] = None
    cards: List[CardCreate]
