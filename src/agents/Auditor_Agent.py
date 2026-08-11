import networkx as nx
from typing import List, Dict, Any, Optional
from src.utils.metrics import calcular_metricas_red_criminal, analizar_interdiccion_desarticulacion

class AuditorAgent:
    """
    Agente Auditor y Crítico Forense (Reflection / Quality Control).
    
    Evalúa la validez criminológica y matemática de los resultados de optimización (Gurobi):
    - Verifica si la solución no es trivial (más de 1 nodo).
    - Compara el tamaño detectado con el estimado en el parte policial.
    - Evalúa la coherencia de propensión criminal (PCG) del grupo.
    - Genera el ranking táctico de desarticulación criminal (Network Interdiction / HVT).
    """

    def __init__(self, tolerancia_tamano: float = 0.5):
        self.tolerancia_tamano = tolerancia_tamano

    def auditar_solucion(
        self,
        grafo: nx.Graph,
        nodos_banda: List[int],
        nodos_raiz: List[int],
        tamano_estimado_informe: int = 0
    ) -> Dict[str, Any]:
        """
        Realiza la auditoría de la banda criminal detectada y emite un dictamen táctico con HVT.
        """
        n_detectados = len(nodos_banda)
        metricas_red = calcular_metricas_red_criminal(grafo, nodos_banda)
        ranking_interdiccion = analizar_interdiccion_desarticulacion(grafo, nodos_banda)

        diagnostico = {
            "aprobado": True,
            "motivo": "Solución matemáticamente coherente y validada.",
            "accion_sugerida": "CONTINUAR",
            "metricas_red": metricas_red,
            "ranking_interdiccion": ranking_interdiccion,
            "hvt_prioritario": ranking_interdiccion[0] if ranking_interdiccion else None,
            "observaciones": []
        }

        # 1. Validación: Solución trivial o vacía
        if n_detectados <= 1:
            diagnostico["aprobado"] = False
            diagnostico["motivo"] = "La optimización devolvió una solución trivial (<= 1 nodo)."
            diagnostico["accion_sugerida"] = "REINTENTAR_INCREMENTAR_PHI"
            print(f"[AuditorAgent] Alerta: {diagnostico['motivo']} Sugerencia: {diagnostico['accion_sugerida']}")
            return diagnostico

        # 2. Validación: Comparación de tamaño con el reporte policial
        if tamano_estimado_informe > 0:
            diferencia_relativa = abs(n_detectados - tamano_estimado_informe) / tamano_estimado_informe
            if diferencia_relativa > self.tolerancia_tamano:
                msg_tamano = f"Discrepancia de tamaño: {n_detectados} detectados vs {tamano_estimado_informe} en informe policial."
                diagnostico["observaciones"].append(msg_tamano)
                print(f"[AuditorAgent] Advertencia: {msg_tamano}")

        # 3. Validación: Propensión criminal (PCG)
        delta_pcg = metricas_red.get("delta_riesgo_pcg", 0.0)
        if delta_pcg < 0:
            msg_pcg = "El grupo detectado tiene un PCG promedio inferior al resto de la red. Verificar si hay nodos puente de bajo riesgo."
            diagnostico["observaciones"].append(msg_pcg)
            print(f"[AuditorAgent] Observación: {msg_pcg}")

        hvt_id = diagnostico.get('hvt_prioritario', {}).get('id_sospechoso', 'N/A')
        print(f"[AuditorAgent] Auditoría completada con éxito. Blanco de Alto Impacto (HVT): {hvt_id}")
        return diagnostico
