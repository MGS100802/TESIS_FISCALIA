import os
from pathlib import Path
from fpdf import FPDF
from fpdf.enums import XPos, YPos

class PoliceReportPDFGenerator:
    def __init__(self, output_dir="data/reportes"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_report_1(self):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "MINISTERIO PUBLICO - FISCALIA DE CHILE", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "PARTE POLICIAL N° 2026-08-9901 - SECCION INTELIGENCIA POLICIAL", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        pdf.ln(5)

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, "1. RESUMEN DEL CASO Y TIPOLOGIA DELICTIVA", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        texto_resumen = (
            "Se investiga la operacion de una organizacion criminal dedicada al robo con violencia e intimidacion "
            "y receptacion de vehiculos en la zona norte de la Region Metropolitana. La banda opera de manera "
            "coordinada con mandos de ejecucion directa y redes de proteccion."
        )
        pdf.multi_cell(0, 5, texto_resumen)
        pdf.ln(4)

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, "2. OBJETIVOS PRINCIPALES Y SUJETOS DE INTERES (NODOS RAIZ)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        texto_sospechosos = (
            "Tras vigilancia encubierta e interceptaciones telefonicas, se identifica como lideres estrategicos "
            "y blancos prioritarios a los siguientes imputados:\n"
            "- Blanco Principal 1: Sujeto ID 1 (RUT 1), quien ejerce el liderazgo operativo y coordina las armas.\n"
            "- Blanco Principal 2: Sujeto ID 3 (RUT 3), encargado de la logistica y ocultamiento de especies.\n"
            "Se estima un total de 12 sospechosos vinculados activamente a la estructura criminal."
        )
        pdf.multi_cell(0, 5, texto_sospechosos)
        pdf.ln(4)

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, "3. EVIDENCIA Y METADATOS FORENSES", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        texto_metadatos = (
            "- Armas incautadas: 2 pistolas 9mm y municion.\n"
            "- Vehiculos identificados: 3 SUV con encargo por robo.\n"
            "- Comunas afectadas: Quilicura, Renca y Lampa.\n"
            "- Delitos conexos: Receptacion, porte ilegal de armas y asociacion ilicita."
        )
        pdf.multi_cell(0, 5, texto_metadatos)

        filepath = self.output_dir / "parte_policial_caso_banda_norte.pdf"
        pdf.output(str(filepath))
        print(f"[OK] Parte policial 1 generado en: {filepath}")
        return str(filepath)

    def create_report_2(self):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "MINISTERIO PUBLICO - FISCALIA DE CHILE", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "PARTE POLICIAL N° 2026-08-9902 - UNIDAD DE ANALISIS CRIMINAL", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        pdf.ln(5)

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, "1. RESUMEN DEL CASO Y TIPOLOGIA DELICTIVA", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        texto_resumen = (
            "Investigacion por red de sustraccion y desarme ilicito de vehiculos motorizados. "
            "La agrupacion delictiva distribuye roles entre ejecutores de atracos y acopiadores de piezas."
        )
        pdf.multi_cell(0, 5, texto_resumen)
        pdf.ln(4)

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, "2. OBJETIVOS PRINCIPALES Y SUJETOS DE INTERES", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        texto_sospechosos = (
            "Se individualiza como nodo articulador clave al Sujeto ID 4 (RUT 4) y su colaborador directo Sujeto ID 5 (RUT 5).\n"
            "El grupo comprende un numero estimado de 8 sospechosos directos."
        )
        pdf.multi_cell(0, 5, texto_sospechosos)
        pdf.ln(4)

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, "3. EVIDENCIA Y METADATOS FORENSES", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        texto_metadatos = (
            "- Especies: Autopartes de alta gama e instrumentos de oxicorte.\n"
            "- Comunas afectadas: San Bernardo y El Bosque.\n"
            "- Delitos conexos: Robo con fuerza y receptacion."
        )
        pdf.multi_cell(0, 5, texto_metadatos)

        filepath = self.output_dir / "parte_policial_caso_desarme_vehiculos.pdf"
        pdf.output(str(filepath))
        print(f"[OK] Parte policial 2 generado en: {filepath}")
        return str(filepath)

if __name__ == "__main__":
    gen = PoliceReportPDFGenerator()
    gen.create_report_1()
    gen.create_report_2()
