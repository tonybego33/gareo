# Lecteur DWG → plans de l'appli

Lecture directe des DWG R2004+ (AC1018 à AC1032, AutoCAD / BricsCAD) en Python, avec Pillow et numpy, d'après la spécification ODA. Pas besoin d'AutoCAD ni de conversion DXF.

- `dwg.py` : conteneur (en-tête chiffré, sections compressées), carte des handles, objets (LINE, LWPOLYLINE, POLYLINE_2D, ARC, CIRCLE, TEXT, MTEXT, ATTRIB, INSERT, BLOCK_HEADER, LAYER). `Flat` aplatit l'espace objet, blocs imbriqués compris. Les hachures ne sont pas lues, c'est voulu.
- `batch.py` : lit tous les DWG d'un dossier, écarte les calques d'étude `AREP_*` (sauf `AREP_Fond de plan`) et `DEFPOINTS`, enregistre les primitives.
- `reg2.py` : recale un plan dessiné dans son propre repère (cas des sous-sols) sur un plan de référence : rotation + translation, score = part des murs qui retombent sur des murs de la référence. Vérifier le résultat à l'œil : pour Toulon, le sous-sol du BV a dû être contraint par l'escalier du PASO Est.
- `levels.py` : assemble un plan par niveau (une source par bâtiment, la première sert de base), retire les cartouches, dessine textes et étiquettes, exporte en JPEG. Réglé pour Toulon (cadre, étiquettes) : à adapter pour une autre gare.

Les DWG et les données de mission ne sont pas dans ce dépôt. Les chemins d'entrée (`/home/claude/in/…`) sont à adapter.
