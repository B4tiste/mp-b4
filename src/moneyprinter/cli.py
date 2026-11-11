"""Interface en ligne de commande de MoneyPrinter."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from decimal import Decimal
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from moneyprinter.schemas import (
    MVPProfileError,
    VideoDocument,
    format_duration,
    validate_mvp_profile,
)

logger = logging.getLogger(__name__)


def load_and_validate_json(json_path: Path) -> VideoDocument:
    """
    Charge et valide un fichier JSON pour la vidéo MoneyPrinter.

    Args:
        json_path: Chemin vers le fichier JSON.

    Returns:
        Document vidéo validé.

    Raises:
        OSError: Si le fichier ne peut pas être lu.
        UnicodeDecodeError: Si le fichier n'est pas UTF-8 valide.
        json.JSONDecodeError: Si le JSON est malformé.
        ValidationError: Si le schéma ou le profil MVP est invalide.
    """
    json_path = Path(json_path)
    source = json_path.read_text(encoding="utf-8")
    payload = json.loads(source, parse_float=Decimal)
    document = VideoDocument.model_validate(payload)
    validate_mvp_profile(document)
    return document


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="moneyprinter",
        description="Outils de validation de scripts vidéo MoneyPrinter.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser(
        "validate",
        help="valide un fichier JSON selon le schéma et le profil MVP",
    )
    validate_parser.add_argument("json_path", type=Path, help="chemin du script JSON")
    return parser


def _format_validation_error(error: ValidationError) -> str:
    messages = []
    for detail in error.errors():
        location = ".".join(str(part) for part in detail["loc"]) or "document"
        messages.append(f"{location}: {detail['msg']}")
    return "\n".join(messages)


def _validate_file(json_path: Path) -> int:
    try:
        document = load_and_validate_json(json_path)
    except (OSError, UnicodeDecodeError) as error:
        logger.error("Impossible de lire '%s': %s", json_path, error)
        return 1
    except json.JSONDecodeError as error:
        logger.error(
            "JSON malformé dans '%s' (ligne %s, colonne %s): %s",
            json_path,
            error.lineno,
            error.colno,
            error.msg,
        )
        return 1
    except ValidationError as error:
        logger.error(
            "Schéma invalide dans '%s':\n%s",
            json_path,
            _format_validation_error(error),
        )
        return 1
    except MVPProfileError as error:
        logger.error("Profil MVP invalide dans '%s': %s", json_path, error)
        return 1

    video = document.video
    print(f"Script valide : {document.title}")
    print(f"Format : {video.width} × {video.height} à {video.fps} FPS")
    print(f"Nombre de scènes : {len(video.scenes)}")
    print(f"Durée totale : {format_duration(video.total_duration_seconds)} secondes")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Exécute la CLI et retourne un code de sortie."""
    logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")
    args = _build_parser().parse_args(argv)

    if args.command == "validate":
        return _validate_file(args.json_path)

    return 2


if __name__ == "__main__":
    sys.exit(main())
