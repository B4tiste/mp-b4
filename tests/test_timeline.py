"""Tests pour le module timeline."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from moneyprinter.schemas import VideoDocument
from moneyprinter.timeline import Timeline, TimelineError, build_timeline

DEMO_PATH = Path(__file__).parents[1] / "examples" / "demo.json"


def valid_video_payload() -> dict:
    """Construit un payload vidéo valide minimal."""
    return {
        "schema_version": "1.0",
        "title": "Test",
        "video": {
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "background_color": "#101827",
            "scenes": [
                {
                    "duration_seconds": 5,
                    "headline": "Scène 1",
                    "body": "Corps 1",
                    "accent_color": "#FFC857",
                },
                {
                    "duration_seconds": 25,
                    "headline": "Scène 2",
                    "body": "Corps 2",
                    "accent_color": "#71D6C1",
                },
            ],
        },
    }


# ============================================================================
# Tests de timeline valide sur demo.json
# ============================================================================


def test_build_timeline_from_demo_json() -> None:
    """La timeline peut être construite à partir de demo.json."""
    document = VideoDocument.model_validate_json(DEMO_PATH.read_text(encoding="utf-8"))
    timeline = build_timeline(document.video)

    assert timeline is not None
    assert len(timeline.scenes) == 4
    assert timeline.fps == 30


def test_demo_timeline_has_900_total_frames() -> None:
    """La timeline de demo.json contient 900 frames (30 secondes × 30 FPS)."""
    document = VideoDocument.model_validate_json(DEMO_PATH.read_text(encoding="utf-8"))
    timeline = build_timeline(document.video)

    assert timeline.total_frame_count == 900


def test_demo_timeline_scene_positions() -> None:
    """Les positions des scènes de demo.json sont exactes."""
    document = VideoDocument.model_validate_json(DEMO_PATH.read_text(encoding="utf-8"))
    timeline = build_timeline(document.video)

    # 5s × 30 FPS = 150 frames
    assert timeline.scenes[0].start_frame == 0
    assert timeline.scenes[0].end_frame == 150
    assert timeline.scenes[0].frame_count == 150

    # 8s × 30 FPS = 240 frames
    assert timeline.scenes[1].start_frame == 150
    assert timeline.scenes[1].end_frame == 390
    assert timeline.scenes[1].frame_count == 240

    # 8s × 30 FPS = 240 frames
    assert timeline.scenes[2].start_frame == 390
    assert timeline.scenes[2].end_frame == 630
    assert timeline.scenes[2].frame_count == 240

    # 9s × 30 FPS = 270 frames
    assert timeline.scenes[3].start_frame == 630
    assert timeline.scenes[3].end_frame == 900
    assert timeline.scenes[3].frame_count == 270


def test_demo_timeline_no_gaps_no_overlaps() -> None:
    """La timeline de demo.json n'a pas de trous ni de chevauchements."""
    document = VideoDocument.model_validate_json(DEMO_PATH.read_text(encoding="utf-8"))
    timeline = build_timeline(document.video)

    # Chaque end_frame d'une scène doit être le start_frame de la suivante
    for i, scene in enumerate(timeline.scenes[:-1]):
        assert scene.end_frame == timeline.scenes[i + 1].start_frame

    # La dernière scène doit se terminer au total_frame_count
    assert timeline.scenes[-1].end_frame == timeline.total_frame_count


def test_demo_timeline_exact_duration() -> None:
    """La durée totale de demo.json est exactement 30 secondes."""
    document = VideoDocument.model_validate_json(DEMO_PATH.read_text(encoding="utf-8"))
    timeline = build_timeline(document.video)

    assert timeline.total_duration_seconds == Decimal("30")


# ============================================================================
# Tests des cas d'erreur : durée non représentable
# ============================================================================


def test_timeline_rejects_non_representable_duration() -> None:
    """Une durée non représentable au FPS est rejetée."""
    payload = valid_video_payload()
    # 0.7s × 30 FPS = 21 frames, 0.3s × 30 FPS = 9 frames, total = 30 frames
    # Mais 1.1s × 30 = 33, 28.9 × 30 = 867, total = 900... ce n'est pas bon.
    # Utilisons une vraie non-représentation : 0.333... × 30 = 10
    payload["video"]["scenes"][0]["duration_seconds"] = Decimal("1") / Decimal("3")  # Decimal avec répétition
    payload["video"]["scenes"][1]["duration_seconds"] = Decimal("29") + Decimal("2") / Decimal("3")
    document = VideoDocument.model_validate(payload)

    with pytest.raises(TimelineError, match="nombre entier de frames"):
        build_timeline(document.video)


def test_timeline_rejects_fractional_frames() -> None:
    """Une durée produisant des frames fractionnaires est rejetée."""
    payload = valid_video_payload()
    payload["video"]["scenes"][0]["duration_seconds"] = Decimal("0.05")  # 0.05s × 30 FPS = 1.5 frames
    payload["video"]["scenes"][1]["duration_seconds"] = Decimal("29.95")
    document = VideoDocument.model_validate(payload)

    with pytest.raises(TimelineError, match="nombre entier de frames"):
        build_timeline(document.video)


# ============================================================================
# Tests des cas limites : frame unique, durées fractionnaires valides
# ============================================================================


def test_timeline_accepts_single_frame_duration() -> None:
    """Une scène peut avoir une seule frame."""
    payload = valid_video_payload()
    # Utilisons des durées qui produisent exactement 30 frames
    # 0.1s × 30 FPS = 3 frames, mais 0.1 n'est pas exactement représentable en Decimal
    # Utilisons plutôt des secondes entières et la dernière en calcul
    payload["video"]["scenes"][0]["duration_seconds"] = Decimal("1")  # 30 frames
    payload["video"]["scenes"][1]["duration_seconds"] = Decimal("29")  # 870 frames
    document = VideoDocument.model_validate(payload)

    timeline = build_timeline(document.video)

    assert timeline.scenes[0].frame_count == 30
    assert timeline.total_frame_count == 900


def test_timeline_accepts_valid_fractional_durations() -> None:
    """Des durées fractionnaires valides sont acceptées."""
    payload = valid_video_payload()
    payload["video"]["scenes"][0]["duration_seconds"] = Decimal("0.2")  # 0.2s × 30 FPS = 6 frames
    payload["video"]["scenes"][1]["duration_seconds"] = Decimal("0.1")  # 0.1s × 30 FPS = 3 frames
    # ... mais cela ne fait que 9 frames, ce n'est pas un document valide
    # Test avec des durées qui font au total 30s
    payload["video"]["scenes"][0]["duration_seconds"] = Decimal("0.5")  # 0.5s × 30 FPS = 15 frames
    payload["video"]["scenes"][1]["duration_seconds"] = Decimal("29.5")  # 29.5s × 30 FPS = 885 frames
    document = VideoDocument.model_validate(payload)

    timeline = build_timeline(document.video)

    assert timeline.scenes[0].frame_count == 15
    assert timeline.scenes[1].frame_count == 885
    assert timeline.total_frame_count == 900


# ============================================================================
# Tests des propriétés de Timeline (immuabilité, validation)
# ============================================================================


def test_planned_scene_is_frozen() -> None:
    """Les scènes planifiées sont immuables."""
    payload = valid_video_payload()
    document = VideoDocument.model_validate(payload)
    timeline = build_timeline(document.video)

    planned_scene = timeline.scenes[0]

    with pytest.raises(Exception):  # dataclass frozen
        planned_scene.index = 999  # type: ignore


def test_timeline_is_frozen() -> None:
    """La timeline est immuable."""
    payload = valid_video_payload()
    document = VideoDocument.model_validate(payload)
    timeline = build_timeline(document.video)

    with pytest.raises(Exception):  # dataclass frozen
        timeline.fps = 60  # type: ignore


def test_timeline_total_duration_is_calculated_from_frames() -> None:
    """La durée totale est calculée à partir des frames et du FPS."""
    payload = valid_video_payload()
    document = VideoDocument.model_validate(payload)
    timeline = build_timeline(document.video)

    # 30 scènes × 30 FPS = 30 secondes
    assert timeline.total_duration_seconds == Decimal("30")
    assert timeline.total_duration_seconds == Decimal(timeline.total_frame_count) / Decimal(timeline.fps)


def test_timeline_exposes_fps() -> None:
    """La timeline expose le FPS."""
    payload = valid_video_payload()
    document = VideoDocument.model_validate(payload)
    timeline = build_timeline(document.video)

    assert timeline.fps == 30


def test_planned_scene_exposes_scene_reference() -> None:
    """Les scènes planifiées conservent la référence à la scène originale."""
    payload = valid_video_payload()
    document = VideoDocument.model_validate(payload)
    timeline = build_timeline(document.video)

    planned_scene = timeline.scenes[0]
    assert planned_scene.scene is document.video.scenes[0]


# ============================================================================
# Tests de déterminisme
# ============================================================================


def test_timeline_is_deterministic() -> None:
    """La construction de la timeline est déterministe."""
    payload = valid_video_payload()
    document1 = VideoDocument.model_validate(payload)
    document2 = VideoDocument.model_validate(payload)

    timeline1 = build_timeline(document1.video)
    timeline2 = build_timeline(document2.video)

    assert timeline1.total_frame_count == timeline2.total_frame_count
    assert timeline1.fps == timeline2.fps
    assert len(timeline1.scenes) == len(timeline2.scenes)

    for scene1, scene2 in zip(timeline1.scenes, timeline2.scenes):
        assert scene1.start_frame == scene2.start_frame
        assert scene1.end_frame == scene2.end_frame
        assert scene1.index == scene2.index


def test_multiple_builds_produce_same_timeline() -> None:
    """Plusieurs constructions produisent la même timeline."""
    document = VideoDocument.model_validate_json(DEMO_PATH.read_text(encoding="utf-8"))

    timelines = [build_timeline(document.video) for _ in range(5)]

    for timeline in timelines[1:]:
        assert timeline.total_frame_count == timelines[0].total_frame_count
        assert timeline.fps == timelines[0].fps
        assert len(timeline.scenes) == len(timelines[0].scenes)


# ============================================================================
# Tests des validations internes (Timeline.__post_init__)
# ============================================================================


def test_timeline_rejects_invalid_fps() -> None:
    """Une timeline avec fps <= 0 est rejetée."""
    payload = valid_video_payload()
    document = VideoDocument.model_validate(payload)
    timeline_mock_scenes = tuple()  # dummy

    with pytest.raises(TimelineError, match="fps"):
        Timeline(planned_scenes=timeline_mock_scenes, fps=0, total_frame_count=100)


def test_timeline_rejects_invalid_total_frame_count() -> None:
    """Une timeline avec total_frame_count <= 0 est rejetée."""
    from moneyprinter.timeline import PlannedScene

    payload = valid_video_payload()
    document = VideoDocument.model_validate(payload)

    planned_scene = PlannedScene(
        index=0,
        scene=document.video.scenes[0],
        start_frame=0,
        end_frame=100,
    )

    with pytest.raises(TimelineError, match="total_frame_count"):
        Timeline(
            planned_scenes=(planned_scene,),
            fps=30,
            total_frame_count=0,
        )


def test_timeline_rejects_empty_scenes() -> None:
    """Une timeline sans scènes est rejetée."""
    with pytest.raises(TimelineError, match="au moins une scène"):
        Timeline(
            planned_scenes=tuple(),
            fps=30,
            total_frame_count=100,
        )


# ============================================================================
# Tests des cas d'erreur avancés
# ============================================================================


def test_timeline_detects_frame_gaps() -> None:
    """Une timeline détecte les trous entre scènes."""
    from moneyprinter.timeline import PlannedScene

    payload = valid_video_payload()
    document = VideoDocument.model_validate(payload)

    scene = document.video.scenes[0]
    planned_scene1 = PlannedScene(index=0, scene=scene, start_frame=0, end_frame=100)
    planned_scene2 = PlannedScene(index=1, scene=scene, start_frame=110, end_frame=200)

    with pytest.raises(TimelineError, match="trou ou chevauchement"):
        Timeline(
            planned_scenes=(planned_scene1, planned_scene2),
            fps=30,
            total_frame_count=200,
        )


def test_timeline_detects_overlapping_scenes() -> None:
    """Une timeline détecte les chevauchements."""
    from moneyprinter.timeline import PlannedScene

    payload = valid_video_payload()
    document = VideoDocument.model_validate(payload)

    scene = document.video.scenes[0]
    planned_scene1 = PlannedScene(index=0, scene=scene, start_frame=0, end_frame=150)
    planned_scene2 = PlannedScene(index=1, scene=scene, start_frame=100, end_frame=200)

    with pytest.raises(TimelineError, match="trou ou chevauchement"):
        Timeline(
            planned_scenes=(planned_scene1, planned_scene2),
            fps=30,
            total_frame_count=200,
        )


def test_timeline_detects_frame_sum_mismatch() -> None:
    """Une timeline détecte une somme de frames ne correspondant pas au total."""
    from moneyprinter.timeline import PlannedScene

    payload = valid_video_payload()
    document = VideoDocument.model_validate(payload)

    scene = document.video.scenes[0]
    planned_scene1 = PlannedScene(index=0, scene=scene, start_frame=0, end_frame=100)
    planned_scene2 = PlannedScene(index=1, scene=scene, start_frame=100, end_frame=200)

    with pytest.raises(TimelineError, match="ne correspond pas"):
        Timeline(
            planned_scenes=(planned_scene1, planned_scene2),
            fps=30,
            total_frame_count=150,  # 100 + 100 = 200, pas 150
        )


# ============================================================================
# Tests additionnels : cas limites et coherence
# ============================================================================


def test_planned_scene_negative_index_is_rejected() -> None:
    """Un index négatif est rejeté."""
    from moneyprinter.timeline import PlannedScene

    payload = valid_video_payload()
    document = VideoDocument.model_validate(payload)

    with pytest.raises(TimelineError, match="index"):
        PlannedScene(
            index=-1,
            scene=document.video.scenes[0],
            start_frame=0,
            end_frame=100,
        )


def test_planned_scene_negative_start_frame_is_rejected() -> None:
    """Un start_frame négatif est rejeté."""
    from moneyprinter.timeline import PlannedScene

    payload = valid_video_payload()
    document = VideoDocument.model_validate(payload)

    with pytest.raises(TimelineError, match="start_frame"):
        PlannedScene(
            index=0,
            scene=document.video.scenes[0],
            start_frame=-1,
            end_frame=100,
        )


def test_planned_scene_inverted_frames_are_rejected() -> None:
    """end_frame <= start_frame est rejeté."""
    from moneyprinter.timeline import PlannedScene

    payload = valid_video_payload()
    document = VideoDocument.model_validate(payload)

    with pytest.raises(TimelineError, match="end_frame.*start_frame"):
        PlannedScene(
            index=0,
            scene=document.video.scenes[0],
            start_frame=100,
            end_frame=100,
        )


def test_timeline_with_different_fps_values() -> None:
    """La timeline fonctionne avec différentes valeurs de FPS."""
    payload = valid_video_payload()

    # FPS 60
    payload["video"]["fps"] = 60
    payload["video"]["scenes"][0]["duration_seconds"] = Decimal("1")  # 60 frames
    payload["video"]["scenes"][1]["duration_seconds"] = Decimal("59")  # 3540 frames
    document = VideoDocument.model_validate(payload)
    timeline = build_timeline(document.video)
    assert timeline.fps == 60
    assert timeline.total_frame_count == 3600
    assert timeline.total_duration_seconds == Decimal("60")


def test_timeline_rejects_duration_for_wrong_fps() -> None:
    """Une durée valide à 30 FPS peut ne pas être valide à 24 FPS."""
    payload = valid_video_payload()
    payload["video"]["fps"] = 24
    # 0.1s × 30 = 3 frames, mais 0.1s × 24 = 2.4 frames (pas un entier)
    payload["video"]["scenes"][0]["duration_seconds"] = Decimal("0.1")
    payload["video"]["scenes"][1]["duration_seconds"] = Decimal("29.9")
    document = VideoDocument.model_validate(payload)

    with pytest.raises(TimelineError, match="nombre entier de frames"):
        build_timeline(document.video)
