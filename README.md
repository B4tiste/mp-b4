# MoneyPrinter

MoneyPrinter est un projet personnel qui vise à transformer des scripts JSON en
vidéos verticales originales pour YouTube Shorts et Instagram Reels. Le jalon
J1 pose les fondations Python et vérifie les scripts ; il ne produit pas encore
de vidéo.

## Prérequis

- Python 3.12 ou plus récent (version minimale testée : Python 3.12.3).
- `pip`.

FFmpeg, Pillow, Docker et une connexion réseau ne sont pas nécessaires pour
utiliser le code de J1.

## Installation locale

Depuis la racine du projet, créez un environnement virtuel puis installez
MoneyPrinter en mode éditable avec ses outils de développement :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Utilisation de la CLI

Validez le fichier d'exemple :

```bash
moneyprinter validate examples/demo.json
```

La commande affiche le titre, le format, le nombre de scènes et la durée totale.
Elle renvoie `0` si le JSON respecte le schéma et le profil MVP, et un code non
nul avec un message explicite en cas de problème. Pour consulter les options :

```bash
moneyprinter --help
```

## Tests

```bash
pytest
```

## Limites du jalon J1

J1 définit et valide le format JSON de base, ainsi que le profil MVP
(1080 × 1920, 30 FPS et exactement 30 secondes). Il ne comprend aucun rendu
vidéo, traitement d'image, appel à une IA, synthèse vocale, publication,
service HTTP ou stockage persistant. Les règles génériques du schéma restent
distinctes des contraintes de ce profil afin de permettre d'autres profils
ultérieurement.
