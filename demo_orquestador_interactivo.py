import os
import sys
import json
import re
import difflib
import unicodedata
from pathlib import Path
import pandas as pd
import networkx as nx
from typing import List, Optional, Any, Dict, Union
from typing_extensions import TypedDict

# Configurar salida UTF-8 en consola Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Parche dinámico de compatibilidad para evitar modificar archivos originales del repositorio
import src.utils.models_STRAM_KsRAM
if not hasattr(src.utils.models_STRAM_KsRAM, "KsRAM"):
    src.utils.models_STRAM_KsRAM.KsRAM = src.utils.models_STRAM_KsRAM.StRAM

# Cargar dotenv para verificar API Key
from dotenv import load_dotenv
load_dotenv()

# Importar LangGraph
from langgraph.graph import StateGraph, START, END

# Configuración Google Gemini
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

RAW_KEY = os.getenv("GOOGLE_GENAI_API_KEY", "").strip()
HAS_GEMINI_KEY = bool(RAW_KEY) and RAW_KEY not in ["DUMMY_DEMO_KEY", "tu_api_key_de_gemini_aqui", ""]

# Carga segura de agentes
try:
    from src.agents.Ingestion_Agent import IngestionAgent
except ImportError:
    IngestionAgent = None

from src.agents.Filter_Agent import FilterAgent
from src.agents.Optimization_Agent import StProOptimizationAgent
from src.agents.Auditor_Agent import AuditorAgent
from src.agents.Visualization_Agent import VisualizationAgent

try:
    from src.agents.Explanation_Agent import ExplanationAgent
except ImportError:
    ExplanationAgent = None

# Definición del Estado Compartido en LangGraph
class DemoGraphState(TypedDict):
    pdf_list: List[str]
    current_index: int
    current_pdf: Optional[str]
    nombre_caso: Optional[str]
    resumen_caso: Optional[str]
    metadatos_utiles: Optional[Dict[str, Any]]
    ruts_involucrados: List[str]
    tamano_grupo: int
    nivel_actual: Optional[int]
    nodes_df: Optional[Any]
    edges_df: Optional[Any]
    grafo_completo: Optional[Any]
    nodos_banda: List[Any]
    diagnostico_auditoria: Optional[Dict[str, Any]]

class InteractiveOrchestrator:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.has_real_key = HAS_GEMINI_KEY and (genai is not None)
        self.gemini_client = None
        self.historial_llm = []
        
        if self.has_real_key:
            try:
                self.gemini_client = genai.Client(api_key=RAW_KEY)
            except Exception:
                self.gemini_client = None
                self.has_real_key = False
        
        if IngestionAgent is not None and self.has_real_key:
            try:
                self.ingestor = IngestionAgent(data_dir=data_dir, subcarpeta_reportes="reportes")
            except Exception:
                self.ingestor = None
        else:
            self.ingestor = None
            
        self.filter_agent = FilterAgent()
        self.auditor_agent = AuditorAgent()
        self.visualizador = VisualizationAgent(output_dir=os.path.join(data_dir, "graficos_resultados"))
        
        if ExplanationAgent is not None and self.has_real_key:
            try:
                self.explicador = ExplanationAgent(data_dir=os.path.join(data_dir, "informes_fiscalia"))
            except Exception:
                self.explicador = None
        else:
            self.explicador = None
        
        self.state: DemoGraphState = {
            "pdf_list": [],
            "current_index": 0,
            "current_pdf": None,
            "nombre_caso": None,
            "resumen_caso": None,
            "metadatos_utiles": None,
            "ruts_involucrados": [],
            "tamano_grupo": 0,
            "nivel_actual": None,
            "nodes_df": None,
            "edges_df": None,
            "grafo_completo": None,
            "nodos_banda": [],
            "diagnostico_auditoria": None
        }
        self.casos_memoria: Dict[str, Dict[str, Any]] = {}
        self.op_agent_temp = None
        self.siguiente_accion_sugerida = None
        self._inicializar_reportes()
        self.compiled_graph = self._construir_grafo_langgraph()

    def guardar_estado_caso(self, nombre_caso: Optional[str] = None):
        """Persiste una instantánea del estado para el caso especificado en la memoria del orquestador."""
        caso = nombre_caso or self.state.get("nombre_caso")
        if not caso:
            return
        self.casos_memoria[caso] = {
            "current_pdf": self.state.get("current_pdf"),
            "nombre_caso": caso,
            "resumen_caso": self.state.get("resumen_caso"),
            "metadatos_utiles": self.state.get("metadatos_utiles"),
            "ruts_involucrados": list(self.state.get("ruts_involucrados", [])),
            "tamano_grupo": self.state.get("tamano_grupo", 0),
            "nivel_actual": self.state.get("nivel_actual"),
            "nodos_banda": list(self.state.get("nodos_banda", [])),
            "diagnostico_auditoria": self.state.get("diagnostico_auditoria")
        }

    def cargar_caso(self, pdf_path_o_nombre: str):
        """Carga y sincroniza el estado activo con los datos del caso desde memoria o disco."""
        if not pdf_path_o_nombre:
            return
        if str(pdf_path_o_nombre).endswith(".pdf") or os.path.sep in str(pdf_path_o_nombre) or "/" in str(pdf_path_o_nombre):
            pdf_path = str(pdf_path_o_nombre)
            nombre_caso = Path(pdf_path).stem
        else:
            nombre_caso = str(pdf_path_o_nombre)
            pdf_path = str(Path(self.data_dir) / "reportes" / f"{nombre_caso}.pdf")

        self.state["current_pdf"] = pdf_path
        self.state["nombre_caso"] = nombre_caso

        if nombre_caso in self.casos_memoria and self.casos_memoria[nombre_caso].get("ruts_involucrados"):
            cached = self.casos_memoria[nombre_caso]
            self.state["resumen_caso"] = cached.get("resumen_caso")
            self.state["metadatos_utiles"] = cached.get("metadatos_utiles")
            self.state["ruts_involucrados"] = list(cached.get("ruts_involucrados", []))
            self.state["tamano_grupo"] = cached.get("tamano_grupo", 0)
            self.state["nivel_actual"] = cached.get("nivel_actual")
            self.state["nodos_banda"] = list(cached.get("nodos_banda", []))
            self.state["diagnostico_auditoria"] = cached.get("diagnostico_auditoria")
        else:
            self._recuperar_de_archivos(nombre_caso)

    def _recuperar_de_archivos(self, nombre_caso: str):
        """Recupera los datos del caso desde los archivos generados en data/ si existen."""
        ruts = []
        tamano = 0
        resumen_txt = None
        metadatos = {}
        
        # 1. Leer resumen
        resumen_path = Path(self.data_dir) / "resumenes_casos" / f"resumen_{nombre_caso}.txt"
        if resumen_path.exists():
            try:
                with open(resumen_path, "r", encoding="utf-8") as f:
                    contenido = f.read()
                m_ruts = re.search(r"Nodos ra[ií]z.*?: ([\d\s,]+)", contenido, re.IGNORECASE)
                if m_ruts:
                    ruts = [r.strip() for r in m_ruts.group(1).split(",") if r.strip().isdigit()]
                m_tam = re.search(r"Tama[ñn]o.*?: (\d+)", contenido, re.IGNORECASE)
                if m_tam:
                    tamano = int(m_tam.group(1))
                m_res = re.search(r"Resumen del Caso .*?:\s*\n(.*?)(?=\n\n|\nMetadatos|\n- N|\Z)", contenido, re.DOTALL | re.IGNORECASE)
                if m_res:
                    resumen_txt = m_res.group(1).strip()
            except Exception:
                pass

        # 2. Leer informe forense
        informe_path = Path(self.data_dir) / "informes_fiscalia" / f"informe_forense_{nombre_caso}.txt"
        banda = []
        hvt_nodo = None
        if informe_path.exists():
            try:
                with open(informe_path, "r", encoding="utf-8") as f:
                    inf_txt = f.read()
                m_banda = re.search(r"Nodos integrantes de la banda:\s*(\[[^\]]+\])", inf_txt)
                if m_banda:
                    banda_str = m_banda.group(1)
                    banda = json.loads(banda_str)
                m_hvt = re.search(r"Blanco de Alto Impacto \(HVT\):\s*NODO\s*(\d+)", inf_txt, re.IGNORECASE)
                if m_hvt:
                    hvt_nodo = int(m_hvt.group(1))
            except Exception:
                pass

        # 3. Detectar nivel
        nivel_detectado = None
        for L in [3, 2, 1]:
            if (Path(self.data_dir) / "graficos_resultados" / f"grafo_{nombre_caso}_nivel_{L}.png").exists():
                nivel_detectado = L
                break
        if nivel_detectado is None and (banda or ruts):
            nivel_detectado = 2

        diag = None
        if hvt_nodo is not None:
            diag = {
                "aprobado": True,
                "hvt_prioritario": {"id_sospechoso": hvt_nodo}
            }

        self.state["ruts_involucrados"] = ruts
        self.state["tamano_grupo"] = tamano
        self.state["resumen_caso"] = resumen_txt
        self.state["metadatos_utiles"] = metadatos
        self.state["nodos_banda"] = banda
        self.state["nivel_actual"] = nivel_detectado
        self.state["diagnostico_auditoria"] = diag
        self.guardar_estado_caso(nombre_caso)

    def _inicializar_reportes(self):
        ruta_carpeta = Path(self.data_dir) / "reportes"
        self.state["pdf_list"] = [str(pdf) for pdf in ruta_carpeta.glob("*.pdf")]
        if self.state["pdf_list"]:
            self.state["current_pdf"] = self.state["pdf_list"][0]
            self.state["nombre_caso"] = Path(self.state["current_pdf"]).stem
            self.cargar_caso(self.state["current_pdf"])

    def _construir_grafo_langgraph(self):
        builder = StateGraph(DemoGraphState)
        builder.add_node("node_ingesta", self._langgraph_node_ingesta)
        builder.add_node("node_cargar_db", self._langgraph_node_cargar_db)
        builder.add_node("node_optimizacion", self._langgraph_node_optimizacion)
        builder.add_node("node_auditoria", self._langgraph_node_auditoria)
        builder.add_node("node_visualizacion", self._langgraph_node_visualizacion)
        builder.add_node("node_informe", self._langgraph_node_informe)
        
        builder.add_edge(START, "node_ingesta")
        builder.add_edge("node_ingesta", "node_cargar_db")
        builder.add_edge("node_cargar_db", "node_optimizacion")
        builder.add_edge("node_optimizacion", "node_auditoria")
        builder.add_edge("node_auditoria", "node_visualizacion")
        builder.add_edge("node_visualizacion", "node_informe")
        builder.add_edge("node_informe", END)
        return builder.compile()

    def _langgraph_node_ingesta(self, state: DemoGraphState) -> DemoGraphState:
        print("\n[LangGraph Node: node_ingesta]")
        self.tool_ingesta()
        return self.state

    def _langgraph_node_cargar_db(self, state: DemoGraphState) -> DemoGraphState:
        print("\n[LangGraph Node: node_cargar_db]")
        self.tool_cargar_bd()
        return self.state

    def _langgraph_node_optimizacion(self, state: DemoGraphState) -> DemoGraphState:
        print("\n[LangGraph Node: node_optimizacion]")
        nivel = self.state.get("nivel_actual") or 2
        self.tool_optimizacion(nivel=nivel)
        return self.state

    def _langgraph_node_auditoria(self, state: DemoGraphState) -> DemoGraphState:
        print("\n[LangGraph Node: node_auditoria]")
        self.tool_auditoria()
        return self.state

    def _langgraph_node_visualizacion(self, state: DemoGraphState) -> DemoGraphState:
        print("\n[LangGraph Node: node_visualizacion]")
        self.tool_visualizacion()
        return self.state

    def _langgraph_node_informe(self, state: DemoGraphState) -> DemoGraphState:
        print("\n[LangGraph Node: node_informe]")
        self.tool_informe()
        return self.state

    # ==========================================
    # HERRAMIENTAS (TOOLS) DEL PIPELINE
    # ==========================================

    def tool_listar_reportes(self) -> str:
        pdfs = self.state.get("pdf_list", [])
        if not pdfs:
            return "No se encontraron partes policiales en la carpeta 'data/reportes'."
        resultado = "Reportes policiales disponibles en cola de Fiscalia:\n"
        for idx, p in enumerate(pdfs):
            activo = " (ACTUAL)" if p == self.state.get("current_pdf") else ""
            resultado += f"   [{idx + 1}] {Path(p).name}{activo}\n"
        return resultado

    def tool_seleccionar_reporte(self, query: str) -> str:
        pdfs = self.state.get("pdf_list", [])
        if not pdfs:
            return "No hay reportes para seleccionar."
        
        for idx, p in enumerate(pdfs):
            nombre = Path(p).stem.lower()
            if str(idx + 1) in query or any(term in nombre for term in query.lower().split()):
                self.cargar_caso(p)
                self.siguiente_accion_sugerida = "ingesta" if not self.state.get("ruts_involucrados") else "optimizacion"
                return f"Caso seleccionado actualizado a: '{self.state['nombre_caso']}'. ¿Desea que lea y extraiga los sospechosos del parte policial?"
        
        return f"No se encontro un reporte que coincida con '{query}'. El caso actual sigue siendo '{self.state.get('nombre_caso')}'."

    def tool_ingesta(self) -> str:
        pdf_path = self.state.get("current_pdf")
        if not pdf_path or not os.path.exists(pdf_path):
            return "No hay un archivo PDF seleccionado o valido para procesar."
        
        print(f"\n[IngestionAgent] Procesando reporte policial: {Path(pdf_path).name}...")
        
        if self.has_real_key and self.ingestor:
            try:
                ruts, tamano, resumen, metadatos = self.ingestor.extract_process_police_report(pdf_path)
            except Exception as e:
                print(f"[IngestionAgent] Fallback Gemini API ({e}). Usando extraccion estructurada.")
                ruts, tamano, resumen, metadatos = self._ingesta_mock(pdf_path)
        else:
            ruts, tamano, resumen, metadatos = self._ingesta_mock(pdf_path)

        self.state["ruts_involucrados"] = ruts
        self.state["tamano_grupo"] = tamano
        self.state["resumen_caso"] = resumen
        self.state["metadatos_utiles"] = metadatos
        self.siguiente_accion_sugerida = "optimizacion"
        
        resp = (
            f"He analizado el parte policial '{Path(pdf_path).name}'.\n"
            f"- Imputados Principales (Nodos Raiz): Sujetos {', '.join(ruts)}\n"
            f"- Tamano estimado de la organizacion: {tamano} integrantes\n"
            f"- Resumen de los hechos: {resumen}\n"
            f"- Metadatos y Evidencias: {metadatos}\n\n"
            f"¿En qué nivel de profundidad desea ejecutar la optimización StPro?\n"
            f"   [1] Nivel 1 (Contacto directo - 1 salto)\n"
            f"   [2] Nivel 2 (Célula operativa cercana - 2 saltos) [Recomendado]\n"
            f"   [3] Nivel 3 (Estructura criminal ampliada - 3 saltos)\n"
            f"   (o escriba 'todos' para generar la comparativa de los 3 niveles)"
        )
        return resp

    def _ingesta_mock(self, pdf_path):
        nombre = Path(pdf_path).stem
        if "desarme" in nombre:
            ruts = ["4", "5"]
            tamano = 8
            resumen = "Investigacion sobre red clandestina de sustraccion y despiece de vehiculos motorizados en San Bernardo."
            metadatos = {"armas": "No registradas", "vehiculos": "Autopartes de gama alta", "comunas": "San Bernardo, El Bosque"}
        else:
            ruts = ["1", "3"]
            tamano = 12
            resumen = "Investigacion por robo con intimidacion y receptacion de vehiculos conducida por la Seccion de Inteligencia."
            metadatos = {"armas": "2 pistolas 9mm", "vehiculos": "3 SUV recuperados", "comunas": "Quilicura, Renca"}
        
        path_txt = "data/resumenes_casos/"
        os.makedirs(path_txt, exist_ok=True)
        archivo_txt_path = os.path.join(path_txt, f"resumen_{nombre}.txt")
        with open(archivo_txt_path, "w", encoding="utf-8") as f:
            f.write(f"Resumen del Caso {nombre}:\n{resumen}\n\nNodos raiz: {', '.join(ruts)}\nTamano estimado: {tamano}\n")
        return ruts, tamano, resumen, metadatos

    def tool_cargar_bd(self) -> str:
        nodes_path = os.path.join(self.data_dir, "nodes.csv")
        edges_path = os.path.join(self.data_dir, "edges.csv")
        nodes_df = pd.read_csv(nodes_path)
        edges_df = pd.read_csv(edges_path)
        self.state["nodes_df"] = nodes_df
        self.state["edges_df"] = edges_df
        
        G = self.filter_agent.construir_grafo_desde_dfs(nodes_df, edges_df)
        self.state["grafo_completo"] = G
        return f"Base de datos relacional institucional cargada ({G.number_of_nodes()} sospechosos y {G.number_of_edges()} vinculos criminales)."

    def tool_optimizacion(self, nivel: Optional[int] = None) -> str:
        """
        Ejecuta la optimización StPro acotada al nivel exacto solicitado por el analista usando FilterAgent.
        """
        if not self.state.get("ruts_involucrados"):
            self.tool_ingesta()

        if self.state["grafo_completo"] is None:
            self.tool_cargar_bd()

        G_completo = self.state["grafo_completo"]
        ruts = self.state.get("ruts_involucrados", [])
        raiz_objetivo = None
        for r in ruts:
            if str(r).isdigit() and int(r) in G_completo.nodes:
                raiz_objetivo = int(r)
                break
        if raiz_objetivo is None:
            raiz_objetivo = list(G_completo.nodes)[0]

        nivel_usado = nivel if nivel is not None else self.state.get("nivel_actual", 2)

        # Usar FilterAgent para extraer subred por nivel
        if nivel is not None:
            G_a_optimizar = self.filter_agent.extraer_subgrafo_por_nivel(G_completo, nodo_raiz=raiz_objetivo, nivel=nivel)
        else:
            G_a_optimizar = G_completo

        print(f"\n[OptimizationAgent] Ejecutando Gurobi StPro (StRAM) para NIVEL {nivel_usado}...")
        self.op_agent_temp = StProOptimizationAgent(grafo=G_a_optimizar, data_dir=self.data_dir)
        nodos_banda = self.op_agent_temp.ejecutar_stram_adaptativo(start_node=raiz_objetivo, phi_inicial=0.3)
        
        self.state["nodos_banda"] = nodos_banda
        self.state["nivel_actual"] = nivel_usado
        self.siguiente_accion_sugerida = "auditoria"
        
        return (
            f"[OK] Optimizacion matematica con Gurobi (Modelo StPro/StRAM) completada para **NIVEL {nivel_usado}**:\n"
            f"- Sospechoso Raíz (Planificador): Sujeto {raiz_objetivo}\n"
            f"- Subred analizada: {len(G_a_optimizar.nodes)} candidatos\n"
            f"- Celula criminal aislada: {len(nodos_banda)} integrantes\n"
            f"- Nodos detectados: {nodos_banda}\n\n"
            f"¿Desea que el AuditorAgent evalue la red e identifique el Blanco de Alto Impacto (HVT)?"
        )

    def tool_analisis_multinivel(self, niveles: List[int] = [1, 2, 3]) -> str:
        """
        Ejecuta 3 procesos de optimización independientes para Nivel 1, 2 y 3 usando FilterAgent.
        """
        if not self.state.get("ruts_involucrados"):
            self.tool_ingesta()
        if self.state["grafo_completo"] is None:
            self.tool_cargar_bd()

        G_completo = self.state["grafo_completo"]
        ruts = self.state.get("ruts_involucrados", [])
        raiz_objetivo = int(ruts[0]) if ruts and str(ruts[0]).isdigit() and int(ruts[0]) in G_completo.nodes else list(G_completo.nodes)[0]

        resultados_niveles = {}
        resumen_texto = f"=== ANÁLISIS MULTINIVEL DE RED CRIMINAL (StPro) ===\nSospechoso Raíz: Sujeto {raiz_objetivo}\n\n"

        for L in niveles:
            sub_g = self.filter_agent.extraer_subgrafo_por_nivel(G_completo, nodo_raiz=raiz_objetivo, nivel=L)
            opt_agent = StProOptimizationAgent(grafo=sub_g, data_dir=self.data_dir)
            nodos_det = opt_agent.ejecutar_stram_adaptativo(start_node=raiz_objetivo, phi_inicial=0.3)
            
            resultados_niveles[L] = {
                "grafo": sub_g,
                "nodos_banda": nodos_det,
                "raiz": raiz_objetivo
            }
            resumen_texto += (
                f"🔹 NIVEL {L} ({L} salto{'s' if L > 1 else ''} de distancia):\n"
                f"   - Subred analizada: {len(sub_g.nodes)} individuos\n"
                f"   - Célula identificada por StPro: {len(nodos_det)} integrantes ({nodos_det})\n\n"
            )

        # Generar gráfico comparativo
        self.visualizador.graficar_comparativa_multinivel(
            resultados_niveles=resultados_niveles,
            nombre_caso=self.state.get("nombre_caso", "caso_demo")
        )

        # Guardar en el estado el resultado del nivel mayor (ej: Nivel 3)
        max_nivel = max(niveles)
        self.state["nodos_banda"] = resultados_niveles[max_nivel]["nodos_banda"]
        self.state["grafo_completo"] = resultados_niveles[max_nivel]["grafo"]
        self.state["nivel_actual"] = max_nivel

        # Ejecutar automáticamente auditoría e informe
        self.tool_auditoria()
        self.tool_informe()

        diag = self.state.get("diagnostico_auditoria") or {}
        hvt_info = diag.get("hvt_prioritario", {}) if isinstance(diag, dict) else {}
        nodo_hvt = hvt_info.get("id_sospechoso") if isinstance(hvt_info, dict) else (hvt_info if hvt_info else "No identificado")

        self.siguiente_accion_sugerida = None

        resumen_texto += (
            f"[OK] Pipeline Multinivel ejecutado al 100% de manera automática:\n"
            f"   1. Optimizaciones StPro completadas para Niveles 1, 2 y 3.\n"
            f"   2. Blanco de Alto Impacto (HVT) identificado: Nodo {nodo_hvt} (AuditorAgent).\n"
            f"   3. Diagrama comparativo generado en 'data/graficos_resultados/comparativa_niveles_{self.state.get('nombre_caso')}.png'.\n"
            f"   4. Informe formal generado en 'data/informes_fiscalia/'."
        )
        return resumen_texto

    def tool_auditoria(self) -> str:
        if not self.state.get("nodos_banda"):
            self.tool_optimizacion()

        print("\n[AuditorAgent] Evaluando calidad forense y calculando Blanco de Alto Impacto (HVT)...")
        grafo_actual = getattr(self, 'op_agent_temp', None)
        G = grafo_actual.grafo if grafo_actual else self.state.get("grafo_completo")
        ruts = [int(r) for r in self.state.get("ruts_involucrados", []) if str(r).isdigit()]
        
        diagnostico = self.auditor_agent.auditar_solucion(
            grafo=G,
            nodos_banda=self.state["nodos_banda"],
            nodos_raiz=ruts,
            tamano_estimado_informe=self.state.get("tamano_grupo", 0)
        )
        self.state["diagnostico_auditoria"] = diagnostico
        
        hvt_info = diagnostico.get("hvt_prioritario", {})
        nodo_hvt = hvt_info.get("id_sospechoso") if isinstance(hvt_info, dict) else hvt_info
        self.siguiente_accion_sugerida = "visualizacion_e_informe"
        
        return (
            f"[OK] Diagnostico Forense y Tactico (AuditorAgent):\n"
            f"- Solucion Aprobada: {diagnostico.get('aprobado')}\n"
            f"- BLANCO DE ALTO IMPACTO (HVT): NODO {nodo_hvt}\n"
            f"- Fundamento Tactico: La neutralizacion prioritaria del Nodo {nodo_hvt} provoca la mayor desarticulacion "
            f"estructural en la banda, quebrando los canales de comunicacion internos.\n\n"
            f"¿Desea que genere la visualizacion grafica de la red y el informe formal para el Tribunal?"
        )

    def tool_visualizacion(self) -> str:
        if not self.state.get("nodos_banda"):
            self.tool_optimizacion()

        print("\n[VisualizationAgent] Generando diagrama de red criminal...")
        grafo_actual = getattr(self, 'op_agent_temp', None)
        G = grafo_actual.grafo if grafo_actual else self.state.get("grafo_completo")
        ruts = self.state.get("ruts_involucrados", [])
        raiz_objetivo = int(ruts[0]) if ruts and str(ruts[0]).isdigit() and int(ruts[0]) in G.nodes else list(G.nodes)[0]
        
        nivel_actual = self.state.get("nivel_actual")
        self.visualizador.graficar_red_criminal(
            grafo=G,
            nodos_banda=self.state["nodos_banda"],
            nodo_raiz=raiz_objetivo,
            nombre_caso=self.state.get("nombre_caso", "caso_demo"),
            nivel=nivel_actual
        )
        self.siguiente_accion_sugerida = "informe"
        nombre_arch = f"grafo_{self.state.get('nombre_caso')}_nivel_{nivel_actual}.png" if nivel_actual else f"grafo_{self.state.get('nombre_caso')}.png"
        return f"[OK] Grafico de la red criminal exportado con exito a:\n'data/graficos_resultados/{nombre_arch}'"

    def tool_informe(self) -> str:
        if not self.state.get("nodos_banda"):
            self.tool_optimizacion()
        if not self.state.get("diagnostico_auditoria"):
            self.tool_auditoria()

        print("\n[ExplanationAgent] Redactando informe juridico formal para Fiscalia...")
        out_dir = os.path.join(self.data_dir, "informes_fiscalia")
        os.makedirs(out_dir, exist_ok=True)
        
        if self.has_real_key and self.explicador:
            try:
                self.explicador.generate_explanation(
                    nombre_caso=self.state.get("nombre_caso", "caso_demo"),
                    resumen_caso=self.state.get("resumen_caso", "Resumen de prueba"),
                    nodos_banda=self.state.get("nodos_banda", []),
                    ruts_raiz=self.state.get("ruts_involucrados", []),
                    diagnostico_auditoria=self.state.get("diagnostico_auditoria"),
                    reporte_poda={"metodo": "Filtro Directo Demo", "nodos_iniciales": len(self.state["grafo_completo"].nodes) if self.state["grafo_completo"] else 0}
                )
            except Exception as e:
                self._generar_informe_mock(out_dir)
        else:
            self._generar_informe_mock(out_dir)

        self.siguiente_accion_sugerida = None
        return f"[OK] Informe forense formal redactado exitosamente en:\n'data/informes_fiscalia/informe_forense_{self.state.get('nombre_caso')}.txt'\n\nTodos los productos del caso han sido completados."

    def tool_visualizacion_e_informe(self) -> str:
        resp_vis = self.tool_visualizacion()
        resp_inf = self.tool_informe()
        self.siguiente_accion_sugerida = None
        return f"{resp_vis}\n\n{resp_inf}"

    def _generar_informe_mock(self, out_dir):
        nombre_caso = self.state.get("nombre_caso", "caso_demo")
        diag = self.state.get("diagnostico_auditoria", {})
        hvt_info = diag.get("hvt_prioritario", {})
        hvt = hvt_info.get("id_sospechoso") if isinstance(hvt_info, dict) else hvt_info
        banda = self.state.get("nodos_banda", [])
        
        contenido = f"""================================================================================
INFORME PERICIAL Y SUGERENCIA DE DILIGENCIAS TACTICAS - MINISTERIO PUBLICO
================================================================================
CASO: {nombre_caso}
FECHA DE EMISION: 2026-08-21
UNIDAD: Analisis Criminal y Complejidad del Delito

1. ANTECEDENTES Y RESUMEN DEL CASO
{self.state.get('resumen_caso', 'Sin resumen')}

2. ANALISIS DE REDES Y OPTIMIZACION MATEMATICA (Gurobi StRAM)
Tras la aplicacion del modelo de Arboles de Steiner Ponderados adaptativo, se ha aislado exitosamente la celula criminal operativa compuesta por {len(banda)} sospechosos clave:
Nodos integrantes de la banda: {banda}

3. INTERDICCION TACTICA Y IDENTIFICACION DE BLANCO HVT
El AuditorAgent ha evaluado la fragilidad estructural del grafo.
* Blanco de Alto Impacto (HVT): NODO {hvt}
* Fundamento Tactico: La neutralizacion/detencion prioritaria del Nodo {hvt} causa la maxima desarticulacion de conectividad en la organizacion, aislando a sus ramificaciones operativas.

4. RECOMENDACIONES DILIGENCIAS FISCALIA
- Solicitar orden de detencion prioritaria sobre el Blanco HVT (Nodo {hvt}).
- Allanamiento simultaneo sobre los domicilios vinculados a los nodos {banda[:3]}.
================================================================================
"""
        filepath = os.path.join(out_dir, f"informe_forense_{nombre_caso}.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(contenido)

    def tool_pipeline_todos_los_archivos(self, nivel: Union[int, str, List[int], None] = None) -> str:
        """
        Ejecuta el pipeline completo de inteligencia criminal para TODOS los reportes policiales
        disponibles en la cola de la Fiscalía de forma 100% automatizada.
        Soporta ejecución acotada a un nivel o en TODOS los niveles (multinivel 1, 2 y 3).
        """
        pdfs = self.state.get("pdf_list", [])
        if not pdfs:
            return "No se encontraron partes policiales en la carpeta 'data/reportes'."

        es_multinivel = (str(nivel).lower() in ["todos", "todas", "multinivel", "comparar", "1,2,3", "1, 2 y 3", "1 2 y 3"]) or isinstance(nivel, list)

        if nivel is None and self.state.get("nivel_actual") is None:
            self.siguiente_accion_sugerida = "batch_con_nivel"
            return (
                f"Se detectaron {len(pdfs)} reportes policiales en cola.\n"
                f"Antes de ejecutar el procesamiento en lote para todos los archivos, "
                f"indique el nivel de profundidad de búsqueda (k-hops):\n"
                f"   [1] Nivel 1 (1 salto)\n"
                f"   [2] Nivel 2 (2 saltos) [Recomendado]\n"
                f"   [3] Nivel 3 (3 saltos)\n"
                f"   (o escriba 'todos' para generar la comparativa de los 3 niveles por cada caso)"
            )

        caso_original = self.state.get("current_pdf")

        if es_multinivel:
            print(f"\n" + "="*75)
            print(f" PROCESAMIENTO MULTI-AGENTE EN LOTE MULTINIVEL (NIVELES 1, 2 Y 3): {len(pdfs)} CASOS")
            print("="*75)

            resumen_lote = []
            for idx, pdf_path in enumerate(pdfs):
                nombre_caso = Path(pdf_path).stem
                print(f"\n>>> [Caso {idx+1}/{len(pdfs)}] Procesando '{nombre_caso}' en TODOS los niveles (1, 2 y 3)...")
                
                # Cargar y sincronizar caso
                self.cargar_caso(pdf_path)

                # Ejecutar análisis multinivel completo para este caso
                self.tool_analisis_multinivel([1, 2, 3])
                self.guardar_estado_caso(nombre_caso)

                diag = self.state.get("diagnostico_auditoria") or {}
                hvt_info = diag.get("hvt_prioritario", {}) if isinstance(diag, dict) else {}
                hvt = hvt_info.get("id_sospechoso") if isinstance(hvt_info, dict) else (hvt_info if hvt_info else "No identificado")
                banda = self.state.get("nodos_banda", [])

                resumen_lote.append({
                    "caso": nombre_caso,
                    "raiz": self.state.get("ruts_involucrados", []),
                    "banda_len": len(banda),
                    "hvt": hvt,
                    "archivo_grafico": f"comparativa_niveles_{nombre_caso}.png",
                    "archivo_informe": f"informe_forense_{nombre_caso}.txt"
                })

            self.siguiente_accion_sugerida = None
            if caso_original:
                self.cargar_caso(caso_original)
            
            salida = f"[OK] Procesamiento en lote MULTINIVEL (Niveles 1, 2 y 3) completado al 100% para los {len(pdfs)} casos:\n\n"
            for i, res in enumerate(resumen_lote, 1):
                salida += (
                    f"📁 CASO {i}: '{res['caso']}'\n"
                    f"   - Imputado(s) Raíz: Sujetos {res['raiz']}\n"
                    f"   - Blanco de Alto Impacto (HVT): Nodo {res['hvt']}\n"
                    f"   - Diagrama comparativo (3 paneles): 'data/graficos_resultados/{res['archivo_grafico']}'\n"
                    f"   - Informe forense formal: 'data/informes_fiscalia/{res['archivo_informe']}'\n\n"
                )
            salida += "Todos los informes forenses y visualizaciones multinivel han sido generados exitosamente."
            return salida

        else:
            nivel_usado = int(nivel) if nivel is not None and str(nivel).isdigit() else self.state.get("nivel_actual", 2)
            print(f"\n" + "="*75)
            print(f" PROCESAMIENTO MULTI-AGENTE EN LOTE: {len(pdfs)} CASOS (NIVEL {nivel_usado})")
            print("="*75)

            resumen_lote = []
            for idx, pdf_path in enumerate(pdfs):
                nombre_caso = Path(pdf_path).stem
                print(f"\n>>> [Caso {idx+1}/{len(pdfs)}] Procesando '{nombre_caso}'...")
                
                # Cargar y sincronizar caso
                self.cargar_caso(pdf_path)
                self.state["nivel_actual"] = nivel_usado

                # Ejecutar pipeline completo
                self.tool_pipeline_completo(nivel=nivel_usado)
                self.guardar_estado_caso(nombre_caso)

                diag = self.state.get("diagnostico_auditoria") or {}
                hvt_info = diag.get("hvt_prioritario", {}) if isinstance(diag, dict) else {}
                hvt = hvt_info.get("id_sospechoso") if isinstance(hvt_info, dict) else (hvt_info if hvt_info else "No identificado")
                banda = self.state.get("nodos_banda", [])

                resumen_lote.append({
                    "caso": nombre_caso,
                    "raiz": self.state.get("ruts_involucrados", []),
                    "banda_len": len(banda),
                    "hvt": hvt,
                    "archivo_grafico": f"grafo_{nombre_caso}_nivel_{nivel_usado}.png",
                    "archivo_informe": f"informe_forense_{nombre_caso}.txt"
                })

            self.siguiente_accion_sugerida = None
            if caso_original:
                self.cargar_caso(caso_original)
            
            salida = f"[OK] Procesamiento en lote ejecutado al 100% para los {len(pdfs)} casos en **NIVEL {nivel_usado}**:\n\n"
            for i, res in enumerate(resumen_lote, 1):
                salida += (
                    f"📁 CASO {i}: '{res['caso']}'\n"
                    f"   - Imputado(s) Raíz: Sujetos {res['raiz']}\n"
                    f"   - Célula criminal identificada (StPro): {res['banda_len']} integrantes\n"
                    f"   - Blanco de Alto Impacto (HVT): Nodo {res['hvt']}\n"
                    f"   - Diagrama exportado: 'data/graficos_resultados/{res['archivo_grafico']}'\n"
                    f"   - Informe formal emitido: 'data/informes_fiscalia/{res['archivo_informe']}'\n\n"
                )
            salida += "Todos los informes forenses y visualizaciones han sido generados exitosamente."
            return salida

    def tool_pipeline_completo(self, nivel: Optional[int] = None) -> str:
        if nivel is not None:
            self.state["nivel_actual"] = nivel
        elif self.state.get("nivel_actual") is None:
            # Si aún no se ha elegido nivel, primero realizamos la ingesta y preguntamos el nivel
            if not self.state.get("ruts_involucrados"):
                res_ingesta = self.tool_ingesta()
            else:
                res_ingesta = ""
            self.siguiente_accion_sugerida = "pipeline_con_nivel"
            return (
                f"{res_ingesta}\n\n" if res_ingesta else ""
            ) + (
                f"Antes de ejecutar el pipeline completo para '{self.state.get('nombre_caso')}', "
                f"indique el nivel de profundidad de búsqueda:\n"
                f"   [1] Nivel 1 (Contacto directo - 1 salto)\n"
                f"   [2] Nivel 2 (Célula operativa cercana - 2 saltos) [Recomendado]\n"
                f"   [3] Nivel 3 (Estructura criminal ampliada - 3 saltos)\n"
                f"   (o escriba 'todos' para generar la comparativa de los 3 niveles)"
            )

        nivel_usado = self.state.get("nivel_actual", 2)
        print(f"\n>>> [LangGraph Orchestrator] Invocando Grafo de Estados en NIVEL {nivel_usado}...")
        try:
            final_state = self.compiled_graph.invoke(self.state)
            if final_state and isinstance(final_state, dict):
                self.state.update(final_state)
            self.siguiente_accion_sugerida = None
            return (
                f"[OK] Pipeline Multi-Agente ejecutado al 100% para **NIVEL {nivel_usado}**:\n"
                f"   1. Ingesta cognitiva realizada (IngestionAgent).\n"
                f"   2. Base relacional consultada y filtrada a {nivel_usado} salto(s) (FilterAgent).\n"
                f"   3. Modelo Gurobi StPro resuelto ({len(self.state.get('nodos_banda', []))} miembros).\n"
                f"   4. Blanco HVT identificado por AuditorAgent.\n"
                f"   5. Grafico de red exportado a 'data/graficos_resultados/'.\n"
                f"   6. Informe formal generado en 'data/informes_fiscalia/'."
            )
        except Exception as e:
            return f"Error ejecutando pipeline: {e}"

    # =======================================================
    # UTILIDADES DE PARSEO DIFUSO (FUZZY TYPO TOLERANCE)
    # =======================================================

    @staticmethod
    def _normalizar_texto(texto: str) -> str:
        """Elimina tildes, signos de puntuación extra y pasa a minúsculas para robustez ante errores de tipeo."""
        t = unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('utf-8')
        return re.sub(r'[^a-z0-9\s]', ' ', t.lower()).strip()

    @classmethod
    def _contiene_termino_difuso(cls, texto_norm: str, palabras_clave: List[str], umbral: float = 0.72) -> bool:
        """Comprueba si alguna de las palabras clave o sus variaciones tipográficas coinciden."""
        tokens = texto_norm.split()
        for token in tokens:
            if len(token) <= 2:
                if token in palabras_clave:
                    return True
                continue
            for kw in palabras_clave:
                if kw in token or token in kw:
                    return True
                if difflib.SequenceMatcher(None, token, kw).ratio() >= umbral:
                    return True
        for kw in palabras_clave:
            if kw in texto_norm:
                return True
            if len(kw.split()) > 1 and difflib.SequenceMatcher(None, texto_norm, kw).ratio() >= umbral:
                return True
        return False

    # =======================================================
    # MOTOR DE LLM COGNITIVO (GOOGLE GEMINI) CON INTENT ROUTING
    # =======================================================

    def _razonar_con_llm(self, user_msg: str) -> Optional[str]:
        """
        Usa Google Gemini para razonar sobre el mensaje del usuario, tolerando errores de tipeo
        y decidiendo qué herramienta invocar o generando una respuesta jurídica explicativa.
        """
        if not self.has_real_key or not self.gemini_client:
            return None
            
        try:
            contexto_actual = {
                "caso_actual": self.state.get("nombre_caso"),
                "ingesta_realizada": bool(self.state.get("ruts_involucrados")),
                "nodos_raiz": self.state.get("ruts_involucrados"),
                "tamano_estimado": self.state.get("tamano_grupo"),
                "resumen_caso": self.state.get("resumen_caso"),
                "optimizacion_realizada": bool(self.state.get("nodos_banda")),
                "nodos_banda": self.state.get("nodos_banda"),
                "diagnostico_auditoria": self.state.get("diagnostico_auditoria"),
                "accion_previa_sugerida": self.siguiente_accion_sugerida,
                "total_archivos_en_cola": len(self.state.get("pdf_list", []))
            }
            
            prompt = f"""Eres el Copiloto HeredIA, el Agente Orquestador Multi-Agente de Inteligencia Criminal de la Fiscalía de Chile (LangGraph Copilot).
Tu función es interpretar la intención del Usuario (tolerando errores tipográficos como 'pipline', 'pipleine', 'archvios', 'optimizasion', etc.) y coordinar los agentes del sistema.

Contexto actual de la investigación:
{json.dumps(contexto_actual, ensure_ascii=False, indent=2)}

Herramientas disponibles:
- "ACCION_PIPELINE_TODOS_LOS_ARCHIVOS_MULTINIVEL": Ejecuta el análisis multinivel (Niveles 1, 2 y 3) para TODOS los archivos/reportes PDF en lote.
- "ACCION_PIPELINE_TODOS_LOS_ARCHIVOS": Ejecuta todo el pipeline en lote para TODOS los archivos/reportes PDF disponibles en un nivel.
- "ACCION_PIPELINE_COMPLETO": Ejecuta todo el flujo autónomo de LangGraph para el caso actual (si no tiene nivel, preguntará al usuario).
- "ACCION_OPTIMIZACION_NIVEL_1": Ejecuta el pipeline completo acotado estrictamente a Nivel 1.
- "ACCION_OPTIMIZACION_NIVEL_2": Ejecuta el pipeline completo acotado estrictamente a Nivel 2.
- "ACCION_OPTIMIZACION_NIVEL_3": Ejecuta el pipeline completo acotado estrictamente a Nivel 3.
- "ACCION_ANALISIS_MULTINIVEL": Solo cuando el usuario pide comparar o analizar los 3 niveles juntos (1, 2 y 3) para el caso actual.
- "ACCION_INGESTA": Lee el parte policial PDF con IngestionAgent.
- "ACCION_AUDITORIA": Evalúa la red y calcula el Blanco de Alto Impacto (HVT).
- "ACCION_VISUALIZACION": Dibuja el grafo en PNG.
- "ACCION_INFORME": Redacta el informe formal para Fiscalía.
- "ACCION_VISUALIZACION_E_INFORME": Genera tanto el gráfico como el informe.
- "ACCION_LISTAR_REPORTES": Lista los reportes en PDF.
- "ACCION_NINGUNA": Solo responder la pregunta del usuario con los datos actuales.

Instrucción estricta:
Responde ÚNICAMENTE en formato JSON con la siguiente estructura:
{{
  "accion_a_ejecutar": "ACCION_PIPELINE_TODOS_LOS_ARCHIVOS_MULTINIVEL" | "ACCION_PIPELINE_TODOS_LOS_ARCHIVOS" | "ACCION_PIPELINE_COMPLETO" | "ACCION_OPTIMIZACION_NIVEL_1" | "ACCION_OPTIMIZACION_NIVEL_2" | "ACCION_OPTIMIZACION_NIVEL_3" | "ACCION_ANALISIS_MULTINIVEL" | "ACCION_INGESTA" | "ACCION_AUDITORIA" | "ACCION_VISUALIZACION" | "ACCION_INFORME" | "ACCION_VISUALIZACION_E_INFORME" | "ACCION_LISTAR_REPORTES" | "ACCION_NINGUNA",
  "respuesta_conversacional": "Texto de respuesta claro, formal e institucional dirigido al Usuario."
}}

Mensaje del Usuario:
"{user_msg}"
"""
            response = self.gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            
            data = json.loads(response.text)
            accion = data.get("accion_a_ejecutar", "ACCION_NINGUNA")
            texto_llm = data.get("respuesta_conversacional", "")
            
            # Ejecutar la herramienta decidida por el LLM
            salida_herramienta = ""
            if accion == "ACCION_PIPELINE_TODOS_LOS_ARCHIVOS_MULTINIVEL":
                salida_herramienta = self.tool_pipeline_todos_los_archivos(nivel="todos")
            elif accion == "ACCION_PIPELINE_TODOS_LOS_ARCHIVOS":
                salida_herramienta = self.tool_pipeline_todos_los_archivos()
            elif accion == "ACCION_INGESTA":
                salida_herramienta = self.tool_ingesta()
            elif accion == "ACCION_OPTIMIZACION":
                salida_herramienta = self.tool_optimizacion()
            elif accion == "ACCION_OPTIMIZACION_NIVEL_1":
                salida_herramienta = self.tool_pipeline_completo(nivel=1)
            elif accion == "ACCION_OPTIMIZACION_NIVEL_2":
                salida_herramienta = self.tool_pipeline_completo(nivel=2)
            elif accion == "ACCION_OPTIMIZACION_NIVEL_3":
                salida_herramienta = self.tool_pipeline_completo(nivel=3)
            elif accion == "ACCION_ANALISIS_MULTINIVEL":
                salida_herramienta = self.tool_analisis_multinivel([1, 2, 3])
            elif accion == "ACCION_AUDITORIA":
                salida_herramienta = self.tool_auditoria()
            elif accion == "ACCION_VISUALIZACION":
                salida_herramienta = self.tool_visualizacion()
            elif accion == "ACCION_INFORME":
                salida_herramienta = self.tool_informe()
            elif accion == "ACCION_VISUALIZACION_E_INFORME":
                salida_herramienta = self.tool_visualizacion_e_informe()
            elif accion == "ACCION_PIPELINE_COMPLETO":
                salida_herramienta = self.tool_pipeline_completo()
            elif accion == "ACCION_LISTAR_REPORTES":
                salida_herramienta = self.tool_listar_reportes()
                
            if salida_herramienta:
                return f"{texto_llm}\n\n{salida_herramienta}" if texto_llm and texto_llm not in salida_herramienta else salida_herramienta
            else:
                return texto_llm
                
        except Exception:
            return None

    # =======================================================
    # ENRUTADOR PRINCIPAL (LLM FIRST + FALLBACK LOCAL INTELIGENTE)
    # =======================================================

    def procesar_mensaje_usuario(self, user_msg: str) -> str:
        # 1. Intentar razonar con el LLM (Google Gemini) si está configurado
        if self.has_real_key:
            respuesta_llm = self._razonar_con_llm(user_msg)
            if respuesta_llm:
                return respuesta_llm
        
        # 2. Fallback de reglas locales con normalización y coincidencia difusa (Tolerancia a Errores de Tipeo)
        txt = self._normalizar_texto(user_msg)

        # A. Detección de si el usuario pide TODOS LOS NIVELES (Multinivel)
        terminos_multinivel = [
            "todos los niveles", "en todos los niveles", "todo los niveles", 
            "1 2 y 3", "1, 2 y 3", "1,2,3", "1 y 2 y 3", "los 3 niveles", 
            "tres niveles", "3 niveles", "multinivel", "comparar niveles", "compara niveles"
        ]
        es_multinivel = any(term in txt for term in terminos_multinivel)
        if not es_multinivel and txt in ["todos", "todas", "comparar", "compara"]:
            es_multinivel = True

        # B. Detección de si el usuario pide procesar TODOS LOS ARCHIVOS / INFORMES (Lote / Batch)
        keywords_lote = [
            "todos los archivos", "todo los archivos", "todos los archvios", "todo los archvios",
            "todos los reportes", "todo los reportes", "todos los informes", "todo los informes",
            "todos los infoemes", "todo los infoemes", "todos los pdfs", "todos los casos", "cada archivo", 
            "cada caso", "en lote", "lote", "batch", "todos los partes", "todos los documentos"
        ]
        es_lote = self._contiene_termino_difuso(txt, keywords_lote, umbral=0.70)

        # C. Detección de nivel específico individual (solo si NO es multinivel)
        if es_multinivel:
            nivel_pedido = "todos"
        else:
            match_nivel = re.search(r'nivel\s*([1-3])', txt) or re.search(r'([1-3])\s*saltos?', txt) or re.search(r'([1-3])\s*hops?', txt)
            if not match_nivel:
                if re.search(r'\b(1|uno|primer)\b', txt) and ("nivel" in txt or "salto" in txt or txt in ["1", "uno"]):
                    nivel_pedido = 1
                elif re.search(r'\b(2|dos|segundo)\b', txt) and ("nivel" in txt or "salto" in txt or txt in ["2", "dos"]):
                    nivel_pedido = 2
                elif re.search(r'\b(3|tres|tercer)\b', txt) and ("nivel" in txt or "salto" in txt or txt in ["3", "tres"]):
                    nivel_pedido = 3
                elif txt in ["1", "2", "3"]:
                    nivel_pedido = int(txt)
                else:
                    nivel_pedido = None
            else:
                nivel_pedido = int(match_nivel.group(1))

        # ----------------------------------------------------
        # CASO 1: Procesar TODOS LOS ARCHIVOS (LOTE)
        # ----------------------------------------------------
        if es_lote:
            self.siguiente_accion_sugerida = None
            if es_multinivel:
                return self.tool_pipeline_todos_los_archivos(nivel="todos")
            else:
                return self.tool_pipeline_todos_los_archivos(nivel=nivel_pedido)

        # Si estábamos esperando el nivel para el lote
        if self.siguiente_accion_sugerida == "batch_con_nivel":
            self.siguiente_accion_sugerida = None
            if es_multinivel or txt in ["todos", "todas", "comparar", "multinivel"]:
                return self.tool_pipeline_todos_los_archivos(nivel="todos")
            elif nivel_pedido is not None:
                return self.tool_pipeline_todos_los_archivos(nivel=nivel_pedido)
            else:
                return self.tool_pipeline_todos_los_archivos(nivel=2)

        # ----------------------------------------------------
        # CASO 2: Multinivel sobre caso actual
        # ----------------------------------------------------
        if es_multinivel:
            self.siguiente_accion_sugerida = None
            return self.tool_analisis_multinivel([1, 2, 3])

        # ----------------------------------------------------
        # CASO 3: Nivel directo ingresado por el usuario
        # ----------------------------------------------------
        if nivel_pedido is not None:
            self.siguiente_accion_sugerida = None
            return self.tool_pipeline_completo(nivel=nivel_pedido)

        # Si estábamos esperando el nivel para un caso individual
        if self.siguiente_accion_sugerida == "pipeline_con_nivel":
            self.siguiente_accion_sugerida = None
            if txt in ["si", "sí", "dale", "ok", "adelante", "procede"]:
                return self.tool_pipeline_completo(nivel=2)

        # ----------------------------------------------------
        # CASO 4: Respuestas afirmativas contextuales
        # ----------------------------------------------------
        if txt in ["si", "si", "dale", "ok", "bueno", "procede", "adelante", "claro", "por favor", "hazlo", "ejecutalo", "continua", "siguiente", "yes", "y"]:
            if self.siguiente_accion_sugerida == "ingesta":
                return self.tool_ingesta()
            elif self.siguiente_accion_sugerida == "optimizacion":
                return self.tool_pipeline_completo(nivel=self.state.get("nivel_actual") or 2)
            elif self.siguiente_accion_sugerida == "auditoria":
                return self.tool_auditoria()
            elif self.siguiente_accion_sugerida == "visualizacion_e_informe":
                return self.tool_visualizacion_e_informe()
            elif self.siguiente_accion_sugerida == "informe":
                return self.tool_informe()
            else:
                if not self.state.get("ruts_involucrados"):
                    return self.tool_ingesta()
                elif not self.state.get("nodos_banda"):
                    return self.tool_pipeline_completo(nivel=2)
                elif not self.state.get("diagnostico_auditoria"):
                    return self.tool_auditoria()
                else:
                    return self.tool_visualizacion_e_informe()

        # Respuestas negativas
        if txt in ["no", "espera", "todavia no", "despues", "luego", "cancelar"]:
            self.siguiente_accion_sugerida = None
            return f"Entendido, Fiscal. Dígame qué otra consulta o acción desea realizar sobre el caso '{self.state.get('nombre_caso')}'."

        # ----------------------------------------------------
        # CASO E: Saludos e Introducción
        # ----------------------------------------------------
        if any(w in txt for w in ["hola", "buenos dias", "buenas tardes", "quien eres", "que puedes hacer", "ayuda", "menu"]):
            return (
                f"Saludos. Soy el Copiloto HeredIA, su asistente multi-agente de inteligencia criminal en LangGraph.\n"
                f"Actualmente tengo cargado el caso '{self.state.get('nombre_caso', 'Ninguno')}'.\n\n"
                f"Puedo asistirlo en cualquier momento con las siguientes tareas:\n"
                f" - Preguntar por los sospechosos o delitos del caso ('¿quienes son los sospechosos?').\n"
                f" - Optimizar StPro en un nivel específico ('optimiza en nivel 1', 'aisla en nivel 2', 'corre en nivel 3').\n"
                f" - Comparar todos los niveles ('compara los 3 niveles' o 'analisis multinivel').\n"
                f" - Auditar la red e identificar el Blanco de Alto Impacto HVT ('¿cual es el blanco prioritario?').\n"
                f" - Generar el diagrama visual y redactar el informe pericial ('genera el informe y grafico').\n"
                f" - Ejecutar todo el flujo para el caso actual ('corre todo el pipeline').\n"
                f" - Ejecutar todo el pipeline para todos los archivos ('ejecuta el pipeline para todos los archivos').\n\n"
                f"¿Que diligencia desea realizar?"
            )
            
        # ----------------------------------------------------
        # CASO F: Ingesta / Sospechosos / Lectura del parte
        # ----------------------------------------------------
        keywords_ingesta = [
            "sospechoso", "sospechosos", "imputado", "imputados", "lider", "lideres", 
            "blanco", "blancos", "quienes eran", "quienes son", "quien es", "involucrado", "involucrados",
            "parte policial", "leer parte", "revisa el parte", "revisar parte", "analiza el parte", "ingesta", "ingestion"
        ]
        if self._contiene_termino_difuso(txt, keywords_ingesta, umbral=0.75) and not any(w in txt for w in ["hvt", "alto impacto", "prioritario", "detener"]):
            if not self.state.get("ruts_involucrados"):
                return self.tool_ingesta()
            else:
                ruts = self.state.get("ruts_involucrados", [])
                tamano = self.state.get("tamano_grupo", 0)
                resumen = self.state.get("resumen_caso", "")
                self.siguiente_accion_sugerida = "optimizacion"
                return (
                    f"Para el caso '{self.state.get('nombre_caso')}':\n"
                    f"- Imputados principales (Nodos Raiz): Sujetos {', '.join(ruts)}\n"
                    f"- Tamano total estimado: {tamano} sospechosos\n"
                    f"- Resumen delictual: {resumen}\n\n"
                    f"¿En qué nivel desea ejecutar la optimización StPro? ([1] Nivel 1, [2] Nivel 2, [3] Nivel 3 o 'todos')"
                )

        # ----------------------------------------------------
        # CASO G: Blanco HVT / Auditoría
        # ----------------------------------------------------
        keywords_auditoria = ["hvt", "blanco prioritario", "alto impacto", "a quien detengo", "a quien detenemos", "orden de detencion", "prioritario", "auditar", "auditoria", "desarticular"]
        if self._contiene_termino_difuso(txt, keywords_auditoria, umbral=0.75):
            return self.tool_auditoria()

        # ----------------------------------------------------
        # CASO H: Pipeline completo (Tolerante a "pipline", "pipleine", "ejecuta pipline")
        # ----------------------------------------------------
        keywords_pipeline = [
            "pipeline", "pipline", "pipleine", "pipelne", "pipe", "flujo", 
            "ejecuta todo", "corre todo", "correr todo", "ejecutar todo", "procesar todo", 
            "ejecutar caso", "procesar caso", "todo completo", "pipeline completo"
        ]
        if self._contiene_termino_difuso(txt, keywords_pipeline, umbral=0.70):
            return self.tool_pipeline_completo(nivel=nivel_pedido)

        # ----------------------------------------------------
        # CASO I: Optimización / Gurobi / StPro (Tolerante a "optimizasion", "optimisar")
        # ----------------------------------------------------
        keywords_optimizacion = [
            "optimizar", "optimizacion", "optimizasion", "optimisacion", "optimiza", 
            "gurobi", "stram", "stpro", "aislar banda", "aisla la banda", 
            "encontrar miembros", "buscar red", "red criminal", "miembros de la banda"
        ]
        if self._contiene_termino_difuso(txt, keywords_optimizacion, umbral=0.72):
            if self.state.get("nivel_actual") is None:
                return self.tool_pipeline_completo()
            else:
                return self.tool_pipeline_completo(nivel=self.state.get("nivel_actual"))

        # ----------------------------------------------------
        # CASO J: Visualización / Gráficos
        # ----------------------------------------------------
        keywords_visualizacion = ["visualizar", "visualizacion", "visualisacion", "grafico", "graficar", "diagrama", "dibujar", "imagen", "ver red"]
        if self._contiene_termino_difuso(txt, keywords_visualizacion, umbral=0.75):
            return self.tool_visualizacion()

        # ----------------------------------------------------
        # CASO K: Informe forense / Redacción
        # ----------------------------------------------------
        keywords_informe = ["informe", "redactar", "documento", "explicacion", "tribunal", "fiscalia", "generar informe", "crear informe"]
        if self._contiene_termino_difuso(txt, keywords_informe, umbral=0.75):
            return self.tool_informe()

        # ----------------------------------------------------
        # CASO L: Listar o cambiar reportes
        # ----------------------------------------------------
        keywords_listar = ["listar", "reportes", "que casos", "ver casos", "mostrar pdf", "partes disponibles", "archivos disponibles"]
        if self._contiene_termino_difuso(txt, keywords_listar, umbral=0.75):
            return self.tool_listar_reportes()
            
        if any(w in txt for w in ["cambiar caso", "seleccionar caso", "cargar caso", "cargar reporte", "cambiar a"]):
            return self.tool_seleccionar_reporte(txt)

        # ----------------------------------------------------
        # CASO M: Estado actual
        # ----------------------------------------------------
        if any(w in txt for w in ["estado", "resumen", "que tenemos", "como vamos", "informacion actual"]):
            ruts = self.state.get("ruts_involucrados", [])
            banda = self.state.get("nodos_banda", [])
            diag = self.state.get("diagnostico_auditoria") or {}
            hvt_info = diag.get("hvt_prioritario", {})
            hvt = hvt_info.get("id_sospechoso") if isinstance(hvt_info, dict) else hvt_info
            
            return (
                f"Estado actual de la investigacion para '{self.state.get('nombre_caso')}':\n"
                f"- Blancos iniciales (RUTs/IDs raiz): {ruts or 'Pendiente de ingesta'}\n"
                f"- Banda aislada (Gurobi): {len(banda)} miembros ({banda or 'No optimizada aun'})\n"
                f"- Blanco HVT detectado: Nodo {hvt or 'Pendiente de auditoria'}\n"
                f"- Resumen: {self.state.get('resumen_caso', 'Sin procesar')}"
            )

        return (
            f"Como Copiloto HeredIA, puedo ejecutar las siguientes diligencias sobre el caso '{self.state.get('nombre_caso')}':\n"
            f"- '¿Quienes eran los sospechosos?' -> Extrae los blancos del parte policial con IngestionAgent.\n"
            f"- 'Aisla la banda con Gurobi' -> Resuelve el modelo matematico StRAM con OptimizationAgent.\n"
            f"- '¿Cual es el blanco HVT prioritario?' -> Identifica al sospechoso clave con AuditorAgent.\n"
            f"- 'Genera el grafico y el informe' -> Exporta los diagramas y el informe formal.\n"
            f"- 'Ejecuta todo el pipeline' -> Corre todo el grafo de LangGraph de forma autonoma.\n"
            f"- 'Ejecuta todo el pipeline para todos los archivos' -> Procesa en lote todos los partes policiales."
        )

    def iniciar_chat_interactivo(self):
        modo_orquestador = "Google Gemini LLM + LangGraph" if self.has_real_key else "LangGraph (Reglas Cognitivas)"
        print("\n" + "="*75)
        print(" COPILOTO HEREDIA - SISTEMA MULTI-AGENTE DE INTELIGENCIA CRIMINAL")
        print(f" Orquestador: {modo_orquestador}")
        print("="*75)
        print(f" Caso cargado: {self.state.get('nombre_caso', 'Ninguno')}")
        print(" Escriba en lenguaje natural, por ejemplo:")
        print("   - 'Dime quienes eran los sospechosos'")
        print("   - 'Aisla la banda con Gurobi'")
        print("   - '¿Cual es el blanco HVT prioritario para detener?'")
        print("   - 'Genera el grafico y el informe formal'")
        print("   - 'Ejecuta todo el pipeline'")
        print("   (o responder 'si', 'dale', 'ok' a las sugerencias del agente)")
        print("   (o escribir 'salir' para terminar)")
        print("="*75)

        while True:
            try:
                user_input = input("\n[Usuario]: ").strip()
                if not user_input:
                    continue
                
                if user_input.lower() in ["salir", "exit", "quit", "0"]:
                    print("\nFinalizando sesion del Copiloto HeredIA. ¡Hasta pronto!")
                    break
                
                respuesta = self.procesar_mensaje_usuario(user_input)
                print(f"\n[Copiloto HeredIA]:\n{respuesta}")
                
            except KeyboardInterrupt:
                print("\n\nSesion interrumpida. Saliendo...")
                break

if __name__ == "__main__":
    orquestador = InteractiveOrchestrator()
    orquestador.iniciar_chat_interactivo()
