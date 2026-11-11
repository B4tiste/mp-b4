"""Moteur de rendu visuel pour scènes avec Pillow."""

from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from moneyprinter.timeline import PlannedScene


class RendererError(ValueError):
    """Erreur lors du rendu d'une scène."""


class PillowSceneRenderer:
    """Moteur de rendu de scènes en PNG avec Pillow."""

    def __init__(
        self,
        font_path: str | Path | None = None,
        font_size_title: int = 80,
        font_size_body: int = 50,
    ):
        """
        Initialise le renderer.

        Args:
            font_path: Chemin vers une police TrueType. Si None, utilise DejaVuSans.ttf.
            font_size_title: Taille de police du titre en points.
            font_size_body: Taille de police du corps en points.
        """
        if font_path is None:
            # Chercher DejaVuSans.ttf dans les emplacements standard Ubuntu
            candidates = [
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            ]
            font_path = next((p for p in candidates if p.exists()), None)
            if font_path is None:
                raise RendererError(
                    "Police TrueType non trouvée. Veuillez installer fonts-dejavu "
                    "ou spécifier font_path."
                )

        self.font_path = Path(font_path)
        if not self.font_path.exists():
            raise RendererError(f"Police non trouvée : {self.font_path}")

        self.font_size_title = font_size_title
        self.font_size_body = font_size_body

    def render(
        self,
        planned_scene: PlannedScene,
        width: int,
        height: int,
        background_color: str,
        scene_count: int,
    ) -> Image.Image:
        """
        Rend une scène planifiée en image PIL.

        Args:
            planned_scene: Scène planifiée avec index et contenu.
            width: Largeur en pixels.
            height: Hauteur en pixels.
            background_color: Couleur de fond au format hexadécimal (#RRGGBB).
            scene_count: Nombre total de scènes (pour l'indicateur de progression).

        Returns:
            Image PIL en mode RGB.

        Raises:
            RendererError: Si le texte ne peut pas tenir dans les zones disponibles.
        """
        # Créer l'image avec la couleur de fond
        bg_color = self._parse_hex_color(background_color)
        img = Image.new("RGB", (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)

        # Charger les polices
        try:
            font_title = ImageFont.truetype(str(self.font_path), self.font_size_title)
            font_body = ImageFont.truetype(str(self.font_path), self.font_size_body)
        except OSError as e:
            raise RendererError(f"Impossible de charger la police : {e}") from e

        # Paramètres de mise en page
        margin = int(height * 0.08)  # 8% de la hauteur
        safe_width = width - 2 * margin
        accent_color = self._parse_hex_color(planned_scene.scene.accent_color)

        # 1. Barre décorative en haut
        bar_height = 8
        draw.rectangle(
            [(0, margin // 2), (width, margin // 2 + bar_height)],
            fill=accent_color,
        )

        # 2. Titre
        y_title = margin
        headline = planned_scene.scene.headline
        y_title = self._draw_text_block(
            draw,
            headline,
            font_title,
            y_title,
            margin,
            safe_width,
            accent_color,
            max_lines=3,
        )

        # 3. Espace intermédiaire
        y_body = y_title + int(height * 0.06)

        # 4. Corps de texte
        body = planned_scene.scene.body
        y_body = self._draw_text_block(
            draw,
            body,
            font_body,
            y_body,
            margin,
            safe_width,
            (200, 200, 200),  # Gris clair pour le corps
            max_lines=8,
        )

        # 5. Indicateur de progression en bas
        progress_text = f"{planned_scene.index + 1:02d} / {scene_count:02d}"
        self._draw_centered_text(
            draw,
            progress_text,
            font_body,
            height - margin + 20,
            width,
            accent_color,
        )

        return img

    def _draw_text_block(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.FreeTypeFont,
        y_start: int,
        margin: int,
        max_width: int,
        color: tuple[int, int, int],
        max_lines: int,
    ) -> int:
        """
        Dessine un bloc de texte avec retour à la ligne automatique.

        Args:
            draw: Objet ImageDraw.
            text: Texte à dessiner.
            font: Police à utiliser.
            y_start: Position y de début.
            margin: Marge gauche.
            max_width: Largeur disponible pour le texte.
            color: Couleur du texte (RGB tuple).
            max_lines: Nombre maximum de lignes autorisées.

        Returns:
            La position y après le bloc de texte.

        Raises:
            RendererError: Si le texte ne peut pas tenir.
        """
        lines = self._wrap_text(text, font, max_width)

        if len(lines) > max_lines:
            raise RendererError(
                f"Texte trop long pour {max_lines} lignes max : {text!r}"
            )

        y = y_start
        for line in lines:
            draw.text((margin, y), line, font=font, fill=color)
            bbox = draw.textbbox((margin, y), line, font=font)
            y += bbox[3] - bbox[1] + 10  # hauteur ligne + 10px padding

        return y

    def _draw_centered_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.FreeTypeFont,
        y: int,
        width: int,
        color: tuple[int, int, int],
    ) -> None:
        """Dessine du texte centré horizontalement."""
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        draw.text((x, y), text, font=font, fill=color)

    def _wrap_text(
        self, text: str, font: ImageFont.FreeTypeFont, max_width: int
    ) -> list[str]:
        """
        Divise le texte en lignes qui tiennent dans max_width.

        Args:
            text: Texte à diviser.
            font: Police à utiliser pour mesurer.
            max_width: Largeur maximale en pixels.

        Returns:
            Liste de lignes.
        """
        lines: list[str] = []
        words = text.split()

        if not words:
            return lines

        current_line = ""

        for word in words:
            test_line = f"{current_line} {word}".strip()
            bbox = font.getbbox(test_line)
            line_width = bbox[2] - bbox[0]

            if line_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines

    @staticmethod
    def _parse_hex_color(hex_color: str) -> tuple[int, int, int]:
        """
        Convertit une couleur hexadécimale (#RRGGBB) en tuple RGB.

        Args:
            hex_color: Couleur au format #RRGGBB.

        Returns:
            Tuple (R, G, B) avec valeurs 0-255.

        Raises:
            RendererError: Si le format est invalide.
        """
        if not hex_color.startswith("#") or len(hex_color) != 7:
            raise RendererError(f"Couleur invalide : {hex_color}")

        try:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            return (r, g, b)
        except ValueError as e:
            raise RendererError(f"Couleur hexadécimale invalide : {hex_color}") from e
