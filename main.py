import sys
from src.graph.interactive_workflow import InteractiveCriminalOrchestrator
from src.graph.workflow import CriminalInvestigationWorkflow

def main():
    print("\n" + "="*75)
    print(" SISTEMA MULTI-AGENTE AUTONOMO DE INTELIGENCIA CRIMINAL - FISCALIA")
    print(" TESIS DE GRADO - MINISTERIO PUBLICO DE CHILE")
    print("="*75)
    print(" Seleccione el modo de ejecucion:")
    print("   [1] Copiloto HeredIA (Chat Interactivo con LLM / LangGraph) [PREDETERMINADO]")
    print("   [2] Pipeline Autonomo en Lote (Batch tradicional desatendido)")
    print("="*75)
    
    opcion = input("Ingrese opcion [1/2] (Presione Enter para Copiloto HeredIA): ").strip()
    
    if opcion == "2":
        print("\n>>> Iniciando Workflow 100% Autonomo en Lote...")
        pipeline = CriminalInvestigationWorkflow(data_dir="data")
        pipeline.ejecutar_pipeline()
    else:
        orquestador = InteractiveCriminalOrchestrator(data_dir="data")
        orquestador.iniciar_chat_interactivo()

if __name__ == "__main__":
    main()