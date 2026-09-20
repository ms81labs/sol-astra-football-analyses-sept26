"""Versioned import coordinates. Values are never classified by their range."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .domain_types import FiniteFloat, Homography3x3


class CoordinateConvention(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal[1] = 1
    space: Literal["source_pixels", "pitch_normalized_0_100", "pitch_metres", "unknown"]
    axes: Literal["x_right_y_down"] = "x_right_y_down"
    origin: Literal["top_left"] = "top_left"
    pitchLengthM: FiniteFloat | None = Field(default=None, gt=0)
    pitchWidthM: FiniteFloat | None = Field(default=None, gt=0)
    sourceWidth: int | None = Field(default=None, gt=0, strict=True)
    sourceHeight: int | None = Field(default=None, gt=0, strict=True)
    streamId: str | None = Field(default=None, min_length=1)
    # Maps declared observation/processed pixels back into original source pixels.
    sourceFromObservation: Homography3x3 | None = None

    @model_validator(mode="after")
    def complete(self):
        if self.space == "pitch_metres" and (self.pitchLengthM is None or self.pitchWidthM is None):
            raise ValueError("Pitch metres require declared pitch dimensions")
        if (self.sourceWidth is None) != (self.sourceHeight is None):
            raise ValueError("Source dimensions must be declared together")
        if self.space != "source_pixels" and self.sourceFromObservation is not None:
            raise ValueError("Only pixel inputs may carry a source mapping")
        return self
