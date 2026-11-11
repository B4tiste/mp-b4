import json
import shutil
from pathlib import Path

from moneyprinter.cli import main

DEMO_PATH = Path(__file__).parents[1] / "examples" / "demo.json"

# Détecter si FFmpeg et ffprobe sont disponibles
FFMPEG_AND_FFPROBE = (
    shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
)

import pytest


def test_cli_returns_success_for_demo(capsys) -> None:
    exit_code = main(["validate", str(DEMO_PATH)])

    output = capsys.readouterr()

    assert exit_code == 0
    assert "Nombre de scènes : 4" in output.out
    assert "Durée totale : 30 secondes" in output.out


def test_cli_returns_error_for_malformed_json(tmp_path, caplog) -> None:
    json_path = tmp_path / "malformed.json"
    json_path.write_text('{"schema_version":', encoding="utf-8")

    exit_code = main(["validate", str(json_path)])

    assert exit_code != 0
    assert "JSON malformé" in caplog.text
    assert "Traceback" not in caplog.text


def test_cli_returns_error_for_missing_file(tmp_path, caplog) -> None:
    json_path = tmp_path / "missing.json"

    exit_code = main(["validate", str(json_path)])

    assert exit_code != 0
    assert "Impossible de lire" in caplog.text


def test_cli_reports_schema_validation_error(tmp_path, caplog) -> None:
    payload = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
    del payload["video"]["scenes"][0]["headline"]
    json_path = tmp_path / "missing-field.json"
    json_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code = main(["validate", str(json_path)])

    assert exit_code != 0
    assert "headline" in caplog.text
    assert "Traceback" not in caplog.text


# ============================================================================
# Tests de la commande render
# ============================================================================


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_cli_render_generates_mp4(tmp_path, capsys) -> None:
    """La commande render génère un fichier MP4 valide."""
    output_path = tmp_path / "output.mp4"

    exit_code = main(["render", str(DEMO_PATH), "--output", str(output_path)])

    assert exit_code == 0
    assert output_path.exists()
    assert output_path.stat().st_size > 0

    output = capsys.readouterr()
    assert "✓ GÉNÉRATION RÉUSSIE" in output.out
    assert "1080×1920" in output.out
    assert "900" in output.out


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_cli_render_creates_default_output(tmp_path, monkeypatch, capsys) -> None:
    """La commande render crée un fichier par défaut si --output n'est pas spécifié."""
    # Changer le répertoire de travail pour contrôler le chemin par défaut
    monkeypatch.chdir(tmp_path)

    exit_code = main(["render", str(DEMO_PATH)])

    assert exit_code == 0
    # Le chemin par défaut est data/output/<titre>.mp4
    # Le titre dans demo.json est "Pourquoi une année dure environ 365 jours"
    default_output = tmp_path / "data" / "output" / "Pourquoi une année dure environ 365 jours.mp4"
    assert default_output.exists()


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_cli_render_rejects_existing_file_without_overwrite(
    tmp_path, capsys, caplog
) -> None:
    """La commande render rejette un fichier existant sans --overwrite."""
    output_path = tmp_path / "output.mp4"
    output_path.write_text("dummy")

    exit_code = main(
        ["render", str(DEMO_PATH), "--output", str(output_path)]
    )

    assert exit_code != 0
    # Le fichier original doit être préservé
    assert output_path.read_text() == "dummy"
    assert "existe déjà" in caplog.text


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_cli_render_overwrites_with_flag(tmp_path, capsys) -> None:
    """La commande render remplace un fichier existant avec --overwrite."""
    output_path = tmp_path / "output.mp4"
    output_path.write_text("dummy")

    exit_code = main(
        [
            "render",
            str(DEMO_PATH),
            "--output",
            str(output_path),
            "--overwrite",
        ]
    )

    assert exit_code == 0
    assert output_path.exists()
    # Le nouveau fichier ne doit pas être "dummy"
    with open(output_path, "rb") as f:
        content = f.read(4)
        assert content != b"dumm"


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_cli_render_creates_parent_directories(tmp_path, capsys) -> None:
    """La commande render crée les répertoires parents."""
    output_path = tmp_path / "nested" / "deep" / "dir" / "output.mp4"

    exit_code = main(["render", str(DEMO_PATH), "--output", str(output_path)])

    assert exit_code == 0
    assert output_path.exists()
    assert output_path.parent.exists()


def test_cli_render_rejects_missing_json(tmp_path, caplog) -> None:
    """La commande render rejette un fichier JSON manquant."""
    json_path = tmp_path / "missing.json"
    output_path = tmp_path / "output.mp4"

    exit_code = main(["render", str(json_path), "--output", str(output_path)])

    assert exit_code != 0
    assert "Impossible de lire" in caplog.text


def test_cli_render_rejects_invalid_json(tmp_path, caplog) -> None:
    """La commande render rejette un JSON invalide."""
    json_path = tmp_path / "invalid.json"
    json_path.write_text('{"invalid": json}', encoding="utf-8")
    output_path = tmp_path / "output.mp4"

    exit_code = main(["render", str(json_path), "--output", str(output_path)])

    assert exit_code != 0
    assert "JSON malformé" in caplog.text


def test_cli_render_rejects_invalid_schema(tmp_path, caplog) -> None:
    """La commande render rejette un schéma invalide."""
    payload = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
    del payload["video"]["scenes"][0]["headline"]
    json_path = tmp_path / "invalid-schema.json"
    json_path.write_text(json.dumps(payload), encoding="utf-8")
    output_path = tmp_path / "output.mp4"

    exit_code = main(["render", str(json_path), "--output", str(output_path)])

    assert exit_code != 0
    assert "headline" in caplog.text


@pytest.mark.skipif(
    not FFMPEG_AND_FFPROBE,
    reason="Requires FFmpeg and ffprobe",
)
def test_cli_render_shows_summary(tmp_path, capsys) -> None:
    """La commande render affiche un résumé complet."""
    output_path = tmp_path / "output.mp4"

    exit_code = main(["render", str(DEMO_PATH), "--output", str(output_path)])

    assert exit_code == 0

    output = capsys.readouterr()
    assert "✓ GÉNÉRATION RÉUSSIE" in output.out
    assert "Fichier de sortie" in output.out
    assert "Taille" in output.out
    assert "Format" in output.out
    assert "Frames" in output.out
    assert "Durée" in output.out
    assert "Temps de génération" in output.out

