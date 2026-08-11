import pandas as pd
import networkx as nx
from typing import Optional, List, Union
from dotenv import load_dotenv
from src.utils.models_STRAM_KsRAM import StRAM, KsRAM, RGEN, RGENF

load_dotenv()

class StProOptimizationAgent:
    def __init__(
        self, 
        nodes_df: Optional[pd.DataFrame] = None, 
        edges_df: Optional[pd.DataFrame] = None, 
        grafo: Optional[nx.Graph] = None,
        data_dir: str = "data"
    ):
        """
        Inicializa el agente de optimización matemática con Gurobi.
        Puede recibir directamente un grafo podado de NetworkX o DataFrames.
        """
        self.data_dir = data_dir
        self.nodes_df = nodes_df
        self.edges_df = edges_df
        
        if grafo is not None:
            self.grafo = grafo.copy()
        elif nodes_df is not None and edges_df is not None:
            self.grafo = self.construir_grafo()
        else:
            print("[StProOptimizationAgent] Advertencia: No se pasaron datos directos. Cargando CSVs por defecto...")
            self.nodes_df = pd.read_csv(f"{data_dir}/nodes.csv")
            self.edges_df = pd.read_csv(f"{data_dir}/edges.csv")
            self.grafo = self.construir_grafo()

    def construir_grafo(self) -> nx.Graph:
        """Construye un grafo NetworkX desde los DataFrames cargados."""
        G = nx.Graph()
        for _, row in self.nodes_df.iterrows():
            G.add_node(int(row['id']), pcg=float(row.get('pcg', 0.5)), label=int(row.get('label', row.get('id', 0))))
            
        for _, row in self.edges_df.iterrows():
            G.add_edge(int(row['source']), int(row['target']), distance=float(row.get('distance', 1.0)))
            
        return G

    def ejecutar_stram_adaptativo(
        self, 
        start_node: int = 1, 
        phi_inicial: float = 0.3, 
        max_reintentos: int = 3
    ) -> List[int]:
        """
        Ejecuta el modelo StRAM con bucle de calibración adaptativa:
        Si phi_inicial genera infactibilidad o conjunto vacío, incrementa phi progresivamente.
        """
        if not hasattr(self, 'grafo') or self.grafo is None or len(self.grafo.nodes) == 0:
            print("[StProOptimizationAgent] Error: El grafo está vacío.")
            return []

        
        if start_node not in self.grafo.nodes:
            start_node = list(self.grafo.nodes)[0]

        phi_actual = phi_inicial
        for intento in range(max_reintentos):
            try:
                print(f"[StProOptimizationAgent] Optimizando StRAM (Nodo Raíz: {start_node}, Phi: {phi_actual:.2f}, Intento {intento + 1})...")
                m, x, y = StRAM(self.grafo, start_node=start_node, phi=phi_actual, output=0)
                nodos_seleccionados = [j for j in self.grafo.nodes if y[j].X > 0.5]

                if len(nodos_seleccionados) > 1:
                    print(f"[StProOptimizationAgent] Optimización exitosa: {len(nodos_seleccionados)} integrantes detectados.")
                    return nodos_seleccionados
                else:
                    print(f"[StProOptimizationAgent] Solución trivial con phi={phi_actual:.2f}. Ajustando tolerancia...")
                    phi_actual += 0.15

            except Exception as e:
                print(f"[StProOptimizationAgent] Intento {intento + 1} falló ({e}). Relajando parámetro phi...")
                phi_actual += 0.15

        print("[StProOptimizationAgent] No se pudo encontrar solución no trivial tras reintentos adaptativos.")
        return [start_node]

    # Alias para compatibilidad
    def ejecutar_stram(self, start_node: int = 1, phi: float = 0.3) -> List[int]:
        return self.ejecutar_stram_adaptativo(start_node=start_node, phi_inicial=phi)