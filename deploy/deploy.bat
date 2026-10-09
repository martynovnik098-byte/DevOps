@echo off
REM ============================================================
REM CD stage: build docker image FROM THE ARTIFACT and deploy
REM the whole stack (app + Prometheus + Grafana + cAdvisor)
REM via docker compose.
REM Usage:  deploy\deploy.bat   (run ci\build.bat first)
REM ============================================================
setlocal EnableExtensions
cd /d "%~dp0.."

set WHEEL=
if exist "artifacts\LATEST" set /p WHEEL=<"artifacts\LATEST"
if defined WHEEL if not exist "artifacts\%WHEEL%" set WHEEL=
if not defined WHEEL for /f "delims=" %%i in ('dir /b /o-d "artifacts\*.whl" 2^>nul') do if not defined WHEEL set WHEEL=%%i
if not defined WHEEL (
  echo ERROR: no wheel artifact in artifacts\ . Run ci\build.bat first.
  exit /b 1
)

for /f "tokens=2 delims=-" %%v in ("%WHEEL%") do set VERSION=%%v
set IMAGE=notes-app:%VERSION%

echo ==^> Step 1/2. Building image %IMAGE% from artifact artifacts\%WHEEL% ...
docker build --build-arg "WHEEL=artifacts/%WHEEL%" --tag "%IMAGE%" .
if errorlevel 1 goto :fail

echo ==^> Step 2/2. Deploying stack with docker compose ...
set APP_IMAGE=%IMAGE%
docker compose up -d --remove-orphans
if errorlevel 1 goto :fail

docker compose ps
echo.
echo Done! Links:
echo   App          http://localhost:8080
echo   Health check http://localhost:8080/health
echo   Metrics      http://localhost:8080/metrics
echo   Prometheus   http://localhost:9090
echo   Grafana      http://localhost:3000   ^(admin / admin^)
echo   cAdvisor     http://localhost:8081
exit /b 0

:fail
echo ERROR: deploy step failed, see log above.
exit /b 1
