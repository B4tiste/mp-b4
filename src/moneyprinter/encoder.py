"""Encodeur vidéo FFmpeg pour transformer des images PNG en MP4 H.264."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)


class EncoderError(ValueError):
    """Erreur lors de l'encodage vidéo."""


@dataclass(frozen=True)
class EncoderInput:
    """Configuration d'entrée pour l'encodeur FFmpeg."""

    image_paths: tuple[Path, ...]
    frame_counts: tuple[int, ...]
    width: int
    height: int
    fps: int
    output_path: Path
    overwrite: bool = False

    def __post_init__(self) -> None:
        """Valide l'intégrité des entrées."""
        if not self.image_paths:
            raise EncoderError("la liste des images ne peut pas être vide")
        if not self.frame_counts:
            raise EncoderError("la liste des frame_counts ne peut pas être vide")
        if len(self.image_paths) != len(self.frame_counts):
            raise EncoderError(
                f"nombre d'images ({len(self.image_paths)}) ne correspond pas "
                f"au nombre de frame_counts ({len(self.frame_counts)})"
            )
        if self.width <= 0:
            raise EncoderError(f"la largeur doit être > 0 (reçu : {self.width})")
        if self.height <= 0:
            raise EncoderError(f"la hauteur doit être > 0 (reçu : {self.height})")
        if self.fps <= 0:
            raise EncoderError(f"le FPS doit être > 0 (reçu : {self.fps})")

        for i, frame_count in enumerate(self.frame_counts):
            if frame_count <= 0:
                raise EncoderError(
                    f"la scène {i} a un frame_count invalide : {frame_count} "
                    "(doit être > 0)"
                )

        for i, image_path in enumerate(self.image_paths):
            image_path = Path(image_path)
            if not image_path.exists():
                raise EncoderError(f"l'image {i} n'existe pas : {image_path}")
            if not image_path.is_file():
                raise EncoderError(f"l'image {i} n'est pas un fichier : {image_path}")


class FFmpegEncoder:
    """Encodeur vidéo MP4 H.264 via FFmpeg, à partir d'images PNG statiques."""

    # Paramètres FFmpeg constants
    PIXEL_FORMAT = "yuv420p"
    CODEC = "libx264"
    PRESET = "veryfast"
    CRF = 23
    MOVFLAGS = "faststart"

    def __init__(self, encoder_input: EncoderInput) -> None:
        """
        Initialise l'encodeur avec la configuration d'entrée.

        Args:
            encoder_input: Configuration d'entrée contenant images, frames, résolution, etc.

        Raises:
            EncoderError: Si la configuration est invalide ou si FFmpeg est introuvable.
        """
        self.input = encoder_input
        self._validate_ffmpeg_available()

    def _validate_ffmpeg_available(self) -> None:
        """Vérifie que FFmpeg est disponible dans le système."""
        if shutil.which("ffmpeg") is None:
            raise EncoderError(
                "FFmpeg n'a pas été trouvé dans le PATH. "
                "Veuillez installer FFmpeg."
            )

    def encode(self) -> Path:
        """
        Encode les images PNG en une vidéo MP4 H.264.

        Stratégie :
        1. Créer un segment vidéo temporaire pour chaque image.
        2. Répéter chaque image exactement frame_count fois au FPS donné.
        3. Concaténer tous les segments via le concat demuxer FFmpeg.
        4. Produire le MP4 final avec copie des flux (sans réencodage).
        5. Valider le nombre exact de frames.

        Returns:
            Le chemin du fichier MP4 créé.

        Raises:
            EncoderError: Si l'encodage échoue ou si le résultat est invalide.
        """
        # Vérifier le fichier de sortie
        output_path = Path(self.input.output_path)
        if output_path.exists() and not self.input.overwrite:
            raise EncoderError(
                f"le fichier de sortie existe déjà : {output_path} "
                "(utilisez overwrite=True pour le remplacer)"
            )

        # Créer un répertoire temporaire
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            try:
                # Étape 1 : Créer les segments vidéo temporaires
                segment_paths = self._create_segments(tmpdir_path)

                # Étape 2 : Créer le fichier de concaténation
                concat_file_path = self._create_concat_file(tmpdir_path, segment_paths)

                # Étape 3 : Concaténer les segments en un fichier temporaire
                temp_output = tmpdir_path / "temp_output.mp4"
                self._concatenate_segments(concat_file_path, temp_output)

                # Étape 4 : Déplacer le résultat vers la destination
                # Assurer que le répertoire parent existe
                output_path.parent.mkdir(parents=True, exist_ok=True)
                temp_output.replace(output_path)

                logger.info(f"Encodage réussi : {output_path}")
                return output_path

            except EncoderError:
                raise
            except Exception as e:
                raise EncoderError(f"erreur inattendue lors de l'encodage : {e}") from e

    def _create_segments(self, tmpdir: Path) -> list[Path]:
        """
        Crée un segment vidéo temporaire pour chaque image.

        Args:
            tmpdir: Répertoire temporaire pour les segments.

        Returns:
            Liste ordonnée des chemins des segments créés.

        Raises:
            EncoderError: Si un segment ne peut pas être créé.
        """
        segment_paths: list[Path] = []

        for i, (image_path, frame_count) in enumerate(
            zip(self.input.image_paths, self.input.frame_counts)
        ):
            segment_path = tmpdir / f"segment_{i:04d}.mp4"

            # Calculer la durée exacte en secondes
            duration_seconds = frame_count / self.input.fps

            # Commande FFmpeg pour créer un segment
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-loop",
                "1",
                "-i",
                str(image_path),
                "-c:v",
                self.CODEC,
                "-pix_fmt",
                self.PIXEL_FORMAT,
                "-preset",
                self.PRESET,
                "-crf",
                str(self.CRF),
                "-r",
                str(self.input.fps),
                "-t",
                str(duration_seconds),
                "-vf",
                f"scale={self.input.width}:{self.input.height}:force_original_aspect_ratio=decrease,pad={self.input.width}:{self.input.height}:(ow-iw)/2:(oh-ih)/2",
                str(segment_path),
            ]

            try:
                result = subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                logger.debug(f"Segment créé : {segment_path}")
                segment_paths.append(segment_path)
            except subprocess.TimeoutExpired:
                raise EncoderError(
                    f"timeout lors de la création du segment {i} (> 300s)"
                )
            except subprocess.CalledProcessError as e:
                raise EncoderError(
                    f"FFmpeg a échoué pour le segment {i} : "
                    f"{e.stderr or e.stdout}"
                )

        return segment_paths

    def _create_concat_file(self, tmpdir: Path, segment_paths: list[Path]) -> Path:
        """
        Crée un fichier de concaténation au format FFmpeg.

        Args:
            tmpdir: Répertoire temporaire.
            segment_paths: Liste des chemins des segments.

        Returns:
            Chemin du fichier de concaténation.
        """
        concat_file = tmpdir / "concat.txt"
        lines = [f"file '{segment_path.resolve()}'" for segment_path in segment_paths]
        concat_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.debug(f"Fichier de concaténation créé : {concat_file}")
        return concat_file

    def _concatenate_segments(self, concat_file: Path, output_path: Path) -> None:
        """
        Concatène les segments via le concat demuxer FFmpeg.

        Args:
            concat_file: Chemin du fichier de concaténation.
            output_path: Chemin du fichier de sortie.

        Raises:
            EncoderError: Si la concaténation échoue.
        """
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            "-movflags",
            self.MOVFLAGS,
            str(output_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=300,
            )
            logger.debug(f"Concaténation réussie : {output_path}")
        except subprocess.TimeoutExpired:
            raise EncoderError("timeout lors de la concaténation (> 300s)")
        except subprocess.CalledProcessError as e:
            raise EncoderError(
                f"FFmpeg a échoué lors de la concaténation : "
                f"{e.stderr or e.stdout}"
            )

        if not output_path.exists():
            raise EncoderError(f"le fichier final n'a pas été créé : {output_path}")
