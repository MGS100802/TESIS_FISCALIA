import os
import json
from pathlib import Path
from pypdf import PdfReader
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

class IngestionAgent:
    def __init__(self, data_dir="data", subcarpeta_reportes="reportes"):
        self.data_dir = data_dir
        self.client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_API_KEY"))
        self.pdf_dir = os.path.join(self.data_dir, subcarpeta_reportes)
        os.makedirs(self.pdf_dir, exist_ok=True)

    def extract_list_of_pdfs(self):
        """
        Extrae la lista de archivos PDF en la carpeta de reportes.
        """
        ruta_carpeta = Path(self.pdf_dir)
        return [str(pdf) for pdf in ruta_carpeta.glob("*.pdf")]

    def extract_process_police_report(self, path_pdf: str, path_txt="data/resumenes_casos/"):
        """
        Lee un reporte policial en PDF, procesa el texto con Gemini, genera el TXT 
        con trazabilidad del caso y retorna los nodos raíz y el tamaño del grupo.
        """
        print(f"[IngestionAgent] Leyendo archivo PDF: {Path(path_pdf).name}...")
        
        try:
            lector = PdfReader(path_pdf)
            report_text = ""
            for page in lector.pages:
                text_page = page.extract_text()
                if text_page:
                    report_text += text_page + "\n"  # CORREGIDO: Se quitó el doble '+'

            if not report_text.strip():
                print(f"[IngestionAgent] No se pudo extraer texto del PDF: {Path(path_pdf).name}.")
                return [], 0
                
            prompt = f"""Eres un analista de inteligencia criminal experto. Analiza el siguiente parte policial y extrae la información 
            exclusivamente en formato JSON estricto con las siguientes claves:
            - "resumen_caso": Breve resumen forense de los hechos.
            - "nodos_raiz": Lista de RUTs o identificadores de los sospechosos principales identificados inicialmente como objetivos o blancos clave.
            - "sospechosos": Lista de objetos con id (entero o RUT), nombre, rol_presunto, propensión criminal estimada (pcg de 1.0 a 10.0 según antecedentes en el texto) y si es nodo_raiz (true/false).
            - "relaciones": Lista de objetos con source, target (basado en los ids/RUTs) y distance (costo o desconfianza de la relación de 0.1 a 5.0 basada en la cercanía descrita).
            - "Numero de sospechosos": Total de sospechosos identificados en el informe, solo en numero integer para luego usarse en StPro
            - "metadatos_utiles": Otra información clave para la investigación (armas incautadas, vehículos, modus operandi, comunas o ubicaciones involucradas).

            Texto del parte policial:
            {report_text}
            """
        
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',  # CORREGIDO: Modelo oficial válido
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )

            response_json = json.loads(response.text)

            ruts_involucrados = [str(rut) for rut in response_json.get("nodos_raiz", [])]
            tamaño_grupo = int(response_json.get("Numero de sospechosos", 0))
            resumen_caso = response_json.get("resumen_caso", "")
            metadatos_utiles = response_json.get("metadatos_utiles", {})

            # Guardar el resumen del caso en el archivo TXT único
            os.makedirs(path_txt, exist_ok=True)
            nombre_caso = Path(path_pdf).stem
            archivo_txt_path = os.path.join(path_txt, f"resumen_{nombre_caso}.txt")
            
            # CORREGIDO: Se abre 'archivo_txt_path' (el archivo) y no 'path_txt' (la carpeta)
            with open(archivo_txt_path, "w", encoding="utf-8") as f:
                f.write(f"Resumen del Caso {nombre_caso}:\n")
                f.write(resumen_caso + "\n\n")
                f.write("Metadatos Útiles:\n")
                if isinstance(metadatos_utiles, dict):
                    for clave, valor in metadatos_utiles.items():
                        f.write(f"- {str(clave).capitalize()}: {valor}\n")
                else:
                    f.write(f"- {metadatos_utiles}\n")
                f.write(f"\n- Número de sospechosos (Tamaño del grupo): {tamaño_grupo}\n")
                f.write(f"- Nodos raíz (RUTs clave): {', '.join(ruts_involucrados)}\n")

            print(f"[IngestionAgent] Resumen del caso '{nombre_caso}' exportado a: {archivo_txt_path}")
            
            return ruts_involucrados, tamaño_grupo  # CORREGIDO: Se eliminó la coma sobrante

        except Exception as e:
            print(f"Error al procesar el reporte policial con Gemini: {e}")
            return [], 0



