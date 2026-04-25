"""Data models for fieldnotes."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ID_RE = re.compile(r"^\d{4,}$")


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    SPECULATION = "speculation"


class Reference(BaseModel):
    """A pointer from a note into a source file, pinned by sha256."""

    path: str
    sha: str | None = None
    lines: list[int] | None = None

    @field_validator("path")
    @classmethod
    def _path_nonempty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("reference.path must be non-empty")
        return v

    @field_validator("sha")
    @classmethod
    def _sha_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", v):
            raise ValueError("sha must be a 64-char hex sha256")
        return v

    @field_validator("lines")
    @classmethod
    def _lines_valid(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v
        if not v:
            return None
        if len(v) != 2:
            raise ValueError("lines must be exactly [start, end] (1-indexed, inclusive)")
        start, end = v
        if start < 1 or end < 1:
            raise ValueError("line numbers must be >= 1")
        if start > end:
            raise ValueError("lines start must be <= end")
        return v


class Note(BaseModel):
    """A single fieldnote."""

    id: str
    topic: str
    title: str
    confidence: Confidence = Confidence.MEDIUM
    written_by: str = "unknown"
    written_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    supersedes: str | None = None
    superseded_by: str | None = None

    @field_validator("id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        v = str(v).strip()
        if not ID_RE.fullmatch(v):
            raise ValueError("id must be a zero-padded integer string of length >= 4")
        return v

    @field_validator("topic")
    @classmethod
    def _topic_slug(cls, v: str) -> str:
        v = v.strip().lower()
        if not SLUG_RE.fullmatch(v):
            raise ValueError(
                "topic must be kebab-case (lowercase letters, digits, single hyphens)"
            )
        return v

    @field_validator("title")
    @classmethod
    def _title_nonempty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title must be non-empty")
        return v

    @field_validator("tags")
    @classmethod
    def _tags_slugs(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for t in v:
            t = t.strip().lower()
            if not t:
                continue
            if not SLUG_RE.fullmatch(t):
                raise ValueError(f"tag {t!r} must be kebab-case")
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out

    @field_validator("written_at")
    @classmethod
    def _ensure_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    @field_validator("supersedes", "superseded_by")
    @classmethod
    def _id_or_none(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = str(v).strip()
        if not v:
            return None
        if not ID_RE.fullmatch(v):
            raise ValueError("supersedes/superseded_by must reference a valid id")
        return v

    def filename(self) -> str:
        return f"{self.id}-{self.topic}.md"
