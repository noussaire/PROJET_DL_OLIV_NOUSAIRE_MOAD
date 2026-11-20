# Image Upload LIVE V1 — rapport et exploitation

## Résultat

Le mode LIVE du module « Tester Image (Upload) » analyse les octets réels du
fichier sélectionné. Le mode DEMO garde son générateur existant ; la vidéo reste
inchangée. Aucun repli automatique en simulation ou vers un autre modèle.

Le parcours implémenté est : navigateur → JSON base64 → Spring Boot → service
Python → décodage Pillow en mémoire → image BGR → singleton YOLO11m V1 → réponse
en pixels → canvas de l’image. Le modèle est celui déjà chargé par
`detect_any_polygon.py`. Aucun second modèle n’est instancié. Le même verrou
Python protège les requêtes satellite et image contre les inférences simultanées.

Routes ajoutées :

- `POST http://localhost:8080/api/v1/images/analyser`
- `POST http://localhost:8000/api/v1/analyze-image` (appelée par Java)

Les anciennes routes, réponses satellite et métadonnées ExG restent intactes.
`detect_any_polygon.py`, `model_config.py`, les services/DTO satellite et la base
de données ne sont pas modifiés. Aucun entraînement ni installation de dépendance.

## Paramètres et contrat

Checkpoint : `models/yolo11m_olivesmart_v1.pt`. Paramètres : `imgsz=1280`,
`conf=0.20`, `iou=0.50`, `max_det=1000`, `device=cpu`. Le parcours image exige le
profil `yolo11m_v1` ; si le processus a été démarré avec l’ancien profil, il renvoie
une erreur explicite plutôt que de changer de modèle automatiquement.

Requête JSON : `mode:LIVE`, `imageBase64` (base64 strict sans préfixe Data URL),
`imageId`, `imageWidth`, `imageHeight` et `roiPx` facultatif. Une ROI absente/null
signifie image entière ; une liste vide, incomplète, auto-intersectée ou hors
image est refusée. De 3 à 64 sommets, avec coordonnées numériques finies, sont
acceptés. La largeur et la hauteur de l’aperçu sont celles de l’image orientée.

Réponse : `success`, `mode`, `engine:YOLO`, `coordinateSystem:IMAGE_PIXELS`,
identifiant/dimensions/format de l’image, dimensions avant orientation,
`orientationApplied`, `totalDetections`, `rawDetectionCount`, `roiApplied`,
`detections`, modèle, chemin du checkpoint, `inferenceParameters`, durées,
avertissements et erreur éventuelle. Chaque détection contient `id`, `bboxPx`
([x1,y1,x2,y2]), `centerPx` ([x,y]), `confidence`, `classId`, `className`, `source`.
Le total est exactement la longueur de la liste. Zéro détection est un succès.

L’inférence globale reçoit l’image entière orientée ; la ROI filtre ensuite les
centres, bord inclus. Les boîtes ne sont pas recadrées à la ROI. Les coordonnées
YOLO sont celles de l’image orientée avant son redimensionnement interne à 1280.
Il n’y a ni tuilage, ni récupération OpenCV, ni GPS, diamètre en mètres, âge,
catégorie ExG ou diagnostic sanitaire dans cette réponse.

## Validation et limites

- Maximum 8 MiB de données compressées, 12 MiB de corps JSON, 12 millions de
  pixels décodés. Les plafonds sont compatibles avec l’expansion base64.
- Java et Python contrôlent la longueur déclarée avant la lecture du corps.
  Python contrôle la longueur base64 avant son décodage et les dimensions de
  l’image avant l’allocation du tableau RGB complet.
- Format réel identifié par Pillow, vérification structurelle sur un lecteur
  distinct, puis décodage strict. Seuls JPEG, PNG et WebP statiques sont acceptés.
  Fichiers illisibles, tronqués, multitrames/animés et dimensions excessives sont
  refusés. Aucun chemin local ou URL fourni par le client n’est ouvert.
- Orientation EXIF appliquée côté Python par `ImageOps.exif_transpose` ; aperçu
  navigateur avec `createImageBitmap(..., imageOrientation:'from-image')`. Une
  différence de dimensions est refusée explicitement. La transparence est composée
  sur blanc côté Python et sur le canvas ; un avertissement le précise.
- Images conservées en mémoire uniquement dans le traitement applicatif. Les
  captures du banc de test sont des artefacts de vérification visuelle, pas un
  enregistrement automatique des images importées en production.
- Délai Java 60 s, garde CPU Python 45 s vérifiée avant/après l’appel natif,
  délai navigateur 65 s. La garde est coopérative : elle n’interrompt pas une
  inférence native en cours. Annuler/changer d’image invalide l’affichage et annule
  la requête navigateur ; Python peut rester occupé jusqu’à la fin du calcul.
- Une requête concurrente reçoit une erreur explicite 503. Java possède également
  une admission unique pour limiter les corps image simultanément en mémoire.
  La réception du corps Python a un délai socket de 15 s. Cette V1 locale n’est
  pas une infrastructure d’upload publique avec quotas/authentification/proxy.
- Une grande image réduite globalement à 1280 peut perdre de petits arbres.
  Le plafond de 1000 prédictions est signalé s’il est potentiellement atteint.

La classe `trees` ne garantit pas la reconnaissance exclusive des oliviers. Les
performances du dataset expérimental ne valident pas les nouvelles images drone.
Les scores sont des scores de détection ; aucune probabilité sanitaire n’est
produite. Le tuilage et sa gestion des doublons sont réservés à une étape future.

## Interface

Le sélecteur propose image entière (défaut) ou ROI. Le tracé utilise les événements
Pointer pour souris et tactile ; on termine le tracé avec le bouton dédié. Les
coordonnées de ROI sont stockées en pixels de l’image orientée. La transformation
`object-contain` prend en compte l’échelle et les deux marges ; les clics dans les
marges sont ignorés. `ResizeObserver` redessine les mêmes pixels, sans modifier
les détections ; le canvas tient compte de la densité d’écran.

Points, rectangles ou les deux sont disponibles, avec sélection d’une détection
et fiche contenant les vrais pixels, score, classe et source. Les panneaux
satellite ExG/GPS et les dimensions en mètres sont masqués dans l’image LIVE.
Changement de fichier, de mode, de zone ou sortie de l’onglet invalident les
requêtes en attente. Les données simulées ne sont jamais utilisées dans le LIVE.

## Fichiers

Modifiés (sauvegardés avant intervention) :

- `ai_engine_server.py` : nouvelle branche HTTP, validation du corps et erreurs
  image, sous le verrou existant ; branche satellite conservée.
- `frontend-react/index.html` et sa copie
  `springboot-microservice-olive/src/main/resources/static/index.html` : contrôles,
  intégration ciblée du module et mise en page image. Aucun générateur exécuté.

Ajoutés :

- `detect_uploaded_image.py`.
- `frontend-react/upload-image.js` et sa copie Spring Boot statique.
- Java sous `src/main/java/com/olivesmart/detection/` :
  `controller/ImageAnalysisController.java`, `service/ImageDetectionService.java`,
  `dto/ImageAnalysisRequest.java`, `dto/ImageAnalysisResponse.java`,
  `dto/ImageDetectionDto.java`.
- `tests/test_uploaded_image.py`, `tests/upload-image.test.cjs`,
  `tests/upload-image-browser.html`.
- Java : `src/test/java/com/olivesmart/detection/service/ImageApiTest.java`.
- `tools/verify_uploaded_image_integration.py`, `tools/verify_upload_browser.cjs`
  et ce rapport.
- JAR généré dans `springboot-microservice-olive/target/` et rapports de test.

## Vérifications réalisées

- 29 tests Python, 23 JavaScript, 13 Java réussis. Tests existants conservés.
- JPEG/PNG/WebP, images invalides/tronquées, APNG et WebP animés, tailles excessives,
  contrôle du corps avant lecture et des dimensions avant allocation RGB.
- Huit orientations EXIF côté Python ; aperçu navigateur EXIF 6 confirmé aux
  mêmes dimensions orientées 80 × 120 que Python.
- Image entière, ROI, centres, boîtes, zéro détection, erreurs/délais, modèle
  indisponible, verrou CPU partagé, rejet d’une provenance DEMO dans le LIVE.
- Test navigateur sur une image locale autorisée existante :
  `frontend-react/demo_drone_orthophoto.jpg`, 640 × 640. 2 détections pour l’image
  entière ; 1 dans la ROI supérieure. Les listes de boîtes Python/Java sont
  identiques et le frontend conserve le même résultat et le même comptage.
- Sur ce test, inférences complètes de l’ordre de 1,79 à 2,15 s, analyse Python
  complète de l’ordre de 1,79 à 2,17 s ; ROI 1 détection, environ 2,03 s au total.
  Observations ponctuelles CPU, sans garantie de latence ni validation de précision.
- Trois modes, sélection tactile, changement d’image pendant analyse, réponse
  obsolète, erreurs serveur et timeout testés dans le navigateur à 1440/768/390 px.
  DEMO image toujours disponible et explicitement simulé.
- Banc satellite/ExG existant réussi sur les trois largeurs, sans nouvelle
  inférence satellite. Empreintes de `detect_any_polygon.py` et `model_config.py`
  inchangées. Générateur DEMO image et fonctions d’analyse vidéo conservés.
- JAR construit avec succès hors ligne ; aucune dépendance installée.

Les tests de réponse obsolète, timeout et erreur réseau du navigateur emploient
des réponses contrôlées uniquement dans le banc. Ils ne créent pas de résultats
simulés dans l’application de production. Les services Java/Python d’intégration
utilisaient des ports loopback temporaires et ont été arrêtés. Les services de
production n’ont pas été redémarrés.

Rapports : `resultats_tests/image-live/pipeline-checks.json`,
`python-responses.json`, `browser-checks.json` et captures dans le même dossier.
Non-régression cartographique : `resultats_tests/image-live-satellite-regression/`.

## Redémarrage

Arrêter les anciennes instances depuis leurs propres terminaux (Ctrl+C), sans
toucher aux autres applications. Le JAR actualisé est déjà construit. Depuis la
racine, dans un terminal pour Python :

```powershell
$env:OLIVESMART_MODEL = 'yolo11m_v1'
& .\.venv\Scripts\python.exe -B ai_engine_server.py
```

Dans un autre terminal :

```powershell
$env:JAVA_HOME = 'C:\Program Files\Eclipse Adoptium\jdk-21.0.13.9-hotspot'
& "$env:JAVA_HOME\bin\java.exe" -jar springboot-microservice-olive/target/olivesmart-detection-microservice-1.0.0.jar --server.port=8080
```

Le serveur frontend existant sert les fichiers actualisés. S’il n’est pas actif,
dans un troisième terminal : `node frontend-react/server.js`. Recharger avec
Ctrl+F5, laisser DEMO décoché, ouvrir Tester Image (Upload), importer une image,
choisir la zone et analyser. Les lanceurs BAT restent inchangés ; ils nécessitent
Java 17 ou supérieur (Java 21 a été utilisé pour la construction).

Pour reconstruire ultérieurement sans installation :

```powershell
$env:JAVA_HOME = 'C:\Program Files\Eclipse Adoptium\jdk-21.0.13.9-hotspot'
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
mvn -o '-Dmaven.repo.local=C:\Users\pc\.m2\repository' '-Djunit-jupiter.version=5.10.1' -f springboot-microservice-olive/pom.xml package
```

La version JUnit passée en argument utilise le cache existant et ne modifie pas
le POM. Si une machine manque d’un artefact hors ligne, ne pas installer sans
autorisation.

## Retour arrière exact

Sauvegarde : `backups/image-live-20261113-161325/`. Arrêter Python et Java dans
leurs terminaux avant restauration. Depuis la racine :

```powershell
$imageBackup = 'backups/image-live-20261113-161325'
foreach ($imageFile in @('ai_engine_server.py','frontend-react/index.html','springboot-microservice-olive/src/main/resources/static/index.html')) {
    Copy-Item -LiteralPath (Join-Path $imageBackup $imageFile) -Destination $imageFile
}
```

Pour retirer aussi la nouvelle route Java sans supprimer les sources, déplacer
les cinq nouvelles classes et leur test dans un dossier d’archive à l’intérieur
du projet. Le contrôle de chemin précède chaque déplacement, sans récursion :

```powershell
$imageRoot = (Get-Location).Path
$imageDisabled = Join-Path $imageRoot 'backups/image-live-20261113-161325/disabled-java'
New-Item -ItemType Directory -Path $imageDisabled -Force | Out-Null
$imageJavaFiles = @(
 'src/main/java/com/olivesmart/detection/controller/ImageAnalysisController.java',
 'src/main/java/com/olivesmart/detection/service/ImageDetectionService.java',
 'src/main/java/com/olivesmart/detection/dto/ImageAnalysisRequest.java',
 'src/main/java/com/olivesmart/detection/dto/ImageAnalysisResponse.java',
 'src/main/java/com/olivesmart/detection/dto/ImageDetectionDto.java',
 'src/test/java/com/olivesmart/detection/service/ImageApiTest.java'
)
foreach ($imageRelative in $imageJavaFiles) {
    $imageSource = (Resolve-Path -LiteralPath (Join-Path 'springboot-microservice-olive' $imageRelative)).Path
    if (-not $imageSource.StartsWith($imageRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Chemin hors projet' }
    $imageDestination = Join-Path $imageDisabled (($imageRelative -replace '[\\/]','_') + '.disabled')
    Move-Item -LiteralPath $imageSource -Destination $imageDestination
}
```

Conserver le JAR intégré dans la sauvegarde si nécessaire, puis reconstruire
avec `mvn -o ... clean package` (mêmes options que ci-dessus). `clean` enlève les
anciens fichiers de compilation dans `target`, notamment les classes Java retirées,
pas les modèles ou données source. Redémarrer Python/Java et recharger Ctrl+F5.
Les nouveaux fichiers Python/JS et les tests peuvent rester archivés : le serveur
et les HTML restaurés ne référencent plus le parcours LIVE. Aucun checkpoint,
environnement virtuel ou donnée métier ne doit être supprimé.
