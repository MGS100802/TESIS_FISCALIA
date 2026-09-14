@echo off
title Plataforma HeredIA - Fiscalia de Chile (Docker Container)
echo =========================================================================
echo    INICIANDO PLATAFORMA HEREDIA CON DOCKER COMPOSE
echo =========================================================================
echo.
echo [1/2] Construyendo y levantando contenedor Docker...
docker-compose up --build -d
echo.
echo [2/2] Contenedor activo. Abriendo navegador en http://localhost:8501 ...
start http://localhost:8501
echo.
echo Para ver los logs del contenedor ejecute: docker-compose logs -f
echo Para detener la aplicacion ejecute: docker-compose down
echo.
pause
