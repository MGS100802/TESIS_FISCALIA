import networkx as nx
import numpy as np
from typing import List, Dict, Any, Set, Tuple, Optional

def calcular_metricas_clasificacion(
    nodos_predichos: List[int], 
    nodos_reales: List[int], 
    total_universo_nodos: Optional[int] = None
) -> Dict[str, float]:
    """
    Calcula métricas estándar de detección/clasificación binaria frente a un Ground Truth:
    - Precision (Precisión)
    - Recall (Sensibilidad / Cobertura)
    - F1-Score
    - Jaccard Similarity Index
    - Accuracy (si se provee el universo total de nodos)
    """
    set_pred = set(nodos_predichos)
    set_true = set(nodos_reales)

    tp = len(set_pred.intersection(set_true))
    fp = len(set_pred - set_true)
    fn = len(set_true - set_pred)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    union = len(set_pred.union(set_true))
    jaccard = tp / union if union > 0 else 0.0

    metricas = {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "jaccard_index": round(jaccard, 4)
    }

    if total_universo_nodos is not None and total_universo_nodos >= len(set_true):
        tn = total_universo_nodos - (tp + fp + fn)
        accuracy = (tp + tn) / total_universo_nodos if total_universo_nodos > 0 else 0.0
        metricas["accuracy"] = round(accuracy, 4)
        metricas["true_negatives"] = tn

    return metricas

def calcular_metricas_red_criminal(grafo: nx.Graph, nodos_banda: List[int]) -> Dict[str, Any]:
    """
    Calcula métricas forenses y topológicas de la banda criminal detectada en comparación con el resto del grafo.
    """
    if not nodos_banda or len(grafo.nodes) == 0:
        return {}

    nodos_banda_validos = [n for n in nodos_banda if n in grafo.nodes]
    if not nodos_banda_validos:
        return {}

    subgrafo_banda = grafo.subgraph(nodos_banda_validos)

    # 1. Propensión Criminal (PCG)
    pcgs_banda = [grafo.nodes[n].get('pcg', 0.5) for n in nodos_banda_validos]
    nodos_fuera = [n for n in grafo.nodes if n not in nodos_banda_validos]
    pcgs_fuera = [grafo.nodes[n].get('pcg', 0.5) for n in nodos_fuera] if nodos_fuera else [0.0]

    avg_pcg_banda = float(np.mean(pcgs_banda)) if pcgs_banda else 0.0
    avg_pcg_grafo = float(np.mean(pcgs_fuera)) if pcgs_fuera else 0.0

    # 2. Cohesión y Densidad Estructural
    densidad_banda = nx.density(subgrafo_banda)
    clustering_banda = nx.average_clustering(subgrafo_banda) if len(subgrafo_banda.nodes) > 2 else 0.0
    
    # 3. Conectividad
    es_conexo = nx.is_connected(subgrafo_banda)
    num_componentes = nx.number_connected_components(subgrafo_banda)

    return {
        "tamano_banda": len(nodos_banda_validos),
        "pcg_promedio_banda": round(avg_pcg_banda, 3),
        "pcg_promedio_resto_red": round(avg_pcg_grafo, 3),
        "delta_riesgo_pcg": round(avg_pcg_banda - avg_pcg_grafo, 3),
        "densidad_interna": round(densidad_banda, 3),
        "clustering_promedio": round(clustering_banda, 3),
        "subgrafo_conexo": es_conexo,
        "num_componentes_internas": num_componentes
    }

def analizar_interdiccion_desarticulacion(grafo: nx.Graph, nodos_banda: List[int]) -> List[Dict[str, Any]]:
    """
    Análisis de Interdicción y Persecución Táctica (Network Interdiction):
    Simula la remoción individual de cada miembro de la banda para identificar 
    el Blanco de Alto Impacto (HVT - High Value Target) cuya detención fragmenta o debilita más la red.
    """
    nodos_banda_validos = [n for n in nodos_banda if n in grafo.nodes]
    if len(nodos_banda_validos) <= 1:
        return []

    subgrafo_original = grafo.subgraph(nodos_banda_validos).copy()
    eficiencia_base = nx.global_efficiency(subgrafo_original) if len(subgrafo_original.nodes) > 1 else 0.0

    ranking_desarticulacion = []

    for target in nodos_banda_validos:
        # Simular captura / remoción del nodo
        sub_reducido = subgrafo_original.copy()
        sub_reducido.remove_node(target)

        # Medir impacto en conectividad
        eficiencia_nueva = nx.global_efficiency(sub_reducido) if len(sub_reducido.nodes) > 1 else 0.0
        caida_eficiencia = (eficiencia_base - eficiencia_nueva) / eficiencia_base if eficiencia_base > 0 else 0.0
        componentes_aisladas = nx.number_connected_components(sub_reducido)
        
        # Centralidad de intermediación
        betweenness = nx.betweenness_centrality(subgrafo_original).get(target, 0.0)
        pcg_target = grafo.nodes[target].get('pcg', 0.5)

        # Puntaje táctico compuesto de prioridad de detención
        score_prioridad = (0.5 * caida_eficiencia) + (0.3 * betweenness) + (0.2 * (pcg_target / 1.0))

        ranking_desarticulacion.append({
            "id_sospechoso": target,
            "pcg": pcg_target,
            "caida_conectividad_porcentual": round(caida_eficiencia * 100, 2),
            "componentes_desconectadas": componentes_aisladas,
            "betweenness_centrality": round(betweenness, 4),
            "score_prioridad_tactica": round(score_prioridad, 3)
        })

    # Ordenar de mayor a menor impacto de desarticulación
    ranking_desarticulacion.sort(key=lambda x: x["score_prioridad_tactica"], reverse=True)
    return ranking_desarticulacion
