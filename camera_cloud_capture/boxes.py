from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoundingBox:
    """Axis-aligned box in pixel coordinates (x, y is top-left)."""

    x: int
    y: int
    width: int
    height: int
    label: str
    score: float = 1.0

    @property
    def as_xyxy(self) -> tuple[int, int, int, int]:
        return self.x, self.y, self.x + self.width, self.y + self.height
