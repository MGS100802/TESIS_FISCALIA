import os
from pathlib import Path
import pandas as pd
import networkx as nx
from typing import List, Optional, Any, Dict
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from src.agents.Ingestion_Agent import IngestionAgent
from src.agents.Filter_Agent import PruningAgent
from src.agents.Optimization_Agent import StProOptimizationAgent
from src.agents.Auditor_Agent import AuditorAgent
from src.agents.Visualization_Agent import VisualizationAgent
from src.agents.Explanation_Agent import ExplanationAgent

# 1. Definir el Estado Compartido del Grafo de Agentes
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
    nodes_df: Optional[Any]
    edges_df: Optional[Any]
    grafo_podado: Optional[Any]
    reporte_poda: Optional[Dict[str, Any]]
    nodos_banda: List[Any]
    diagnostico_auditoria: Optional[Dict[str, Any]]

class CriminalInvestigationWorkflow:
    def __init__(self, data_dir="data", max_nodes_threshold=50):
        self.data_dir = data_dir
        self.ingestor = IngestionAgent(data_dir=data_dir, subcarpeta_reportes="reportes")
        self.pruning_agent = PruningAgent(max_nodes_threshold=max_nodes_threshold, k_hops=2)
        self.auditor_agent = AuditorAgent()
        self.visualizador = VisualizationAgent(output_dir=os.path.join(data_dir, "graficos_resultados"))
        self.explicador = ExplanationAgent(data_dir=os.path.join(data_dir, "informes_fiscalia"))
        self.workflow = self._construir_grafo()

    def _construir_grafo(self):
        builder = StateGraph(CriminalGraphState)

        # 1. Registrar nodos del sistema multi-agente
        builder.add_node("descubrir_reportes", self.node_descubrir_reportes)
        builder.add_node("ingesta_cognitiva", self.node_ingesta_cognitiva)
        builder.add_node("cargar_db_fiscalia", self.node_cargar_db_fiscalia)
        builder.add_node("poda_inteligente", self.node_poda_inteligente)
        builder.add_node("optimizacion_gurobi", self.node_optimizacion_gurobi)
        builder.add_node("auditoria_critica", self.node_auditoria_critica)
        builder.add_node("generar_grafico", self.node_generar_grafico)
        builder.add_node("generar_informe_fiscal", self.node_generar_informe_fiscal)

        # 2. Definir conexiones lógicas
        builder.add_edge(START, "descubrir_reportes")
        
        builder.add_conditional_edges(
            "descubrir_reportes",
            self.evaluar_reportes_pendientes,
            {
                "procesar": "ingesta_cognitiva",
                "fin": END
            }
        )

        builder.add_edge("ingesta_cognitiva", "cargar_db_fiscalia")
        builder.add_edge("cargar_db_fiscalia", "poda_inteligente")
        builder.add_edge("poda_inteligente", "optimizacion_gurobi")
        builder.add_edge("optimizacion_gurobi", "auditoria_critica")
        builder.add_edge("auditoria_critica", "generar_grafico")
        builder.add_edge("generar_grafico", "generar_informe_fiscal")
        
        builder.add_conditional_edges(
            "generar_informe_fiscal",
            self.evaluar_reportes_pendientes,
            {
                "procesar": "ingesta_cognitiva",
                "fin": END
            }
        )

        return builder.compile()
    
    def node_descubrir_reportes(self, state: CriminalGraphState):
        print("\n[LangGraph] Buscando reportes policiales pendientes en 'data/reportes'...")
        pdf_list = self.ingestor.extract_list_of_pdfs() 
        print(f"[LangGraph] Se encontraron {len(pdf_list)} reportes en cola.")
        return {
            "pdf_list": pdf_list,
            "current_index": 0
        }
    
    def node_ingesta_cognitiva(self, state: CriminalGraphState):
        idx = state["current_index"]
        pdf_path = state["pdf_list"][idx]
        nombre_caso = Path(pdf_path).stem
        
        print(f"\n=======================================================")
        print(f" [Caso Autónomo {idx + 1}/{len(state['pdf_list'])}] : {nombre_caso}")
        print(f"=======================================================")
        
        ruts_involucrados, tamano_grupo, resumen_caso, metadatos_utiles = self.ingestor.extract_process_police_report(pdf_path)
        tipo_delito = self.pruning_agent.clasificar_tipologia_delito(resumen_caso, metadatos_utiles)
        
        return {
            "current_pdf": pdf_path,
            "nombre_caso": nombre_caso,
            "resumen_caso": resumen_caso,
            "metadatos_utiles": metadatos_utiles,
            "tipo_delito": tipo_delito,
            "ruts_involucrados": ruts_involucrados,
            "tamano_grupo": tamano_grupo
        }

    def node_cargar_db_fiscalia(self, state: CriminalGraphState):
        print("\n[LangGraph] Cargando base de datos relacional de la Fiscalía (nodes & edges)...")
        nodes_df = pd.read_csv(os.path.join(self.data_dir, "nodes.csv"))
        edges_df = pd.read_csv(os.path.join(self.data_dir, "edges.csv"))
        return {
            "nodes_df": nodes_df,
            "edges_df": edges_df
        }

    def node_poda_inteligente(self, state: CriminalGraphState):
        print("\n[LangGraph] Ejecutando PruningAgent (Poda Adaptativa y Criminológica)...")
        grafo_completo = self.pruning_agent.construir_grafo_desde_dfs(state["nodes_df"], state["edges_df"])
        
        nodos_raiz = [int(r) for r in state["ruts_involucrados"] if str(r).isdigit()]
        if not nodos_raiz and len(grafo_completo.nodes) > 0:
            nodos_raiz = [list(grafo_completo.nodes)[0]]

        grafo_podado, reporte_poda = self.pruning_agent.podar_grafo_inteligente(
            grafo=grafo_completo,
            nodos_raiz=nodos_raiz,
            tipo_delito=state.get("tipo_delito", "VIOLENTO_ARMADO"),
            resumen_caso=state.get("resumen_caso", "")
        )

        return {
            "grafo_podado": grafo_podado,
            "reporte_poda": reporte_poda
        }

    def node_optimizacion_gurobi(self, state: CriminalGraphState):
        print("\n[LangGraph] Ejecutando StProOptimizationAgent (Gurobi StRAM Adaptativo)...")
        try: 
            grafo_a_optimizar = state.get("grafo_podado")
            optimizador = StProOptimizationAgent(grafo=grafo_a_optimizar, data_dir=self.data_dir)
            
            ruts = state["ruts_involucrados"]
            raiz_objetivo = int(ruts[0]) if ruts and str(ruts[0]).isdigit() and int(ruts[0]) in optimizador.grafo.nodes else list(optimizador.grafo.nodes)[0]
            
            nodos_banda = optimizador.ejecutar_stram_adaptativo(start_node=raiz_objetivo, phi_inicial=0.3)
            print(f"[LangGraph] Nodos detectados por Gurobi: {nodos_banda}")
            self._optimizador_temp = optimizador
            return {
                "nodos_banda": nodos_banda
            }
        except Exception as e:
            print(f"[LangGraph] Error en optimización: {e}")
            return {
                "nodos_banda": []
            }
        
    def node_auditoria_critica(self, state: CriminalGraphState):
        print("\n[LangGraph] Ejecutando AuditorAgent (Control de Calidad y Análisis HVT)...")
        grafo_actual = getattr(self, '_optimizador_temp', None)
        G = grafo_actual.grafo if grafo_actual else state.get("grafo_podado")
        
        diagnostico = self.auditor_agent.auditar_solucion(
            grafo=G,
            nodos_banda=state["nodos_banda"],
            nodos_raiz=[int(r) for r in state["ruts_involucrados"] if str(r).isdigit()],
            tamano_estimado_informe=state.get("tamano_grupo", 0)
        )
        return {
            "diagnostico_auditoria": diagnostico
        }

    def node_generar_grafico(self, state: CriminalGraphState):
        print("\n[LangGraph] Generando visualización de la red criminal...")
        if hasattr(self, '_optimizador_temp') and state["nodos_banda"]:
            ruts = state["ruts_involucrados"]
            grafo_actual = self._optimizador_temp.grafo
            raiz_objetivo = int(ruts[0]) if ruts and str(ruts[0]).isdigit() and int(ruts[0]) in grafo_actual.nodes else list(grafo_actual.nodes)[0]                
            
            self.visualizador.graficar_red_criminal(
                grafo=grafo_actual,
                nodos_banda=state["nodos_banda"],
                nodo_raiz=raiz_objetivo,
                nombre_caso=state["nombre_caso"]
            )
        return state

    def node_generar_informe_fiscal(self, state: CriminalGraphState):
        print("\n[LangGraph] Redactando informe fiscal forense con ExplanationAgent...")
        os.makedirs(os.path.join(self.data_dir, "informes_fiscalia"), exist_ok=True)
        
        self.explicador.generate_explanation(
            nombre_caso=state["nombre_caso"],
            resumen_caso=state.get("resumen_caso", "Sin resumen disponible."),
            nodos_banda=state["nodos_banda"],
            ruts_raiz=state["ruts_involucrados"],
            diagnostico_auditoria=state.get("diagnostico_auditoria"),
            reporte_poda=state.get("reporte_poda")
        )
        return {"current_index": state["current_index"] + 1}
    
    def evaluar_reportes_pendientes(self, state: CriminalGraphState) -> str:
        idx = state.get("current_index", 0)
        pdf_list = state.get("pdf_list", [])
        
        if idx < len(pdf_list):
            return "procesar"
        else:
            print("\n[LangGraph] Todos los reportes policiales han sido procesados exitosamente.")
            return "fin"

    def ejecutar_pipeline(self):
        """
        Ejecuta el flujo de trabajo multi-agente completo de manera autónoma.
        """
        estado_inicial = {
            "pdf_list": [],
            "current_index": 0,
            "current_pdf": None,
            "nombre_caso": None,
            "resumen_caso": None,
            "metadatos_utiles": None,
            "tipo_delito": None,
            "ruts_involucrados": [],
            "tamano_grupo": 0,
            "nodes_df": None,
            "edges_df": None,
            "grafo_podado": None,
            "reporte_poda": None,
            "nodos_banda": [],
            "diagnostico_auditoria": None
        }
        
        try:
            return self.workflow.invoke(estado_inicial)
        except AttributeError:
            return self.workflow.run(estado_inicial)