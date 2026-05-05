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

# --- LÓGICA DE CÁLCULO AVANZADO ---
def calcular_probabilidad_ajustada(n_exitos, n_total, factor_sos):
    """
    Aplica Time Decay (fijo para últimos partidos) y Ajuste por Rival (SOS).
    """
    if n_total == 0: return 0
    prob_base = n_exitos / n_total
    
    # Time Decay: Premiamos un 15% extra si la racha es reciente (simplificado)
    prob_decay = min(prob_base * 1.15, 1.0)
    
    # SOS: Ajustamos según la fuerza del rival
    # Si el rival es fuerte (0.8), la probabilidad final baja porque es más difícil ganar.
    prob_final = (prob_decay * factor_sos) * 100
    return round(min(prob_final, 100.0), 2)

# --- GESTIÓN DE BORRADO ---
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
        "invicta": buscar(r"(\d+)\s*\((\d+)%\)\s*Valla invicta"),
        "goles_c": buscar(r"(\d+\.\d+)\s*Goles convertidos\s*(\d+\.\d+)"),
        "remates_arco": buscar(r"(\d+\.\d+)\s*Remates al arco\s*(\d+\.\d+)"),
        "corners": buscar(r"(\d+\.\d+)\s*Corners\s*(\d+\.\d+)"),
        "tarjetas": buscar(r"(\d+\.\d+)\s*Tarjetas\s*(\d+\.\d+)")
    }

st.title("⚽ Consola de Análisis Predictivo")

# --- SIDEBAR: AJUSTE SOS ---
st.sidebar.header("🛡️ Parámetros de Ajuste")
st.sidebar.info("El SOS ajusta la probabilidad según el nivel del rival de hoy.")
nivel_rival = st.sidebar.select_slider(
    "Fuerza del Rival (SOS):",
    options=[0.7, 0.8, 0.9, 1.0, 1.1, 1.2],
    value=1.0,
    help="0.7: Rival Elite | 1.0: Rival Parejo | 1.2: Rival Muy Débil"
)

# --- APARTADO DE TEXTO ---
st.subheader("📋 Datos del Partido")
texto_input = st.text_area(
    "Pega aquí el texto de 365Scores:",
    height=200,
    key=f"campo_texto_{st.session_state.contador_borrado}"
)

if st.button("🗑️ Borrar", use_container_width=True):
    ejecutar_borrado()
    st.rerun()

# --- RESULTADOS ---
if texto_input:
    d = extraer_todo(texto_input)
    
    # FILA 1: Probabilidades Ajustadas (Time Decay + SOS)
    st.divider()
    st.subheader("📈 Probabilidades Reales (Ajustadas)")
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        if d["ganar_empate"]:
            prob_ajustada = calcular_probabilidad_ajustada(int(d["ganar_empate"][0]), 9, nivel_rival)
            st.metric("1X Ajustado", f"{prob_ajustada}%", delta=f"{round(prob_ajustada - int(d['ganar_empate'][1]), 1)}%")

    with c2:
        if d["btts"]:
            st.metric("Ambos Marcan", f"{d['btts'][1]}%")

    with c3:
        if d["over25"]:
            st.metric("Over 2.5 Goles", f"{d['over25'][1]}%")

    with c4:
        if d["invicta"]:
            st.metric("Arco en 0 (L)", f"{d['invicta'][1]}%")

    # FILA 2: Eficiencia Ofensiva
    st.divider()
    st.subheader("🎯 Análisis de Eficiencia (Visitante)")
    f2_c1, f2_c2, f2_c3 = st.columns(3)

    if d["goles_c"] and d["remates_arco"]:
        # Letalidad: Tiros al arco necesarios para 1 gol
        letalidad = round(float(d["remates_arco"][1]) / float(d["goles_c"][1]), 2)
        f2_c1.metric("Letalidad", f"{letalidad} tiros/gol")
        f2_c2.metric("Prom. Goles", d["goles_c"][1])
        f2_c3.metric("Remates al Arco", d["remates_arco"][1])

    # FILA 3: Mercados de Volumen
    st.divider()
    f3_c1, f3_c2 = st.columns(2)
    with f3_c1:
        if d["corners"]:
            total_c = float(d["corners"][0]) + float(d["corners"][1])
            st.write(f"🚩 **Corners Proyectados:** {total_c}")
            st.progress(min(total_c/16, 1.0))
    with f3_c2:
        if d["tarjetas"]:
            total_t = float(d["tarjetas"][0]) + float(d["tarjetas"][1])
            st.write(f"🟨 **Tarjetas Proyectadas:** {total_t}")
            st.progress(min(total_t/10, 1.0))

    # RECOMENDACIÓN FINAL
    st.divider()
    if d["ganar_empate"]:
        score_final = calcular_probabilidad_ajustada(int(d["ganar_empate"][0]), 9, nivel_rival)
        if score_final >= 80:
            st.success(f"🏆 **PICK RECOMENDADO:** Doble Oportunidad Local (1X). Confianza sólida ajustada: {score_final}%")
        elif float(d["goles_c"][1]) > 1.85 and letalidad < 3.5:
            st.warning("🔥 **PICK RECOMENDADO:** Over 1.5 Goles Visitante (Alta Letalidad Detectada)")
        else:
            st.info("⚖️ **ESTADO:** Sin ventaja estadística clara. Considerar mercado de Corners.")
