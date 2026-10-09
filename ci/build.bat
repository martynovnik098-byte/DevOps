@echo off
REM ============================================================
REM CI stage: run tests and build the wheel artifact inside a
REM Python container. Nothing but Docker is required on host.
REM Result is saved to artifacts\ and picked up by deploy step.
REM Usage:  ci\build.bat
REM ============================================================
setlocal EnableExtensions
cd /d "%~dp0.."
if not exist artifacts mkdir artifacts

echo ==^> Step 1/3. Running tests inside container python:3.12-slim ...
docker run --rm --volume "%cd%\app:/app" --workdir /app python:3.12-slim bash -c "pip install --quiet flask prometheus-client && python -m unittest discover -s tests -v"
if errorlevel 1 goto :fail

echo ==^> Step 2/3. Building wheel artifact inside container ...
docker run --rm --volume "%cd%\app:/app" --workdir /app --volume "%cd%\artifacts:/out" python:3.12-slim bash -c "pip install --quiet build && python -m build --wheel --outdir /out"
if errorlevel 1 goto :fail

set WHEEL=
for /f "delims=" %%i in ('dir /b /o-d "artifacts\*.whl"') do if not defined WHEEL set WHEEL=%%i
if not defined WHEEL goto :fail_no_wheel
>"artifacts\LATEST" echo %WHEEL%

echo ==^> Step 3/3. Done. Artifact saved: artifacts\%WHEEL%
echo     Next step: deploy\deploy.bat
exit /b 0

:fail_no_wheel
echo ERROR: no wheel file found in artifacts\ .
exit /b 1

:fail
echo ERROR: CI step failed, see log above.
exit /b 1
