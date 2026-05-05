import streamlit as st
import pytesseract
from PIL import Image
import shutil
import re

# --- CONFIGURACIÓN DE MOTOR OCR ---
t_path = shutil.which("tesseract")
if t_path:
    pytesseract.pytesseract.tesseract_cmd = t_path

st.set_page_config(page_title="Radar de Valor Pro", layout="wide")

# --- GESTIÓN DEL ESTADO DEL TEXTO ---
if 'input_datos' not in st.session_state:
    st.session_state['input_datos'] = ""

def limpiar_consola():
    st.session_state['input_datos'] = ""

def extraer_todo(texto):
    def buscar(patron):
        m = re.search(patron, texto, re.IGNORECASE)
        return m.groups() if m else None

    return {
        "ganar_empate": buscar(r"(\d+)\s*\((\d+)%\)\s*Empató o Ganó"),
        "btts": buscar(r"(\d+)\s*\((\d+)%\)\s*Ambos equipos marcaron"),
        "over25": buscar(r"(\d+)\s*\((\d+)%\)\s*Más de 2\.5 goles"),
        "invicta": buscar(r"(\d+)\s*\((\d+)%\)\s*Valla invicta"),
        "goles_c": buscar(r"(\d+\.\d+)\s*Goles convertidos\s*(\d+\.\d+)"),
        "remates_arco": buscar(r"(\d+\.\d+)\s*Remates al arco\s*(\d+\.\d+)"),
        "corners": buscar(r"(\d+\.\d+)\s*Corners\s*(\d+\.\d+)"),
        "tarjetas": buscar(r"(\d+\.\d+)\s*Tarjetas\s*(\d+\.\d+)")
    }

st.title("⚽ Consola de Análisis: Pegar y Borrar")

# --- APARTADO DE TEXTO CON BOTÓN DE BORRADO ---
st.subheader("📋 Datos del Partido")

col_input, col_ctrl = st.columns([5, 1])

with col_ctrl:
    st.write("###") # Espaciador
    if st.button("🗑️ Borrar", use_container_width=True):
        limpiar_consola()
        st.rerun()

with col_input:
    texto_input = st.text_area(
        "Pega aquí el texto de 365Scores:",
        value=st.session_state['input_datos'],
        height=200,
        placeholder="Ej: Todas las competiciones... Últimos 9 partidos...",
        key="campo_texto"
    )
    st.session_state['input_datos'] = texto_input

# --- PROCESAMIENTO ---
if texto_input:
    d = extraer_todo(texto_input)
    
    # Fila 1: Métricas de Mercado
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if d["ganar_empate"]: st.metric("1X (Local)", f"{d['ganar_empate'][1]}%")
    with c2:
        if d["btts"]: st.metric("Ambos Marcan", f"{d['btts'][1]}%")
    with c3:
        if d["over25"]: st.metric("Over 2.5 Goles", f"{d['over25'][1]}%")
    with c4:
        if d["invicta"]: st.metric("Valla Invicta L", f"{d['invicta'][1]}%")

    # Fila 2: Letalidad y Volumen
    st.divider()
    st.subheader("🎯 Eficiencia del Visitante")
    f2_c1, f2_c2, f2_c3 = st.columns(3)

    if d["goles_c"] and d["remates_arco"]:
        # Calculamos letalidad según tus datos (1.91 goles / 5.91 remates al arco)
        letalidad = round(float(d["remates_arco"][1]) / float(d["goles_c"][1]), 2)
        f2_c1.metric("Letalidad", f"{letalidad} tiros/gol")
        f2_c2.metric("Goles Promedio", d["goles_c"][1])
        f2_c3.metric("Remates al Arco", d["remates_arco"][1])

    # Fila 3: Otros Mercados
    st.divider()
    f3_c1, f3_c2 = st.columns(2)
    with f3_c1:
        if d["corners"]:
            total_c = float(d["corners"][0]) + float(d["corners"][1])
            st.write(f"🚩 **Corners Proyectados:** {total_c}")
            st.progress(min(total_c/15, 1.0))
    with f3_c2:
        if d["tarjetas"]:
            total_t = float(d["tarjetas"][0]) + float(d["tarjetas"][1])
            st.write(f"🟨 **Tarjetas Proyectadas:** {total_t}")
            st.progress(min(total_t/8, 1.0))

    # Recomendación Final
    st.divider()
    if d["ganar_empate"] and int(d["ganar_empate"][1]) >= 85:
        st.success(f"🏆 **PICK SUGERIDO:** Doble Oportunidad Local (1X)")
    elif d["over25"] and int(d["over25"][1]) >= 55:
        st.warning("🔥 **PICK SUGERIDO:** Over 2.5 Goles")
    else:
        st.info("⚖️ **ESTADO:** Analizar mercado de Corners o esperar al Live.")
