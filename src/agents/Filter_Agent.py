import networkx as nx
import pandas as pd
from typing import List, Dict, Tuple, Optional, Any

class LevelFilterAgent:
    """
    Agente de Filtrado Topológico por Nivel (k-hops / Ego-Network) para Fiscalía.
    
    Aplica el preprocesamiento oficial de la herramienta StPro (Paper Troncoso & Weber, Fig 6):
    Extrae la sub-red de sospechosos a distancia <= nivel (saltos) desde el sospechoso principal
    (RUT Planificador / Nodos Raíz) antes de ejecutar el optimizador matemático.
    """

    def __init__(self, max_nodes_threshold: int = 50, k_hops: int = 2, umbral_pcg_minimo: float = 0.3):
        self.k_hops = k_hops
        self.max_nodes_threshold = max_nodes_threshold

    def construir_grafo_desde_dfs(self, nodes_df: pd.DataFrame, edges_df: pd.DataFrame) -> nx.Graph:
        """Crea un grafo NetworkX a partir de DataFrames de nodos y aristas de Fiscalía."""
        G = nx.Graph()
        for _, row in nodes_df.iterrows():
            attr = {
                "pcg": float(row.get("pcg", 0.5)),
                "label": int(row.get("label", row.get("id", 0)))
            }
            if "tipo_delito" in row:
                attr["tipo_delito"] = str(row["tipo_delito"]).lower()
            G.add_node(int(row["id"]), **attr)
            
        for _, row in edges_df.iterrows():
            G.add_edge(int(row["source"]), int(row["target"]), distance=float(row.get("distance", 1.0)))
        return G

    def clasificar_tipologia_delito(self, resumen_caso: str = "", metadatos: Optional[Dict] = None) -> str:
        """Clasificación informativa del caso para trazabilidad forense."""
        texto = (resumen_caso or "").lower()
        if metadatos:
            texto += " " + str(metadatos).lower()

        if any(w in texto for w in ["homicidio", "arma", "violencia", "robo", "encerrona", "turbazo", "secuestro"]):
            return "VIOLENTO_ARMADO"
        elif any(w in texto for w in ["droga", "narcotráfico", "cocaína", "sustancia"]):
            return "NARCOTRAFICO"
        return "GENERAL"

    def extraer_subgrafo_por_nivel(self, grafo: nx.Graph, nodo_raiz: int, nivel: int = 2) -> nx.Graph:
        """
        Extrae la subred a distancia <= nivel (k-hops) desde la raíz, tal como opera
        la herramienta de la Fiscalía de Chile (Paper StPro, Fig 6).
        """
        if nodo_raiz not in grafo.nodes:
            if len(grafo.nodes) > 0:
                nodo_raiz = list(grafo.nodes)[0]
            else:
                return nx.Graph()

        distancias = nx.single_source_shortest_path_length(grafo, nodo_raiz, cutoff=nivel)
        nodos_nivel = set(distancias.keys())
        return grafo.subgraph(nodos_nivel).copy()

    def podar_grafo_inteligente(
        self,
        grafo: nx.Graph,
        nodos_raiz: List[int],
        tipo_delito: str = "GENERAL",
        resumen_caso: str = "",
        nivel: Optional[int] = None
    ) -> Tuple[nx.Graph, Dict[str, Any]]:
        """
        Filtra el grafo exclusivamente por NIVEL (distancia en saltos k-hops desde las raíces).
        
        Retorna:
            (subgrafo_por_nivel, reporte_dict)
        """
        hops_a_usar = nivel if nivel is not None else self.k_hops
        n_inicial = len(grafo.nodes)
        e_inicial = len(grafo.edges)
        
        raices_validas = [int(r) for r in nodos_raiz if int(r) in grafo.nodes]
        if not raices_validas and len(grafo.nodes) > 0:
            raices_validas = [list(grafo.nodes)[0]]

        # Extraer todos los nodos a distancia <= hops_a_usar de los nodos raíz
        nodos_k_hops = set(raices_validas)
        for raiz in raices_validas:
            sub_ego = nx.single_source_shortest_path_length(grafo, raiz, cutoff=hops_a_usar)
            nodos_k_hops.update(sub_ego.keys())

        subgrafo = grafo.subgraph(nodos_k_hops).copy()
        n_final = len(subgrafo.nodes)
        e_final = len(subgrafo.edges)

        reporte = {
            "nodos_iniciales": n_inicial,
            "aristas_iniciales": e_inicial,
            "tipo_delito_detectado": tipo_delito,
            "nivel_aplicado": hops_a_usar,
            "poda_activada": True,
            "motivo_decision": (
                f"Filtrado exclusivo por Nivel={hops_a_usar} aplicado desde raíz {raices_validas}. "
                f"Red acotada de {n_inicial} a {n_final} sospechosos ({n_inicial - n_final} fuera del radio de {hops_a_usar} saltos)."
            ),
            "nodos_eliminados": n_inicial - n_final,
            "nodos_finales": n_final,
            "aristas_finales": e_final,
            "puentes_protegidos": []
        }

        print(f"[FilterAgent] {reporte['motivo_decision']}")
        return subgrafo, reporte


# Alias para compatibilidad con el resto del sistema
FilterAgent = LevelFilterAgent
PruningAgent = LevelFilterAgent
