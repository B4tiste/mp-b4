"""Pipeline complet : JSON → Timeline → PNG → MP4 → Validation."""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

from moneyprinter.encoder import EncoderError, EncoderInput, FFmpegEncoder
from moneyprinter.renderer import PillowSceneRenderer, RendererError
from moneyprinter.timeline import Timeline, TimelineError, build_timeline
from moneyprinter.validator import FFprobeValidator, ValidatorError

logger = logging.getLogger(__name__)


class PipelineError(ValueError):
    """Erreur lors de l'exécution du pipeline."""


@dataclass(frozen=True)
class PipelineResult:
    """Résultat de l'exécution du pipeline."""

    output_path: Path
    duration_seconds: float
    width: int
    height: int
    frame_count: int
    file_size_bytes: int
    total_seconds: float

    @property
    def file_size_mb(self) -> float:
        """Taille du fichier en MB."""
        return self.file_size_bytes / (1024 * 1024)


def render_pipeline(
    document: object,
    output_path: Path,
    overwrite: bool = False,
) -> PipelineResult:
    """
    Exécute le pipeline complet : JSON → Timeline → PNG → MP4 → Validation.

    Args:
        document: Document vidéo validé (VideoDocument).
        output_path: Chemin de sortie du fichier MP4.
        overwrite: Si True, remplace le fichier de sortie existant.

    Returns:
        PipelineResult contenant les métriques de la vidéo.

    Raises:
        PipelineError: Si l'une des étapes échoue.
    """
    try:
        # Import local pour éviter la dépendance circulaire
        from moneyprinter.schemas import VideoDocument

        if not isinstance(document, VideoDocument):
            raise PipelineError("document doit être une instance VideoDocument")

        video = document.video
        output_path = Path(output_path)

        # Vérifier si le fichier de sortie existe
        if output_path.exists() and not overwrite:
            raise PipelineError(
                f"le fichier de sortie existe déjà : {output_path} "
                "(utilisez --overwrite pour le remplacer)"
            )

        # ====================================================================
        # Étape 1 : Construire la timeline
        # ====================================================================
        logger.info("Construction de la timeline...")
        timeline = build_timeline(video)
        logger.debug(f"  Total frames : {timeline.total_frame_count}")

        # ====================================================================
        # Étape 2 : Rendre les images PNG dans un répertoire temporaire
        # ====================================================================
        logger.info("Rendu des images PNG...")
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            renderer = PillowSceneRenderer()
            image_paths: list[Path] = []

            for planned_scene in timeline.planned_scenes:
                img = renderer.render(
                    planned_scene=planned_scene,
                    width=video.width,
                    height=video.height,
                    background_color=video.background_color,
                    scene_count=len(video.scenes),
                )

                scene_index = planned_scene.index + 1
                image_path = temp_dir_path / f"scene_{scene_index:02d}.png"
                img.save(image_path)
                image_paths.append(image_path)
                logger.debug(f"  Rendu : {image_path}")

            logger.info(f"✓ {len(image_paths)} images rendues")

            # ====================================================================
            # Étape 3 : Encoder la vidéo MP4
            # ====================================================================
            logger.info("Encodage de la vidéo MP4...")

            # Créer les répertoires parents si nécessaire
            output_path.parent.mkdir(parents=True, exist_ok=True)

            frame_counts = tuple(scene.frame_count for scene in timeline.planned_scenes)
            encoder_input = EncoderInput(
                image_paths=tuple(image_paths),
                frame_counts=frame_counts,
                width=video.width,
                height=video.height,
                fps=video.fps,
                output_path=output_path,
                overwrite=True,  # On contrôle déjà l'overwrite au-dessus
            )

            encoder = FFmpegEncoder(encoder_input)
            result_mp4 = encoder.encode()
            file_size = result_mp4.stat().st_size

            logger.info(f"✓ Vidéo encodée : {result_mp4}")
            logger.info(f"  Taille : {file_size / 1024 / 1024:.1f} MB")

            # ====================================================================
            # Étape 4 : Valider le résultat avec ffprobe
            # ====================================================================
            logger.info("Validation de la vidéo...")
            validator = FFprobeValidator()
            properties = validator.validate(
                result_mp4,
                expected_codec="h264",
                expected_width=video.width,
                expected_height=video.height,
                expected_fps=video.fps,
                expected_pixel_format="yuv420p",
                expected_frame_count=timeline.total_frame_count,
                expected_duration_seconds=float(timeline.total_duration_seconds),
            )
            logger.info("✓ Validation réussie")

        # ====================================================================
        # Étape 5 : Retourner les résultats
        # ====================================================================
        return PipelineResult(
            output_path=result_mp4,
            duration_seconds=properties["duration_seconds"],
            width=properties["width"],
            height=properties["height"],
            frame_count=int(properties["frame_count"]),
            file_size_bytes=file_size,
            total_seconds=float(timeline.total_duration_seconds),
        )

    except TimelineError as e:
        raise PipelineError(f"Erreur timeline : {e}") from e
    except RendererError as e:
        raise PipelineError(f"Erreur renderer : {e}") from e
    except EncoderError as e:
        raise PipelineError(f"Erreur encodeur : {e}") from e
    except ValidatorError as e:
        raise PipelineError(f"Erreur validation : {e}") from e
