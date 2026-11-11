#!/usr/bin/env python3
"""Script de démonstration : génère des PNG pour chaque scène de demo.json."""

import json
from pathlib import Path

from moneyprinter.cli import load_and_validate_json
from moneyprinter.renderer import PillowSceneRenderer
from moneyprinter.timeline import build_timeline


def main(demo_json_path: str | Path = "examples/demo.json") -> None:
    """
    Charge demo.json, construit la timeline, et rend chaque scène en PNG.

    Args:
        demo_json_path: Chemin vers le fichier JSON de démonstration.
    """
    demo_json_path = Path(demo_json_path)

    # Charger et valider le document JSON
    document = load_and_validate_json(demo_json_path)
    video = document.video

    # Construire la timeline
    timeline = build_timeline(video)

    # Créer le répertoire de sortie
    output_dir = Path("data/output/scenes")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialiser le renderer
    renderer = PillowSceneRenderer()

    # Rendre chaque scène
    for planned_scene in timeline.planned_scenes:
        img = renderer.render(
            planned_scene=planned_scene,
            width=video.width,
            height=video.height,
            background_color=video.background_color,
            scene_count=len(video.scenes),
        )

        # Enregistrer l'image
        scene_index = planned_scene.index + 1
        output_path = output_dir / f"scene_{scene_index:02d}.png"
        img.save(output_path)
        print(f"✓ Rendu : {output_path}")

    print(f"\n✓ {len(timeline.planned_scenes)} scènes rendues dans {output_dir}")


if __name__ == "__main__":
    main()
