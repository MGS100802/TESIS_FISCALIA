# TESIS_FISCALIA

## Sistema Multi-Agente Autónomo para Detección, Análisis y Desarticulación de Redes Criminales

Sistema inteligente de apoyo a la toma de decisiones para el **Ministerio Público / Fiscalía**, fundamentado en la convergencia de:
- **Arquitectura Multi-Agente (MAS)** orquestada mediante **LangGraph**.
- **Modelos de Lenguaje Avanzados (LLMs)** mediante **Google Gemini** para la ingesta cognitiva y redacción forense.
- **Teoría de Grafos y Análisis de Redes Complejas (CNA)** implementado en **NetworkX**.
- **Optimización Matemática Lineal Entera Mixta (MIP)** resuelta con **Gurobi** (modelos de Árboles de Steiner Ponderados - *StRAM/KsRAM*).

---

## 1. Grafo Cíclico del Workflow Multi-Agente

El flujo opera mediante un **Grafo Dirigido Cíclico** con bucles de retroalimentación, autocorrección de parámetros matemáticos y gestión de colas de casos:

```mermaid
flowchart TD
    A[Parte Policial PDF] --> B[IngestionAgent <br> <i>Extracción cognitiva con Gemini</i>]
    B -->|Extrae sospechosos, tipología y metadatos| C[PruningAgent / FilterAgent <br> <i>Poda adaptativa y criminológica</i>]
    
    C -->|Consulta grafo institucional| D[(Base de Datos: Nodos y Aristas)]
    D --> C
    
    C -->|Subgrafo podado relevante| E[StProOptimizationAgent <br> <i>Gurobi MIP / StRAM</i>]
    
    E --> F{AuditorAgent <br> <i>Control de Calidad Forense</i>}
    
    F -- "Infactible / Solución trivial (Reintentar y ajustar φ)" --> E
    F -- "Solución Válida y Aprobada" --> G[Análisis de Interdicción Táctica <br> <i>Cálculo de Blanco de Alto Impacto (HVT)</i>]
    
    G --> H[VisualizationAgent <br> <i>Renderizado de Red Criminal</i>]
    H --> I[ExplanationAgent <br> <i>Redacción Jurídica con Gemini</i>]
    I --> J[Informe Forense y Dictamen Penal (.md)]
    
    J -.->|Bucle de Cola: ¿Quedan más reportes por procesar?| A
```

---

## 2. Agentes Especializados del Ecosistema

1. **`IngestionAgent` (`src/agents/Ingestion_Agent.py`)**:
   - Lee partes policiales en PDF y extrae sospechosos clave (RUTs raíz), tamaño estimado de la banda, tipología penal y metadatos forenses usando **Google Gemini**.
   - Genera resúmenes forenses en `data/resumenes_casos/`.

2. **`PruningAgent` (`src/agents/Filter_Agent.py`)**:
   - **Poda Adaptativa:** Si $N \le 50$, preserva delitos instrumentales conexos (receptación de autos, armas); si $N > 50$, activa poda por $k$-hops y afinidad delictiva descartando delitos disonantes (fraudes/estafas menores).
   - **Protección de Puentes:** Blindaje de puntos de articulación (`nx.articulation_points`) para evitar fracturar la red.

3. **`StProOptimizationAgent` (`src/agents/Optimization_Agent.py`)**:
   - Resuelve el modelo de Árboles de Steiner Ponderados (`StRAM`) en **Gurobi**.
   - Incorpora bucle adaptativo de calibración de $\phi$ ante soluciones triviales.

4. **`AuditorAgent` (`src/agents/Auditor_Agent.py`)**:
   - Realiza control de calidad criminológico y valida el diferencial de riesgo ($\Delta\text{PCG}$).
   - Simula **Interdicción de Redes (*Network Interdiction*)** para identificar al **Blanco de Alto Impacto (HVT - High-Value Target)** cuya captura quiebra la conectividad de la banda.

5. **`VisualizationAgent` (`src/agents/Visualization_Agent.py`)**:
   - Genera representaciones visuales en alta resolución (PNG, 300 DPI) destacando nodos raíz, banda aislada y entorno.

6. **`ExplanationAgent` (`src/agents/Explanation_Agent.py`)**:
   - Redacta el informe forense formal y la propuesta de persecución penal en Markdown (`data/informes_fiscalia/`) para el fiscal adjunto.

---

## 3. Métricas y Evaluación Científica (`src/utils/metrics.py`)

- **Clasificación vs. Ground Truth (`data/true_nodes.csv`):** Precision, Recall, F1-Score, Jaccard Similarity Index, Accuracy.
- **Métricas de Red:** Propensión criminal promedio ($\overline{\text{PCG}}$), densidad interna, clustering promedio, conectividad.
- **Interdicción Táctica:** Caída porcentual de eficiencia global ($\Delta E_{\text{global}}$), centralidad de intermediación (*Betweenness*) y score de prioridad de detención.

---

## 4. Estructura del Repositorio

```text
TESIS_FISCALIA/
│
├── data/
│   ├── reportes/                 # PDFs policiales de entrada
│   ├── resumenes_casos/          # Resúmenes forenses en TXT generados por Gemini
│   ├── graficos_resultados/      # Gráficos PNG de las redes detectadas
│   ├── informes_fiscalia/        # Informes formales para Fiscalía en Markdown (.md)
│   ├── nodes.csv                 # Base de datos de sospechosos (id, pcg, label)
│   ├── edges.csv                 # Base de datos de vínculos (source, target, distance)
│   └── true_nodes.csv            # Ground Truth para validación de la tesis
│
├── src/
│   ├── agents/
│   │   ├── Ingestion_Agent.py    # Ingesta cognitiva de reportes policiales con LLM
│   │   ├── Filter_Agent.py       # PruningAgent (Poda adaptativa y criminológica)
│   │   ├── Optimization_Agent.py # StProOptimizationAgent (Gurobi StRAM adaptativo)
│   │   ├── Auditor_Agent.py      # AuditorAgent (Control de calidad y cálculo HVT)
│   │   ├── Visualization_Agent.py# Generación de gráficos de red
│   │   └── Explanation_Agent.py  # Redacción de informes jurídicos formales con IA
│   │
│   ├── graph/
│   │   └── workflow.py           # Orquestador del grafo de estados en LangGraph
│   │
│   ├── utils/
│   │   ├── models_STRAM_KsRAM.py # Formulaciones matemáticas en Gurobi (StRAM, KsRAM, RGEN)
│   │   └── metrics.py            # Evaluación cuantitativa, métricas de red e interdicción
│   │
│   └── database/                 # Módulos de persistencia y consultas institucionales
│
├── main.py                       # Punto de entrada y ejecución autónoma del pipeline
├── requirements.txt              # Dependencias del proyecto
├── .env                          # Variables de entorno (claves API de Google Gemini / Gurobi)
└── README.md                     # Documentación oficial del proyecto
```

---

## 5. Instalación y Ejecución

```bash
# 1. Crear y activar entorno virtual
python -m venv venv
.\venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar archivo .env
# GOOGLE_GENAI_API_KEY="tu_api_key_de_gemini"

# 4. Ejecutar pipeline autónomo
python main.py
```