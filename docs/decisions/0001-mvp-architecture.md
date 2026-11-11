# Décision 0001 : architecture du MVP

- Statut : acceptée
- Date : 2026-11-11

## Contexte

Le premier jalon doit établir une base locale pour convertir plus tard des
scripts JSON en vidéos verticales. Il doit rester simple à installer et à tester
sur une seule machine Ubuntu, sans rendre vidéo ni dépendance à des services
externes.

## Décisions

### Package Python en `src/`

Le code applicatif réside dans `src/moneyprinter/`. Le package est installable
en mode éditable avec `pip install -e ".[dev]"`, et la commande `moneyprinter`
est déclarée comme point d'entrée de paquet. Pydantic v2 définit les modèles
stricts du document et des scènes ; `Decimal` conserve une addition exacte des
durées.

Les règles génériques (version, champs requis, couleurs, valeurs positives et
scènes non vides) sont séparées de la fonction validant le profil MVP
(1080 × 1920, 30 FPS et durée totale de 30 secondes).

### CLI avant API HTTP

Une CLI est suffisante pour l'usage J1 : valider localement un JSON et obtenir
un résultat immédiat. Elle ne demande ni serveur, ni dépendance réseau, ni
gestion d'authentification ou de cycle de vie de service. Une API HTTP pourra
être envisagée lorsqu'un besoin d'intégration multi-clients sera défini.

### Docker et SQLite reportés

Docker ajouterait un coût de configuration et d'exploitation sans bénéfice
nécessaire pour une commande locale légère. SQLite est également reporté :
J1 ne conserve aucun état et n'a besoin que de lire un fichier JSON. Ces choix
pourront être réévalués si le déploiement ou la gestion d'éléments persistants
le justifie.

### Aucun rendu dans J1

Le périmètre s'arrête aux fondations, aux schémas, à la validation de profil et
à leur documentation. Pillow, FFmpeg, synthèse vocale, génération par IA et
publication ne sont pas introduits prématurément.

## Conséquences

- Les scripts invalides sont rejetés avant tout futur traitement.
- Les règles MVP peuvent évoluer sans modifier les contraintes fondamentales
  du format de document.
- Le rendu et les formats de sortie restent à concevoir au jalon suivant.
