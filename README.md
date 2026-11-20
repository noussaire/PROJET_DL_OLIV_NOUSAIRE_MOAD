# OliveSmart

Projet de Moad Moussaoui et Noussaire Benassou — EMSI, sous la direction du Pr. Mohamed Lachgar.

Détection d'arbres sur une parcelle satellite ou une image importée. Trois services : moteur Python sur **8000**, API Spring Boot **3.2.4** sur **8080**, interface web servie par Node.js sur **3000**. Aucune base de données n'est nécessaire. Le serveur Python utilise la bibliothèque HTTP standard, sans FastAPI.

## 1. Prérequis

- Windows 10/11 pour les fichiers `.bat` ; lancement manuel possible sous Linux/macOS.
- Python **3.11 ou 3.12** recommandé, avec pip et venv.
- **JDK 17 ou 21** et **Maven 3.9+** dans le PATH.
- **Node.js 20+** et Git.
- Internet pour installer les dépendances, charger les bibliothèques CDN du frontend et les tuiles satellite Esri.
- Ports **3000, 8000, 8080** libres.

Vérifier dans PowerShell :

```powershell
py --version
java -version
mvn -v
node -v
git --version
```

**La ligne Java version de `mvn -v` doit indiquer 17 ou 21.** Si Maven utilise Java 8, corriger JAVA_HOME. Exemple à adapter au dossier de votre JDK :

```powershell
$env:JAVA_HOME = 'C:\Program Files\Eclipse Adoptium\jdk-21.0.13.9-hotspot'
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
mvn -v
```

## 2. Cloner et installer

```powershell
git clone https://github.com/noussaire/PROJET_DL_OLIV_NOUSAIRE_MOAD.git
cd PROJET_DL_OLIV_NOUSAIRE_MOAD
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Avec Python 3.12, remplacer `py -3.11` par `py -3.12`. Ne pas copier un environnement `.venv` depuis une autre machine : le recréer. Appeler directement son Python évite les erreurs d'activation PowerShell et les alias du Microsoft Store.

Le frontend utilise des CDN et le serveur Node.js natif : **aucun npm install nécessaire**. Le premier téléchargement de PyTorch peut prendre plusieurs minutes.

Les poids sont inclus : `models/yolo11m_olivesmart_v1.pt` (environ 40,5 Mo, modèle par défaut **YOLO11m V1**, classe `trees`) et `best.pt` (ancien profil YOLOv8n). Ne pas les renommer. L'analyse d'image LIVE exige le profil par défaut :

```powershell
$env:OLIVESMART_MODEL = 'yolo11m_v1'
```

## 3. Démarrer : méthode manuelle recommandée

Ouvrir trois terminaux **à la racine du dépôt**. Respecter cet ordre.

### Terminal 1 : moteur IA

```powershell
.\.venv\Scripts\python.exe -u ai_engine_server.py
```

Attendre `Ready: YOLO11m V1`. Depuis un autre terminal :

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Vérifier `status: UP`, `modelLoaded: true`, `profile: yolo11m_v1`. HTTP 503 indique un problème de chargement : lire la sortie Python avant de continuer.

### Terminal 2 : backend Java

```powershell
cd springboot-microservice-olive
mvn clean verify
java -jar target/olivesmart-detection-microservice-1.0.0.jar
```

Ne lancer le JAR que si Maven affiche **BUILD SUCCESS**. Après le démarrage Spring Boot, vérifier depuis un autre terminal :

```powershell
Invoke-RestMethod http://localhost:8080/api/v1/parcelles/metriques-modele
```

L'URL Python configurée dans `src/main/resources/application.properties` est `http://localhost:8000`.

### Terminal 3 : interface

```powershell
cd frontend-react
node server.js
```

Ouvrir **http://localhost:3000**. Garder les trois terminaux ouverts. `Ctrl+C` arrête chaque service. Après modification Java, arrêter le backend, recompiler et relancer le JAR.

### Variante Windows : lancement groupé

Après installation des dépendances et vérification de JAVA_HOME :

```powershell
.\Lancer_Tout_Le_Projet.bat
```

Le script vérifie les prérequis, compile et teste Java puis démarre les services. Attendre leurs messages de démarrage et vérifier les deux URL ci-dessus ; une fenêtre ouverte ne suffit pas à prouver que le modèle est chargé. Ne pas cumuler lancement manuel et groupé. Fermer les processus avec `Ctrl+C` dans leurs fenêtres.

### Linux/macOS

Créer l'environnement avec `python3.11 -m venv .venv`, puis utiliser `.venv/bin/python` à la place de `.\.venv\Scripts\python.exe`. Les commandes Maven, Java et Node restent identiques. Utiliser `curl http://localhost:8000/health` pour vérifier Python.

## 4. Utilisation et limites

- **Carte LIVE** : tracer la zone demandée puis analyser. Les nouvelles tuiles nécessitent Internet. La détection combine YOLO et OpenCV ; le nombre final peut différer du nombre brut de boîtes YOLO.
- **Image importée LIVE** : importer un JPEG/PNG, éventuellement tracer une zone d'intérêt puis analyser. Résultats en pixels, sans GPS, âge, diamètre en mètres ni diagnostic sanitaire.
- **DEMO** : résultats de démonstration, distincts d'une analyse réelle.

Les couleurs de la carte utilisent **ExG = 2G − R − B**, moyenné sur 7 × 7 pixels au centre de chaque arbre. Avec plus de cinq arbres, rouge sous le 15e percentile, orange entre le 15e et le 30e, vert à partir du 30e. Avec cinq arbres ou moins, les seuils sont 0 et 10. Les égalités peuvent modifier les proportions des couleurs.

**Ces couleurs ne prouvent pas une maladie ou la bonne santé d'un arbre.** Les libellés historiques SAIN/STRESS/SUSPECT représentent une comparaison de verdure sans validation diagnostique. La classe `trees` ne garantit pas que chaque arbre soit un olivier. Les métriques d'entraînement ne garantissent pas les performances sur une nouvelle image.

## 5. Tests

Depuis la racine :

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
node --test tests/exg-display.test.cjs tests/map-results.test.cjs tests/traceability.test.cjs tests/upload-image.test.cjs
mvn -B -f springboot-microservice-olive/pom.xml test
```

Deux fichiers historiques de `backups/` sont conservés pour les tests de non-régression. Les tests unitaires ne constituent pas une validation agronomique ni une vérification exhaustive de toutes les fonctions dans le navigateur.

## 6. Dépannage

- **Python ouvre le Store / .venv inaccessible** : installer Python, utiliser `py -3.11`, recréer `.venv` et appeler directement son exécutable.
- **mvn introuvable** : installer Maven et ajouter son dossier bin au PATH.
- **release version 17 not supported** : corriger JAVA_HOME et vérifier `mvn -v`.
- **Impossible de supprimer le JAR pendant mvn clean** : arrêter d'abord le backend qui utilise ce JAR, puis recompiler.
- **Port occupé / Address already in use / EADDRINUSE** : arrêter l'ancienne instance. `Get-NetTCPConnection -State Listen -LocalPort 3000,8000,8080` permet d'identifier les processus.
- **ModuleNotFoundError** : installer requirements.txt avec le Python de `.venv`, puis lancer son `-m pip check`.
- **Modèle absent / health 503** : vérifier les poids et l'erreur Python, puis redémarrer. Aucun autre modèle n'est substitué automatiquement.
- **Erreur 502/504** : vérifier Python sur 8000 puis Java sur 8080 et leurs journaux. Une grande parcelle peut prendre du temps sur CPU.
- **Carte vide / interface incomplète** : vérifier Internet, les CDN et les requêtes Esri bloquées par le réseau ou les extensions.
- **Ancienne interface** : recompiler Java et recharger avec Ctrl+F5. Ne pas exécuter `frontend-react/generate_index_html.js`, générateur historique ne contenant pas toutes les évolutions actuelles.

Les dépendances Python ont des versions minimales dans requirements.txt : une installation future peut nécessiter des ajustements. Le guide et les tests aident à diagnostiquer les problèmes ; aucune absence totale de bugs sur toutes les machines n'est garantie.

## 7. Structure et documentation

- `ai_engine_server.py` : serveur IA ; `detect_any_polygon.py` : satellite et ExG.
- `detect_uploaded_image.py` : images importées ; `model_config.py` et `models/` : modèle.
- `springboot-microservice-olive/` : backend Java ; `frontend-react/` : interface web.
- `tests/`, `tools/` : tests et vérifications.
- `olive_tree_yolo11_training_colab.ipynb` : entraînement optionnel ; inutile pour démarrer avec les poids inclus.
- `rapports_et_articles_pdf/`, `rapports_html/`, `figures/`, `tables/` : livrables académiques.

Documentation complémentaire : [IMAGE_LIVE_V1.md](IMAGE_LIVE_V1.md), [YOLO11M_INTEGRATION.md](YOLO11M_INTEGRATION.md), [EXG_TRANSPARENCY.md](EXG_TRANSPARENCY.md), [MAP_DISPLAY.md](MAP_DISPLAY.md), [TRACEABILITY.md](TRACEABILITY.md).
