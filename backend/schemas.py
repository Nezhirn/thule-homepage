"""Pydantic schemas for the Homepage API."""
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

import config

VALID_SIZES = {"1x1", "2x1", "1x2", "2x2"}


class APIModel(BaseModel):
    """Base model that rejects unknown fields instead of silently dropping them."""

    model_config = ConfigDict(extra="forbid")


class SettingsUpdate(APIModel):
    background_image: Optional[str] = Field(default=None, max_length=config.MAX_URL_LENGTH)
    blur_radius: Optional[int] = Field(default=None, ge=0, le=config.MAX_BLUR_RADIUS)
    dark_mode: Optional[bool] = None


class SettingsResponse(BaseModel):
    id: int
    background_image: Optional[str] = None
    blur_radius: int
    dark_mode: bool


class CardCreate(APIModel):
    title: str = Field(min_length=1, max_length=config.MAX_TITLE_LENGTH)
    url: Optional[str] = Field(default=None, max_length=config.MAX_URL_LENGTH)
    icon_path: Optional[str] = Field(default=None, max_length=config.MAX_URL_LENGTH)
    size: str = "1x1"
    grid_col: int = Field(default=1, ge=1, le=config.COLS_PER_ROW)
    grid_row: int = Field(default=1, ge=1, le=config.MAX_GRID_ROW)
    open_in_new_tab: bool = True

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title must not be empty")
        return v

    @field_validator("size")
    @classmethod
    def validate_size(cls, v: str) -> str:
        if v not in VALID_SIZES:
            raise ValueError(f"Invalid size '{v}'. Allowed: {', '.join(sorted(VALID_SIZES))}")
        return v


class CardUpdate(APIModel):
    title: Optional[str] = Field(default=None, max_length=config.MAX_TITLE_LENGTH)
    url: Optional[str] = Field(default=None, max_length=config.MAX_URL_LENGTH)
    icon_path: Optional[str] = Field(default=None, max_length=config.MAX_URL_LENGTH)
    size: Optional[str] = None
    position: Optional[int] = Field(default=None, ge=0)
    grid_col: Optional[int] = Field(default=None, ge=1, le=config.COLS_PER_ROW)
    grid_row: Optional[int] = Field(default=None, ge=1, le=config.MAX_GRID_ROW)
    open_in_new_tab: Optional[bool] = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            raise ValueError("Title must not be null")
        v = v.strip()
        if not v:
            raise ValueError("Title must not be empty")
        return v

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
    open_in_new_tab: bool = True


class CardsReorderRequest(APIModel):
    card_ids: List[int] = Field(min_length=1, max_length=config.MAX_REORDER_IDS)


class FetchIconRequest(APIModel):
    url: str = Field(min_length=1, max_length=config.MAX_URL_LENGTH)


class FetchIconResponse(BaseModel):
    icon_path: Optional[str] = None


class FullDataResponse(BaseModel):
    settings: SettingsResponse
    cards: List[CardResponse]


class MessageResponse(BaseModel):
    message: str


class UploadResponse(BaseModel):
    filename: str
    url: str


class ImportData(BaseModel):
    """Data for transactional import."""

    settings: Optional[SettingsUpdate] = None
    cards: List[CardCreate] = Field(max_length=config.MAX_IMPORT_CARDS)
