import os
import pandas as pd
import networkx as nx
from dotenv import load_dotenv
from src.agents.Ingestion_Agent import IngestionAgent
from src.utils.models_STRAM_KsRAM import StRAM, RGEN, RGENF

load_dotenv()

class StProOptimizationAgent:
    def __init__(self, nodes_df: pd.DataFrame = None, edges_df: pd.DataFrame = None, data_dir="data"):
        """
        Inicializa el agente de optimización asegurando la creación del grafo.
        """
        self.data_dir = data_dir
        
        # 1. Asignar los dataframes recibidos (por ejemplo, desde las bases de datos locales de la fiscalía)
        if nodes_df is not None and edges_df is not None:
            self.nodes_df = nodes_df
            self.edges_df = edges_df
        else:
            # Respaldo por si se llama al optimizador de forma aislada
            print("[StProOptimizationAgent] Advertencia: No se pasaron dataframes directos. Cargando desde archivos CSV locales predeterminados...")
            self.nodes_df = pd.read_csv(f"{data_dir}/nodes.csv")
            self.edges_df = pd.read_csv(f"{data_dir}/edges.csv")

        # 2. Inicializar explícitamente el atributo grafo
        self.grafo = self.construir_grafo()

    def construir_grafo(self):
        G = nx.Graph()
        
        for _, row in self.nodes_df.iterrows():
            G.add_node(int(row['id']), pcg=float(row['pcg']), label=int(row['label']))
            
        for _, row in self.edges_df.iterrows():
            G.add_edge(int(row['source']), int(row['target']), distance=float(row['distance']))
            
        return G

    def ejecutar_stram(self, start_node: int = 1, phi: float = 0.3):
        """Ejecuta el modelo StRAM (StPro) utilizando Gurobi."""
        # Doble verificación por seguridad
        if not hasattr(self, 'grafo') or self.grafo is None:
            self.grafo = self.construir_grafo()
        try:
            m, x, y = StRAM(self.grafo, start_node=start_node, phi=phi, output=0)
            nodos_seleccionados = [j for j in self.grafo.nodes if y[j].X > 0.5]
            return nodos_seleccionados
        except Exception as e:
            print(f"Error al ejecutar StRAM: {e}")
            return []
#if __name__ == "__main__":    
 #   ingestor = IngestionAgent()
#  optimizador = StProOptimizationAgent(ingestion_agent=ingestor)
 #   nodos_banda = optimizador.ejecutar_stram(start_node=1, phi=0.3)
 #   print("\n========================================")
 #   print(" RESULTADOS FINALES DE LA OPTIMIZACIÓN ")
 #   print("========================================")
 #   print(f"Nodos detectados (banda criminal): {nodos_banda}")
 #   print(f"Total de sospechosos identificados: {len(nodos_banda)}")
 #   print("========================================")