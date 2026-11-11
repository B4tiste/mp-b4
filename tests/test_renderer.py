"""Tests du moteur de rendu Pillow."""

import io
from pathlib import Path

import pytest
from PIL import Image

from moneyprinter.renderer import PillowSceneRenderer, RendererError
from moneyprinter.schemas import Scene
from moneyprinter.timeline import PlannedScene


class TestPillowSceneRenderer:
    """Tests de PillowSceneRenderer."""

    @pytest.fixture
    def renderer(self):
        """Renderer par défaut pour les tests."""
        return PillowSceneRenderer()

    @pytest.fixture
    def simple_scene(self):
        """Scène simple pour les tests."""
        return PlannedScene(
            index=0,
            scene=Scene(
                duration_seconds=5,
                headline="Test Title",
                body="Test body text.",
                accent_color="#FF5733",
            ),
            start_frame=0,
            end_frame=150,
        )

    def test_create_valid_image(self, renderer, simple_scene):
        """Test 1 : Crée une image PIL valide."""
        img = renderer.render(
            planned_scene=simple_scene,
            width=1080,
            height=1920,
            background_color="#101827",
            scene_count=1,
        )
        assert isinstance(img, Image.Image)

    def test_image_resolution(self, renderer, simple_scene):
        """Test 2 : Résolution correcte 1080 × 1920."""
        img = renderer.render(
            planned_scene=simple_scene,
            width=1080,
            height=1920,
            background_color="#101827",
            scene_count=1,
        )
        assert img.size == (1080, 1920)

    def test_image_mode_rgb(self, renderer, simple_scene):
        """Test 3 : Mode couleur RGB."""
        img = renderer.render(
            planned_scene=simple_scene,
            width=1080,
            height=1920,
            background_color="#101827",
            scene_count=1,
        )
        assert img.mode == "RGB"

    def test_background_color_applied(self, renderer, simple_scene):
        """Test 4 : Couleur de fond appliquée exactement."""
        bg_color = "#1F2937"  # Un gris foncé
        img = renderer.render(
            planned_scene=simple_scene,
            width=1080,
            height=1920,
            background_color=bg_color,
            scene_count=1,
        )

        # Charger le pixel sans aucun texte (coin bas-droit loin du contenu)
        pixel = img.getpixel((1050, 1850))
        expected_rgb = (0x1F, 0x29, 0x37)
        assert pixel == expected_rgb, f"Pixel: {pixel}, Attendu: {expected_rgb}"

    def test_renders_all_demo_scenes(self):
        """Test 6 : Rend sans exception les quatre scènes de démonstration."""
        from moneyprinter.cli import load_and_validate_json
        from moneyprinter.timeline import build_timeline

        demo_path = Path(__file__).parent.parent / "examples" / "demo.json"
        document = load_and_validate_json(demo_path)
        timeline = build_timeline(document.video)
        renderer = PillowSceneRenderer()

        for planned_scene in timeline.planned_scenes:
            img = renderer.render(
                planned_scene=planned_scene,
                width=document.video.width,
                height=document.video.height,
                background_color=document.video.background_color,
                scene_count=len(document.video.scenes),
            )
            assert img.size == (document.video.width, document.video.height)

    def test_export_and_reload_png(self, renderer, simple_scene, tmp_path):
        """Test 7 : Export et relecture d'un PNG."""
        img = renderer.render(
            planned_scene=simple_scene,
            width=1080,
            height=1920,
            background_color="#101827",
            scene_count=1,
        )

        png_path = tmp_path / "test.png"
        img.save(png_path)

        reloaded = Image.open(png_path)
        assert reloaded.size == (1080, 1920)
        assert reloaded.mode == "RGB"

    def test_determinism(self, renderer, simple_scene):
        """Test 8 : Deux rendus identiques → images identiques."""
        img1 = renderer.render(
            planned_scene=simple_scene,
            width=1080,
            height=1920,
            background_color="#101827",
            scene_count=1,
        )

        img2 = renderer.render(
            planned_scene=simple_scene,
            width=1080,
            height=1920,
            background_color="#101827",
            scene_count=1,
        )

        # Comparer les données de pixels
        assert img1.tobytes() == img2.tobytes()

    def test_long_text_with_wrapping(self, renderer):
        """Test 9 : Texte long avec retour à la ligne."""
        long_body = (
            "Cette est une phrase très longue qui devrait être divisée "
            "en plusieurs lignes pour tenir dans la largeur disponible."
        )
        scene = PlannedScene(
            index=0,
            scene=Scene(
                duration_seconds=5,
                headline="Title",
                body=long_body,
                accent_color="#FF5733",
            ),
            start_frame=0,
            end_frame=150,
        )

        img = renderer.render(
            planned_scene=scene,
            width=1080,
            height=1920,
            background_color="#101827",
            scene_count=1,
        )
        assert img.size == (1080, 1920)

    def test_error_text_too_long(self, renderer):
        """Test 10 : Erreur explicite si texte ne peut pas tenir."""
        # Générer un texte excessivement long
        extremely_long_body = "Word " * 1000
        scene = PlannedScene(
            index=0,
            scene=Scene(
                duration_seconds=5,
                headline="Title",
                body=extremely_long_body,
                accent_color="#FF5733",
            ),
            start_frame=0,
            end_frame=150,
        )

        with pytest.raises(RendererError, match="Texte trop long"):
            renderer.render(
                planned_scene=scene,
                width=1080,
                height=1920,
                background_color="#101827",
                scene_count=1,
            )

    def test_missing_font_error(self, tmp_path):
        """Test 11 : Gestion d'une police absente."""
        fake_font_path = tmp_path / "nonexistent.ttf"

        with pytest.raises(RendererError, match="Police non trouvée"):
            PillowSceneRenderer(font_path=str(fake_font_path))

    def test_input_data_not_modified(self, renderer, simple_scene):
        """Test 12 : Les données d'entrée ne sont pas modifiées."""
        original_headline = simple_scene.scene.headline
        original_body = simple_scene.scene.body

        renderer.render(
            planned_scene=simple_scene,
            width=1080,
            height=1920,
            background_color="#101827",
            scene_count=1,
        )

        assert simple_scene.scene.headline == original_headline
        assert simple_scene.scene.body == original_body

    def test_accent_color_visible(self, renderer, simple_scene):
        """Test 5 : Présence observable de pixels de couleur d'accent."""
        img = renderer.render(
            planned_scene=simple_scene,
            width=1080,
            height=1920,
            background_color="#000000",  # Noir
            scene_count=1,
        )

        # La barre décorative utilise la couleur d'accent
        # Elle est positionnée à margin/2 où margin = height * 0.08 = 1920 * 0.08 = 153.6 ≈ 153
        # Donc barre à y = 76 environ, hauteur 8
        accent_rgb = (0xFF, 0x57, 0x33)
        found_accent = False

        for y in range(50, 100):  # Zone où la barre devrait être
            for x in range(0, 1080):
                if img.getpixel((x, y)) == accent_rgb:
                    found_accent = True
                    break
            if found_accent:
                break

        assert found_accent, "Couleur d'accent non trouvée dans l'image"

    def test_invalid_hex_color(self, renderer, simple_scene):
        """Test : Erreur sur couleur hexadécimale invalide."""
        with pytest.raises(RendererError, match="Couleur invalide"):
            renderer.render(
                planned_scene=simple_scene,
                width=1080,
                height=1920,
                background_color="invalid_color",
                scene_count=1,
            )

    def test_scene_progress_indicator(self, renderer):
        """Test : Indicateur de progression correctement positionné."""
        scene = PlannedScene(
            index=1,
            scene=Scene(
                duration_seconds=5,
                headline="Scene 2",
                body="This is scene 2 of 4.",
                accent_color="#71D6C1",
            ),
            start_frame=0,
            end_frame=150,
        )

        img = renderer.render(
            planned_scene=scene,
            width=1080,
            height=1920,
            background_color="#101827",
            scene_count=4,
        )

        # L'image doit être rendable sans erreur
        assert img.size == (1080, 1920)

    def test_render_all_scene_indices(self, renderer):
        """Test : Rendu avec différents indices de scène."""
        for index in range(4):
            scene = PlannedScene(
                index=index,
                scene=Scene(
                    duration_seconds=5,
                    headline=f"Scene {index + 1}",
                    body="Body text.",
                    accent_color="#FF5733",
                ),
                start_frame=0,
                end_frame=150,
            )

            img = renderer.render(
                planned_scene=scene,
                width=1080,
                height=1920,
                background_color="#101827",
                scene_count=4,
            )

            assert img.size == (1080, 1920)
