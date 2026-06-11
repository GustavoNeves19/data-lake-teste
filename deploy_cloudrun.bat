@echo off
REM Deploy para Google Cloud Run — Nevoni 360° Dashboard
REM Pre-requisito: gcloud CLI instalado e autenticado

SET PROJECT_ID=sapient-metrics-492914-m7
SET SERVICE=nevoni-dashboard-360
SET REGION=us-east1
SET IMAGE=gcr.io/%PROJECT_ID%/%SERVICE%

echo ========================================
echo Deploy Nevoni 360° → Cloud Run
echo Projeto: %PROJECT_ID%
echo Servico:  %SERVICE%
echo Regiao:   %REGION%
echo ========================================
echo.

REM Build e push da imagem
echo [1/3] Build e push da imagem Docker...
gcloud builds submit --tag %IMAGE% --project %PROJECT_ID%

REM Deploy no Cloud Run com secret para credentials
echo [2/3] Deploy no Cloud Run...
gcloud run deploy %SERVICE% ^
  --image %IMAGE% ^
  --platform managed ^
  --region %REGION% ^
  --project %PROJECT_ID% ^
  --port 8080 ^
  --memory 512Mi ^
  --cpu 1 ^
  --min-instances 1 ^
  --max-instances 3 ^
  --allow-unauthenticated ^
  --set-secrets="/secrets/credentials.json=nevoni-bq-credentials:latest" ^
  --set-env-vars="GOOGLE_APPLICATION_CREDENTIALS=/secrets/credentials.json"

echo [3/3] URL do servico:
gcloud run services describe %SERVICE% --region %REGION% --project %PROJECT_ID% --format "value(status.url)"

pause
