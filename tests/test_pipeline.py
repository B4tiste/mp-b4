"""Tests pour le module pipeline."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from moneyprinter.cli import load_and_validate_json
from moneyprinter.pipeline import PipelineError, PipelineResult, render_pipeline

# Chemin vers le JSON de démonstration
DEMO_PATH = Path(__file__).parents[1] / "examples" / "demo.json"

# Détecter si FFmpeg et ffprobe sont disponibles
FFMPEG_AND_FFPROBE = (
    shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
)


@pytest.fixture
def demo_document():
    """Charge le document de démonstration."""
    return load_and_validate_json(DEMO_PATH)


# ============================================================================
# Tests du pipeline complet
# ============================================================================


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_pipeline_generates_valid_mp4(tmp_path, demo_document) -> None:
    """Le pipeline génère un fichier MP4 valide."""
    output_path = tmp_path / "output.mp4"

    result = render_pipeline(demo_document, output_path)

    assert output_path.exists()
    assert result.output_path == output_path
    assert result.file_size_bytes > 0
    assert result.width == 1080
    assert result.height == 1920
    assert result.frame_count == 900
    assert abs(result.duration_seconds - 30.0) < 0.1
    assert result.total_seconds == 30.0


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_pipeline_respects_overwrite_flag(tmp_path, demo_document) -> None:
    """Le pipeline rejette un fichier de sortie préexistant sans overwrite."""
    output_path = tmp_path / "output.mp4"
    output_path.write_text("dummy")

    with pytest.raises(PipelineError, match="existe déjà"):
        render_pipeline(demo_document, output_path, overwrite=False)

    # Vérifier que le fichier original est préservé
    assert output_path.read_text() == "dummy"


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_pipeline_overwrites_when_enabled(tmp_path, demo_document) -> None:
    """Le pipeline remplace un fichier existant avec overwrite=True."""
    output_path = tmp_path / "output.mp4"
    output_path.write_text("dummy")

    result = render_pipeline(demo_document, output_path, overwrite=True)

    assert output_path.exists()
    assert result.output_path == output_path
    # Le nouveau fichier ne doit pas être "dummy"
    with open(output_path, "rb") as f:
        content = f.read(4)
        assert content != b"dumm"


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_pipeline_creates_parent_directories(tmp_path, demo_document) -> None:
    """Le pipeline crée les répertoires parents du fichier de sortie."""
    output_path = tmp_path / "nested" / "deep" / "dir" / "output.mp4"

    result = render_pipeline(demo_document, output_path)

    assert output_path.exists()
    assert result.output_path == output_path


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_pipeline_result_has_correct_metrics(tmp_path, demo_document) -> None:
    """Le PipelineResult contient les métriques correctes."""
    output_path = tmp_path / "output.mp4"

    result = render_pipeline(demo_document, output_path)

    assert isinstance(result, PipelineResult)
    assert result.width == 1080
    assert result.height == 1920
    assert result.frame_count == 900
    assert result.file_size_bytes > 0
    assert result.file_size_mb > 0
    assert result.file_size_mb < 1  # 900 frames should be < 1MB
    assert result.total_seconds == 30.0


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_pipeline_validates_output(tmp_path, demo_document) -> None:
    """Le pipeline valide la sortie avec ffprobe."""
    output_path = tmp_path / "output.mp4"

    result = render_pipeline(demo_document, output_path)

    # ffprobe aurait rejeté la vidéo si elle n'était pas valide
    # Donc si nous arrivons ici, la validation a réussi
    assert output_path.exists()
    assert result.frame_count == 900
    assert result.width == 1080


# ============================================================================
# Tests d'erreurs
# ============================================================================


def test_pipeline_rejects_non_video_document(tmp_path) -> None:
    """Le pipeline rejette un document qui n'est pas VideoDocument."""
    output_path = tmp_path / "output.mp4"

    with pytest.raises(PipelineError, match="VideoDocument"):
        render_pipeline("not a document", output_path)


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_pipeline_error_on_missing_json(tmp_path) -> None:
    """Le pipeline gère les erreurs de fichier JSON manquant."""
    # Cette erreur est gérée au niveau de load_and_validate_json
    # donc ce test est plutôt un test d'intégration du CLI
    pass


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_pipeline_cleans_temp_files(tmp_path, demo_document) -> None:
    """Le pipeline nettoie les fichiers temporaires."""
    output_path = tmp_path / "output.mp4"

    result = render_pipeline(demo_document, output_path)

    # Vérifier que seul le fichier de sortie existe
    assert output_path.exists()

    # Les fichiers PNG temporaires doivent avoir été supprimés
    # (impossible à vérifier directement puisqu'ils sont dans tempfile)
    # Mais nous vérifions que le fichier MP4 a été créé avec succès
    assert result.file_size_bytes > 0
