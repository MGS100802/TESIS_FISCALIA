# TESIS_FISCALIA
# Sistema Multiagente Cognitivo y Optimización Matemática para la Investigación Criminal (StRAM)

Repositorio oficial para el desarrollo de la tesis de postgrado enfocada en la **construcción agéntica autónoma de grafos y optimización basada en árboles de Steiner** para el análisis y disrupción de redes criminales, integrando explicabilidad de IA (XAI) y filtrado contextual de causas.

---

## 🏗️ Arquitectura del Sistema Multiagente (MAS)

El pipeline de procesamiento se compone de **4 agentes autónomos** orquestados mediante LangGraph:

1. **`Ingestion_Agent`**: Carga, normaliza y estructura los datos de sospechosos (`nodes.csv`) y relaciones/distancias sociales (`edges.csv`).
2. **`Filter_Agent`**: Realiza un filtrado previo del grafo, eliminando nodos y aristas con antecedentes o causas no relacionadas al tipo de ilícito investigado (evitando ruido analítico).
3. **`Optimization_Agent`**: Núcleo matemático basado en Programación Entera Mixta (MILP) que ejecuta el modelo *StPro* (Node-Weighted Steiner Tree Problem) a partir de un sospechoso raíz ($r$) y un parámetro de presupuesto ($\varphi$).
4. **`Explaner_Agent` (XAI)**: Traduce la subred criminal optimizada en un informe forense fundamentado en lenguaje natural para la toma de decisiones del fiscal.


---

## 📂 Estructura del Repositorio

```text
TESIS_FISCALIA/
│
├── data/                      # Datos anonimizados y ground truth
│   ├── nodes.csv              # Universo de sospechosos y propensiones (Pcg)
│   ├── edges.csv              # Aristas de relaciones y distancias sociales (d_ij)
│   └── true_nodes.csv         # Ground truth (miembros reales de la banda objetivo)
│
├── src/                       # Código fuente principal
│   ├── agents/                # Módulos de los 5 Agentes Autónomos
│   ├── database/              # Conexión con Neo4j
│   ├── utils/                 # Modelos matemáticos (PuLP) y métricas
│   └── main.py                # Orquestador principal de LangGraph
│
├── .env                       # Variables de entorno
├── requirements.txt           # Dependencias del proyecto
└── README.md                  # Documentación