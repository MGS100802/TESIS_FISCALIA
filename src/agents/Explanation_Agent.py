import os
import json
from google import genai
from dotenv import load_dotenv
from typing import Optional, Dict, Any, List

load_dotenv()

class ExplanationAgent:
    def __init__(self, data_dir="data/informes_fiscalia"):
        self.data_dir = data_dir
        self.client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_API_KEY"))
        os.makedirs(self.data_dir, exist_ok=True)

    def generate_explanation(
        self, 
        nombre_caso: str, 
        resumen_caso: str, 
        nodos_banda: list, 
        ruts_raiz: list,
        diagnostico_auditoria: Optional[Dict[str, Any]] = None,
        reporte_poda: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Utiliza Gemini para redactar un informe forense y de inteligencia criminal 
        formal basado en los resultados de la optimización matemática y auditoría táctica (HVT).
        """
        print(f"[ExplanationAgent] Redactando informe fiscal para el caso: {nombre_caso}...")

        auditoria_str = json.dumps(diagnostico_auditoria, indent=2, ensure_ascii=False) if diagnostico_auditoria else "No disponible."
        poda_str = json.dumps(reporte_poda, indent=2, ensure_ascii=False) if reporte_poda else "No disponible."

        prompt = f"""
        Eres un asesor experto en inteligencia criminal y derecho procesal penal del Ministerio Público / Fiscalía.
        A partir de los resultados de la Arquitectura Multi-Agente (Ingesta, Poda Criminológica, Optimización Matemática StRAM/Gurobi y Auditoría de Red), redacta un **Informe de Inteligencia y Propuesta de Persecución Penal** formal para el fiscal adjunto a cargo de la causa.

        DATOS DEL CASO Y MODELADO:
        - Nombre del Caso / RUC: {nombre_caso}
        - Resumen Forense Inicial: {resumen_caso}
        - Blancos Clave Iniciales (Nodos Raíz): {ruts_raiz}
        - Integrantes de la Banda Criminal Detectados por el Algoritmo (RUTs/IDs): {nodos_banda}
        - Reporte de Poda y Filtrado Criminológico:
        {poda_str}
        - Diagnóstico de Auditoría e Interdicción Táctica (HVT):
        {auditoria_str}

        El informe debe estructurarse estrictamente con las siguientes secciones en formato profesional (Markdown con redacción jurídica formal):
        1. ANTECEDENTES Y SÍNTESIS DE LA INVESTIGACIÓN: Síntesis de los hechos y tipología penal.
        2. ANÁLISIS DE RED Y METODOLOGÍA MATEMÁTICA: Justificación de cómo la optimización aisló a la estructura criminal y el criterio de poda criminológica aplicado.
        3. ESTRUCTURA Y ROLES DE LA ORGANIZACIÓN CRIMINAL: Detalle de los implicados detectados, su nivel de riesgo/propensión y roles probables.
        4. ESTRATEGIA DE DESARTICULACIÓN E INTERDICCIÓN TÁCTICA: Análisis del Blanco de Alto Impacto (HVT - High Value Target) y cómo su captura fragmenta la organización.
        5. SOLICITUD DE DILIGENCIAS INVESTIGATIVAS AL FISCAL: Propuesta priorizada de medidas intrusivas (órdenes de detención, entrada y registro, interceptación telefónica, incautación de bienes).
        """
        
        try:
            response = self.client.models.generate_content(
                model='gemini-3.1-flash-lite',
                contents=prompt
            )
            informe_fiscal = response.text

            archivo_salida = os.path.join(self.data_dir, f"informe_fiscal_{nombre_caso}.md")
            with open(archivo_salida, "w", encoding="utf-8") as f:
                f.write(informe_fiscal)
            print(f"[ExplanationAgent] Informe fiscal formal generado exitosamente en: {archivo_salida}")
            return informe_fiscal
        except Exception as e:
            print(f"[ExplanationAgent] Error al generar el informe fiscal: {e}")
            return None
