#!/bin/bash
echo "========================================================================="
echo "   INICIANDO PLATAFORMA HEREDIA CON DOCKER COMPOSE"
echo "========================================================================="

docker-compose up --build -d
echo "[INFO] Aplicación disponible en http://localhost:8501"
