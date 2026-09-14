# Dockerfile para la Plataforma HeredIA (Fiscalía de Chile)
FROM python:3.11-slim

# Evitar prompts interactivos y buffers de Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Instalar dependencias del sistema operativo (Graphviz, fuentes, utilidades de compilación)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    graphviz \
    libgraphviz-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Definir directorio de trabajo
WORKDIR /app

# Copiar requerimientos e instalar dependencias de Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código fuente del proyecto
COPY . /app/

# Crear carpetas de datos si no existen
RUN mkdir -p /app/data/reportes \
    /app/data/graficos_resultados \
    /app/data/informes_fiscalia \
    /app/data/resumenes_casos

# Exponer el puerto por defecto de Streamlit
EXPOSE 8501

# Configuración de salud del contenedor
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Comando por defecto para iniciar la aplicación web
ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
