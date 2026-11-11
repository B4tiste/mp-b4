"""Tests pour le module validator."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from moneyprinter.validator import FFprobeValidator, ValidatorError


# ============================================================================
# Tests de détection de ffprobe
# ============================================================================


def test_validator_detects_missing_ffprobe() -> None:
    """FFprobeValidator rejette si ffprobe est introuvable."""
    with patch("moneyprinter.validator.shutil.which", return_value=None):
        with pytest.raises(ValidatorError, match="ffprobe"):
            FFprobeValidator()


def test_validator_accepts_available_ffprobe() -> None:
    """FFprobeValidator s'initialise correctement si ffprobe est disponible."""
    with patch("moneyprinter.validator.shutil.which", return_value="/usr/bin/ffprobe"):
        validator = FFprobeValidator()
        assert validator is not None


# ============================================================================
# Tests de validation de fichiers
# ============================================================================


def test_validator_rejects_nonexistent_file() -> None:
    """FFprobeValidator rejette un fichier inexistant."""
    with patch("moneyprinter.validator.shutil.which", return_value="/usr/bin/ffprobe"):
        validator = FFprobeValidator()
        with pytest.raises(ValidatorError, match="n'existe pas"):
            validator.validate(Path("/tmp/nonexistent.mp4"))


# ============================================================================
# Tests de validation des propriétés (avec mock ffprobe)
# ============================================================================


@pytest.fixture
def mock_validator():
    """Crée un validateur avec ffprobe mocké."""
    with patch("moneyprinter.validator.shutil.which", return_value="/usr/bin/ffprobe"):
        return FFprobeValidator()


def create_mock_ffprobe_output(
    codec: str = "h264",
    width: int = 1080,
    height: int = 1920,
    fps: str = "30/1",
    pix_fmt: str = "yuv420p",
    nb_frames: str = "900",
    duration: str = "30.0",
    has_audio: bool = False,
) -> dict:
    """Crée une sortie ffprobe mockée."""
    streams = [
        {
            "codec_type": "video",
            "codec_name": codec,
            "width": width,
            "height": height,
            "r_frame_rate": fps,
            "avg_frame_rate": fps,
            "pix_fmt": pix_fmt,
            "nb_frames": nb_frames,
        }
    ]
    if has_audio:
        streams.append(
            {
                "codec_type": "audio",
                "codec_name": "aac",
            }
        )
    return {
        "streams": streams,
        "format": {
            "duration": duration,
        },
    }


def test_validator_accepts_valid_h264_video(mock_validator, tmp_path) -> None:
    """Le validateur accepte une vidéo H.264 valide."""
    video_path = tmp_path / "test.mp4"
    video_path.write_bytes(b"dummy")

    mock_output = json.dumps(
        create_mock_ffprobe_output(
            codec="h264",
            width=1080,
            height=1920,
            fps="30/1",
            pix_fmt="yuv420p",
            nb_frames="900",
            duration="30.0",
        )
    )

    with patch("moneyprinter.validator.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output)

        properties = mock_validator.validate(
            video_path,
            expected_codec="h264",
            expected_width=1080,
            expected_height=1920,
            expected_fps=30,
            expected_pixel_format="yuv420p",
            expected_frame_count=900,
            expected_duration_seconds=30.0,
        )

        assert properties["codec"] == "h264"
        assert properties["width"] == 1080
        assert properties["height"] == 1920
        assert properties["pixel_format"] == "yuv420p"
        assert int(properties["frame_count"]) == 900


def test_validator_rejects_wrong_codec(mock_validator, tmp_path) -> None:
    """Le validateur rejette un mauvais codec."""
    video_path = tmp_path / "test.mp4"
    video_path.write_bytes(b"dummy")

    mock_output = json.dumps(
        create_mock_ffprobe_output(codec="vp9")  # Pas H.264
    )

    with patch("moneyprinter.validator.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output)

        with pytest.raises(ValidatorError, match="codec"):
            mock_validator.validate(
                video_path,
                expected_codec="h264",
            )


def test_validator_rejects_wrong_width(mock_validator, tmp_path) -> None:
    """Le validateur rejette une mauvaise largeur."""
    video_path = tmp_path / "test.mp4"
    video_path.write_bytes(b"dummy")

    mock_output = json.dumps(create_mock_ffprobe_output(width=720))

    with patch("moneyprinter.validator.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output)

        with pytest.raises(ValidatorError, match="largeur"):
            mock_validator.validate(video_path, expected_width=1080)


def test_validator_rejects_wrong_height(mock_validator, tmp_path) -> None:
    """Le validateur rejette une mauvaise hauteur."""
    video_path = tmp_path / "test.mp4"
    video_path.write_bytes(b"dummy")

    mock_output = json.dumps(create_mock_ffprobe_output(height=1080))

    with patch("moneyprinter.validator.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output)

        with pytest.raises(ValidatorError, match="hauteur"):
            mock_validator.validate(video_path, expected_height=1920)


def test_validator_rejects_wrong_fps(mock_validator, tmp_path) -> None:
    """Le validateur rejette un mauvais FPS."""
    video_path = tmp_path / "test.mp4"
    video_path.write_bytes(b"dummy")

    mock_output = json.dumps(create_mock_ffprobe_output(fps="24/1"))

    with patch("moneyprinter.validator.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output)

        with pytest.raises(ValidatorError, match="FPS"):
            mock_validator.validate(video_path, expected_fps=30)


def test_validator_rejects_wrong_pixel_format(mock_validator, tmp_path) -> None:
    """Le validateur rejette un mauvais format de pixel."""
    video_path = tmp_path / "test.mp4"
    video_path.write_bytes(b"dummy")

    mock_output = json.dumps(create_mock_ffprobe_output(pix_fmt="yuv444p"))

    with patch("moneyprinter.validator.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output)

        with pytest.raises(ValidatorError, match="format de pixel"):
            mock_validator.validate(video_path, expected_pixel_format="yuv420p")


def test_validator_rejects_wrong_frame_count(mock_validator, tmp_path) -> None:
    """Le validateur rejette un mauvais nombre de frames."""
    video_path = tmp_path / "test.mp4"
    video_path.write_bytes(b"dummy")

    mock_output = json.dumps(create_mock_ffprobe_output(nb_frames="600"))

    with patch("moneyprinter.validator.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output)

        with pytest.raises(ValidatorError, match="nombre de frames"):
            mock_validator.validate(video_path, expected_frame_count=900)


def test_validator_rejects_wrong_duration(mock_validator, tmp_path) -> None:
    """Le validateur rejette une mauvaise durée."""
    video_path = tmp_path / "test.mp4"
    video_path.write_bytes(b"dummy")

    mock_output = json.dumps(create_mock_ffprobe_output(duration="20.0"))

    with patch("moneyprinter.validator.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output)

        with pytest.raises(ValidatorError, match="durée"):
            mock_validator.validate(
                video_path,
                expected_duration_seconds=30.0,
            )


def test_validator_rejects_audio_present(mock_validator, tmp_path) -> None:
    """Le validateur rejette une vidéo avec flux audio."""
    video_path = tmp_path / "test.mp4"
    video_path.write_bytes(b"dummy")

    mock_output = json.dumps(
        create_mock_ffprobe_output(has_audio=True)
    )

    with patch("moneyprinter.validator.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output)

        with pytest.raises(ValidatorError, match="flux audio"):
            mock_validator.validate(video_path)


def test_validator_rejects_no_video_stream(mock_validator, tmp_path) -> None:
    """Le validateur rejette un fichier sans flux vidéo."""
    video_path = tmp_path / "test.mp4"
    video_path.write_bytes(b"dummy")

    mock_output = json.dumps(
        {
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                }
            ],
            "format": {},
        }
    )

    with patch("moneyprinter.validator.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output)

        with pytest.raises(ValidatorError, match="aucun flux vidéo"):
            mock_validator.validate(video_path)


def test_validator_handles_ffprobe_timeout(mock_validator, tmp_path) -> None:
    """Le validateur gère les timeouts ffprobe."""
    video_path = tmp_path / "test.mp4"
    video_path.write_bytes(b"dummy")

    with patch("moneyprinter.validator.subprocess.run") as mock_run:
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("ffprobe", 30)

        with pytest.raises(ValidatorError, match="timeout"):
            mock_validator.validate(video_path)


def test_validator_handles_ffprobe_error(mock_validator, tmp_path) -> None:
    """Le validateur gère les erreurs ffprobe."""
    video_path = tmp_path / "test.mp4"
    video_path.write_bytes(b"dummy")

    with patch("moneyprinter.validator.subprocess.run") as mock_run:
        import subprocess
        error = subprocess.CalledProcessError(1, "ffprobe")
        error.stderr = "Some error"
        mock_run.side_effect = error

        with pytest.raises(ValidatorError, match="ffprobe a échoué"):
            mock_validator.validate(video_path)


def test_validator_handles_invalid_json(mock_validator, tmp_path) -> None:
    """Le validateur gère un JSON invalide de ffprobe."""
    video_path = tmp_path / "test.mp4"
    video_path.write_bytes(b"dummy")

    with patch("moneyprinter.validator.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="not valid json")

        with pytest.raises(ValidatorError, match="JSON invalide"):
            mock_validator.validate(video_path)


def test_validator_tolerates_fps_precision_error(mock_validator, tmp_path) -> None:
    """Le validateur tolère les petites imprécisions de FPS (< 0.1)."""
    video_path = tmp_path / "test.mp4"
    video_path.write_bytes(b"dummy")

    # Fournir 30.05 FPS au lieu de 30 (dans la tolérance)
    mock_output = json.dumps(create_mock_ffprobe_output(fps="3005/100"))

    with patch("moneyprinter.validator.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output)

        properties = mock_validator.validate(
            video_path,
            expected_fps=30,
        )
        # Doit passer sans erreur
        assert abs(properties["fps"] - 30.05) < 0.1


def test_validator_tolerates_duration_precision_error(mock_validator, tmp_path) -> None:
    """Le validateur tolère les petites imprécisions de durée (< 0.01s)."""
    video_path = tmp_path / "test.mp4"
    video_path.write_bytes(b"dummy")

    mock_output = json.dumps(create_mock_ffprobe_output(duration="30.005"))

    with patch("moneyprinter.validator.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output)

        properties = mock_validator.validate(
            video_path,
            expected_duration_seconds=30.0,
        )
        # Doit passer sans erreur
        assert abs(properties["duration_seconds"] - 30.0) < 0.01


def test_validator_optional_properties(mock_validator, tmp_path) -> None:
    """Le validateur permet l'omission de propriétés optionnelles."""
    video_path = tmp_path / "test.mp4"
    video_path.write_bytes(b"dummy")

    mock_output = json.dumps(create_mock_ffprobe_output())

    with patch("moneyprinter.validator.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output)

        # Appeler sans propriétés optionnelles
        properties = mock_validator.validate(video_path)

        # Doit retourner des propriétés même sans validation stricte
        assert "codec" in properties
        assert "width" in properties
        assert "height" in properties
