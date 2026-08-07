import os
from pathlib import Path
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

class ExplanationAgent:
    def __init__(self, data_dir="reportes"):
        self.data_dir = data_dir
        self.client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_API_KEY"))

    def generate_explanation(self, nombre_caso: str, resumen_caso: str, nodos_banda: list, ruts_raiz: list):
        """
        Utiliza Gemini para redactar un informe forense y de inteligencia criminal 
        formal basado en los resultados de la optimización matemática.
        """
        print(f"[ExplanationAgent] Redactando informe fiscal para el caso: {nombre_caso}...")

        prompt = f"""
        Eres un asesor experto en inteligencia criminal y fiscalía. A partir de los resultados del modelo matemático de optimización de redes criminales (StRAM/Gurobi), redacta un **Informe de Inteligencia y Propuesta de Persecución Penal** formal para el fiscal a cargo.

        DATOS DEL CASO:
        - Nombre del Caso: {nombre_caso}
        - Resumen Forense Inicial: {resumen_caso}
        - Blancos Clave / Objetivos Principales (Nodos Raíz): {ruts_raiz}
        - Integrantes de la Banda Criminal Detectados por el Algoritmo (RUTs/IDs): {nodos_banda}

        El informe debe estructurarse estrictamente con las siguientes secciones en formato profesional:
        1. ANTECEDENTES Y MARCO TÁCTICO: Breve síntesis del caso.
        2. ANÁLISIS DE RED Y RESULTADOS MATEMÁTICOS: Explicación de cómo el modelo detectó esta estructura de la banda a partir de los blancos clave.
        3. IDENTIFICACIÓN DE LOS IMPLICADOS: Detalle de los miembros detectados en la red criminal.
        4. CONCLUSIONES Y RECOMENDACIONES INVESTIGATIVAS: Propuesta de diligencias (órdenes de entrada y registro, interceptaciones, etc.) para el fiscal.
        """
        
        try:
            response = self.client.models.generate_content(
                model = 'gemini-3.1-flash-lite',
                contents = prompt)
            informe_fiscal = response.contents[0].text

            archivo_salida = os.path.join(self.data_dir, f"informe_fiscal_{nombre_caso}.txt")
            with open(archivo_salida, "w", encoding="utf-8") as f:
                f.write(informe_fiscal)
            print(f"[ExplanationAgent] Informe fiscal generado exitosamente para el caso: {nombre_caso}.")
            return informe_fiscal
        except Exception as e:
            print(f"[ExplanationAgent] Error al generar el informe fiscal: {e}")
            return None
