"""Interface en ligne de commande de MoneyPrinter."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from moneyprinter.pipeline import PipelineError, PipelineResult, render_pipeline
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
        description="Outils de validation et de génération de vidéos MoneyPrinter.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Commande validate
    validate_parser = subparsers.add_parser(
        "validate",
        help="valide un fichier JSON selon le schéma et le profil MVP",
    )
    validate_parser.add_argument("json_path", type=Path, help="chemin du script JSON")

    # Commande render
    render_parser = subparsers.add_parser(
        "render",
        help="génère une vidéo MP4 à partir d'un script JSON",
    )
    render_parser.add_argument("json_path", type=Path, help="chemin du script JSON")
    render_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="chemin de sortie du fichier MP4 (défaut : data/output/<titre>.mp4)",
    )
    render_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="remplace le fichier de sortie s'il existe",
    )
    render_parser.add_argument(
        "--verbose",
        action="store_true",
        help="active les logs détaillés (niveau DEBUG)",
    )

    return parser


def _format_validation_error(error: ValidationError) -> str:
    messages = []
    for detail in error.errors():
        location = ".".join(str(part) for part in detail["loc"]) or "document"
        messages.append(f"{location}: {detail['msg']}")
    return "\n".join(messages)


def _format_summary(result: PipelineResult, elapsed_seconds: float) -> str:
    """Formate un résumé de la génération."""
    lines = [
        "",
        "=" * 70,
        "✓ GÉNÉRATION RÉUSSIE",
        "=" * 70,
        f"Fichier de sortie : {result.output_path}",
        f"Taille : {result.file_size_mb:.1f} MB",
        f"Format : {result.width}×{result.height} @ {int(result.fps)} FPS",
        f"Frames : {result.frame_count}",
        f"Durée : {result.total_seconds:.1f}s",
        f"Temps de génération : {elapsed_seconds:.1f}s",
        "=" * 70,
        "",
    ]
    return "\n".join(lines)


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


def _render_file(
    json_path: Path,
    output_path: Path | None,
    overwrite: bool,
    verbose: bool,
) -> int:
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

    # Déterminer le chemin de sortie
    if output_path is None:
        output_dir = Path("data/output")
        output_path = output_dir / f"{document.title}.mp4"

    output_path = Path(output_path)

    try:
        logger.info("Démarrage de la génération de la vidéo...")
        start_time = time.time()

        result = render_pipeline(document, output_path, overwrite=overwrite)

        elapsed = time.time() - start_time

        # Ajouter l'attribut fps au résultat pour l'affichage
        result.__dict__["fps"] = document.video.fps

        print(_format_summary(result, elapsed))
        return 0

    except PipelineError as error:
        logger.error("Erreur pipeline : %s", error)
        return 1
    except Exception as error:
        logger.error("Erreur inattendue : %s", error)
        if verbose:
            raise
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    """Exécute la CLI et retourne un code de sortie."""
    args = _build_parser().parse_args(argv)

    # Configurer le logging
    if args.command == "render" and hasattr(args, "verbose") and args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    else:
        logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")

    if args.command == "validate":
        return _validate_file(args.json_path)
    elif args.command == "render":
        return _render_file(
            args.json_path,
            args.output,
            args.overwrite,
            getattr(args, "verbose", False),
        )

    return 2


if __name__ == "__main__":
    sys.exit(main())

