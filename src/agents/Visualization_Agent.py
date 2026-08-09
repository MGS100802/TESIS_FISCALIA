import os
import matplotlib.pyplot as plt
import networkx as nx

class VisualizationAgent:
    def __init__(self, output_dir="data/graficos_resultados"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
    def graficar_red_criminal(self, grafo: nx.Graph, nodos_banda: list, nodo_raiz, nombre_caso: str):
        """
        Genera un gráfico de la red criminal resaltando los nodos seleccionados por el optimizador.
        """
        if not grafo or len(grafo.nodes) == 0:
            print("[VisualizationAgent] Advertencia: El grafo está vacío. No se puede generar el gráfico.")
            return
        plt.figure(figsize=(10, 8))

        pos = nx.spring_layout(grafo, seed=42)  # Posiciones de los nodos

        nodos_normales = [n for n in grafo.nodes if n not in nodos_banda and n != nodo_raiz]
        nodos_en_banda = [n for n in nodos_banda if n != nodo_raiz]

        nx.draw_networkx_nodes(grafo, pos, nodelist=nodos_normales, node_color='lightblue', node_size=300, label='Nodos Normales')
        if nodo_raiz in grafo.nodes:
            nx.draw_networkx_nodes(grafo, pos, nodelist=[nodo_raiz], node_color='red', node_size=500, label='Nodo Raíz')
        if nodos_en_banda:
            nx.draw_networkx_nodes(grafo, pos, nodelist=nodos_en_banda, node_color='orange', node_size=400, label='Nodos en Banda')

        nx.draw_networkx_edges(grafo, pos, alpha=0.5, width= 1.5, edge_color = 'gray')

        nx.draw_networkx_labels(grafo, pos, font_size=9, font_family="sans-serif", font_color='black')

        plt.title(f"Red Criminal - Caso: {nombre_caso}", fontsize=14)
        plt.axis('off')
        plt.legend(loc='upper right')

        path_grafico = os.path.join(self.output_dir, f"grafo_{nombre_caso}.png")
        plt.savefig(path_grafico, format='png', dpi=300)
        plt.close()

        print(f"[VisualizationAgent] Gráfico de la red criminal generado y guardado en: {path_grafico}")
