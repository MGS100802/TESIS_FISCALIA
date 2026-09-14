import os
import sys
from pathlib import Path
import streamlit as st
import pandas as pd
from PIL import Image

# Configurar salida UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Importar el orquestador interactivo de demostración
from demo_orquestador_interactivo import InteractiveOrchestrator, HAS_GEMINI_KEY

# Configuración de Página de Streamlit (Sin Emojis)
st.set_page_config(
    page_title="Fiscalía de Chile - Sistema HeredIA",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos Institucionales CSS
st.markdown("""
<style>
    /* Paleta Institucional Fiscalía de Chile */
    :root {
        --primary-color: #1b365d;
        --secondary-color: #a6192e;
        --accent-gold: #c69214;
        --bg-card: #f8f9fa;
    }
    
    .main-header {
        background: linear-gradient(135deg, #1b365d 0%, #0d1b2a 100%);
        color: white;
        padding: 22px 28px;
        border-radius: 8px;
        margin-bottom: 22px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border-left: 6px solid #a6192e;
    }
    .main-header h1 {
        margin: 0;
        font-size: 24px;
        font-weight: 700;
        letter-spacing: 0.5px;
        color: #ffffff !important;
        text-transform: uppercase;
    }
    .main-header p {
        margin: 6px 0 0 0;
        font-size: 14px;
        color: #cbd5e1;
    }
    
    .metric-box {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 14px 18px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        border-top: 3px solid #1b365d;
    }
    .metric-title {
        font-size: 11px;
        text-transform: uppercase;
        color: #64748b;
        font-weight: 700;
        margin-bottom: 4px;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 19px;
        font-weight: 700;
        color: #1b365d;
    }
    .metric-hvt {
        color: #a6192e !important;
        font-weight: 800;
    }
    
    .badge-status {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-online {
        background-color: #dcfce7;
        color: #166534;
        border: 1px solid #bbf7d0;
    }
    .badge-level {
        background-color: #e0f2fe;
        color: #0369a1;
        border: 1px solid #bae6fd;
    }
    
    .agent-pill {
        display: inline-block;
        background: #f8fafc;
        border: 1px solid #cbd5e1;
        padding: 4px 9px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        margin-right: 4px;
        margin-bottom: 5px;
        color: #334155;
    }
    
    .stButton>button {
        border-radius: 4px;
        font-weight: 600;
        transition: all 0.2s;
    }
</style>
""", unsafe_allow_html=True)

# Inicialización de Sesión
if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = InteractiveOrchestrator(data_dir="data")

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {
            "role": "assistant",
            "content": (
                "**SISTEMA DE INTELIGENCIA CRIMINAL HEREDIA** | *Ministerio Público / Fiscalía de Chile*\n\n"
                "El sistema se encuentra operativo para la ingesta de partes policiales, resolución de modelos matemáticos StPro (Gurobi), "
                "identificación de Blancos de Alto Impacto (HVT) y emisión de informes periciales formales.\n\n"
                "Indique la diligencia investigativa o consulta que desea realizar."
            )
        }
    ]

orchestrator: InteractiveOrchestrator = st.session_state.orchestrator
state = orchestrator.state

# Actualizar lista de PDFs si se han agregado
ruta_reportes = Path(orchestrator.data_dir) / "reportes"
if ruta_reportes.exists():
    pdfs_actuales = [str(p) for p in ruta_reportes.glob("*.pdf")]
    state["pdf_list"] = pdfs_actuales
    if pdfs_actuales:
        if not state.get("current_pdf"):
            orchestrator.cargar_caso(pdfs_actuales[0])
        elif not state.get("ruts_involucrados"):
            orchestrator.cargar_caso(state.get("current_pdf"))

# ==========================================
# BARRA LATERAL (SIDEBAR)
# ==========================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/d/d7/Logotipo_Fiscal%C3%ADa_-_Ministerio_P%C3%BAblico_de_Chile.svg?utm_source=es.wikipedia.org&utm_campaign=index&utm_content=original", width= 180)
    st.markdown("### FISCALÍA DE CHILE")
    st.caption("Unidad de Análisis Criminal y Focos Investigativos")
    
    st.divider()
    
    # Selector de Caso Activo
    st.markdown("#### CASO EN INVESTIGACIÓN")
    pdfs = state.get("pdf_list", [])
    if pdfs:
        nombres_casos = [Path(p).stem for p in pdfs]
        caso_actual_idx = 0
        if state.get("nombre_caso") in nombres_casos:
            caso_actual_idx = nombres_casos.index(state.get("nombre_caso"))
        
        seleccion = st.selectbox(
            "Seleccionar expediente policial:",
            options=range(len(nombres_casos)),
            format_func=lambda x: nombres_casos[x],
            index=caso_actual_idx
        )
        if pdfs[seleccion] != state.get("current_pdf"):
            orchestrator.cargar_caso(pdfs[seleccion])
            st.rerun()
    else:
        st.warning("No se registran partes policiales en la carpeta de datos.")

    # Carga de nuevo Parte Policial PDF
    st.markdown("#### INGESTA DE PARTE POLICIAL (PDF)")
    uploaded_file = st.file_uploader("Cargar parte policial en formato PDF", type=["pdf"])
    if uploaded_file is not None:
        save_path = Path("data") / "reportes" / uploaded_file.name
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Archivo '{uploaded_file.name}' ingresado al sistema.")
        orchestrator._inicializar_reportes()
        st.rerun()

    st.divider()

    # Ejecución Rápida por Niveles
    st.markdown("#### EJECUCIÓN RÁPIDA POR NIVELES")
    
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("[ Nivel 1 ] 1 Salto", use_container_width=True):
            with st.spinner("Ejecutando optimización en Nivel 1..."):
                res = orchestrator.tool_pipeline_completo(nivel=1)
                st.session_state.chat_messages.append({"role": "user", "content": "Ejecutar pipeline completo en Nivel 1"})
                st.session_state.chat_messages.append({"role": "assistant", "content": res})
                st.rerun()
                
        if st.button("[ Nivel 2 ] 2 Saltos", use_container_width=True):
            with st.spinner("Ejecutando optimización en Nivel 2..."):
                res = orchestrator.tool_pipeline_completo(nivel=2)
                st.session_state.chat_messages.append({"role": "user", "content": "Ejecutar pipeline completo en Nivel 2"})
                st.session_state.chat_messages.append({"role": "assistant", "content": res})
                st.rerun()

    with col_b2:
        if st.button("[ Nivel 3 ] 3 Saltos", use_container_width=True):
            with st.spinner("Ejecutando optimización en Nivel 3..."):
                res = orchestrator.tool_pipeline_completo(nivel=3)
                st.session_state.chat_messages.append({"role": "user", "content": "Ejecutar pipeline completo en Nivel 3"})
                st.session_state.chat_messages.append({"role": "assistant", "content": res})
                st.rerun()

        if st.button("[ Multinivel ] 1, 2 y 3", use_container_width=True):
            with st.spinner("Ejecutando análisis multinivel..."):
                res = orchestrator.tool_analisis_multinivel([1, 2, 3])
                st.session_state.chat_messages.append({"role": "user", "content": "Ejecutar análisis comparativo multinivel (1, 2 y 3)"})
                st.session_state.chat_messages.append({"role": "assistant", "content": res})
                st.rerun()

    if st.button("EJECUTAR LOTE (BATCH - NIVEL 2)", use_container_width=True, type="primary"):
        with st.spinner("Procesando lote completo en Nivel 2..."):
            res = orchestrator.tool_pipeline_todos_los_archivos(nivel=2)
            st.session_state.chat_messages.append({"role": "user", "content": "Ejecutar procesamiento en lote para todos los expedientes en Nivel 2"})
            st.session_state.chat_messages.append({"role": "assistant", "content": res})
            st.rerun()

    if st.button("EJECUTAR LOTE (BATCH - NIVEL 3)", use_container_width=True):
        with st.spinner("Procesando lote completo en Nivel 3..."):
            res = orchestrator.tool_pipeline_todos_los_archivos(nivel=3)
            st.session_state.chat_messages.append({"role": "user", "content": "Ejecutar procesamiento en lote para todos los expedientes en Nivel 3"})
            st.session_state.chat_messages.append({"role": "assistant", "content": res})
            st.rerun()

    st.divider()

    # Estado del Ecosistema Multi-Agente
    st.markdown("#### ARQUITECTURA MULTI-AGENTE")
    st.markdown("""
    <div>
        <span class="agent-pill">LangGraph Orchestrator</span>
        <span class="agent-pill">IngestionAgent</span>
        <span class="agent-pill">LevelFilterAgent</span>
        <span class="agent-pill">StPro / Gurobi</span>
        <span class="agent-pill">AuditorAgent</span>
        <span class="agent-pill">VisualizationAgent</span>
        <span class="agent-pill">ExplanationAgent</span>
    </div>
    """, unsafe_allow_html=True)
    
    if HAS_GEMINI_KEY:
        st.markdown("<span class='badge-status badge-online'>ESTADO: Gemini 2.5 Flash Habilitado</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span class='badge-status badge-level'>ESTADO: Modo Local / Predictivo</span>", unsafe_allow_html=True)

# ==========================================
# CABECERA PRINCIPAL Y MÉTRICAS
# ==========================================
st.markdown("""
<div class="main-header">
    <h1>Ministerio Público | Fiscalía de Chile</h1>
    <p>Plataforma de Inteligencia Criminal y Desarticulación de Organizaciones Delictivas (HeredIA)</p>
</div>
""", unsafe_allow_html=True)

# Recopilación de métricas actuales
caso_nombre = state.get("nombre_caso", "No seleccionado")
ruts_raiz = state.get("ruts_involucrados", [])
raiz_str = ", ".join([str(r) for r in ruts_raiz]) if ruts_raiz else "Pendiente"
tamano_est = state.get("tamano_grupo", 0)
banda_nodos = state.get("nodos_banda", [])
banda_len = len(banda_nodos) if banda_nodos else 0
nivel_act = state.get("nivel_actual", "No definido")

diag = state.get("diagnostico_auditoria") or {}
hvt_info = diag.get("hvt_prioritario", {}) if isinstance(diag, dict) else {}
hvt_nodo = hvt_info.get("id_sospechoso") if isinstance(hvt_info, dict) else (hvt_info if hvt_info else "No determinado")

# Barra de Métricas Superiores
col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
with col_m1:
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-title">EXPEDIENTE POLICIAL</div>
        <div class="metric-value">{caso_nombre}</div>
    </div>
    """, unsafe_allow_html=True)

with col_m2:
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-title">IMPUTADOS RAÍZ</div>
        <div class="metric-value">Sujetos {raiz_str}</div>
    </div>
    """, unsafe_allow_html=True)

with col_m3:
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-title">CÉLULA AISLADA (StPro)</div>
        <div class="metric-value">{banda_len} miembros</div>
    </div>
    """, unsafe_allow_html=True)

with col_m4:
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-title">BLANCO PRIORITARIO (HVT)</div>
        <div class="metric-value metric-hvt">Nodo {hvt_nodo}</div>
    </div>
    """, unsafe_allow_html=True)

with col_m5:
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-title">PROFUNDIDAD TOPOLÓGICA</div>
        <div class="metric-value">Nivel {nivel_act}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# PESTAÑAS (TABS) DEL SISTEMA
# ==========================================
tab_chat, tab_grafo, tab_multi, tab_informe, tab_lote = st.tabs([
    "Copiloto HeredIA (Asistente Interactivo)",
    "Red Criminal & Blanco HVT",
    "Análisis Comparativo Multinivel",
    "Informe Pericial Formal (Tribunal)",
    "Procesamiento Automatizado en Lote"
])

# ------------------------------------------
# TAB 1: COPILOTO HEREDIA (CHAT)
# ------------------------------------------
with tab_chat:
    st.markdown("#### Interacción en Lenguaje Natural con Copiloto HeredIA")
    st.caption("Consulte sobre sospechosos, solicite optimizaciones por nivel o emita informes formales.")
    
    # Sugerencias rápidas (Quick Prompt Pills)
    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    with col_p1:
        if st.button("[ Consultar Imputados y Delitos ]", use_container_width=True):
            user_msg = "¿Quiénes son los sospechosos y de qué trata el parte policial?"
            st.session_state.chat_messages.append({"role": "user", "content": user_msg})
            with st.spinner("Consultando Copiloto HeredIA..."):
                resp = orchestrator.procesar_mensaje_usuario(user_msg)
                st.session_state.chat_messages.append({"role": "assistant", "content": resp})
            st.rerun()
            
    with col_p2:
        if st.button("[ Optimizar Subred en Nivel 2 ]", use_container_width=True):
            user_msg = "Ejecuta la optimizacion en nivel 2 para aislar la banda criminal"
            st.session_state.chat_messages.append({"role": "user", "content": user_msg})
            with st.spinner("Ejecutando modelo matemático StPro..."):
                resp = orchestrator.procesar_mensaje_usuario(user_msg)
                st.session_state.chat_messages.append({"role": "assistant", "content": resp})
            st.rerun()

    with col_p3:
        if st.button("[ Evaluar Blanco Prioritario HVT ]", use_container_width=True):
            user_msg = "¿Cuál es el blanco de alto impacto HVT y por qué?"
            st.session_state.chat_messages.append({"role": "user", "content": user_msg})
            with st.spinner("Auditando red criminal..."):
                resp = orchestrator.procesar_mensaje_usuario(user_msg)
                st.session_state.chat_messages.append({"role": "assistant", "content": resp})
            st.rerun()

    with col_p4:
        if st.button("[ Redactar Informe Pericial ]", use_container_width=True):
            user_msg = "Genera el informe formal para el Tribunal"
            st.session_state.chat_messages.append({"role": "user", "content": user_msg})
            with st.spinner("Redactando informe jurídico..."):
                resp = orchestrator.procesar_mensaje_usuario(user_msg)
                st.session_state.chat_messages.append({"role": "assistant", "content": resp})
            st.rerun()

    # Contenedor de Chat
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Entrada de Chat
    if prompt := st.chat_input("Escriba su consulta o instrucción para el Copiloto HeredIA..."):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Copiloto HeredIA procesando solicitud..."):
                respuesta = orchestrator.procesar_mensaje_usuario(prompt)
                st.markdown(respuesta)
                st.session_state.chat_messages.append({"role": "assistant", "content": respuesta})
        st.rerun()

# ------------------------------------------
# TAB 2: RED CRIMINAL & BLANCO HVT
# ------------------------------------------
with tab_grafo:
    st.markdown(f"#### Estructura de Red Criminal - Caso: {caso_nombre}")
    
    col_g1, col_g2 = st.columns([3, 2])
    
    with col_g1:
        # Buscar gráfico generado
        archivos_posibles = [
            f"grafo_{caso_nombre}_nivel_{nivel_act}.png",
            f"grafo_{caso_nombre}.png",
            f"comparativa_niveles_{caso_nombre}.png"
        ]
        
        img_path = None
        for arch in archivos_posibles:
            p = Path("data") / "graficos_resultados" / arch
            if p.exists():
                img_path = p
                break
                
        if img_path and img_path.exists():
            img = Image.open(img_path)
            st.image(img, caption=f"Diagrama de Red Criminal ({img_path.name})", use_container_width=True)
        else:
            st.info("No se registra visualización gráfica generada para este caso. Puede generarla presionando el botón inferior.")
            if st.button("Generar Visualización de Red", key="btn_gen_vis"):
                with st.spinner("Generando diagrama de red criminal..."):
                    orchestrator.tool_visualizacion()
                    st.rerun()

    with col_g2:
        st.markdown("##### Blanco de Alto Impacto (HVT)")
        if hvt_nodo != "No determinado":
            st.success(f"**Blanco Prioritario Identificado:** Sujeto / Nodo **{hvt_nodo}**")
            st.markdown(f"""
            - **Fundamento Táctico:** La neutralización y detención prioritaria del **Nodo {hvt_nodo}** fractura la topología de la organización delictiva, aislando a sus células operativas del núcleo directivo.
            - **Nodos Integrantes de la Célula:** {banda_nodos}
            - **Profundidad de Búsqueda:** Nivel {nivel_act}
            """)
        else:
            st.warning("El Blanco HVT aún no ha sido calculado. Ejecute la auditoría o el pipeline completo.")

        st.markdown("##### Miembros de la Célula Delictiva")
        if banda_nodos:
            df_banda = pd.DataFrame({
                "ID Sospechoso": banda_nodos,
                "Rol en Organización": ["Imputado Principal (Raíz)" if str(n) in [str(r) for r in ruts_raiz] else ("Blanco HVT" if str(n) == str(hvt_nodo) else "Operador / Enlace") for n in banda_nodos],
                "Prioridad Procesal": ["Alta (Orden de Detención)" if str(n) in [str(r) for r in ruts_raiz] or str(n) == str(hvt_nodo) else "Media (Seguimiento / Allanamiento)" for n in banda_nodos]
            })
            st.dataframe(df_banda, use_container_width=True, hide_index=True)
        else:
            st.info("No se registran miembros aislados.")

# ------------------------------------------
# TAB 3: COMPARATIVA MULTINIVEL
# ------------------------------------------
with tab_multi:
    st.markdown(f"#### Análisis Comparativo Multinivel (Niveles 1, 2 y 3) - {caso_nombre}")
    st.caption("Comparación de la expansión de la red criminal a 1, 2 y 3 saltos topológicos desde el imputado raíz.")
    
    col_mc1, col_mc2 = st.columns([1, 4])
    with col_mc1:
        if st.button("Ejecutar Comparativa (Niveles 1, 2 y 3)", key="btn_multi_run", type="primary", use_container_width=True):
            with st.spinner("Calculando StPro para Niveles 1, 2 y 3..."):
                res = orchestrator.tool_analisis_multinivel([1, 2, 3])
                st.session_state.chat_messages.append({"role": "assistant", "content": res})
                st.rerun()

    path_comp = Path("data") / "graficos_resultados" / f"comparativa_niveles_{caso_nombre}.png"
    if path_comp.exists():
        img_comp = Image.open(path_comp)
        st.image(img_comp, caption=f"Comparativa Topológica Multinivel - Caso: {caso_nombre}", use_container_width=True)
    else:
        st.info("Presione 'Ejecutar Comparativa' para generar los diagramas en paralelo de los 3 niveles.")

    # Tabla comparativa conceptual
    st.markdown("##### Resumen Conceptual de Niveles Topológicos")
    df_niveles = pd.DataFrame({
        "Nivel (k-hops)": ["Nivel 1", "Nivel 2 (Recomendado)", "Nivel 3"],
        "Radio Topológico": ["1 salto directo", "2 saltos de conexión", "3 saltos de conexión"],
        "Alcance Investigativo": ["Contactos inmediatos y coautores directos del parte", "Célula operativa local y testaferros cercanos", "Estructura criminal expandida, financistas y proveedores"],
        "Utilidad Procesal": ["Órdenes de detención flagrantes inmediatas", "Formalización por Asociación Ilícita / Lavado de Activos", "Desarticulación macro-estructural de focos delictivos"]
    })
    st.dataframe(df_niveles, use_container_width=True, hide_index=True)

# ------------------------------------------
# TAB 4: INFORME FORENSE (FISCALÍA)
# ------------------------------------------
with tab_informe:
    st.markdown(f"#### Informe Pericial Formal para Ministerio Público - Caso: {caso_nombre}")
    
    path_informe = Path("data") / "informes_fiscalia" / f"informe_forense_{caso_nombre}.txt"
    
    col_inf1, col_inf2 = st.columns([3, 1])
    with col_inf2:
        if st.button("Regenerar Informe Pericial", use_container_width=True):
            with st.spinner("Redactando informe pericial..."):
                res_inf = orchestrator.tool_informe()
                st.success("Informe generado exitosamente.")
                st.rerun()
                
    if path_informe.exists():
        with open(path_informe, "r", encoding="utf-8") as f:
            texto_informe = f.read()
            
        with col_inf2:
            st.download_button(
                label="Descargar Informe Oficial (.txt)",
                data=texto_informe,
                file_name=f"informe_forense_{caso_nombre}.txt",
                mime="text/plain",
                use_container_width=True
            )
            
        st.text_area("Vista previa del Informe:", value=texto_informe, height=450)
    else:
        st.info("Aún no se ha emitido un informe para este caso. Puede generarlo presionando 'Regenerar Informe Pericial'.")

# ------------------------------------------
# TAB 5: PROCESAMIENTO EN LOTE (BATCH)
# ------------------------------------------
with tab_lote:
    st.markdown("#### Procesamiento Multi-Agente en Lote (Todos los Casos)")
    st.caption("Ejecución automatizada y desatendida del análisis de inteligencia criminal para todos los partes policiales en cola.")
    
    col_l1, col_l2, col_l3 = st.columns(3)
    with col_l1:
        if st.button("Ejecutar Lote en Nivel 1", use_container_width=True):
            with st.spinner("Procesando lote en Nivel 1..."):
                res = orchestrator.tool_pipeline_todos_los_archivos(nivel=1)
                st.session_state.chat_messages.append({"role": "assistant", "content": res})
                st.rerun()

    with col_l2:
        if st.button("Ejecutar Lote en Nivel 2", use_container_width=True, type="primary"):
            with st.spinner("Procesando lote en Nivel 2..."):
                res = orchestrator.tool_pipeline_todos_los_archivos(nivel=2)
                st.session_state.chat_messages.append({"role": "assistant", "content": res})
                st.rerun()

    with col_l3:
        if st.button("Ejecutar Lote Multinivel (1, 2 y 3)", use_container_width=True):
            with st.spinner("Procesando lote multinivel..."):
                res = orchestrator.tool_pipeline_todos_los_archivos(nivel="todos")
                st.session_state.chat_messages.append({"role": "assistant", "content": res})
                st.rerun()

    st.markdown("##### Casos en Cola de Procesamiento")
    if pdfs:
        df_cola = pd.DataFrame({
            "N°": range(1, len(pdfs) + 1),
            "Archivo PDF": [Path(p).name for p in pdfs],
            "Identificador Caso": [Path(p).stem for p in pdfs],
            "Informe Forense": ["Generado" if (Path("data") / "informes_fiscalia" / f"informe_forense_{Path(p).stem}.txt").exists() else "Pendiente" for p in pdfs],
            "Cartografía de Red": ["Generado" if any((Path("data") / "graficos_resultados").glob(f"*{Path(p).stem}*.png")) else "Pendiente" for p in pdfs]
        })
        st.dataframe(df_cola, use_container_width=True, hide_index=True)
    else:
        st.warning("No se registran partes policiales en cola.")
