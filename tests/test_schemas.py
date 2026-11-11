import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from moneyprinter.schemas import (
    MVPProfileError,
    VideoDocument,
    validate_mvp_profile,
)

DEMO_PATH = Path(__file__).parents[1] / "examples" / "demo.json"


def valid_document() -> dict:
    return {
        "schema_version": "1.0",
        "title": "Une année autour du Soleil",
        "video": {
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "background_color": "#101827",
            "scenes": [
                {
                    "duration_seconds": 5,
                    "headline": "Une année",
                    "body": "La Terre avance sur son orbite.",
                    "accent_color": "#FFC857",
                },
                {
                    "duration_seconds": 25,
                    "headline": "Le tour",
                    "body": "Un tour prend environ 365 jours.",
                    "accent_color": "#71D6C1",
                },
            ],
        },
    }


def test_demo_json_is_valid_and_matches_mvp_profile() -> None:
    document = VideoDocument.model_validate_json(DEMO_PATH.read_text(encoding="utf-8"))

    validate_mvp_profile(document)

    assert len(document.video.scenes) == 4
    assert document.video.total_duration_seconds == Decimal("30")


def test_required_field_is_rejected_when_missing() -> None:
    payload = valid_document()
    del payload["video"]["scenes"][0]["body"]

    with pytest.raises(ValidationError, match="body"):
        VideoDocument.model_validate(payload)


def test_unknown_field_is_rejected() -> None:
    payload = valid_document()
    payload["unexpected"] = True

    with pytest.raises(ValidationError, match="extra_forbidden"):
        VideoDocument.model_validate(payload)


def test_invalid_color_is_rejected() -> None:
    payload = valid_document()
    payload["video"]["background_color"] = "blue"

    with pytest.raises(ValidationError, match="pattern"):
        VideoDocument.model_validate(payload)


@pytest.mark.parametrize("duration", [0, -1, Decimal("-0.01")])
def test_non_positive_scene_duration_is_rejected(duration: int | Decimal) -> None:
    payload = valid_document()
    payload["video"]["scenes"][0]["duration_seconds"] = duration

    with pytest.raises(ValidationError):
        VideoDocument.model_validate(payload)


def test_empty_scenes_list_is_rejected() -> None:
    payload = valid_document()
    payload["video"]["scenes"] = []

    with pytest.raises(ValidationError):
        VideoDocument.model_validate(payload)


@pytest.mark.parametrize("title", ["", "  \t"])
def test_blank_required_text_is_rejected(title: str) -> None:
    payload = valid_document()
    payload["title"] = title

    with pytest.raises(ValidationError, match="composé d'espaces"):
        VideoDocument.model_validate(payload)


def test_mvp_profile_rejects_nonconforming_resolution() -> None:
    payload = valid_document()
    payload["video"]["width"] = 720
    document = VideoDocument.model_validate(payload)

    with pytest.raises(MVPProfileError, match="1080"):
        validate_mvp_profile(document)


def test_mvp_profile_rejects_nonconforming_fps() -> None:
    payload = valid_document()
    payload["video"]["fps"] = 24
    document = VideoDocument.model_validate(payload)

    with pytest.raises(MVPProfileError, match="30 FPS"):
        validate_mvp_profile(document)


def test_mvp_profile_rejects_incorrect_total_duration() -> None:
    payload = valid_document()
    payload["video"]["scenes"][1]["duration_seconds"] = Decimal("24.9")
    document = VideoDocument.model_validate(payload)

    with pytest.raises(MVPProfileError, match="30 secondes"):
        validate_mvp_profile(document)


def test_mvp_profile_accepts_exact_total_duration() -> None:
    payload = valid_document()
    payload["video"]["scenes"][0]["duration_seconds"] = Decimal("0.1")
    payload["video"]["scenes"][1]["duration_seconds"] = Decimal("29.9")
    document = VideoDocument.model_validate(payload)

    validate_mvp_profile(document)

    assert document.video.total_duration_seconds == Decimal("30.0")
