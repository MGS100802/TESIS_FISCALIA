# TESIS_FISCALIA
<<<<<<< HEAD
# Sistema Multi-Agente Autónomo para Detección y Análisis de Redes Criminales

Sistema inteligente basado en **Arquitectura Multi-Agente (MAS)**, **Teoría de Grafos** y **Optimización Matemática (Gurobi)**, orquestado mediante **LangGraph**, diseñado para automatizar la ingesta de partes policiales, el filtrado estructural de redes delictivas, la persecución penal y la generación de informes forenses para el Ministerio Público / Fiscalía.

---

## Arquitectura del Pipeline y Componentes (LangGraph)

El flujo autónomo de punta a punta opera secuencialmente mediante un grafo de estados:

1. **`IngestionAgent`**: Detecta y procesa automáticamente reportes policiales en formato PDF, extrayendo los RUTs involucrados, metadatos y generando resúmenes cognitivos asistidos por **Google Gemini**.
2. **Consulta de Base de Datos Dinámica (SQL)**: Conecta con el repositorio institucional filtrando transaccionalmente nodos y aristas de interés en función de los blancos detectados.
3. **`PruningAgent`**: Aplica una poda inteligente del grafo basada en cercanía estructural ($k$-hops) y tipología delictiva, eliminando ruido y reduciendo la complejidad computacional.
4. **`StProOptimizationAgent` (Gurobi)**: Ejecuta modelos de optimización lineal entera mixta (StRAM) para aislar matemáticamente a los miembros de la banda criminal a partir de un nodo raíz (blanco clave).
5. **`VisualizationAgent`**: Genera visualizaciones de redes complejas de alto impacto visual, destacando nodos objetivos y miembros de la organización detectados.
6. **`ExplanationAgent`**: Utiliza modelos avanzados de lenguaje (Gemini) para redactar un informe forense e inteligencia criminal formal adaptado con lenguaje jurídico para el fiscal a cargo.

---

## Estructura del Proyecto

```text
TESIS_FISCALIA/
│
├── data/
│   ├── reportes/                 # Colocar aquí los PDFs policiales de entrada
│   ├── resumenes_casos/          # Resúmenes forenses en texto generados por Gemini
│   ├── graficos_resultados/      # Visualizaciones PNG de las redes detectadas
│   ├── informes_fiscalia/        # Informes fiscales formales en formato Markdown
│   └── fiscalia.db               # Base de datos relacional de la fiscalía (SQLite)
│
├── src/
│   ├── agents/
│   │   ├── ingestion_agent.py    # Procesamiento y extracción de PDFs
│   │   ├── pruning_agent.py      # Poda estructural y filtrado de redes
│   │   ├── stpro_agent.py        # Modelo de optimización matemática con Gurobi
│   │   ├── visualization_agent.py# Generación de grafos con NetworkX/Matplotlib
│   │   └── explanation_agent.py  # Redacción de informes fiscales con IA
│   │
│   ├── graph/
│   │   └── workflow.py           # Definición del grafo de estados en LangGraph
│   │
│   └── main.py                   # Orquestador y punto de entrada principal
│
├── .gitignore                    # Exclusión de archivos sensibles y datos locales
├── requirements.txt              # Dependencias del proyecto (UTF-8)
└── README.md                     # Documentación oficial del repositorio