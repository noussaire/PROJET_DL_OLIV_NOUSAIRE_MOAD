# OliveSmart : affichage cartographique

## Périmètre

Seuls les deux `index.html` et un nouveau module de présentation `map-results.js`
(copié dans les ressources statiques Spring Boot) changent l'application.
Le modèle, ses paramètres, Python, Java, OpenCV, les routes, Esri, les polygones,
les coordonnées GPS et la base de données ne sont pas modifiés.

Le sélecteur applique trois présentations aux mêmes arbres hybrides : points
(défaut), rectangles ou les deux. Les points sont des `L.circleMarker` attachés
aux coordonnées API, de rayon fixe en pixels. Un renderer Canvas partagé évite
un élément SVG/DOM par arbre. La sélection met en évidence l'arbre et ouvre sa
fiche ; le clic ne remonte pas au gestionnaire de dessin du polygone.

Les rectangles utilisent les bornes API sans agrandissement. Si seules des
dimensions individuelles existent, l'approximation métrique antérieure sert à
dessiner leur emprise estimée. Aucune dimension absente n'est remplacée par une
valeur arbitraire. Sans bornes ni diamètre, aucun rectangle n'est inventé.

Les deux comptes sont distincts : YOLO brut dans le polygone et hybride. Le nombre
hybride provient de la liste `trees`. Le brut provient de
`analysisMetadata.yoloInPolygonCount`, ou d'une liste brute complète avec marqueurs
`insideParcel`. Sinon l'interface affiche « Non disponible ». Aucun point brut
n'est créé à partir de ce compte ; la carte représente explicitement l'hybride.
Une différence entre le total API et ses métadonnées est signalée.

Les couleurs sont les indicateurs visuels ExG heuristiques existants. La fiche
affiche identifiant, source, confiance, GPS et dimensions réellement fournies,
qualifiées d'estimations. Les scores incluant OpenCV sont signalés non calibrés.
Aucune probabilité sanitaire, dimension fictive, estimation d'âge ou qualification
« centenaire » n'est affichée dans la fiche. Les trois anciennes catégories d'âge
visibles deviennent des classes de diamètre estimé, sans changer les données API.
Les anciennes données embarquées et les expériences historiques restent conservées.

Le défilement mobile rend la carte accessible sous les barres d'outils avec une
hauteur minimale de 360 pixels. Les contrôles et la mise en page desktop existants
sont conservés.

## Vérifications

- 17 tests JavaScript (11 existants et 6 nouveaux), 13 Python et 7 Java réussis.
- Logique des tests existants inchangée.
- Dans Edge, la page réelle est chargée dans un iframe de test. Des réponses API
  synthétiques, explicitement identifiées, testent les comptes 179 / 219 sans
  lancer l'inférence et sans fabriquer des résultats de production.
- Trois modes, clics et maintien de la sélection testés aux largeurs 1440, 768 et
  390 pixels.
- Coordonnées API inchangées, projection réelle Leaflet cohérente aux zooms 17,
  19 et 18 après déplacements, rayon en pixels stable.
- 500 points avec un Canvas partagé : environ 11 à 22 ms pour la création des
  couches dans cette vérification, pas une garantie de performances universelle.
- Captures inspectées aux trois largeurs. Le rapport de style du banc de test a
  zéro échec ; son avertissement de largeur de texte concerne la ligne de résultat
  du banc, volontairement plus courte que l'iframe de l'application.
- Empreintes de `detect_any_polygon.py`, `model_config.py`, `ai_engine_server.py`
  et `traceability.js` inchangées pendant cette intervention.

Résultats : `resultats_tests/map-display/browser-checks.json` et captures dans le
même dossier. Aucun serveur de production, entraînement ou installation requis.
Les tests navigateur ont utilisé des ports locaux temporaires et ont été arrêtés.

Commandes de vérification depuis la racine :

```powershell
node --test tests/traceability.test.cjs tests/map-results.test.cjs
node tools/verify_map_display.cjs
& .\.venv\Scripts\python.exe -B -m unittest discover -s tests -p 'test_*.py' -v
```

Le dernier script navigateur utilise Edge/Chrome déjà installé et l'inspecteur
de la compétence locale `design-taste-frontend`. La page garde ses dépendances
CDN et son fond Esri habituels ; aucun paquet n'est installé. Les tests Java
utilisent la commande hors ligne Java 21 décrite dans `YOLO11M_INTEGRATION.md`.

## Retour arrière

Les deux fichiers modifiés ont été sauvegardés avant intervention dans
`backups/map-display-20261113-143439/`. Depuis la racine du projet :

```powershell
Copy-Item -LiteralPath 'backups/map-display-20261113-143439/frontend-react/index.html' -Destination 'frontend-react/index.html'
Copy-Item -LiteralPath 'backups/map-display-20261113-143439/springboot-microservice-olive/src/main/resources/static/index.html' -Destination 'springboot-microservice-olive/src/main/resources/static/index.html'
```

Les nouveaux fichiers `map-results.js` peuvent rester : l'ancien HTML ne les
référence pas. Aucun modèle ni donnée n'a besoin d'être supprimé pour revenir en
arrière. Recharger le navigateur avec Ctrl+F5 après mise à jour ou restauration.
Si l'interface est servie depuis un JAR, reconstruire ce JAR pour y inclure les
ressources statiques actualisées.
