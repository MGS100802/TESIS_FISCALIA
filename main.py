from src.graph.workflow import CriminalInvestigationWorkflow

if __name__ == "__main__":
    # Inicializar y ejecutar el workflow 100% autónomo
    pipeline = CriminalInvestigationWorkflow(data_dir="data")
    pipeline.ejecutar_pipeline()