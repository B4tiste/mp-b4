"""Schémas JSON et règles de validation des scripts vidéo."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def _require_nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("le texte ne peut pas être vide ou composé d'espaces")
    return value


NonBlankText = Annotated[str, AfterValidator(_require_nonblank)]
PositiveInt = Annotated[int, Field(gt=0, strict=True)]
PositiveDuration = Annotated[Decimal, Field(gt=Decimal("0"))]
HexColor = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Scene(StrictModel):
    duration_seconds: PositiveDuration
    headline: NonBlankText
    body: NonBlankText
    accent_color: HexColor


class Video(StrictModel):
    width: PositiveInt
    height: PositiveInt
    fps: PositiveInt
    background_color: HexColor
    scenes: list[Scene] = Field(min_length=1)

    @property
    def total_duration_seconds(self) -> Decimal:
        return sum(
            (scene.duration_seconds for scene in self.scenes),
            start=Decimal("0"),
        )


class VideoDocument(StrictModel):
    schema_version: Literal["1.0"]
    title: NonBlankText
    video: Video


class MVPProfileError(ValueError):
    """Un document valide génériquement ne respecte pas le profil MVP."""


def validate_mvp_profile(document: VideoDocument) -> None:
    """Vérifie les contraintes propres au profil vidéo MVP."""
    video = document.video

    if (video.width, video.height) != (1080, 1920):
        raise MVPProfileError(
            "la résolution du profil MVP doit être de 1080 × 1920 "
            f"(reçu : {video.width} × {video.height})"
        )
    if video.fps != 30:
        raise MVPProfileError(
            f"la fréquence du profil MVP doit être de 30 FPS (reçu : {video.fps})"
        )
    if video.total_duration_seconds != Decimal("30"):
        raise MVPProfileError(
            "la durée totale du profil MVP doit être de 30 secondes "
            f"(reçu : {format_duration(video.total_duration_seconds)} secondes)"
        )


def format_duration(duration: Decimal) -> str:
    """Formate une durée sans exposer de zéros décimaux superflus."""
    formatted = format(duration, "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted
