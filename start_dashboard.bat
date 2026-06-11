@echo off
REM Dashboard 360° Nevoni — inicialização local Windows
REM Execute este arquivo a partir da raiz do projeto

cd /d "%~dp0"

echo Iniciando Nevoni 360° Dashboard...
echo Projeto BQ: sapient-metrics-492914-m7
echo Acesse: http://localhost:8080
echo.

py -3 -m streamlit run dashboard/app.py --server.port=8080 --server.address=localhost

pause
