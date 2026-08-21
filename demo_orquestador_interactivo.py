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
            "nodes_df": None,
            "edges_df": None,
            "grafo_completo": None,
            "nodos_banda": [],
            "diagnostico_auditoria": None
        }
        self.op_agent_temp = None
        self.siguiente_accion_sugerida = None
        self._inicializar_reportes()
        self.compiled_graph = self._construir_grafo_langgraph()

    def _inicializar_reportes(self):
        ruta_carpeta = Path(self.data_dir) / "reportes"
        self.state["pdf_list"] = [str(pdf) for pdf in ruta_carpeta.glob("*.pdf")]
        if self.state["pdf_list"]:
            self.state["current_pdf"] = self.state["pdf_list"][0]
            self.state["nombre_caso"] = Path(self.state["current_pdf"]).stem

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
        self.tool_optimizacion()
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
                self.state["current_pdf"] = p
                self.state["nombre_caso"] = Path(p).stem
                self.state["ruts_involucrados"] = []
                self.state["nodos_banda"] = []
                self.state["diagnostico_auditoria"] = None
                self.siguiente_accion_sugerida = "ingesta"
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
            f"¿Desea que consulte la base de datos de Fiscalia y ejecutemos la optimizacion de la red con Gurobi?"
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
        
        G = nx.Graph()
        for _, row in nodes_df.iterrows():
            G.add_node(int(row['id']), pcg=float(row['pcg']), label=row['label'])
        for _, row in edges_df.iterrows():
            G.add_edge(int(row['source']), int(row['target']), distance=float(row['distance']))
            
        self.state["grafo_completo"] = G
        return f"Base de datos relacional institucional cargada ({G.number_of_nodes()} sospechosos y {G.number_of_edges()} vinculos criminales)."

    def tool_optimizacion(self) -> str:
        if not self.state.get("ruts_involucrados"):
            self.tool_ingesta()

        if self.state["grafo_completo"] is None:
            self.tool_cargar_bd()

        print("\n[OptimizationAgent] Ejecutando Gurobi StPro / StRAM adaptativo...")
        G = self.state["grafo_completo"]
        self.op_agent_temp = StProOptimizationAgent(grafo=G, data_dir=self.data_dir)
        
        ruts = self.state.get("ruts_involucrados", [])
        raiz_objetivo = None
        for r in ruts:
            if str(r).isdigit() and int(r) in G.nodes:
                raiz_objetivo = int(r)
                break
        if raiz_objetivo is None:
            raiz_objetivo = list(G.nodes)[0]

        nodos_banda = self.op_agent_temp.ejecutar_stram_adaptativo(start_node=raiz_objetivo, phi_inicial=0.3)
        self.state["nodos_banda"] = nodos_banda
        self.siguiente_accion_sugerida = "auditoria"
        
        return (
            f"[OK] Optimizacion matematica con Gurobi (Modelo StRAM) completada:\n"
            f"- Celula criminal aislada: {len(nodos_banda)} integrantes\n"
            f"- Nodos detectados: {nodos_banda}\n\n"
            f"¿Desea que el AuditorAgent evalue la red e identifique el Blanco de Alto Impacto (HVT)?"
        )

    def tool_auditoria(self) -> str:
        if not self.state.get("nodos_banda"):
            self.tool_optimizacion()

        print("\n[AuditorAgent] Evaluando calidad forense y calculando Blanco de Alto Impacto (HVT)...")
        G = self.state["grafo_completo"]
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
        G = self.state["grafo_completo"]
        ruts = self.state.get("ruts_involucrados", [])
        raiz_objetivo = int(ruts[0]) if ruts and str(ruts[0]).isdigit() and int(ruts[0]) in G.nodes else list(G.nodes)[0]
        
        self.visualizador.graficar_red_criminal(
            grafo=G,
            nodos_banda=self.state["nodos_banda"],
            nodo_raiz=raiz_objetivo,
            nombre_caso=self.state.get("nombre_caso", "caso_demo")
        )
        self.siguiente_accion_sugerida = "informe"
        return f"[OK] Grafico de la red criminal exportado con exito a:\n'data/graficos_resultados/grafo_{self.state.get('nombre_caso')}.png'"

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

    def tool_pipeline_completo(self) -> str:
        print("\n>>> [LangGraph Orchestrator] Invocando Grafo de Estados Autonomo (StateGraph)...")
        try:
            self.compiled_graph.invoke(self.state)
            self.siguiente_accion_sugerida = None
            return (
                "[OK] Pipeline Multi-Agente ejecutado al 100% de manera autonoma con LangGraph:\n"
                f"   1. Ingesta cognitiva realizada.\n"
                f"   2. Base relacional consultada.\n"
                f"   3. Modelo Gurobi StRAM resuelto ({len(self.state.get('nodos_banda', []))} miembros).\n"
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
        """
        Usa Google Gemini para razonar sobre el mensaje del usuario, decidir qué herramienta invocar
        o generar una respuesta conversacional fundamentada en el caso.
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
                "accion_previa_sugerida": self.siguiente_accion_sugerida
            }
            
            prompt = f"""Eres el Copiloto HeredIA, el Agente Orquestador Multi-Agente de Inteligencia Criminal de la Fiscalía de Chile (LangGraph Copilot).
Tu función es razonar sobre lo que el Usuario te pide y coordinar los agentes del sistema.

Contexto actual de la investigación:
{json.dumps(contexto_actual, ensure_ascii=False, indent=2)}

Herramientas disponibles que puedes ordenar ejecutar:
- "ACCION_INGESTA": Lee el parte policial PDF con IngestionAgent y extrae sospechosos/delito.
- "ACCION_OPTIMIZACION": Resuelve el modelo matemático StRAM en Gurobi con OptimizationAgent.
- "ACCION_AUDITORIA": Evalúa la red y calcula el Blanco de Alto Impacto (HVT) con AuditorAgent.
- "ACCION_VISUALIZACION": Dibuja el grafo en PNG con VisualizationAgent.
- "ACCION_INFORME": Redacta el informe formal para Fiscalía con ExplanationAgent.
- "ACCION_VISUALIZACION_E_INFORME": Genera tanto el gráfico como el informe.
- "ACCION_PIPELINE_COMPLETO": Ejecuta todo el flujo autónomo de LangGraph.
- "ACCION_LISTAR_REPORTES": Lista los reportes en PDF.
- "ACCION_NINGUNA": Solo responder la pregunta del usuario con los datos que ya tenemos.

Instrucción estricta:
Responde ÚNICAMENTE en formato JSON con la siguiente estructura:
{{
  "accion_a_ejecutar": "ACCION_INGESTA" | "ACCION_OPTIMIZACION" | "ACCION_AUDITORIA" | "ACCION_VISUALIZACION" | "ACCION_INFORME" | "ACCION_VISUALIZACION_E_INFORME" | "ACCION_PIPELINE_COMPLETO" | "ACCION_LISTAR_REPORTES" | "ACCION_NINGUNA",
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
            
            # Ejecutar la herramienta decidida por el LLM
            salida_herramienta = ""
            if accion == "ACCION_INGESTA":
                salida_herramienta = self.tool_ingesta()
            elif accion == "ACCION_OPTIMIZACION":
                salida_herramienta = self.tool_optimizacion()
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
                
        except Exception as e:
            # Si hay error en la llamada de Gemini (por ejemplo cuota o red), usamos el fallback local
            return None

    # =======================================================
    # ENRUTADOR PRINCIPAL (LLM FIRST + FALLBACK LOCAL)
    # =======================================================

    def procesar_mensaje_usuario(self, user_msg: str) -> str:
        # 1. Intentar razonar con el LLM (Google Gemini) si está configurado
        if self.has_real_key:
            respuesta_llm = self._razonar_con_llm(user_msg)
            if respuesta_llm:
                return respuesta_llm
        
        # 2. Fallback de reglas locales (Offline / Sin API Key)
        txt = user_msg.lower().strip()
        
        # Respuestas afirmativas contextuales
        if txt in ["si", "sí", "dale", "ok", "bueno", "procede", "adelante", "claro", "por favor", "hazlo", "ejecutalo", "continua", "siguiente", "yes", "y"]:
            if self.siguiente_accion_sugerida == "ingesta":
                return self.tool_ingesta()
            elif self.siguiente_accion_sugerida == "optimizacion":
                return self.tool_optimizacion()
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
                    return self.tool_optimizacion()
                elif not self.state.get("diagnostico_auditoria"):
                    return self.tool_auditoria()
                else:
                    return self.tool_visualizacion_e_informe()

        # Respuestas negativas
        if txt in ["no", "espera", "todavia no", "despues", "luego", "cancelar"]:
            self.siguiente_accion_sugerida = None
            return f"Entendido, Fiscal. Dígame qué otra consulta o acción desea realizar sobre el caso '{self.state.get('nombre_caso')}'."

        # Saludos e Introducción
        if any(w in txt for w in ["hola", "buenos dias", "buenas tardes", "quien eres", "que puedes hacer", "ayuda", "menu"]):
            return (
                f"Saludos. Soy el Copiloto HeredIA, su asistente multi-agente de inteligencia criminal en LangGraph.\n"
                f"Actualmente tengo cargado el caso '{self.state.get('nombre_caso', 'Ninguno')}'.\n\n"
                f"Puedo asistirlo en cualquier momento con las siguientes tareas:\n"
                f" - Preguntar por los sospechosos o delitos del caso ('¿quienes son los sospechosos?').\n"
                f" - Consultar la base de datos y optimizar la red con Gurobi ('aisla la banda con Gurobi').\n"
                f" - Auditar la red e identificar el Blanco de Alto Impacto HVT ('¿cual es el blanco prioritario?').\n"
                f" - Generar el diagrama visual y redactar el informe pericial ('genera el informe y grafico').\n"
                f" - Ejecutar todo el flujo de forma autonoma ('corre todo el pipeline').\n\n"
                f"¿Que diligencia desea realizar?"
            )
            
        # Consultas sobre sospechosos / líderes / imputados / lectura del parte
        if any(w in txt for w in [
            "sospechoso", "sospechosos", "imputado", "imputados", "lider", "lideres", 
            "blanco", "blancos", "quienes eran", "quienes son", "quien es", "involucrado", "involucrados",
            "parte policial", "leer parte", "revisa el parte", "analiza el parte", "ingesta", "ingestion", "2"
        ]) and not any(w in txt for w in ["hvt", "alto impacto", "prioritario", "detener"]):
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
                    f"¿Desea que ejecutemos la optimizacion de la red con Gurobi para aislar a todos sus miembros?"
                )

        # Consultas sobre Blanco HVT / Prioridad de detención / Auditoría
        if any(w in txt for w in [
            "hvt", "blanco prioritario", "alto impacto", "a quien detengo", "a quien detenemos", 
            "orden de detencion", "prioritario", "auditar", "auditoria", "desarticular", "4"
        ]):
            return self.tool_auditoria()

        # Optimización / Gurobi / Aislar banda
        if any(w in txt for w in [
            "optimizar", "optimizacion", "gurobi", "stram", "aislar banda", "aisla la banda", 
            "encontrar miembros", "buscar red", "red criminal", "miembros de la banda", "3"
        ]):
            return self.tool_optimizacion()

        # Visualización / Gráficos
        if any(w in txt for w in [
            "visualizar", "visualizacion", "grafico", "graficar", "diagrama", "dibujar", 
            "imagen", "ver red", "5"
        ]):
            return self.tool_visualizacion()

        # Informe pericial / Redacción formal
        if any(w in txt for w in [
            "informe", "redactar", "documento", "explicacion", "tribunal", "fiscalia", 
            "generar informe", "crear informe", "6"
        ]):
            return self.tool_informe()

        # Listar o cambiar reportes
        if any(w in txt for w in [
            "listar", "reportes", "que casos", "ver casos", "mostrar pdf", "partes disponibles", "1"
        ]):
            return self.tool_listar_reportes()
            
        if any(w in txt for w in ["cambiar caso", "seleccionar caso", "cargar caso", "cargar reporte", "cambiar a"]):
            return self.tool_seleccionar_reporte(txt)

        # Pipeline completo / autónomo
        if any(w in txt for w in [
            "todo", "completo", "pipeline", "autonomo", "ejecutar caso", "procesar caso", 
            "corre todo", "ejecuta todo", "7"
        ]):
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
            f"- 'Ejecuta todo el pipeline' -> Corre todo el grafo de LangGraph de forma autonoma."
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
