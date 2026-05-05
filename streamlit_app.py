import streamlit as st
import pytesseract
from PIL import Image
import shutil
import re

# --- CONFIGURACIÓN DE MOTOR OCR ---
t_path = shutil.which("tesseract")
if t_path:
    pytesseract.pytesseract.tesseract_cmd = t_path

st.set_page_config(page_title="Radar de Valor Pro: Odds Edition", layout="wide")

# --- LÓGICA DE BORRADO FÍSICO ---
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
        "corners": buscar(r"(\d+\.\d+)\s*Corners\s*(\d+\.\d+)"),
    }

# --- INTERFAZ ---
st.title("⚽ Consola de Análisis + Comparador de Cuotas")

# --- APARTADO DE ENTRADA DE DATOS ---
col_stats, col_odds = st.columns(2)

with col_stats:
    st.subheader("📋 Estadísticas (365Scores)")
    texto_stats = st.text_area(
        "Pega los datos del partido aquí:",
        height=150,
        key=f"stats_{st.session_state.contador_borrado}"
    )

with col_odds:
    st.subheader("💰 Cuotas (Bookie)")
    texto_cuotas = st.text_area(
        "Pega las cuotas (ej: 1.85, 3.40):",
        height=150,
        key=f"odds_{st.session_state.contador_borrado}",
        placeholder="Local: 1.80\nEmpate: 3.20\nVisita: 4.50"
    )

if st.button("🗑️ Borrar Todo", use_container_width=True):
    ejecutar_borrado()
    st.rerun()

# --- PROCESAMIENTO ---
if texto_stats:
    d = extraer_todo(texto_stats)
    
    # Extraer cuotas usando regex (busca números decimales)
    odds_encontradas = re.findall(r"\d+\.\d+", texto_cuotas)
    
    st.divider()
    
    # Análisis de Probabilidad y Valor
    if d["ganar_empate"]:
        prob_stats = int(d["ganar_empate"][1])
        st.subheader(f"📈 Análisis de Probabilidad: {prob_stats}% (Base)")
        
        # Si hay cuotas, calculamos el Value
        if odds_encontradas:
            cuota_1x = float(odds_encontradas[0]) # Tomamos la primera cuota como referencia para el ejemplo
            prob_bookie = (1 / cuota_1x) * 100
            value = prob_stats - prob_bookie
            
            v_col1, v_col2, v_col3 = st.columns(3)
            v_col1.metric("Cuota Ingresada", cuota_1x)
            v_col2.metric("Prob. Implícita Casa", f"{round(prob_bookie, 1)}%")
            v_col3.metric("Valor Detectado", f"{round(value, 1)}%", delta=f"{round(value, 1)}%")
            
            if value > 5:
                st.success(f"🎯 **VALUE BET DETECTADA:** La cuota de {cuota_1x} es superior a lo que dictan las estadísticas.")
            else:
                st.warning("⚠️ **SIN VALOR:** La cuota es muy baja para el riesgo estadístico.")

    # Mostrar el resto de métricas que ya teníamos
    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        if d["btts"]: st.metric("Ambos Marcan", f"{d['btts'][1]}%")
    with c2:
        if d["over25"]: st.metric("Over 2.5 Goles", f"{d['over25'][1]}%")
    with c3:
        if d["corners"]:
            total_c = float(d["corners"][0]) + float(d["corners"][1])
            st.metric("Corners Totales", total_c)

else:
    st.info("Pega las estadísticas para activar el comparador de valor.")
