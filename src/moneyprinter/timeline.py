"""Planification temporelle des scènes sans approximation ni arrondi silencieux."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from moneyprinter.schemas import Scene, Video


class TimelineError(ValueError):
    """Erreur lors de la construction de la timeline."""


@dataclass(frozen=True)
class PlannedScene:
    """Scène planifiée sur la timeline avec ses positions de frames."""

    index: int
    scene: Scene
    start_frame: int
    end_frame: int

    @property
    def frame_count(self) -> int:
        """Nombre de frames de cette scène (toujours > 0)."""
        return self.end_frame - self.start_frame

    def __post_init__(self) -> None:
        if self.index < 0:
            raise TimelineError("l'index de scène ne peut pas être négatif")
        if self.start_frame < 0:
            raise TimelineError("start_frame ne peut pas être négatif")
        if self.end_frame <= self.start_frame:
            raise TimelineError(
                f"end_frame ({self.end_frame}) doit être > start_frame ({self.start_frame})"
            )


@dataclass(frozen=True)
class Timeline:
    """Timeline immuable contenant les scènes planifiées et les métadonnées temporelles."""

    planned_scenes: tuple[PlannedScene, ...]
    fps: int
    total_frame_count: int

    @property
    def scenes(self) -> tuple[PlannedScene, ...]:
        """Accès public aux scènes planifiées."""
        return self.planned_scenes

    @property
    def total_duration_seconds(self) -> Decimal:
        """Durée totale exacte en secondes, calculée à partir des frames et du FPS."""
        return Decimal(self.total_frame_count) / Decimal(self.fps)

    def __post_init__(self) -> None:
        if self.fps <= 0:
            raise TimelineError("fps doit être strictement positif")
        if self.total_frame_count <= 0:
            raise TimelineError("total_frame_count doit être strictement positif")

        # Vérifier que les scènes sont non vides
        if not self.planned_scenes:
            raise TimelineError("une timeline doit contenir au moins une scène")

        # Vérifier la continuité et l'absence de chevauchement
        expected_start = 0
        for i, planned_scene in enumerate(self.planned_scenes):
            if planned_scene.start_frame != expected_start:
                raise TimelineError(
                    f"la scène {i} commence à {planned_scene.start_frame} "
                    f"mais devrait commencer à {expected_start} (trou ou chevauchement)"
                )
            expected_start = planned_scene.end_frame

        # Vérifier que le total des frames correspond
        if expected_start != self.total_frame_count:
            raise TimelineError(
                f"la somme des frames ({expected_start}) ne correspond pas "
                f"au total_frame_count ({self.total_frame_count})"
            )


def build_timeline(video: Video) -> Timeline:
    """
    Construit une timeline à partir d'un modèle vidéo.

    Convertit chaque durée de scène en nombre entier de frames au FPS donné.
    Lève TimelineError si une durée n'est pas représentable exactement au FPS choisi.

    Args:
        video: Modèle vidéo Pydantic contenant la liste des scènes et les paramètres.

    Returns:
        Un objet Timeline immuable et valide.

    Raises:
        TimelineError: Si une durée n'est pas convertible ou si la timeline est invalide.
    """
    fps = Decimal(video.fps)
    planned_scenes: list[PlannedScene] = []
    current_frame = 0

    for index, scene in enumerate(video.scenes):
        # Convertir la durée en secondes à nombre entier de frames
        frame_count = _duration_to_frame_count(scene.duration_seconds, fps)

        planned_scene = PlannedScene(
            index=index,
            scene=scene,
            start_frame=current_frame,
            end_frame=current_frame + frame_count,
        )
        planned_scenes.append(planned_scene)
        current_frame += frame_count

    # Créer et valider la timeline
    timeline = Timeline(
        planned_scenes=tuple(planned_scenes),
        fps=video.fps,
        total_frame_count=current_frame,
    )

    return timeline


def _duration_to_frame_count(duration_seconds: Decimal, fps_decimal: Decimal) -> int:
    """
    Convertit une durée en secondes à un nombre entier de frames.

    Refuse toute durée non représentable exactement : une durée est valide
    si et seulement si (duration * fps) est un entier.

    Args:
        duration_seconds: Durée en secondes (Decimal).
        fps_decimal: FPS (Decimal).

    Returns:
        Nombre entier de frames.

    Raises:
        TimelineError: Si la durée n'est pas exactement représentable au FPS donné.
    """
    frame_count_decimal = duration_seconds * fps_decimal

    # Vérifier que le résultat est un entier
    if frame_count_decimal % 1 != 0:
        raise TimelineError(
            f"la durée {duration_seconds} s à {fps_decimal} FPS "
            f"ne correspond pas à un nombre entier de frames "
            f"({frame_count_decimal} frames)"
        )

    return int(frame_count_decimal)
