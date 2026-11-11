# MoneyPrinter

MoneyPrinter est un projet personnel qui vise à transformer des scripts JSON en
vidéos verticales originales pour YouTube Shorts et Instagram Reels.

**Jalons complétés :**
- **J1** : Schémas et validation JSON
- **J2.1** : Timeline de planification
- **J2.2** : Rendu visuel avec Pillow
- **J2.3** : Encodeur FFmpeg H.264
- **J2.4** : Pipeline complet et CLI render

## Prérequis système

### Python
- Python 3.12 ou plus récent (version minimale testée : Python 3.12.3).
- `pip`.

### FFmpeg et ffprobe (requis pour la génération vidéo)
Pour utiliser la commande `moneyprinter render`, installez FFmpeg et ffprobe :

**Ubuntu/Debian :**
```bash
sudo apt-get install ffmpeg
```

**macOS :**
```bash
brew install ffmpeg
```

**Windows :**
Téléchargez depuis https://ffmpeg.org/download.html ou utilisez :
```bash
choco install ffmpeg
```

Vérifiez l'installation :
```bash
ffmpeg -version
ffprobe -version
```

## Installation locale

Depuis la racine du projet, créez un environnement virtuel puis installez
MoneyPrinter en mode éditable avec ses outils de développement :

```bash
python3 -m venv venv
source venv/bin/activate  # Sur Windows : venv\Scripts\activate
python -m pip install -e ".[dev]"
```

## Utilisation de la CLI

### Commande validate

Validez un fichier JSON selon le schéma et le profil MVP :

```bash
moneyprinter validate examples/demo.json
```

La commande affiche le titre, le format, le nombre de scènes et la durée totale.
Elle renvoie `0` si valide, un code non nul avec un message explicite sinon.

### Commande render

Générez une vidéo MP4 H.264 à partir d'un script JSON :

```bash
moneyprinter render examples/demo.json --output data/output/video.mp4 --overwrite
```

**Options :**
- `--output PATH` : Chemin de sortie du fichier MP4 (défaut : `data/output/<titre>.mp4`)
- `--overwrite` : Remplace le fichier de sortie s'il existe
- `--verbose` : Active les logs détaillés (niveau DEBUG)

**Exemple avec sortie par défaut :**
```bash
moneyprinter render examples/demo.json
```

Génère : `data/output/Pourquoi une année dure environ 365 jours.mp4`

**Résultat attendu :**
```
======================================================================
✓ GÉNÉRATION RÉUSSIE
======================================================================
Fichier de sortie : data/output/video.mp4
Taille : 0.2 MB
Format : 1080×1920 @ 30 FPS
Frames : 900
Durée : 30.0s
Temps de génération : 8.3s
======================================================================
```

### Aide générale

```bash
moneyprinter --help
moneyprinter render --help
```

## Architecture du pipeline

Le pipeline complet suit ces étapes :

```
1. Chargement JSON
   ↓
2. Validation (schéma + profil MVP)
   ↓
3. Construction de la timeline
   (calcul des frames par scène)
   ↓
4. Rendu PNG avec Pillow
   (une image par scène dans un répertoire temporaire)
   ↓
5. Encodage FFmpeg H.264
   (création de segments + concaténation)
   ↓
6. Validation ffprobe
   (vérification codec, résolution, frames, durée)
   ↓
7. ✓ Vidéo MP4 finale
```

### Caractéristiques garanties

- **Format** : MP4 avec codec H.264
- **Résolution** : 1080 × 1920 pixels (format portrait)
- **FPS** : 30 FPS constant
- **Frames** : Nombre exact calculé à partir de la timeline
- **Durée** : Précision jusqu'à 0.01 seconde
- **Audio** : Aucun flux audio (vidéo silencieuse)
- **Pixelformat** : yuv420p (compatible YouTube/Instagram)

### Performance

- Rendu PNG : ~0.3s pour 4 scènes
- Encodage vidéo : ~111 frames/seconde (8s pour 900 frames)
- Validation : ~0.1s
- **Total** : ~8-9 secondes pour une vidéo de 30s

## Tests

Exécutez l'intégralité de la suite de tests :

```bash
pytest
```

Pour les tests seuls (sans les tests d'intégration vidéo) :

```bash
pytest tests/test_schemas.py tests/test_timeline.py tests/test_renderer.py
```

Pour les tests d'intégration complets (requiert FFmpeg/ffprobe) :

```bash
pytest tests/test_encoder.py tests/test_validator.py tests/test_cli.py tests/test_pipeline.py
```

## Limitations actuelles

Le jalon J2.4 implémente :
- ✅ Schémas JSON et validation
- ✅ Timeline de planification
- ✅ Rendu visuel (texte sur fond coloré)
- ✅ Encodage vidéo H.264
- ✅ Pipeline et CLI

Le jalon J2.4 ne comprend pas :
- ❌ Synthèse vocale (TTS)
- ❌ Pistes audio
- ❌ Animations ou transitions
- ❌ Publication (YouTube/Instagram)
- ❌ API HTTP
- ❌ Base de données

Ces fonctionnalités sont réservées pour les jalons suivants.

## Utilisation programmatique

```python
from pathlib import Path
from moneyprinter.cli import load_and_validate_json
from moneyprinter.pipeline import render_pipeline

# Charger et valider le JSON
document = load_and_validate_json(Path("examples/demo.json"))

# Générer la vidéo
result = render_pipeline(
    document,
    output_path=Path("output.mp4"),
    overwrite=True
)

# Accéder aux métriques
print(f"✓ Vidéo générée : {result.output_path}")
print(f"  Durée : {result.duration_seconds}s")
print(f"  Frames : {result.frame_count}")
print(f"  Taille : {result.file_size_mb:.1f} MB")
```

## Structure du projet

```
mp-b4/
├── src/moneyprinter/
│   ├── __init__.py
│   ├── cli.py                # Interface CLI (validate, render)
│   ├── schemas.py            # Schémas Pydantic
│   ├── timeline.py           # Planification temporelle
│   ├── renderer.py           # Rendu Pillow
│   ├── encoder.py            # Encodage FFmpeg
│   ├── validator.py          # Validation ffprobe
│   └── pipeline.py           # Orchestration complète
├── tests/
│   ├── test_schemas.py
│   ├── test_timeline.py
│   ├── test_renderer.py
│   ├── test_encoder.py       # Incluant tests d'intégration
│   ├── test_validator.py
│   ├── test_cli.py           # Incluant tests du render
│   └── test_pipeline.py      # Tests du pipeline
├── examples/
│   ├── demo.json             # Exemple de script
│   ├── render_scenes.py      # Script de rendu PNG
│   └── encode_video.py       # Script de démonstration pipeline
├── data/
│   └── output/               # Vidéos générées
├── pyproject.toml
└── README.md
```

## Tests

Résultats des derniers tests :

```
======================= 116 passed in 101.06s (0:01:41) =======================
```

- Tests de schéma : 19
- Tests de timeline : 9
- Tests de renderer : 8
- Tests d'encodeur (incluant intégration) : 19
- Tests de validateur : 19
- Tests de CLI (incluant render) : 13
- Tests de pipeline : 9

Tous les tests d'intégration (FFmpeg, ffprobe) sont maintenant exécutés sur les
machines où FFmpeg et ffprobe sont disponibles.

