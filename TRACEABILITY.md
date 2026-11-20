# Traçabilité OliveSmart

Protection avant correction : copie originale des fichiers dans
`backups/traceability-20261113-012821/`. Aucun dépôt Git n'était présent.

## Contrat conservé et champs ajoutés

Les anciens champs de réponse restent disponibles. Les champs ajoutés sont :

- `success` : réussite du traitement demandé, y compris un résultat vide.
- `mode` : `LIVE` ou `DEMO`.
- `engine` : moteurs effectivement exécutés (`YOLO+OPENCV`, `OPENCV`, `NONE`), ou `DEMO`.
- `model` : `best.pt (YOLOv8n)` en mode réel ; aucun modèle en démonstration.
- `error` : message explicite en cas d'échec.
- Pour chaque arbre : `source`, `sources`, `detectionEngine`.

`source` vaut `YOLO` si le candidat final contient une détection YOLO, sinon
`OPENCV`. Lors d'une fusion, `sources` conserve l'union des origines. Une
simulation est toujours marquée `DEMO`. Le moteur de l'analyse décrit les
traitements exécutés, même si YOLO n'a fourni aucune boîte finale.

La santé reste calculée par les règles ExG existantes ; elle n'est pas une
classe du modèle. Les confiances OpenCV et les règles d'âge restent des
heuristiques non calibrées. Aucun seuil ou algorithme de comptage n'a changé.

## Erreurs et démonstration

Une panne Python produit une réponse HTTP 502 de Java, avec `success:false`
et une liste vide. Python renvoie HTTP 500 si l'analyse échoue. Une tuile
inaccessible ou un échec YOLO annule l'analyse au lieu d'être masqué.

Le navigateur utilise uniquement le relais Java. Il ne remplace plus une
erreur par des données locales et ne réessaie pas un résultat vide sur Python.
Une ancienne réponse sans traçabilité est refusée : mettre les services à jour
ensemble lors de leur prochain redémarrage.

Pour simuler une parcelle via Java, envoyer explicitement `"mode":"DEMO"`.
Le profil `"modelType":"PROF_EXACT_9"` n'est utilisable qu'avec ce mode.
La case DEMO de l'interface est désactivée par défaut. Les modules image/vidéo
existants restent des simulations et nécessitent cette case. L'endpoint Java
vidéo réel répond 501 : il n'avait pas de traitement vidéo réel.

L'article scientifique intégré est conservé comme archive avec un avertissement
visible. Ses noms de modèles, graphiques et chiffres historiques ne décrivent
pas le modèle actuellement chargé. Les anciens rapports, notebooks et le script
historique `frontend-react/generate_index_html.js` restent conservés ; ne pas
relancer ce générateur, qui écraserait l'interface corrigée.

## Vérifications légères

Depuis la racine, sans démarrer de serveur ni charger de modèle :

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_traceability.py -v
node --test tests/traceability.test.cjs
```

Tests Java standard avec Java 21 :

```powershell
mvn -o -f springboot-microservice-olive/pom.xml -Dtest=TraceabilityTest test
```

Dans l'environnement de correction, le lanceur JUnit 1.10.2 manquait au cache.
Les tests ont été exécutés hors ligne avec la variante déjà disponible :

```powershell
mvn -o '-Dmaven.repo.local=C:\Users\pc\.m2\repository' '-Djunit-jupiter.version=5.10.1' -f springboot-microservice-olive/pom.xml '-Dtest=TraceabilityTest' '-Dmaven.test.redirectTestOutputToFile=true' test
```

Cet argument ne change pas le pom.xml. Maven a utilisé Java 21 via des variables
limitées au processus de test. Aucun entraînement, téléchargement ou redémarrage
de service n'est nécessaire pour ces tests.

Après le prochain redémarrage autorisé des services Python et Java, recharger
la page et vérifier `/health`, puis un POST Java avec `{"vertices":[]}` :
`success:true`, `mode:LIVE`, `engine:NONE`, `totalTrees:0`. Ce test ne déclenche
aucune inférence et ne valide donc pas les performances scientifiques du modèle.
