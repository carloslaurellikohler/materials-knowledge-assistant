from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    metadata_filters: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    source: str
    chapter: str | None = None
    section: str | None = None
    page: int | None = None
    excerpt: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]

