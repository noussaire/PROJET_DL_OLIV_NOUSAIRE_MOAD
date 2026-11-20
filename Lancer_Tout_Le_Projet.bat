@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo ERREUR : creer .venv et installer requirements.txt. Voir README.md.
    pause
    exit /b 1
)
if not exist "models\yolo11m_olivesmart_v1.pt" (
    echo ERREUR : poids YOLO11m manquants.
    pause
    exit /b 1
)
where node >nul 2>nul
if errorlevel 1 goto :missing
where mvn >nul 2>nul
if errorlevel 1 goto :missing
where java >nul 2>nul
if errorlevel 1 goto :missing
powershell -NoProfile -Command "if (Get-NetTCPConnection -State Listen -LocalPort 3000,8000,8080 -ErrorAction SilentlyContinue) { Write-Host 'ERREUR : un port du projet est occupe. Arreter les anciennes instances.'; exit 1 }"
if errorlevel 1 (
    pause
    exit /b 1
)
echo Verification de Java utilise par Maven : JDK 17 ou 21 requis.
call mvn -v
call mvn -B -f springboot-microservice-olive\pom.xml clean verify
if errorlevel 1 (
    echo ERREUR de compilation. Voir README.md pour JAVA_HOME et les JAR verrouilles.
    pause
    exit /b 1
)
start "OliveSmart IA :8000" /D "%~dp0" cmd /k .venv\Scripts\python.exe -u ai_engine_server.py
start "OliveSmart Java :8080" /D "%~dp0springboot-microservice-olive" cmd /k java -jar target\olivesmart-detection-microservice-1.0.0.jar
start "OliveSmart Web :3000" /D "%~dp0frontend-react" cmd /k node server.js
echo Attendre Ready et le demarrage Spring Boot dans les fenetres.
echo Verifier http://localhost:8000/health et http://localhost:8080/api/v1/parcelles/metriques-modele
echo Puis ouvrir http://localhost:3000 . Arret : Ctrl+C dans chaque fenetre.
pause
exit /b 0
:missing
echo ERREUR : Java, Maven et Node.js doivent etre dans PATH. Voir README.md.
pause
exit /b 1
