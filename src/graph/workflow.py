import os
from pathlib import Path
import pandas as pd
from typing import List, Optional, Any
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from src.agents.Ingestion_Agent import IngestionAgent
from src.agents.Optimization_Agent import StProOptimizationAgent
from src.agents.Visualization_Agent import VisualizationAgent
from src.agents.Explanation_Agent import ExplanationAgent

# 1. Definir el Estado Compartido 
class CriminalGraphState(TypedDict):
    pdf_list: List[str]
    current_index: int
    current_pdf: Optional[str]
    nombre_caso: Optional[str]
    ruts_involucrados: List[str]
    tamano_grupo: int
    nodes_df: Optional[Any]
    edges_df: Optional[Any]
    nodos_banda: List[Any]

class CriminalInvestigationWorkflow:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.ingestor = IngestionAgent(data_dir=data_dir, subcarpeta_pdf="pdf_reportes")
        self.visualizador = VisualizationAgent(output_dir=os.path.join(data_dir, "graficos_resultados"))
        self.explicador = ExplanationAgent(output_dir=os.path.join(data_dir, "informes_fiscales"))
        self.workflow = self._construir_grafo()

    def _construir_grafo(self):
        # Inicializar el grafo agentico con el esquema de estado
        builder = StateGraph(CriminalGraphState)

        # Registrar los nodos del pipeline
        builder.add_node("descubrir_reportes", self.node_descubrir_reportes)
        builder.add_node("ingesta_cognitiva", self.node_ingesta_cognitiva)
        builder.add_node("cargar_db_fiscalia", self.node_cargar_db_fiscalia)
        builder.add_node("optimizacion_gurobi", self.node_optimizacion_gurobi)
        builder.add_node("generar_grafico", self.node_generar_grafico)

        # Definir las conexiones lógicas 
        builder.add_edge(START, "descubrir_reportes")
        
        # Condicional autónomo: Si hay reportes, procesar; si no, terminar
        builder.add_conditional_edges(
            "descubrir_reportes",
            self.evaluar_reportes_pendientes,
            {
                "procesar": "ingesta_cognitiva",
                "fin": END
            }
        )

        builder.add_edge("ingesta_cognitiva", "cargar_db_fiscalia")
        builder.add_edge("cargar_db_fiscalia", "optimizacion_gurobi")
        builder.add_edge("optimizacion_gurobi", "generar_grafico")
        
        # Bucle autónomo: Volver a evaluar si quedan más reportes por procesar
        builder.add_conditional_edges(
            "generar_grafico",
            self.evaluar_reportes_pendientes,
            {
                "Procesar": "ingesta_cognitiva",
                "Fin": END
            }
        )

        #Ver la arquitectura final del grafo agentico para ver si es necesario agregar edges condicionales (volver a correr la optimizacion para mas ruts en el mismo caso, por ejemplo)
        return builder.compile()
    
    def node_descubrir_reportes(self, state: CriminalGraphState):
        print("\n[LangGraph] Buscando reportes policiales pendientes...")
        pdf_list = self.ingestor.extract_list_of_pdfs() 
        return {
            "pdf_list": pdf_list,
            "current_index": 0
        }
    
    def node_ingesta_cognitiva(self, state: CriminalGraphState):
        idx = state["current_index"]
        pdf_path = state["pdf_list"][idx]
        nombre_caso = Path(pdf_path).stem
        
        print(f"\n--- [Caso Autónomo {idx + 1}/{len(state['pdf_list'])}] : {nombre_caso} ---")
        
        #
        ruts_involucrados, tamano_grupo = self.ingestor.extract_process_police_report(pdf_path)
        
        return {
            "current_pdf": pdf_path,
            "nombre_caso": nombre_caso,
            "ruts_involucrados": ruts_involucrados,
            "tamano_grupo": tamano_grupo
        }
    def node_cargar_db_fiscalia(self, state: CriminalGraphState):
        print("\n[LangGraph] Cargando bases de datos institucionales de la fiscalía...")
        #Aqui hay que cargar las bases de datos locales verdaderas, probablemente cambiar a conexion con base datos SQL para consultas cruzadas entre diferentes bases
        nodes_df = pd.read_csv(os.path.join(self.data_dir, "nodes.csv"))
        edges_df = pd.read_csv(os.path.join(self.data_dir, "edges.csv"))
        return {
            "nodes_df": nodes_df,
            "edges_df": edges_df
        }
    def node_optimizacion_gurobi(self, state: CriminalGraphState):
        print("\n[LangGraph] Ejecutando optimización con Gurobi (StPro)...")
        try: 
            optimizador = StProOptimizationAgent(nodes_df=state["nodes_df"], edges_df=state["edges_df"])
            ruts = state["ruts_involucrados"]
            raiz_objetivo = ruts[0] if ruts and ruts[0] in optimizador.grafo.nodes else list(optimizador.grafo.nodes)[0]
            nodos_banda = optimizador.ejecutar_stram(start_node=int(raiz_objetivo), phi=0.3)
            print(f"[LangGraph] Nodos detectados (banda criminal): {nodos_banda}")
            self._optimizador_temp = optimizador
            return {
                "nodos_banda": nodos_banda
            }
        except Exception as e:
            print(f"[LangGraph] Error en optimización: {e}")
            return {
                "nodos_banda": []
            }
        
    def node_generar_grafico(self, state: CriminalGraphState):
        print("\n[LangGraph] Generando grafo de resultados...")
        if hasattr(self, '_optimizador_temp') and state["nodos_banda"]:
            ruts = state["ruts_involucrados"]
            raiz_objetivo = ruts[0] if ruts and ruts[0] in self._optimizador_temp.grafo.nodes else list(self._optimizador_temp.grafo.nodes)[0]                
            self.visualizador.graficar_red_criminal(
                grafo=self._optimizador_temp.grafo,
                nodos_banda=state["nodos_banda"],
                nodo_raiz=raiz_objetivo,
                nombre_caso=state["nombre_caso"]
                                                )
        return state

    def node_generar_informe_fiscal(self, state: CriminalGraphState):
        print("[LangGraph] Redactando informe fiscal con ExplanationAgent...")
        self.explicador.generate_explanation(
            nombre_caso=state["nombre_caso"],
            resumen_caso=state["resumen_caso"],
            nodos_banda=state["nodos_banda"],
            ruts_raiz=state["ruts_involucrados"]
        )
        return {"current_index": state["current_index"] + 1}
    
    def evaluar_reportes_pendientes(self, state: CriminalGraphState) -> str:
        """
        Evalúa si quedan más reportes PDF por procesar en la cola.
        Retorna 'procesar' para continuar al siguiente caso o 'fin' para terminar.
        """
        idx = state.get("current_index", 0)
        pdf_list = state.get("pdf_list", [])
        
        if idx < len(pdf_list):
            return "Procesar"
        else:
            print("\n[LangGraph] Todos los reportes han sido procesados con éxito.")
            return "Fin"

    def ejecutar_pipeline(self):
        """
        Ejecuta el flujo de trabajo completo de manera autónoma.
        """
        estado_inicial = {
            "pdf_list": [],
            "current_index": 0,
            "current_pdf": None,
            "nombre_caso": None,
            "ruts_involucrados": [],
            "tamano_grupo": 0,
            "nodes_df": None,
            "edges_df": None,
            "nodos_banda": []
        }
        
        self.workflow.run(estado_inicial)
        