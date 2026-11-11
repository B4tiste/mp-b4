"""Validation technique des fichiers vidéo MP4 via ffprobe."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class ValidatorError(ValueError):
    """Erreur lors de la validation vidéo."""


class FFprobeValidator:
    """Validateur technique pour fichiers vidéo MP4."""

    def __init__(self) -> None:
        """
        Initialise le validateur.

        Raises:
            ValidatorError: Si ffprobe est introuvable.
        """
        if shutil.which("ffprobe") is None:
            raise ValidatorError(
                "ffprobe n'a pas été trouvé dans le PATH. "
                "Veuillez installer FFmpeg (qui contient ffprobe)."
            )

    def validate(
        self,
        video_path: Path,
        expected_codec: str = "h264",
        expected_width: int | None = None,
        expected_height: int | None = None,
        expected_fps: int | None = None,
        expected_pixel_format: str = "yuv420p",
        expected_frame_count: int | None = None,
        expected_duration_seconds: float | None = None,
    ) -> dict:
        """
        Valide les propriétés techniques d'une vidéo.

        Args:
            video_path: Chemin du fichier MP4.
            expected_codec: Codec vidéo attendu (par défaut: h264).
            expected_width: Largeur attendue en pixels (optionnel).
            expected_height: Hauteur attendue en pixels (optionnel).
            expected_fps: FPS attendu (optionnel).
            expected_pixel_format: Format de pixel attendu (par défaut: yuv420p).
            expected_frame_count: Nombre exact de frames attendues (optionnel).
            expected_duration_seconds: Durée attendue en secondes (optionnel).

        Returns:
            Dictionnaire des propriétés validées.

        Raises:
            ValidatorError: Si une propriété ne correspond pas.
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise ValidatorError(f"le fichier vidéo n'existe pas : {video_path}")

        # Récupérer les métadonnées ffprobe
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-print_format",
                    "json",
                    "-show_streams",
                    "-show_format",
                    str(video_path),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            probe_data = json.loads(result.stdout)
        except subprocess.TimeoutExpired:
            raise ValidatorError(f"timeout ffprobe pour {video_path}")
        except subprocess.CalledProcessError as e:
            raise ValidatorError(
                f"ffprobe a échoué pour {video_path} : {e.stderr}"
            )
        except json.JSONDecodeError as e:
            raise ValidatorError(
                f"ffprobe a produit un JSON invalide : {e}"
            )

        # Chercher le flux vidéo
        video_stream = None
        for stream in probe_data.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
                break

        if video_stream is None:
            raise ValidatorError(f"aucun flux vidéo trouvé dans {video_path}")

        # Vérifier qu'il n'y a pas de flux audio
        audio_streams = [
            s for s in probe_data.get("streams", [])
            if s.get("codec_type") == "audio"
        ]
        if audio_streams:
            raise ValidatorError(
                f"{len(audio_streams)} flux audio trouvé(s), aucun attendu"
            )

        # Valider les propriétés
        properties = {
            "codec": video_stream.get("codec_name"),
            "width": video_stream.get("width"),
            "height": video_stream.get("height"),
            "pixel_format": video_stream.get("pix_fmt"),
            "fps": None,  # À calculer
            "frame_count": video_stream.get("nb_frames"),
            "duration_seconds": None,  # À calculer
        }

        # Calculer les FPS à partir de r_frame_rate ou avg_frame_rate
        fps_str = video_stream.get("r_frame_rate") or video_stream.get("avg_frame_rate")
        if fps_str:
            try:
                numerator, denominator = map(int, fps_str.split("/"))
                properties["fps"] = numerator / denominator
            except (ValueError, IndexError):
                logger.warning(f"Impossible de parser r_frame_rate : {fps_str}")

        # Calculer la durée à partir du format
        format_info = probe_data.get("format", {})
        if "duration" in format_info:
            try:
                properties["duration_seconds"] = float(format_info["duration"])
            except (ValueError, TypeError):
                logger.warning(f"Impossible de parser duration : {format_info.get('duration')}")

        # Vérifications
        if expected_codec and properties["codec"] != expected_codec:
            raise ValidatorError(
                f"codec : attendu {expected_codec}, reçu {properties['codec']}"
            )

        if expected_width and properties["width"] != expected_width:
            raise ValidatorError(
                f"largeur : attendu {expected_width}, reçu {properties['width']}"
            )

        if expected_height and properties["height"] != expected_height:
            raise ValidatorError(
                f"hauteur : attendu {expected_height}, reçu {properties['height']}"
            )

        if expected_pixel_format and properties["pixel_format"] != expected_pixel_format:
            raise ValidatorError(
                f"format de pixel : attendu {expected_pixel_format}, reçu {properties['pixel_format']}"
            )

        if expected_fps and properties["fps"]:
            # Tolérance de 0.1 FPS pour les imprécisions flottantes
            if abs(properties["fps"] - expected_fps) > 0.1:
                raise ValidatorError(
                    f"FPS : attendu {expected_fps}, reçu {properties['fps']}"
                )

        if expected_frame_count:
            if properties["frame_count"] is None:
                raise ValidatorError(
                    f"nombre de frames : impossible à déterminer via ffprobe"
                )
            if int(properties["frame_count"]) != expected_frame_count:
                raise ValidatorError(
                    f"nombre de frames : attendu {expected_frame_count}, reçu {int(properties['frame_count'])}"
                )

        if expected_duration_seconds and properties["duration_seconds"]:
            # Tolérance de 0.01 secondes
            if abs(properties["duration_seconds"] - expected_duration_seconds) > 0.01:
                raise ValidatorError(
                    f"durée : attendu {expected_duration_seconds}s, reçu {properties['duration_seconds']}s"
                )

        return properties
