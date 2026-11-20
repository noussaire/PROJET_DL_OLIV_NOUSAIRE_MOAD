# Transparence ExG — rapport d’intervention

## Audit préalable

Le service calcule `ExG = 2G − R − B` sur les canaux RGB de la mosaïque Esri,
sans normalisation. OpenCV décode une image BGR ; le code extrait correctement
B à l’indice 0, G à l’indice 1 et R à l’indice 2, puis travaille en float32.

Pour chaque arbre hybride final, le centre est arrondi par `int(round(...))`.
Le code prend la moyenne NumPy dans la fenêtre de centre −3 à centre +3 inclus,
soit 7 × 7 pixels, réduite aux bords de la mosaïque. Le résultat float32 est
converti en float Python. La fenêtre n’est pas masquée par le feuillage ni par
le polygone : tous ses pixels contribuent. Ce n’est pas une moyenne de toute la
couronne. Le masque de feuillage utilisé ailleurs dans OpenCV est distinct.

Les seuils dépendent du nombre d’arbres hybrides finaux :

- Plus de cinq : percentiles 15 et 30 des moyennes ExG de cette population,
  avec l’interpolation linéaire NumPy existante.
- Cinq ou moins : seuils fixes 0 et 10. Ces petites séries ne sont pas classées
  relativement aux autres arbres.
- Rouge : valeur strictement inférieure au seuil bas.
- Orange : valeur supérieure ou égale au seuil bas, strictement inférieure au
  seuil haut.
- Vert : valeur supérieure ou égale au seuil haut.

Les égalités et les ex æquo peuvent produire une catégorie vide. Les couleurs ne
garantissent pas des proportions 15/15/70. Avant cette intervention, Python
transmettait les codes historiques `health` / `healthStatus`, mais pas la valeur
ExG, les seuils ou les caractéristiques de la fenêtre. Ces valeurs locales étaient
donc perdues avant l’affichage.

## Modification compatible

Le nouveau champ facultatif par arbre `exgMetadata` contient :

- `value` : résultat numérique existant, sans nouvel arrondi ; une valeur non
  finie est décrite comme absente, sans modifier la classification historique.
- `category` : HIGH, INTERMEDIATE ou LOW, simple traduction du code existant.
- `formula`, `rgbScale`, `classificationMethod`, `lowerThreshold`, `upperThreshold`.
- `populationSize`, `nominalWindowSize`, `sampleWidth`, `sampleHeight`,
  `samplePixelCount`, `sampling`, `healthValidated:false`.

Java conserve ce dictionnaire dans `DetectedTreeDto`, sans le recalculer. Les
anciens constructeurs et champs JSON restent disponibles ; le nouveau champ est
omis lorsqu’il est absent. Le frontend le conserve explicitement dans son mappage.
Les anciens codes SAIN/STRESS/SUSPECT restent des codes techniques de compatibilité,
pas des diagnostics affichés.

La fiche montre identifiant, source, nature du score de détection, valeur ExG,
catégorie descriptive, fenêtre effective, seuils, population, position GPS estimée
et dimensions de couronne disponibles. Valeur absente, texte à la place d’un
nombre, NaN, infini, catégorie ou fenêtre incohérente ne deviennent pas une valeur
inventée ou une catégorie déclarée vérifiée. Une catégorie historique peut être
décrite en l’absence des nouvelles métadonnées, mais la méthode et la valeur sont
alors explicitement non renseignées. Aucun score de détection ne devient une
probabilité de santé.

Les libellés sont : végétation relativement plus verte selon ExG, niveau ExG
intermédiaire, végétation relativement moins verte selon ExG. Les couleurs et les
résultats de classification restent identiques. Les légendes des démonstrations
image/vidéo sont marquées simulées ; leur importation et leurs algorithmes restent
inchangés. Les descriptions d’anciennes expériences dans l’archive ne sont pas
réécrites.

La section native dépliable « Comprendre l’indicateur ExG » est accessible au
clavier et depuis chaque fiche. Elle explique la formule, la fenêtre, les deux
méthodes de seuils, les comparaisons strictes, les scores YOLO/OpenCV et les limites.

## Fichiers modifiés

- `detect_any_polygon.py` : fonction descriptive pure et ajout du dictionnaire
  de métadonnées ; aucune modification des calculs existants.
- `springboot-microservice-olive/src/main/java/com/olivesmart/detection/dto/DetectedTreeDto.java`.
- `frontend-react/index.html` et `frontend-react/map-results.js`, ainsi que leurs
  deux copies dans `springboot-microservice-olive/src/main/resources/static/`.
- `tests/map-display-browser.html` : ajout des contrôles ExG au banc navigateur.
- `tools/verify_map_display.cjs` : dossier de sortie de test configurable.

Ajouts : `tests/test_exg_metadata.py`, `tests/exg-display.test.cjs`,
`springboot-microservice-olive/src/test/java/com/olivesmart/detection/service/ExgMetadataTest.java`
et ce rapport.

Les réponses et journaux générés par le test satellite ont également été sauvegardés
avant leur régénération. Aucun changement de modèle, paramètre, API, base de données
ou algorithme drone. Aucun entraînement ou installation de dépendance.

## Vérifications

- 18 tests Python, 20 tests JavaScript, 8 tests Java réussis ; logique des anciens
  tests inchangée.
- Comparaison AST du module Python avec sa sauvegarde : après retrait de la seule
  fonction descriptive et du seul champ `exgMetadata`, les programmes sont
  structurellement identiques. Cela couvre détection, OpenCV, seuils et GPS.
- Comparaison sur images contrôlées : tous les anciens champs des arbres restent
  identiques, y compris comptes, scores, géométrie, codes et catégories.
- Cas limites testés : séries de trois et cinq arbres, population de huit arbres,
  égalités aux seuils 0 et 10, seuils égaux, fenêtre réduite 4 × 4, valeur zéro,
  valeurs absentes, non finies, hors plage ou de type invalide.
- Java : anciennes réponses acceptées, absence conservée, valeurs et seuils du
  nouveau dictionnaire transmis sans recalcul.
- Parcours réel isolé Python → Java → module frontend : 23 arbres sur une petite
  parcelle de test, tous les dictionnaires ExG conservés et cohérents. Configuration
  YOLO11m V1 vérifiée inchangée : 1280 / 0,20 / 0,50 / 1000 / CPU.
- Exemple réel transmis : ExG 26,612245559692383 ; seuil bas
  26,75306167602539 ; seuil haut 27,824490356445313 ; catégorie LOW. Une valeur
  positive peut donc appartenir à la catégorie relativement moins verte.
- Navigateur Edge aux largeurs 1440, 768 et 390 : valeur ExG, catégorie, seuils,
  lien ouvrant la méthodologie et absence de débordement horizontal vérifiés.
  Les contrôles cartographiques, coordonnées, zooms et 500 points restent testés.
  Le scénario 179/219 du navigateur est synthétique et n’est pas une nouvelle
  mesure de détection. Captures inspectées ; aucun échec de l’inspecteur du banc.
- Les serveurs d’intégration utilisaient des ports locaux temporaires et ont été
  arrêtés. Aucun serveur de production n’a été redémarré.

Résultats navigateur et contrôle du parcours réel :
`resultats_tests/exg-transparency/browser-checks.json`, `pipeline-checks.json` et
captures du même dossier. Réponse réelle complète :
`resultats_tests/yolo11m_satellite_integration.json`.

## Limites restantes

Ombres, saison, résolution, couleur naturelle des feuilles, sol, voisinage,
compression et qualité RGB influencent ce calcul. Une fenêtre fixe en pixels
ne couvre pas la même surface au sol selon l’échelle de l’image. Les valeurs
brutes et seuils relatifs ne garantissent pas une comparaison entre images,
parcelles ou dates. Les décimales affichées sont une précision numérique, pas
une précision radiométrique établie. Les percentiles dépendent aussi des arbres
retenus par le pipeline hybride.

Il n’existe ici aucune validation sanitaire, classification de maladie, mesure
calibrée de chlorophylle, de carence ou de stress hydrique. Les tests valident le
logiciel et la transmission des calculs, pas une interprétation agronomique.
Le calcul lui-même n’a pas été amélioré : cela nécessiterait une autorisation et
un protocole distincts.

## Retour arrière

Sauvegarde : `backups/exg-transparency-20261113-153343/`.
Depuis la racine, restaurer les fichiers modifiés de l’application :

```powershell
$exgBackup = 'backups/exg-transparency-20261113-153343'
$exgFiles = @(
  'detect_any_polygon.py',
  'frontend-react/index.html',
  'frontend-react/map-results.js',
  'springboot-microservice-olive/src/main/resources/static/index.html',
  'springboot-microservice-olive/src/main/resources/static/map-results.js',
  'springboot-microservice-olive/src/main/java/com/olivesmart/detection/dto/DetectedTreeDto.java',
  'tests/map-display-browser.html',
  'tools/verify_map_display.cjs'
)
foreach ($exgFile in $exgFiles) {
  Copy-Item -LiteralPath (Join-Path $exgBackup $exgFile) -Destination $exgFile
}
```

Les nouveaux tests et ce rapport peuvent rester comme traces ; après restauration,
exécuter les suites historiques si les nouveaux champs ne sont plus présents.
Aucun modèle ni donnée n’a besoin d’être supprimé. Recompiler Java (et le JAR s’il
est utilisé), redémarrer Python et Java au moment choisi, puis recharger avec
Ctrl+F5 pour utiliser la version mise à jour ou restaurée.
