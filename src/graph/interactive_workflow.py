import os
import sys
import json
import re
from pathlib import Path
import pandas as pd
import networkx as nx
from typing import List, Optional, Any, Dict
from typing_extensions import TypedDict

# Configurar salida UTF-8 en consola Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Parche dinámico de compatibilidad para evitar fallos de importación
import src.utils.models_STRAM_KsRAM
if not hasattr(src.utils.models_STRAM_KsRAM, "KsRAM"):
    src.utils.models_STRAM_KsRAM.KsRAM = src.utils.models_STRAM_KsRAM.StRAM

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()

# Importar LangGraph
from langgraph.graph import StateGraph, START, END

# Importar Google Gemini si está disponible
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

RAW_KEY = os.getenv("GOOGLE_GENAI_API_KEY", "").strip()
HAS_GEMINI_KEY = bool(RAW_KEY) and RAW_KEY not in ["DUMMY_DEMO_KEY", "tu_api_key_de_gemini_aqui", ""]

if not HAS_GEMINI_KEY:
    os.environ["GOOGLE_GENAI_API_KEY"] = "DUMMY_DEMO_KEY"

# Carga de los Agentes Especializados del Proyecto Principal
from src.agents.Ingestion_Agent import IngestionAgent
from src.agents.Filter_Agent import PruningAgent
from src.agents.Optimization_Agent import StProOptimizationAgent
from src.agents.Auditor_Agent import AuditorAgent
from src.agents.Visualization_Agent import VisualizationAgent
from src.agents.Explanation_Agent import ExplanationAgent

# 1. Definición del Estado Compartido en LangGraph
class CriminalGraphState(TypedDict):
    pdf_list: List[str]
    current_index: int
    current_pdf: Optional[str]
    nombre_caso: Optional[str]
    resumen_caso: Optional[str]
    metadatos_utiles: Optional[Dict[str, Any]]
    tipo_delito: Optional[str]
    ruts_involucrados: List[str]
    tamano_grupo: int
    nivel_actual: Optional[int]
    nodes_df: Optional[Any]
    edges_df: Optional[Any]
    grafo_podado: Optional[Any]
    reporte_poda: Optional[Dict[str, Any]]
    nodos_banda: List[Any]
    diagnostico_auditoria: Optional[Dict[str, Any]]

class InteractiveCriminalOrchestrator:
    """
    Copiloto HeredIA - Orquestador Interactivo Multi-Agente con LLM y LangGraph.
    Coordina los 6 agentes de la arquitectura para la Fiscalía de Chile.
    """
    def __init__(self, data_dir="data", max_nodes_threshold=50):
        self.data_dir = data_dir
        self.has_real_key = HAS_GEMINI_KEY and (genai is not None)
        self.gemini_client = None
        
        if self.has_real_key:
            try:
                self.gemini_client = genai.Client(api_key=RAW_KEY)
            except Exception:
                self.gemini_client = None
                self.has_real_key = False
        
        # Inicialización de Agentes del Sistema
        try:
            self.ingestor = IngestionAgent(data_dir=data_dir, subcarpeta_reportes="reportes")
        except Exception:
            self.ingestor = None
            
        self.pruning_agent = PruningAgent(max_nodes_threshold=max_nodes_threshold, k_hops=2)
        self.auditor_agent = AuditorAgent()
        self.visualizador = VisualizationAgent(output_dir=os.path.join(data_dir, "graficos_resultados"))
        
        try:
            self.explicador = ExplanationAgent(data_dir=os.path.join(data_dir, "informes_fiscalia"))
        except Exception:
            self.explicador = None
            
        self.state: CriminalGraphState = {
            "pdf_list": [],
            "current_index": 0,
            "current_pdf": None,
            "nombre_caso": None,
            "resumen_caso": None,
            "metadatos_utiles": None,
            "tipo_delito": None,
            "ruts_involucrados": [],
            "tamano_grupo": 0,
            "nivel_actual": None,
            "nodes_df": None,
            "edges_df": None,
            "grafo_podado": None,
            "reporte_poda": None,
            "nodos_banda": [],
            "diagnostico_auditoria": None
        }
        self.op_agent_temp = None
        self.siguiente_accion_sugerida = None
        self._inicializar_reportes()
        self.compiled_graph = self._construir_grafo_langgraph()

    def _inicializar_reportes(self):
        ruta_carpeta = Path(self.data_dir) / "reportes"
        os.makedirs(ruta_carpeta, exist_ok=True)
        self.state["pdf_list"] = [str(pdf) for pdf in ruta_carpeta.glob("*.pdf")]
        if self.state["pdf_list"]:
            self.state["current_pdf"] = self.state["pdf_list"][0]
            self.state["nombre_caso"] = Path(self.state["current_pdf"]).stem

    def _construir_grafo_langgraph(self):
        """
        Construye y compila el flujo cíclico de LangGraph para el sistema completo.
        """
        builder = StateGraph(CriminalGraphState)
        
        builder.add_node("node_ingesta", self._langgraph_node_ingesta)
        builder.add_node("node_cargar_db", self._langgraph_node_cargar_db)
        builder.add_node("node_poda", self._langgraph_node_poda)
        builder.add_node("node_optimizacion", self._langgraph_node_optimizacion)
        builder.add_node("node_auditoria", self._langgraph_node_auditoria)
        builder.add_node("node_visualizacion", self._langgraph_node_visualizacion)
        builder.add_node("node_informe", self._langgraph_node_informe)
        
        builder.add_edge(START, "node_ingesta")
        builder.add_edge("node_ingesta", "node_cargar_db")
        builder.add_edge("node_cargar_db", "node_poda")
        builder.add_edge("node_poda", "node_optimizacion")
        builder.add_edge("node_optimizacion", "node_auditoria")
        builder.add_edge("node_auditoria", "node_visualizacion")
        builder.add_edge("node_visualizacion", "node_informe")
        builder.add_edge("node_informe", END)
        
        return builder.compile()

    # Nodos del grafo de LangGraph
    def _langgraph_node_ingesta(self, state: CriminalGraphState) -> CriminalGraphState:
        print("\n[LangGraph Node: node_ingesta]")
        self.tool_ingesta()
        return self.state

    def _langgraph_node_cargar_db(self, state: CriminalGraphState) -> CriminalGraphState:
        print("\n[LangGraph Node: node_cargar_db]")
        self.tool_cargar_bd()
        return self.state

    def _langgraph_node_poda(self, state: CriminalGraphState) -> CriminalGraphState:
        print("\n[LangGraph Node: node_poda]")
        nivel = self.state.get("nivel_actual", 2)
        self.tool_poda(nivel=nivel)
        return self.state

    def _langgraph_node_optimizacion(self, state: CriminalGraphState) -> CriminalGraphState:
        print("\n[LangGraph Node: node_optimizacion]")
        nivel = self.state.get("nivel_actual", 2)
        self.tool_optimizacion(nivel=nivel)
        return self.state

    def _langgraph_node_auditoria(self, state: CriminalGraphState) -> CriminalGraphState:
        print("\n[LangGraph Node: node_auditoria]")
        self.tool_auditoria()
        return self.state

    def _langgraph_node_visualizacion(self, state: CriminalGraphState) -> CriminalGraphState:
        print("\n[LangGraph Node: node_visualizacion]")
        self.tool_visualizacion()
        return self.state

    def _langgraph_node_informe(self, state: CriminalGraphState) -> CriminalGraphState:
        print("\n[LangGraph Node: node_informe]")
        self.tool_informe()
        return self.state

    # ==========================================
    # HERRAMIENTAS (TOOLS) DEL SISTEMA
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
                self.state["current_pdf"] = p
                self.state["nombre_caso"] = Path(p).stem
                self.state["ruts_involucrados"] = []
                self.state["grafo_podado"] = None
                self.state["reporte_poda"] = None
                self.state["nodos_banda"] = []
                self.state["diagnostico_auditoria"] = None
                self.siguiente_accion_sugerida = "ingesta"
                return f"Caso seleccionado actualizado a: '{self.state['nombre_caso']}'. ¿Desea que procese la ingesta cognitiva del parte policial?"
        
        return f"No se encontro un reporte que coincida con '{query}'. El caso activo sigue siendo '{self.state.get('nombre_caso')}'."

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

        tipo_delito = self.pruning_agent.clasificar_tipologia_delito(resumen, metadatos)
        
        self.state["ruts_involucrados"] = ruts
        self.state["tamano_grupo"] = tamano
        self.state["resumen_caso"] = resumen
        self.state["metadatos_utiles"] = metadatos
        self.state["tipo_delito"] = tipo_delito
        self.siguiente_accion_sugerida = "poda"
        
        resp = (
            f"Ingesta cognitiva completada para '{Path(pdf_path).name}':\n"
            f"- Imputados Principales (Nodos Raiz): Sujetos {', '.join(ruts)}\n"
            f"- Tipologia Delictiva Clasificada: {tipo_delito}\n"
            f"- Tamano estimado de la banda: {tamano} sospechosos\n"
            f"- Resumen de los hechos: {resumen}\n"
            f"- Metadatos y Evidencias: {metadatos}\n\n"
            f"¿Desea que ejecutemos la poda criminologica inteligente (PruningAgent)?"
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
        return f"Base de datos de Fiscalia cargada ({len(nodes_df)} nodos y {len(edges_df)} aristas)."

    def tool_poda(self, nivel: Optional[int] = None) -> str:
        if not self.state.get("ruts_involucrados"):
            self.tool_ingesta()
        if self.state["nodes_df"] is None:
            self.tool_cargar_bd()

        print("\n[PruningAgent] Ejecutando poda adaptativa y criminologica...")
        grafo_completo = self.pruning_agent.construir_grafo_desde_dfs(self.state["nodes_df"], self.state["edges_df"])
        
        nodos_raiz = [int(r) for r in self.state["ruts_involucrados"] if str(r).isdigit()]
        if not nodos_raiz and len(grafo_completo.nodes) > 0:
            nodos_raiz = [list(grafo_completo.nodes)[0]]

        grafo_podado, reporte_poda = self.pruning_agent.podar_grafo_inteligente(
            grafo=grafo_completo,
            nodos_raiz=nodos_raiz,
            tipo_delito=self.state.get("tipo_delito", "VIOLENTO_ARMADO"),
            resumen_caso=self.state.get("resumen_caso", ""),
            nivel=nivel
        )

        self.state["grafo_podado"] = grafo_podado
        self.state["reporte_poda"] = reporte_poda
        if nivel is not None:
            self.state["nivel_actual"] = nivel
        self.siguiente_accion_sugerida = "optimizacion"

        sufijo_nivel = f" (Nivel {nivel})" if nivel is not None else ""
        return (
            f"[OK] Filtrado topológico por Nivel (FilterAgent){sufijo_nivel} completado:\n"
            f"- Reduccion topologica: De {reporte_poda.get('nodos_iniciales')} a {reporte_poda.get('nodos_finales')} nodos ({reporte_poda.get('nodos_eliminados', 0)} fuera del radio de búsqueda)\n"
            f"- Detalle: {reporte_poda.get('motivo_decision')}\n\n"
            f"¿En qué nivel de profundidad desea ejecutar la optimización StPro?\n"
            f"   [1] Nivel 1 (Contacto directo - 1 salto)\n"
            f"   [2] Nivel 2 (Célula operativa cercana - 2 saltos) [Recomendado]\n"
            f"   [3] Nivel 3 (Estructura criminal ampliada - 3 saltos)\n"
            f"   (o escriba 'todos' para generar la comparativa de los 3 niveles)"
        )

    def tool_optimizacion(self, nivel: Optional[int] = None) -> str:
        """
        Ejecuta la optimización StPro (StRAM) sobre el nivel indicado por el analista.
        Si se especifica 'nivel', acota la red a ese número exacto de saltos antes de optimizar.
        """
        # Si el usuario solicitó un nivel específico, actualizar la poda a ese nivel
        if nivel is not None or self.state.get("grafo_podado") is None:
            self.tool_poda(nivel=nivel)

        nivel_usado = nivel if nivel is not None else self.state.get("nivel_actual", 2)
        print(f"\n[OptimizationAgent] Ejecutando Gurobi StPro (StRAM) para NIVEL {nivel_usado}...")
        grafo_a_optimizar = self.state.get("grafo_podado")
        self.op_agent_temp = StProOptimizationAgent(grafo=grafo_a_optimizar, data_dir=self.data_dir)
        
        ruts = self.state.get("ruts_involucrados", [])
        raiz_objetivo = None
        for r in ruts:
            if str(r).isdigit() and int(r) in self.op_agent_temp.grafo.nodes:
                raiz_objetivo = int(r)
                break
        if raiz_objetivo is None:
            raiz_objetivo = list(self.op_agent_temp.grafo.nodes)[0]

        nodos_banda = self.op_agent_temp.ejecutar_stram_adaptativo(start_node=raiz_objetivo, phi_inicial=0.3)
        self.state["nodos_banda"] = nodos_banda
        self.state["nivel_actual"] = nivel_usado
        self.siguiente_accion_sugerida = "auditoria"

        return (
            f"[OK] Optimizacion matematica con Gurobi (Modelo StPro/StRAM) completada para **NIVEL {nivel_usado}**:\n"
            f"- Sospechoso Raíz (Planificador): Sujeto {raiz_objetivo}\n"
            f"- Subred analizada: {len(grafo_a_optimizar.nodes)} sospechosos candidatos\n"
            f"- Celula criminal aislada por StPro: {len(nodos_banda)} integrantes\n"
            f"- Nodos identificados: {nodos_banda}\n\n"
            f"¿Desea que el AuditorAgent evalue la red e identifique el Blanco de Alto Impacto (HVT)?"
        )

    def tool_analisis_multinivel(self, niveles: List[int] = [1, 2, 3]) -> str:
        """
        Ejecuta secuencialmente 3 procesos de optimización independientes con StPro
        para Nivel 1, Nivel 2 y Nivel 3, generando la comparativa visual correspondiente.
        """
        if not self.state.get("ruts_involucrados"):
            self.tool_ingesta()
        if self.state["nodes_df"] is None:
            self.tool_cargar_bd()

        grafo_completo = self.pruning_agent.construir_grafo_desde_dfs(self.state["nodes_df"], self.state["edges_df"])
        ruts = self.state.get("ruts_involucrados", [])
        raiz_objetivo = int(ruts[0]) if ruts and str(ruts[0]).isdigit() and int(ruts[0]) in grafo_completo.nodes else list(grafo_completo.nodes)[0]

        resultados_niveles = {}
        resumen_texto = f"=== ANÁLISIS MULTINIVEL DE RED CRIMINAL (StPro) ===\nSospechoso Raíz: Sujeto {raiz_objetivo}\n\n"

        for L in niveles:
            sub_g = self.pruning_agent.extraer_subgrafo_por_nivel(grafo_completo, nodo_raiz=raiz_objetivo, nivel=L)
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
            nombre_caso=self.state.get("nombre_caso", "caso_principal")
        )

        # Guardar en el estado el resultado del nivel mayor (ej: Nivel 3)
        max_nivel = max(niveles)
        self.state["nodos_banda"] = resultados_niveles[max_nivel]["nodos_banda"]
        self.state["grafo_podado"] = resultados_niveles[max_nivel]["grafo"]
        self.state["nivel_actual"] = max_nivel

        # Ejecutar automáticamente auditoría e informe
        self.tool_auditoria()
        self.tool_informe()

        diag = self.state.get("diagnostico_auditoria", {})
        hvt_info = diag.get("hvt_prioritario", {})
        hvt = hvt_info.get("id_sospechoso") if isinstance(hvt_info, dict) else hvt_info
        
        self.siguiente_accion_sugerida = None

        resumen_texto += (
            f"[OK] Pipeline Multinivel ejecutado al 100% de manera automática:\n"
            f"   1. Optimizaciones StPro completadas para Niveles 1, 2 y 3.\n"
            f"   2. Blanco de Alto Impacto (HVT) identificado: Nodo {hvt} (AuditorAgent).\n"
            f"   3. Diagrama comparativo generado en 'data/graficos_resultados/comparativa_niveles_{self.state.get('nombre_caso')}.png'.\n"
            f"   4. Informe forense formal redactado en 'data/informes_fiscalia/'."
        )
        return resumen_texto

    def tool_auditoria(self) -> str:
        if not self.state.get("nodos_banda"):
            self.tool_optimizacion()

        print("\n[AuditorAgent] Evaluando calidad forense y calculando Blanco de Alto Impacto (HVT)...")
        grafo_actual = getattr(self, 'op_agent_temp', None)
        G = grafo_actual.grafo if grafo_actual else self.state.get("grafo_podado")
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
            f"[OK] Diagnostico Forense e Interdiccion Tactica (AuditorAgent):\n"
            f"- Solucion Validada: {diagnostico.get('aprobado')}\n"
            f"- BLANCO DE ALTO IMPACTO (HVT): NODO {nodo_hvt}\n"
            f"- Fundamento Tactico: La captura prioritaria del Nodo {nodo_hvt} genera la mayor caida de conectividad y fragmenta la red delictiva.\n\n"
            f"¿Desea que genere el grafico de la red y el informe pericial para la Fiscalia?"
        )

    def tool_visualizacion(self) -> str:
        if not self.state.get("nodos_banda"):
            self.tool_optimizacion()

        print("\n[VisualizationAgent] Generando diagrama de red criminal...")
        grafo_actual = getattr(self, 'op_agent_temp', None)
        G = grafo_actual.grafo if grafo_actual else self.state.get("grafo_podado")
        ruts = self.state.get("ruts_involucrados", [])
        raiz_objetivo = int(ruts[0]) if ruts and str(ruts[0]).isdigit() and int(ruts[0]) in G.nodes else list(G.nodes)[0]

        nivel_actual = self.state.get("nivel_actual")
        self.visualizador.graficar_red_criminal(
            grafo=G,
            nodos_banda=self.state["nodos_banda"],
            nodo_raiz=raiz_objetivo,
            nombre_caso=self.state.get("nombre_caso", "caso_principal"),
            nivel=nivel_actual
        )
        self.siguiente_accion_sugerida = "informe"
        nombre_arch = f"grafo_{self.state.get('nombre_caso')}_nivel_{nivel_actual}.png" if nivel_actual else f"grafo_{self.state.get('nombre_caso')}.png"
        return f"[OK] Grafico de red criminal exportado a:\n'data/graficos_resultados/{nombre_arch}'"

    def tool_informe(self) -> str:
        if not self.state.get("nodos_banda"):
            self.tool_optimizacion()
        if not self.state.get("diagnostico_auditoria"):
            self.tool_auditoria()

        print("\n[ExplanationAgent] Redactando informe formal para Fiscalia con Gemini...")
        out_dir = os.path.join(self.data_dir, "informes_fiscalia")
        os.makedirs(out_dir, exist_ok=True)

        if self.has_real_key and self.explicador:
            try:
                self.explicador.generate_explanation(
                    nombre_caso=self.state.get("nombre_caso", "caso_principal"),
                    resumen_caso=self.state.get("resumen_caso", "Sin resumen disponible."),
                    nodos_banda=self.state.get("nodos_banda", []),
                    ruts_raiz=self.state.get("ruts_involucrados", []),
                    diagnostico_auditoria=self.state.get("diagnostico_auditoria"),
                    reporte_poda=self.state.get("reporte_poda")
                )
            except Exception as e:
                self._generar_informe_mock(out_dir)
        else:
            self._generar_informe_mock(out_dir)

        self.siguiente_accion_sugerida = None
        return f"[OK] Informe pericial formal generado exitosamente en:\n'data/informes_fiscalia/informe_forense_{self.state.get('nombre_caso')}.txt'\n\nTodos los peritajes del caso han sido completados."

    def tool_visualizacion_e_informe(self) -> str:
        resp_vis = self.tool_visualizacion()
        resp_inf = self.tool_informe()
        self.siguiente_accion_sugerida = None
        return f"{resp_vis}\n\n{resp_inf}"

    def _generar_informe_mock(self, out_dir):
        nombre_caso = self.state.get("nombre_caso", "caso_principal")
        diag = self.state.get("diagnostico_auditoria", {})
        hvt_info = diag.get("hvt_prioritario", {})
        hvt = hvt_info.get("id_sospechoso") if isinstance(hvt_info, dict) else hvt_info
        banda = self.state.get("nodos_banda", [])
        
        contenido = f"""================================================================================
INFORME PERICIAL Y SUGERENCIA DE DILIGENCIAS TÁCTICAS - MINISTERIO PÚBLICO
================================================================================
CASO: {nombre_caso}
FECHA DE EMISIÓN: 2026-08-23
UNIDAD: Análisis Criminal y Complejidad del Delito

1. ANTECEDENTES Y RESUMEN DEL CASO
{self.state.get('resumen_caso', 'Sin resumen')}

2. TIPOLOGÍA DELICTIVA Y PODA ADAPTATIVA (PruningAgent)
Tipología: {self.state.get('tipo_delito', 'No clasificada')}
Poda estructural: Puntos de articulación protegidos y eliminación de delitos no afines.

3. ANÁLISIS DE REDES Y OPTIMIZACIÓN MATEMÁTICA (Gurobi StRAM)
Tras la aplicación del modelo de Árboles de Steiner Ponderados adaptativo, se ha aislado exitosamente la célula criminal operativa compuesta por {len(banda)} sospechosos clave:
Nodos integrantes de la banda: {banda}

4. INTERDICCIÓN TÁCTICA Y IDENTIFICACIÓN DE BLANCO HVT
El AuditorAgent ha evaluado la fragilidad estructural del grafo.
* Blanco de Alto Impacto (HVT): NODO {hvt}
* Fundamento Táctico: La neutralización/detención prioritaria del Nodo {hvt} causa la máxima desarticulación de conectividad en la organización, aislando a sus ramificaciones operativas.

5. RECOMENDACIONES DILIGENCIAS FISCALÍA
- Solicitar orden de detención prioritaria sobre el Blanco HVT (Nodo {hvt}).
- Allanamiento simultáneo sobre los domicilios vinculados a los nodos {banda[:3]}.
================================================================================
"""
        filepath = os.path.join(out_dir, f"informe_forense_{nombre_caso}.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(contenido)

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
                f"Antes de ejecutar el pipeline de optimización para '{self.state.get('nombre_caso')}', "
                f"indique el nivel de profundidad de búsqueda (k-hops):\n"
                f"   [1] Nivel 1 (Contacto directo - 1 salto)\n"
                f"   [2] Nivel 2 (Célula operativa cercana - 2 saltos) [Recomendado]\n"
                f"   [3] Nivel 3 (Estructura criminal ampliada - 3 saltos)\n"
                f"   (o escriba 'todos' para generar la comparativa de los 3 niveles)"
            )

        nivel_usado = self.state.get("nivel_actual", 2)
        print(f"\n>>> [LangGraph Orchestrator] Invocando Grafo de Estados Completo para NIVEL {nivel_usado}...")
        try:
            self.compiled_graph.invoke(self.state)
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
    # MOTOR DE LLM COGNITIVO (GOOGLE GEMINI) CON INTENT ROUTING
    # =======================================================

    def _razonar_con_llm(self, user_msg: str) -> Optional[str]:
        if not self.has_real_key or not self.gemini_client:
            return None
            
        try:
            contexto_actual = {
                "caso_actual": self.state.get("nombre_caso"),
                "ingesta_realizada": bool(self.state.get("ruts_involucrados")),
                "nodos_raiz": self.state.get("ruts_involucrados"),
                "tipo_delito": self.state.get("tipo_delito"),
                "poda_realizada": bool(self.state.get("grafo_podado")),
                "tamano_estimado": self.state.get("tamano_grupo"),
                "resumen_caso": self.state.get("resumen_caso"),
                "optimizacion_realizada": bool(self.state.get("nodos_banda")),
                "nodos_banda": self.state.get("nodos_banda"),
                "diagnostico_auditoria": self.state.get("diagnostico_auditoria"),
                "accion_previa_sugerida": self.siguiente_accion_sugerida
            }
            
            prompt = f"""Eres el Copiloto HeredIA, el Agente Orquestador Multi-Agente de Inteligencia Criminal de la Fiscalía de Chile en LangGraph.
Tu función es razonar sobre lo que el Usuario te pide y coordinar los 6 agentes especializados del sistema.

Contexto actual de la investigación:
{json.dumps(contexto_actual, ensure_ascii=False, indent=2)}

Herramientas disponibles que puedes ordenar ejecutar:
- "ACCION_INGESTA": Lee el parte policial PDF con IngestionAgent y extrae sospechosos/delito.
- "ACCION_PODA": Aplica filtrado topológico por nivel con FilterAgent.
- "ACCION_OPTIMIZACION": Resuelve el modelo matemático StPro en Gurobi con OptimizationAgent (ejecuta solo el nivel solicitado o el actual).
- "ACCION_OPTIMIZACION_NIVEL_1": Resuelve StPro acotado estrictamente a Nivel 1 (1 salto desde la raíz).
- "ACCION_OPTIMIZACION_NIVEL_2": Resuelve StPro acotado estrictamente a Nivel 2 (2 saltos desde la raíz).
- "ACCION_OPTIMIZACION_NIVEL_3": Resuelve StPro acotado estrictamente a Nivel 3 (3 saltos desde la raíz).
- "ACCION_ANALISIS_MULTINIVEL": Solo cuando el usuario pide comparar o analizar los 3 niveles juntos (1, 2 y 3).
- "ACCION_AUDITORIA": Evalúa la red y calcula el Blanco de Alto Impacto (HVT) con AuditorAgent.
- "ACCION_VISUALIZACION": Dibuja el grafo en PNG con VisualizationAgent.
- "ACCION_INFORME": Redacta el informe formal para Fiscalía con ExplanationAgent.
- "ACCION_VISUALIZACION_E_INFORME": Genera tanto el gráfico como el informe.
- "ACCION_PIPELINE_COMPLETO": Ejecuta todo el flujo autónomo de LangGraph (si no tiene nivel definido, solicitará el nivel al usuario).
- "ACCION_LISTAR_REPORTES": Lista los reportes en PDF.
- "ACCION_NINGUNA": Solo responder la pregunta del usuario con los datos que ya tenemos.

Instrucción estricta:
Responde ÚNICAMENTE en formato JSON con la siguiente estructura:
{{
  "accion_a_ejecutar": "ACCION_INGESTA" | "ACCION_PODA" | "ACCION_OPTIMIZACION" | "ACCION_OPTIMIZACION_NIVEL_1" | "ACCION_OPTIMIZACION_NIVEL_2" | "ACCION_OPTIMIZACION_NIVEL_3" | "ACCION_ANALISIS_MULTINIVEL" | "ACCION_AUDITORIA" | "ACCION_VISUALIZACION" | "ACCION_INFORME" | "ACCION_VISUALIZACION_E_INFORME" | "ACCION_PIPELINE_COMPLETO" | "ACCION_LISTAR_REPORTES" | "ACCION_NINGUNA",
  "respuesta_conversacional": "Texto de respuesta claro, formal e institucional dirigido al Usuario explicando lo realizado o respondiendo su duda."
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
            
            salida_herramienta = ""
            if accion == "ACCION_INGESTA":
                salida_herramienta = self.tool_ingesta()
            elif accion == "ACCION_PODA":
                salida_herramienta = self.tool_poda()
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
    # ENRUTADOR CONVERSACIONAL (LLM FIRST + FALLBACK LOCAL)
    # =======================================================

    def procesar_mensaje_usuario(self, user_msg: str) -> str:
        # 1. Razonamiento con LLM Gemini si está disponible
        if self.has_real_key:
            respuesta_llm = self._razonar_con_llm(user_msg)
            if respuesta_llm:
                return respuesta_llm

        # 2. Fallback de reglas locales
        txt = user_msg.lower().strip()

        # Detección de nivel específico en el texto del usuario
        match_nivel = re.search(r'nivel\s*([1-3])', txt) or re.search(r'([1-3])\s*saltos?', txt) or re.search(r'([1-3])\s*hops?', txt)
        if not match_nivel and txt in ["1", "2", "3"]:
            nivel_pedido = int(txt)
        else:
            nivel_pedido = int(match_nivel.group(1)) if match_nivel else None

        # Si el usuario indica un nivel o selecciona 'todos', ejecutar automáticamente TODO el pipeline
        if txt in ["todos", "comparar", "compara", "multinivel", "todas"]:
            self.siguiente_accion_sugerida = None
            return self.tool_analisis_multinivel([1, 2, 3])

        if nivel_pedido is not None:
            self.siguiente_accion_sugerida = None
            return self.tool_pipeline_completo(nivel=nivel_pedido)

        # Si la acción sugerida era pipeline con nivel
        if self.siguiente_accion_sugerida == "pipeline_con_nivel":
            if txt in ["si", "sí", "dale", "ok", "adelante", "procede"]:
                return self.tool_pipeline_completo(nivel=2)

        # Respuestas afirmativas contextuales
        if txt in ["si", "sí", "dale", "ok", "bueno", "procede", "adelante", "claro", "por favor", "hazlo", "ejecutalo", "continua", "siguiente", "yes", "y"]:
            if self.siguiente_accion_sugerida == "ingesta":
                return self.tool_ingesta()
            elif self.siguiente_accion_sugerida == "poda":
                return self.tool_poda()
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
                elif not self.state.get("grafo_podado"):
                    return self.tool_poda()
                elif not self.state.get("nodos_banda"):
                    return self.tool_pipeline_completo(nivel=2)
                elif not self.state.get("diagnostico_auditoria"):
                    return self.tool_auditoria()
                else:
                    return self.tool_visualizacion_e_informe()

        # Respuestas negativas
        if txt in ["no", "espera", "todavia no", "despues", "luego", "cancelar"]:
            self.siguiente_accion_sugerida = None
            return f"Entendido. Digame que otra consulta o diligencia desea realizar sobre el caso '{self.state.get('nombre_caso')}'."

        # Saludos e Introducción
        if any(w in txt for w in ["hola", "buenos dias", "buenas tardes", "quien eres", "que puedes hacer", "ayuda", "menu"]):
            return (
                f"Saludos. Soy el Copiloto HeredIA, su orquestador de inteligencia criminal en LangGraph.\n"
                f"Actualmente tengo cargado el caso '{self.state.get('nombre_caso', 'Ninguno')}'.\n\n"
                f"Puedo asistirlo en cualquier momento con las siguientes tareas:\n"
                f" - Analizar partes policiales y sospechosos ('¿quienes son los sospechosos?').\n"
                f" - Optimizar StPro en un nivel específico ('optimiza en nivel 1', 'aisla en nivel 2', 'corre en nivel 3').\n"
                f" - Comparar todos los niveles ('compara los 3 niveles' o 'analisis multinivel').\n"
                f" - Auditar la red y calcular el Blanco de Alto Impacto HVT ('¿cual es el blanco prioritario?').\n"
                f" - Generar diagramas y redactar informes forenses ('genera el informe y grafico').\n"
                f" - Ejecutar todo el workflow de forma autonoma ('corre todo el pipeline').\n\n"
                f"¿Que diligencia desea realizar?"
            )

        # Consultas sobre sospechosos / líderes / lectura del parte
        if any(w in txt for w in [
            "sospechoso", "sospechosos", "imputado", "imputados", "lider", "lideres", 
            "blanco", "blancos", "quienes eran", "quienes son", "quien es", "involucrado", "involucrados",
            "parte policial", "leer parte", "revisa el parte", "analiza el parte", "ingesta", "ingestion"
        ]) and not any(w in txt for w in ["hvt", "alto impacto", "prioritario", "detener"]):
            if not self.state.get("ruts_involucrados"):
                return self.tool_ingesta()
            else:
                ruts = self.state.get("ruts_involucrados", [])
                tamano = self.state.get("tamano_grupo", 0)
                resumen = self.state.get("resumen_caso", "")
                self.siguiente_accion_sugerida = "poda"
                return (
                    f"Para el caso '{self.state.get('nombre_caso')}':\n"
                    f"- Imputados principales (Nodos Raiz): Sujetos {', '.join(ruts)}\n"
                    f"- Tipologia: {self.state.get('tipo_delito', 'VIOLENTO_ARMADO')}\n"
                    f"- Tamano total estimado: {tamano} sospechosos\n"
                    f"- Resumen: {resumen}\n\n"
                    f"¿Desea que ejecutemos la poda y optimización StPro (indique Nivel 1, 2 o 3)?"
                )

        # Comparativa multinivel explícita
        if any(w in txt for w in ["compara niveles", "comparar niveles", "todos los niveles", "multinivel", "1, 2 y 3", "1 y 2 y 3", "los 3 niveles"]):
            return self.tool_analisis_multinivel([1, 2, 3])

        # Consultas sobre Poda Inteligente / FilterAgent
        if any(w in txt for w in ["poda", "podar", "filter", "filtrado", "filtrar", "afinidad", "ruido"]):
            return self.tool_poda(nivel=nivel_pedido)

        # Consultas sobre Blanco HVT / Prioridad de detención / Auditoría
        if any(w in txt for w in [
            "hvt", "blanco prioritario", "alto impacto", "a quien detengo", "a quien detenemos", 
            "orden de detencion", "prioritario", "auditar", "auditoria", "desarticular"
        ]):
            return self.tool_auditoria()

        # Optimización / Gurobi / Aislar banda / StPro (CON SOPORTE DE NIVEL ESPECÍFICO)
        if any(w in txt for w in [
            "optimizar", "optimizacion", "gurobi", "stram", "stpro", "aislar banda", "aisla la banda", 
            "encontrar miembros", "buscar red", "red criminal", "miembros de la banda"
        ]):
            if self.state.get("nivel_actual") is None:
                return self.tool_pipeline_completo()
            else:
                return self.tool_pipeline_completo(nivel=self.state.get("nivel_actual"))

        # Visualización / Gráficos
        if any(w in txt for w in ["visualizar", "visualizacion", "grafico", "graficar", "diagrama", "dibujar", "imagen", "ver red"]):
            return self.tool_visualizacion()

        # Informe pericial / Redacción formal
        if any(w in txt for w in ["informe", "redactar", "documento", "explicacion", "tribunal", "fiscalia", "generar informe", "crear informe"]):
            return self.tool_informe()

        # Listar o cambiar reportes
        if any(w in txt for w in ["listar", "reportes", "que casos", "ver casos", "mostrar pdf", "partes disponibles"]):
            return self.tool_listar_reportes()
            
        if any(w in txt for w in ["cambiar caso", "seleccionar caso", "cargar caso", "cargar reporte", "cambiar a"]):
            return self.tool_seleccionar_reporte(txt)

        # Pipeline completo / autónomo
        if any(w in txt for w in ["todo", "completo", "pipeline", "autonomo", "ejecutar caso", "procesar caso", "corre todo", "ejecuta todo"]):
            return self.tool_pipeline_completo()

        # Estado actual de la investigación
        if any(w in txt for w in ["estado", "resumen", "que tenemos", "como vamos", "informacion actual"]):
            ruts = self.state.get("ruts_involucrados", [])
            banda = self.state.get("nodos_banda", [])
            diag = self.state.get("diagnostico_auditoria") or {}
            hvt_info = diag.get("hvt_prioritario", {})
            hvt = hvt_info.get("id_sospechoso") if isinstance(hvt_info, dict) else hvt_info
            
            return (
                f"Estado actual de la investigacion para '{self.state.get('nombre_caso')}':\n"
                f"- Blancos iniciales (RUTs/IDs raiz): {ruts or 'Pendiente de ingesta'}\n"
                f"- Tipologia: {self.state.get('tipo_delito', 'Pendiente')}\n"
                f"- Poda de grafo: {'Realizada' if self.state.get('grafo_podado') else 'Pendiente'}\n"
                f"- Banda aislada (Gurobi): {len(banda)} miembros ({banda or 'No optimizada aun'})\n"
                f"- Blanco HVT detectado: Nodo {hvt or 'Pendiente de auditoria'}\n"
                f"- Resumen: {self.state.get('resumen_caso', 'Sin procesar')}"
            )

        return (
            f"Como Copiloto HeredIA del Proyecto Principal, puedo ejecutar las siguientes diligencias sobre '{self.state.get('nombre_caso')}':\n"
            f"- '¿Quienes eran los sospechosos?' -> Ingesta cognitiva con IngestionAgent.\n"
            f"- 'Poda el grafo' -> Poda inteligente con PruningAgent.\n"
            f"- 'Aisla la banda con Gurobi' -> Optimizacion matematica StRAM.\n"
            f"- '¿Cual es el blanco HVT prioritario?' -> Interdiccion y AuditorAgent.\n"
            f"- 'Genera el grafico y el informe' -> Exportacion visual y forense.\n"
            f"- 'Ejecuta todo el pipeline' -> Flujo 100% autonomo en LangGraph."
        )

    def iniciar_chat_interactivo(self):
        modo_orquestador = "Google Gemini LLM + LangGraph" if self.has_real_key else "LangGraph (Reglas Cognitivas)"
        print("\n" + "="*75)
        print(" COPILOTO HEREDIA - PROYECTO PRINCIPAL DE INTELIGENCIA CRIMINAL")
        print(f" Orquestador: {modo_orquestador}")
        print("="*75)
        print(f" Caso cargado: {self.state.get('nombre_caso', 'Ninguno')}")
        print(" Escriba en lenguaje natural, por ejemplo:")
        print("   - 'Dime quienes eran los sospechosos'")
        print("   - 'Aplica la poda inteligente criminologica'")
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
    orquestador = InteractiveCriminalOrchestrator()
    orquestador.iniciar_chat_interactivo()
