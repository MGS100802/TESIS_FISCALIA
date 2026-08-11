import networkx as nx
import pandas as pd
from typing import List, Dict, Tuple, Optional, Any

class PruningAgent:
    """
    Agente de Poda Inteligente y Filtrado Estructural de Redes Criminales.
    
    Aplica poda condicional adaptativa:
    1. Si el grafo es pequeño/mediano (<= max_nodes_threshold), preserva el grafo íntegro 
       para no perder delitos instrumentales conexos (ej: receptación, porte de armas).
    2. Si el grafo es grande/denso (> max_nodes_threshold), aplica poda por:
       - Vecindad estructural (k-hops).
       - Matriz de afinidad delictiva (exclusión de ruido como estafas/fraudes aislados).
       - Preservación estricta de nodos puente (puntos de articulación) para no quebrar la red.
    """
    
    AFINIDADES_DELICTIVAS = {
        "VIOLENTO_ARMADO": {
            "compatibles": ["homicidio", "robo", "receptacion", "armas", "drogas", "secuestro", "asociacion_ilicita", "extorsion"],
            "ruido": ["fraude", "estafa", "delito_tributario", "giro_doloso", "propiedad_intelectual", "infraccion_aduanera"]
        },
        "NARCOTRAFICO": {
            "compatibles": ["drogas", "armas", "lavado_activos", "receptacion", "homicidio", "asociacion_ilicita", "cohecho"],
            "ruido": ["estafa", "delito_tributario", "giro_doloso", "propiedad_intelectual"]
        },
        "ECONOMICO_PATRIMONIAL": {
            "compatibles": ["estafa", "fraude", "lavado_activos", "cohecho", "asociacion_ilicita", "delito_tributario", "falsificacion"],
            "ruido": ["homicidio", "robo_con_violencia", "secuestro"]
        }
    }

    def __init__(self, max_nodes_threshold: int = 50, k_hops: int = 2, umbral_pcg_minimo: float = 0.3):
        self.max_nodes_threshold = max_nodes_threshold
        self.k_hops = k_hops
        self.umbral_pcg_minimo = umbral_pcg_minimo

    def construir_grafo_desde_dfs(self, nodes_df: pd.DataFrame, edges_df: pd.DataFrame) -> nx.Graph:
        """Crea un grafo NetworkX a partir de DataFrames de nodos y aristas."""
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

    def clasificar_tipologia_delito(self, resumen_caso: str, metadatos: Optional[Dict] = None) -> str:
        """
        Clasifica la tipología investigativa del caso a partir del resumen o metadatos del informe policial.
        """
        texto = (resumen_caso or "").lower()
        if metadatos:
            texto += " " + str(metadatos).lower()

        if any(w in texto for w in ["homicidio", "arma", "violencia", "robo", "encerrona", "turbazo", "secuestro", "pistola", "disparo"]):
            return "VIOLENTO_ARMADO"
        elif any(w in texto for w in ["droga", "narcotráfico", "cocaína", "pasta base", "marihuana", "microtráfico", "sustancia"]):
            return "NARCOTRAFICO"
        elif any(w in texto for w in ["estafa", "fraude", "facturas", "cheque", "tributario", "bancario", "cuello blanco"]):
            return "ECONOMICO_PATRIMONIAL"
        
        # Por defecto en investigaciones fiscales de crimen organizado
        return "VIOLENTO_ARMADO"

    def podar_grafo_inteligente(
        self,
        grafo: nx.Graph,
        nodos_raiz: List[int],
        tipo_delito: str = "VIOLENTO_ARMADO",
        resumen_caso: str = ""
    ) -> Tuple[nx.Graph, Dict[str, Any]]:
        """
        Ejecuta la poda adaptativa del grafo considerando escala, tipología y topología.
        
        Retorna:
            (subgrafo_podado, reporte_poda_dict)
        """
        n_inicial = len(grafo.nodes)
        e_inicial = len(grafo.edges)
        
        raices_validas = [int(r) for r in nodos_raiz if int(r) in grafo.nodes]
        if not raices_validas and len(grafo.nodes) > 0:
            raices_validas = [list(grafo.nodes)[0]]

        reporte = {
            "nodos_iniciales": n_inicial,
            "aristas_iniciales": e_inicial,
            "tipo_delito_detectado": tipo_delito,
            "poda_activada": False,
            "motivo_decision": "",
            "nodos_eliminados": 0,
            "nodos_finales": n_inicial,
            "aristas_finales": e_inicial,
            "puentes_protegidos": []
        }

        # -------------------------------------------------------------
        # CASO 1: Grafo Pequeño o Mediano (<= max_nodes_threshold)
        # -------------------------------------------------------------
        if n_inicial <= self.max_nodes_threshold:
            reporte["motivo_decision"] = (
                f"Grafo de tamaño manejable (N={n_inicial} <= {self.max_nodes_threshold}). "
                f"Se mantiene la estructura completa para preservar delitos instrumentales conexos "
                f"(ej: receptación, porte de armas, nexos logísticos)."
            )
            print(f"[PruningAgent] {reporte['motivo_decision']}")
            return grafo.copy(), reporte

        # -------------------------------------------------------------
        # CASO 2: Grafo Grande/Denso (> max_nodes_threshold) -> Poda Activa
        # -------------------------------------------------------------
        reporte["poda_activada"] = True
        print(f"[PruningAgent] Grafo grande detectado (N={n_inicial} > {self.max_nodes_threshold}). Activando poda adaptativa...")

        # 1. Poda topológica por k-hops desde los nodos raíz
        nodos_k_hops = set(raices_validas)
        for raiz in raices_validas:
            sub_ego = nx.single_source_shortest_path_length(grafo, raiz, cutoff=self.k_hops)
            nodos_k_hops.update(sub_ego.keys())

        subgrafo = grafo.subgraph(nodos_k_hops).copy()

        # 2. Identificar y blindar puntos de articulación (nodos puente)
        puentes_articulacion = list(nx.articulation_points(subgrafo)) if len(subgrafo.nodes) > 2 else []
        reporte["puentes_protegidos"] = puentes_articulacion

        # 3. Poda por Tipología Delictiva y Propensión (PCG)
        afinidad = self.AFINIDADES_DELICTIVAS.get(tipo_delito, self.AFINIDADES_DELICTIVAS["VIOLENTO_ARMADO"])
        lista_ruido = afinidad["ruido"]
        
        nodos_a_remover = set()
        for nodo in subgrafo.nodes:
            # Nunca eliminar los blancos clave (raíz) ni los puentes de articulación
            if nodo in raices_validas or nodo in puentes_articulacion:
                continue

            attr = subgrafo.nodes[nodo]
            tipo_nodo = attr.get("tipo_delito", "")
            pcg_nodo = attr.get("pcg", 0.5)
            grado_nodo = subgrafo.degree(nodo)

            # Regla A: Delito incompatible en la periferia (ej. estafa/fraude puro en caso violento)
            if tipo_nodo and any(r in tipo_nodo for r in lista_ruido):
                nodos_a_remover.add(nodo)
                continue

            # Regla B: Hojas periféricas desconectadas o de propensión insignificante
            if grado_nodo <= 1 and pcg_nodo < self.umbral_pcg_minimo:
                nodos_a_remover.add(nodo)

        subgrafo.remove_nodes_from(nodos_a_remover)

        # 4. Asegurar que la componente conexa principal de las raíces permanezca conectada
        componentes = list(nx.connected_components(subgrafo))
        componente_principal = set()
        for raiz in raices_validas:
            for comp in componentes:
                if raiz in comp:
                    componente_principal.update(comp)
        
        if componente_principal:
            subgrafo = subgrafo.subgraph(componente_principal).copy()

        # Actualizar reporte de métricas
        n_final = len(subgrafo.nodes)
        e_final = len(subgrafo.edges)
        reporte["nodos_eliminados"] = n_inicial - n_final
        reporte["nodos_finales"] = n_final
        reporte["aristas_finales"] = e_final
        reporte["motivo_decision"] = (
            f"Grafo podado exitosamente de {n_inicial} a {n_final} nodos ({reporte['nodos_eliminados']} eliminados). "
            f"Se aplicó filtro de {self.k_hops}-hops para tipología '{tipo_delito}', blindando {len(puentes_articulacion)} puntos de articulación."
        )

        print(f"[PruningAgent] {reporte['motivo_decision']}")
        return subgrafo, reporte


# Alias para compatibilidad con el nombre anterior
FilterAgent = PruningAgent
