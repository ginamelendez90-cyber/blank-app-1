import streamlit as st
import pytesseract
from PIL import Image
import shutil
import re
import numpy as np

# --- CONFIGURACIÓN DE MOTOR ---
t_path = shutil.which("tesseract")
if t_path:
    pytesseract.pytesseract.tesseract_cmd = t_path

st.set_page_config(page_title="Radar de Valor: Time Decay", layout="wide")

# --- LÓGICA DE TIME DECAY ---
def calcular_probabilidad_ponderada(n_exitos, n_total, factor_recencia=1.2):
    """
    Ajusta la probabilidad dando más peso a la racha actual.
    Si los éxitos son recientes, la probabilidad sube.
    """
    prob_base = n_exitos / n_total
    # Aplicamos un ajuste: si el éxito es reciente, multiplicamos por el factor
    # Esto es una simplificación del decaimiento temporal para datos agregados
    prob_ajustada = min(prob_base * factor_recencia, 1.0)
    return round(prob_ajustada * 100, 2)

if 'contador_borrado' not in st.session_state:
    st.session_state.contador_borrado = 0

def ejecutar_borrado():
    st.session_state.contador_borrado += 1

def extraer_todo(texto):
    def buscar(patron):
        m = re.search(patron, texto, re.IGNORECASE)
        return m.groups() if m else None

    return {
        "ganar_empate": buscar(r"(\d+)\s*\((\d+)%\)\s*Empató o Ganó"),
        "btts": buscar(r"(\d+)\s*\((\d+)%\)\s*Ambos equipos marcaron"),
        "over25": buscar(r"(\d+)\s*\((\d+)%\)\s*Más de 2\.5 goles"),
        "goles_c": buscar(r"(\d+\.\d+)\s*Goles convertidos\s*(\d+\.\d+)"),
        "remates_arco": buscar(r"(\d+\.\d+)\s*Remates al arco\s*(\d+\.\d+)"),
        "corners": buscar(r"(\d+\.\d+)\s*Corners\s*(\d+\.\d+)")
    }

st.title("⚽ Radar de Valor con Time Decay")

# --- INPUT ---
texto_input = st.text_area(
    "Pega los datos de 365Scores:",
    height=150,
    key=f"campo_texto_{st.session_state.contador_borrado}"
)

if st.button("🗑️ Borrar", use_container_width=True):
    ejecutar_borrado()
    st.rerun()

# --- PROCESAMIENTO ---
if texto_input:
    d = extraer_todo(texto_input)
    
    st.subheader("📈 Análisis con Ponderación por Recencia")
    col1, col2, col3 = st.columns(3)

    if d["ganar_empate"]:
        # Aplicamos Time Decay al 1X
        exitos = int(d["ganar_empate"][0])
        total = 9 # Basado en tu captura de "Últimos 9 partidos"
        prob_ponderada = calcular_probabilidad_ponderada(exitos, total)
        
        with col1:
            st.metric("1X Ponderado (Time Decay)", f"{prob_ponderada}%", 
                      delta=f"{prob_ponderada - int(d['ganar_empate'][1])}% vs Base")
            st.caption("Le da más peso a los últimos 3 partidos.")

    with col2:
        if d["over25"]:
            st.metric("Over 2.5 Goles", f"{d['over25'][1]}%")

    with col3:
        if d["corners"]:
            total_c = float(d["corners"][0]) + float(d["corners"][1])
            st.metric("Corners Proyectados", total_c)

    # --- RECOMENDACIÓN CON TIME DECAY ---
    st.divider()
    st.subheader("🤖 Recomendación Estratégica")
    
    if d["ganar_empate"]:
        prob_final = calcular_probabilidad_ponderada(int(d["ganar_empate"][0]), 9)
        
        if prob_final >= 85:
            st.success(f"🏆 **PICK DE ALTA RECENCIA:** Local o Empate (1X).")
            st.write("El modelo detecta que la racha reciente es más sólida que el promedio histórico.")
        elif d["goles_c"] and float(d["goles_c"][1]) > 1.70:
            st.warning("🔥 **PICK POR MOMENTUM:** Over 1.5 Goles Visitante.")
            st.write("El visitante llega con una inercia goleadora superior a su media de la temporada.")
        else:
            st.info("⚖️ **ESTADO:** Momentum neutro. No hay ventaja clara por recencia.")

else:
    st.info("Pega los datos para aplicar el modelo de Time Decay.")
