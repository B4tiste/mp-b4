"""Tests pour le module encoder."""

import json
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from moneyprinter.cli import load_and_validate_json
from moneyprinter.encoder import EncoderError, EncoderInput, FFmpegEncoder
from moneyprinter.timeline import build_timeline
from moneyprinter.validator import FFprobeValidator, ValidatorError

# Chemin vers le JSON de démonstration
DEMO_PATH = Path(__file__).parents[1] / "examples" / "demo.json"

# Détecter si FFmpeg et ffprobe sont disponibles
FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None
FFPROBE_AVAILABLE = shutil.which("ffprobe") is not None
FFMPEG_AND_FFPROBE = FFMPEG_AVAILABLE and FFPROBE_AVAILABLE


@pytest.fixture
def demo_document():
    """Charge le document de démonstration."""
    return load_and_validate_json(DEMO_PATH)


@pytest.fixture
def demo_timeline(demo_document):
    """Construit la timeline de démonstration."""
    return build_timeline(demo_document.video)


@pytest.fixture
def demo_images_dir(tmp_path):
    """Crée un répertoire temporaire avec des images de test petites (64×96)."""
    from PIL import Image

    images_dir = tmp_path / "images"
    images_dir.mkdir()

    # Créer 4 images statiques de 64×96 pixels
    for i in range(4):
        img = Image.new("RGB", (64, 96), color=(50 + i * 50, 100, 150))
        img.save(images_dir / f"test_{i}.png")

    return images_dir


# ============================================================================
# Tests de validation des paramètres
# ============================================================================


def test_encoder_input_validation_empty_images() -> None:
    """EncoderInput rejette une liste d'images vide."""
    with pytest.raises(EncoderError, match="liste des images"):
        EncoderInput(
            image_paths=tuple(),
            frame_counts=(10,),
            width=1080,
            height=1920,
            fps=30,
            output_path=Path("/tmp/out.mp4"),
        )


def test_encoder_input_validation_empty_frame_counts() -> None:
    """EncoderInput rejette une liste de frame_counts vide."""
    with pytest.raises(EncoderError, match="frame_counts"):
        EncoderInput(
            image_paths=(Path("/tmp/image.png"),),
            frame_counts=tuple(),
            width=1080,
            height=1920,
            fps=30,
            output_path=Path("/tmp/out.mp4"),
        )


def test_encoder_input_validation_mismatched_lengths() -> None:
    """EncoderInput rejette si le nombre d'images ne correspond pas au nombre de frame_counts."""
    with pytest.raises(EncoderError, match="nombre d'images"):
        EncoderInput(
            image_paths=(Path("/tmp/1.png"), Path("/tmp/2.png")),
            frame_counts=(10,),
            width=1080,
            height=1920,
            fps=30,
            output_path=Path("/tmp/out.mp4"),
        )


def test_encoder_input_validation_invalid_width() -> None:
    """EncoderInput rejette une largeur <= 0."""
    with pytest.raises(EncoderError, match="largeur"):
        EncoderInput(
            image_paths=(Path("/tmp/image.png"),),
            frame_counts=(10,),
            width=0,
            height=1920,
            fps=30,
            output_path=Path("/tmp/out.mp4"),
        )


def test_encoder_input_validation_invalid_height() -> None:
    """EncoderInput rejette une hauteur <= 0."""
    with pytest.raises(EncoderError, match="hauteur"):
        EncoderInput(
            image_paths=(Path("/tmp/image.png"),),
            frame_counts=(10,),
            width=1080,
            height=0,
            fps=30,
            output_path=Path("/tmp/out.mp4"),
        )


def test_encoder_input_validation_invalid_fps() -> None:
    """EncoderInput rejette un FPS <= 0."""
    with pytest.raises(EncoderError, match="FPS"):
        EncoderInput(
            image_paths=(Path("/tmp/image.png"),),
            frame_counts=(10,),
            width=1080,
            height=1920,
            fps=0,
            output_path=Path("/tmp/out.mp4"),
        )


def test_encoder_input_validation_invalid_frame_count() -> None:
    """EncoderInput rejette un frame_count <= 0."""
    with pytest.raises(EncoderError, match="frame_count invalide"):
        EncoderInput(
            image_paths=(Path("/tmp/image.png"),),
            frame_counts=(0,),
            width=1080,
            height=1920,
            fps=30,
            output_path=Path("/tmp/out.mp4"),
        )


def test_encoder_input_validation_nonexistent_image(tmp_path) -> None:
    """EncoderInput rejette une image inexistante."""
    with pytest.raises(EncoderError, match="n'existe pas"):
        EncoderInput(
            image_paths=(tmp_path / "nonexistent.png",),
            frame_counts=(10,),
            width=1080,
            height=1920,
            fps=30,
            output_path=tmp_path / "out.mp4",
        )


def test_encoder_input_validation_directory_as_image(tmp_path) -> None:
    """EncoderInput rejette un répertoire fourni comme image."""
    images_dir = tmp_path / "images"
    images_dir.mkdir()

    with pytest.raises(EncoderError, match="n'est pas un fichier"):
        EncoderInput(
            image_paths=(images_dir,),
            frame_counts=(10,),
            width=1080,
            height=1920,
            fps=30,
            output_path=tmp_path / "out.mp4",
        )


# ============================================================================
# Tests d'intégration : encodage de petites vidéos
# ============================================================================


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_encoder_creates_mp4_file(tmp_path, demo_images_dir) -> None:
    """L'encodeur crée un fichier MP4 valide."""
    output_path = tmp_path / "output.mp4"

    images = sorted(demo_images_dir.glob("test_*.png"))
    encoder_input = EncoderInput(
        image_paths=tuple(images),
        frame_counts=(30, 60, 60, 90),  # Total 240 frames
        width=64,
        height=96,
        fps=30,
        output_path=output_path,
    )

    encoder = FFmpegEncoder(encoder_input)
    result_path = encoder.encode()

    assert result_path.exists()
    assert result_path.stat().st_size > 0


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_encoder_respects_overwrite_flag(tmp_path, demo_images_dir) -> None:
    """L'encodeur rejette un fichier de sortie préexistant sans overwrite=True."""
    output_path = tmp_path / "output.mp4"
    output_path.write_text("dummy")

    images = sorted(demo_images_dir.glob("test_*.png"))
    encoder_input = EncoderInput(
        image_paths=tuple(images),
        frame_counts=(30, 60, 60, 90),
        width=64,
        height=96,
        fps=30,
        output_path=output_path,
        overwrite=False,
    )

    encoder = FFmpegEncoder(encoder_input)

    with pytest.raises(EncoderError, match="existe déjà"):
        encoder.encode()

    # Vérifier que le fichier original est préservé
    assert output_path.read_text() == "dummy"


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_encoder_overwrites_file_when_enabled(tmp_path, demo_images_dir) -> None:
    """L'encodeur remplace un fichier de sortie existant avec overwrite=True."""
    output_path = tmp_path / "output.mp4"
    output_path.write_text("dummy")

    images = sorted(demo_images_dir.glob("test_*.png"))
    encoder_input = EncoderInput(
        image_paths=tuple(images),
        frame_counts=(30, 60, 60, 90),
        width=64,
        height=96,
        fps=30,
        output_path=output_path,
        overwrite=True,
    )

    encoder = FFmpegEncoder(encoder_input)
    result_path = encoder.encode()

    assert result_path.exists()
    assert result_path.stat().st_size > 0
    # Le nouveau fichier ne doit pas être "dummy"
    with open(result_path, "rb") as f:
        content = f.read(4)
        # Un fichier MP4 commence par le magic number ftyp
        assert content[:4] != b"dumm"


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_encoder_creates_parent_directories(tmp_path, demo_images_dir) -> None:
    """L'encodeur crée les répertoires parents du fichier de sortie."""
    output_path = tmp_path / "nested" / "deep" / "dir" / "output.mp4"

    images = sorted(demo_images_dir.glob("test_*.png"))
    encoder_input = EncoderInput(
        image_paths=tuple(images),
        frame_counts=(30, 60, 60, 90),
        width=64,
        height=96,
        fps=30,
        output_path=output_path,
    )

    encoder = FFmpegEncoder(encoder_input)
    result_path = encoder.encode()

    assert result_path.exists()
    assert result_path.parent.exists()


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_encoder_validates_frame_count(tmp_path, demo_images_dir) -> None:
    """L'encodeur produit le nombre exact de frames attendues."""
    output_path = tmp_path / "output.mp4"

    images = sorted(demo_images_dir.glob("test_*.png"))
    encoder_input = EncoderInput(
        image_paths=tuple(images),
        frame_counts=(30, 60, 60, 90),  # Total 240 frames
        width=64,
        height=96,
        fps=30,
        output_path=output_path,
    )

    encoder = FFmpegEncoder(encoder_input)
    encoder.encode()

    # Valider avec ffprobe
    try:
        validator = FFprobeValidator()
        properties = validator.validate(
            output_path,
            expected_frame_count=240,
            expected_fps=30,
        )
        assert int(properties["frame_count"]) == 240
    except ValidatorError:
        pytest.skip("ffprobe not available")


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_encoder_concatenates_scenes_in_order(tmp_path, demo_images_dir) -> None:
    """L'encodeur concatène les scènes dans le bon ordre."""
    output_path = tmp_path / "output.mp4"

    images = sorted(demo_images_dir.glob("test_*.png"))
    encoder_input = EncoderInput(
        image_paths=tuple(images),
        frame_counts=(30, 60, 60, 90),
        width=64,
        height=96,
        fps=30,
        output_path=output_path,
    )

    encoder = FFmpegEncoder(encoder_input)
    result_path = encoder.encode()

    assert result_path.exists()
    # La durée totale doit être 240 / 30 = 8 secondes
    try:
        validator = FFprobeValidator()
        properties = validator.validate(
            result_path,
            expected_duration_seconds=8.0,
        )
        assert abs(properties["duration_seconds"] - 8.0) < 0.1
    except ValidatorError:
        pytest.skip("ffprobe not available")


# ============================================================================
# Tests d'erreurs : FFmpeg absent
# ============================================================================


def test_ffmpeg_encoder_detects_missing_ffmpeg(monkeypatch, tmp_path) -> None:
    """FFmpegEncoder rejette si FFmpeg est introuvable."""
    from unittest.mock import patch
    from PIL import Image

    # Créer une image de test
    dummy_image = tmp_path / "dummy.png"
    Image.new("RGB", (64, 96)).save(dummy_image)

    # Simuler shutil.which retournant None
    with patch("moneyprinter.encoder.shutil.which", return_value=None):
        encoder_input = EncoderInput(
            image_paths=(dummy_image,),
            frame_counts=(10,),
            width=64,
            height=96,
            fps=30,
            output_path=tmp_path / "out.mp4",
        )

        with pytest.raises(EncoderError, match="FFmpeg"):
            FFmpegEncoder(encoder_input)


# ============================================================================
# Tests pour le validateur
# ============================================================================


def test_ffprobe_validator_detects_missing_ffprobe(monkeypatch) -> None:
    """FFprobeValidator rejette si ffprobe est introuvable."""
    from unittest.mock import patch

    with patch("moneyprinter.validator.shutil.which", return_value=None):
        with pytest.raises(ValidatorError, match="ffprobe"):
            FFprobeValidator()


def test_ffprobe_validator_rejects_nonexistent_file(tmp_path) -> None:
    """FFprobeValidator rejette un fichier inexistant."""
    from unittest.mock import patch

    with patch("moneyprinter.validator.shutil.which", return_value="/usr/bin/ffprobe"):
        validator = FFprobeValidator()
        with pytest.raises(ValidatorError, match="n'existe pas"):
            validator.validate(tmp_path / "nonexistent.mp4")


# ============================================================================
# Tests d'acceptation complets avec demo.json
# ============================================================================


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_full_demo_encoding(tmp_path, demo_document, demo_timeline) -> None:
    """Test d'acceptation complet : encode demo.json en 1080×1920 @ 30s."""
    from moneyprinter.renderer import PillowSceneRenderer

    video = demo_document.video

    # Rendre les images
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    renderer = PillowSceneRenderer()
    image_paths: list[Path] = []

    for planned_scene in demo_timeline.planned_scenes:
        img = renderer.render(
            planned_scene,
            width=video.width,
            height=video.height,
            background_color=video.background_color,
            scene_count=len(video.scenes),
        )
        image_path = images_dir / f"scene_{planned_scene.index:02d}.png"
        img.save(image_path)
        image_paths.append(image_path)

    # Encoder
    output_path = tmp_path / "demo.mp4"
    frame_counts = tuple(scene.frame_count for scene in demo_timeline.planned_scenes)
    encoder_input = EncoderInput(
        image_paths=tuple(image_paths),
        frame_counts=frame_counts,
        width=video.width,
        height=video.height,
        fps=video.fps,
        output_path=output_path,
    )

    encoder = FFmpegEncoder(encoder_input)
    result_path = encoder.encode()

    # Valider
    validator = FFprobeValidator()
    properties = validator.validate(
        result_path,
        expected_codec="h264",
        expected_width=1080,
        expected_height=1920,
        expected_fps=30,
        expected_pixel_format="yuv420p",
        expected_frame_count=900,
        expected_duration_seconds=30.0,
    )

    # Assertions
    assert result_path.exists()
    assert int(properties["frame_count"]) == 900
    assert properties["width"] == 1080
    assert properties["height"] == 1920
    assert abs(properties["fps"] - 30.0) < 0.1
    assert properties["codec"] == "h264"
    assert properties["pixel_format"] == "yuv420p"
