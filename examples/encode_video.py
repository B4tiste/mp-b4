#!/usr/bin/env python3
"""
Script de démonstration : génère une vidéo MP4 H.264 à partir de demo.json.

Étapes :
1. Charger et valider demo.json
2. Construire la timeline
3. Rendre les PNG pour chaque scène
4. Encoder la vidéo MP4 avec FFmpegEncoder
5. Valider le résultat avec ffprobe
6. Afficher un résumé
"""

import logging
from pathlib import Path

from moneyprinter.cli import load_and_validate_json
from moneyprinter.encoder import EncoderError, EncoderInput, FFmpegEncoder
from moneyprinter.renderer import PillowSceneRenderer, RendererError
from moneyprinter.timeline import build_timeline, TimelineError
from moneyprinter.validator import FFprobeValidator, ValidatorError

# Configure le logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main(
    demo_json_path: str | Path = "examples/demo.json",
    output_mp4_path: str | Path = "data/output/demo.mp4",
) -> None:
    """
    Charge demo.json, construit la timeline, rend les PNG, encode la vidéo.

    Args:
        demo_json_path: Chemin vers demo.json.
        output_mp4_path: Chemin vers le fichier MP4 de sortie.
    """
    demo_json_path = Path(demo_json_path)
    output_mp4_path = Path(output_mp4_path)

    try:
        # ====================================================================
        # Étape 1 : Charger et valider le document JSON
        # ====================================================================
        logger.info(f"Chargement du JSON : {demo_json_path}")
        document = load_and_validate_json(demo_json_path)
        video = document.video
        logger.info(f"✓ Document valide : {document.title}")
        logger.info(f"  Format : {video.width}×{video.height} à {video.fps} FPS")
        logger.info(f"  Durée : {document.video.total_duration_seconds} secondes")
        logger.info(f"  Scènes : {len(video.scenes)}")

        # ====================================================================
        # Étape 2 : Construire la timeline
        # ====================================================================
        logger.info("Construction de la timeline...")
        timeline = build_timeline(video)
        logger.info(f"✓ Timeline construite")
        logger.info(f"  Total frames : {timeline.total_frame_count}")
        for i, scene in enumerate(timeline.scenes, 1):
            logger.info(
                f"  Scène {i} : frames {scene.start_frame}-{scene.end_frame} "
                f"({scene.frame_count} frames)"
            )

        # ====================================================================
        # Étape 3 : Rendre les images PNG
        # ====================================================================
        logger.info("Rendu des images PNG...")
        scenes_dir = Path("data/output/scenes")
        scenes_dir.mkdir(parents=True, exist_ok=True)

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
            image_path = scenes_dir / f"scene_{scene_index:02d}.png"
            img.save(image_path)
            image_paths.append(image_path)
            logger.info(f"  ✓ Rendu : {image_path}")

        logger.info(f"✓ {len(image_paths)} images rendues")

        # ====================================================================
        # Étape 4 : Encoder la vidéo MP4
        # ====================================================================
        logger.info("Encodage de la vidéo MP4...")

        # Préparer les entrées de l'encodeur
        frame_counts = tuple(scene.frame_count for scene in timeline.planned_scenes)
        encoder_input = EncoderInput(
            image_paths=tuple(image_paths),
            frame_counts=frame_counts,
            width=video.width,
            height=video.height,
            fps=video.fps,
            output_path=output_mp4_path,
            overwrite=True,
        )

        encoder = FFmpegEncoder(encoder_input)
        output_path = encoder.encode()
        logger.info(f"✓ Vidéo encodée : {output_path}")
        logger.info(f"  Taille : {output_path.stat().st_size / 1024 / 1024:.1f} MB")

        # ====================================================================
        # Étape 5 : Valider le résultat avec ffprobe
        # ====================================================================
        logger.info("Validation de la vidéo...")
        try:
            validator = FFprobeValidator()
            properties = validator.validate(
                output_path,
                expected_codec="h264",
                expected_width=video.width,
                expected_height=video.height,
                expected_fps=video.fps,
                expected_pixel_format="yuv420p",
                expected_frame_count=timeline.total_frame_count,
                expected_duration_seconds=float(timeline.total_duration_seconds),
            )
            logger.info("✓ Validation réussie")
            logger.info(f"  Codec : {properties['codec']}")
            logger.info(f"  Résolution : {properties['width']}×{properties['height']}")
            logger.info(f"  FPS : {properties['fps']:.2f}")
            logger.info(f"  Format pixel : {properties['pixel_format']}")
            logger.info(f"  Frames : {properties['frame_count']}")
            logger.info(f"  Durée : {properties['duration_seconds']:.2f}s")

        except ValidatorError as e:
            logger.error(f"✗ Validation échouée : {e}")
            return

        # ====================================================================
        # Étape 6 : Résumé final
        # ====================================================================
        logger.info("\n" + "=" * 70)
        logger.info("✓ DÉMONSTRATION RÉUSSIE")
        logger.info("=" * 70)
        logger.info(f"Fichier de sortie : {output_path}")
        logger.info(f"Taille : {output_path.stat().st_size / 1024 / 1024:.1f} MB")
        logger.info(f"Format : {video.width}×{video.height} @ {video.fps} FPS")
        logger.info(f"Frames : {timeline.total_frame_count}")
        logger.info(f"Durée : {timeline.total_duration_seconds}s")
        logger.info("=" * 70)

    except TimelineError as e:
        logger.error(f"✗ Erreur timeline : {e}")
        return
    except RendererError as e:
        logger.error(f"✗ Erreur renderer : {e}")
        return
    except EncoderError as e:
        logger.error(f"✗ Erreur encodeur : {e}")
        return
    except Exception as e:
        logger.error(f"✗ Erreur inattendue : {e}")
        raise


if __name__ == "__main__":
    main()
