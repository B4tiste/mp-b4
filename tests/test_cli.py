import json
from pathlib import Path

from moneyprinter.cli import main

DEMO_PATH = Path(__file__).parents[1] / "examples" / "demo.json"


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
