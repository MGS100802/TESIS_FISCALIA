import os
import matplotlib.pyplot as plt
import networkx as nx

class VisualizationAgent:
    def __init__(self, output_dir="data/graficos_resultados"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
    def graficar_red_criminal(self, grafo: nx.Graph, nodos_banda: list, nodo_raiz, nombre_caso: str, nivel: int = None):
        """
        Genera un gráfico de la red criminal resaltando los nodos seleccionados por el optimizador StPro.
        Si se especifica nivel, se indica en el título y en el nombre del archivo.
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
            nx.draw_networkx_nodes(grafo, pos, nodelist=[nodo_raiz], node_color='red', node_size=500, label='Nodo Raíz (Planificador)')
        if nodos_en_banda:
            nx.draw_networkx_nodes(grafo, pos, nodelist=nodos_en_banda, node_color='orange', node_size=400, label='Célula Banda (StPro)')

        nx.draw_networkx_edges(grafo, pos, alpha=0.5, width=1.5, edge_color='gray')
        nx.draw_networkx_labels(grafo, pos, font_size=9, font_family="sans-serif", font_color='black')

        sufijo_titulo = f" [Nivel {nivel}]" if nivel is not None else ""
        plt.title(f"Red Criminal{sufijo_titulo} - Caso: {nombre_caso}", fontsize=14)
        plt.axis('off')
        plt.legend(loc='upper right')

        nombre_archivo = f"grafo_{nombre_caso}_nivel_{nivel}.png" if nivel is not None else f"grafo_{nombre_caso}.png"
        path_grafico = os.path.join(self.output_dir, nombre_archivo)
        plt.savefig(path_grafico, format='png', dpi=300)
        plt.close()

        # También guardar como grafo general si es la ejecución principal
        if nivel is not None:
            path_general = os.path.join(self.output_dir, f"grafo_{nombre_caso}.png")
            try:
                import shutil
                shutil.copyfile(path_grafico, path_general)
            except Exception:
                pass

        print(f"[VisualizationAgent] Gráfico de la red criminal generado y guardado en: {path_grafico}")

    def graficar_comparativa_multinivel(self, resultados_niveles: dict, nombre_caso: str):
        """
        Genera un panel comparativo con los grafos de Nivel 1, 2 y 3.
        """
        niveles_disponibles = sorted(list(resultados_niveles.keys()))
        if not niveles_disponibles:
            return

        fig, axes = plt.subplots(1, len(niveles_disponibles), figsize=(7 * len(niveles_disponibles), 6))
        if len(niveles_disponibles) == 1:
            axes = [axes]

        for idx, nivel in enumerate(niveles_disponibles):
            ax = axes[idx]
            datos = resultados_niveles[nivel]
            G = datos.get("grafo")
            banda = datos.get("nodos_banda", [])
            raiz = datos.get("raiz")

            if not G or len(G.nodes) == 0:
                ax.set_title(f"Nivel {nivel} (Sin datos)")
                continue

            pos = nx.spring_layout(G, seed=42)
            normales = [n for n in G.nodes if n not in banda and n != raiz]
            en_banda = [n for n in banda if n != raiz]

            nx.draw_networkx_nodes(G, pos, nodelist=normales, node_color='lightblue', node_size=250, ax=ax)
            if en_banda:
                nx.draw_networkx_nodes(G, pos, nodelist=en_banda, node_color='orange', node_size=380, ax=ax)
            if raiz in G.nodes:
                nx.draw_networkx_nodes(G, pos, nodelist=[raiz], node_color='red', node_size=480, ax=ax)

            nx.draw_networkx_edges(G, pos, alpha=0.4, edge_color='gray', ax=ax)
            nx.draw_networkx_labels(G, pos, font_size=8, font_color='black', ax=ax)

            ax.set_title(f"Nivel {nivel} ({len(G.nodes)} nodos | {len(banda)} en banda)", fontsize=11, fontweight='bold')
            ax.axis('off')

        plt.suptitle(f"Evolución Multinivel de Red Criminal - Caso: {nombre_caso}", fontsize=14)
        path_salida = os.path.join(self.output_dir, f"comparativa_niveles_{nombre_caso}.png")
        plt.tight_layout()
        plt.savefig(path_salida, dpi=300)
        plt.close()
        print(f"[VisualizationAgent] Gráfico comparativo multinivel guardado en: {path_salida}")
