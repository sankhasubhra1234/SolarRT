"""User feedback: validated, rate-limited, stored as JSON lines (one entry per line)."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .security import RateLimiter

RATING_LABELS = {1: "Terrible", 2: "Bad", 3: "Okay", 4: "Good", 5: "Love it"}


class FeedbackIn(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: str = Field("", max_length=2000)
    contact: str = Field("", max_length=200)
    edition: str = Field("web", max_length=20)
    version: str = Field("", max_length=20)

    @field_validator("comment", "contact", "edition", "version")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()


class FeedbackFull(Exception):
    """The feedback file reached its size limit."""


class FeedbackStore:
    def __init__(self, data_dir: str | Path, per_ip_limit: int = 5, window_s: int = 600,
                 max_bytes: int = 20 * 1024 * 1024) -> None:
        self.path = Path(data_dir) / "feedback.jsonl"
        self._lock = threading.Lock()
        # Bounded per-client limiter (5 per 10 minutes by default)
        self._limiter = RateLimiter(per_ip_limit, window_s)
        self.max_bytes = max_bytes

    def allowed(self, client: str) -> bool:
        return self._limiter.allow(client)

    def add(self, fb: FeedbackIn) -> dict[str, Any]:
        entry = {"id": uuid.uuid4().hex[:12], "time": datetime.now(timezone.utc).isoformat(),
                 **fb.model_dump(), "rating_label": RATING_LABELS[fb.rating]}
        with self._lock:
            if self.path.exists() and self.path.stat().st_size >= self.max_bytes:
                raise FeedbackFull(f"{self.path} is {self.path.stat().st_size} bytes")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def summary(self) -> dict[str, Any]:
        items = self.all()
        counts = {r: sum(1 for i in items if i.get("rating") == r) for r in range(1, 6)}
        avg = round(sum(i["rating"] for i in items) / len(items), 2) if items else None
        return {"count": len(items), "average": avg, "by_rating": counts,
                "entries": list(reversed(items))}
