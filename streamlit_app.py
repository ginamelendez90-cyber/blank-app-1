import streamlit as st
import pytesseract
from PIL import Image
import shutil
import re

# --- MOTOR OCR ---
t_path = shutil.which("tesseract")
if t_path:
    pytesseract.pytesseract.tesseract_cmd = t_path

st.set_page_config(page_title="Radar Pro: Value Betting", layout="wide")

# --- LÓGICA DE ESTADO ---
if 'contador' not in st.session_state:
    st.session_state.contador = 0

def borrar_todo():
    st.session_state.contador += 1

def extraer_datos(texto):
    def buscar(patron):
        m = re.search(patron, texto, re.IGNORECASE)
        return m.groups() if m else None

    return {
        "ganar_empate": buscar(r"(\d+)\s*\((\d+)%\)\s*Empató o Ganó"),
        "btts": buscar(r"(\d+)\s*\((\d+)%\)\s*Ambos equipos marcaron"),
        "over25": buscar(r"(\d+)\s*\((\d+)%\)\s*Más de 2\.5 goles"),
        "goles_c": buscar(r"(\d+\.\d+)\s*Goles convertidos\s*(\d+\.\d+)"),
        "remates_arco": buscar(r"(\d+\.\d+)\s*Remates al arco\s*(\d+\.\d+)"),
    }

def identificar_cuotas(texto):
    # Busca números decimales (cuotas)
    nums = re.findall(r"\d+\.\d+", texto)
    # Intenta mapear por orden común: Local (0), Empate (1), Visita (2) o Over/Under
    cuotas = {}
    if len(nums) >= 3:
        cuotas['1X2'] = [float(nums[0]), float(nums[1]), float(nums[2])]
    if len(nums) >= 2:
        cuotas['O/U'] = [float(n) for n in nums[-2:]]
    return cuotas

# --- INTERFAZ ---
st.title("⚽ Radar de Valor: Análisis de Cuotas")

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📋 Estadísticas (365Scores)")
    txt_stats = st.text_area("Pega datos aquí:", height=150, key=f"s_{st.session_state.contador}")

with col_right:
    st.subheader("💰 Cuotas Detectadas")
    txt_odds = st.text_area("Pega cuotas aquí (ej: 1.80 3.40 4.20):", height=150, key=f"o_{st.session_state.contador}")

if st.button("🗑️ Borrar y Siguiente Partido", use_container_width=True):
    borrar_todo()
    st.rerun()

# --- CÁLCULO DE VALOR ---
if txt_stats:
    d = extraer_datos(txt_stats)
    odds = identificar_cuotas(txt_odds)
    
    st.divider()
    st.subheader("📊 Comparativa de Valor (Value Betting)")
    
    # 1. Análisis de Doble Oportunidad Local (1X)
    if d["ganar_empate"] and '1X2' in odds:
        prob_est = int(d["ganar_empate"][1])
        # Aproximación de cuota 1X basada en Local y Empate
        c_l, c_e = odds['1X2'][0], odds['1X2'][1]
        cuota_1x = 1 / ((1/c_l) + (1/c_e))
        prob_mkt = (1 / cuota_1x) * 100
        valor = prob_est - prob_mkt
        
        c1, c2, c3 = st.columns(3)
        c1.metric("1X Real (Est.)", f"{prob_est}%")
        c2.metric("1X Mercado (Odds)", f"{round(prob_mkt, 1)}%")
        
        if valor > 5:
            c3.metric("VALOR", f"+{round(valor, 1)}%", delta="APOSTAR", delta_color="normal")
            st.success(f"🎯 Value Bet en Doble Oportunidad: Cuota estimada {round(cuota_1x, 2)}")
        else:
            c3.metric("VALOR", f"{round(valor, 1)}%", delta="SIN VALOR", delta_color="inverse")

    # 2. Análisis de Over 2.5
    if d["over25"] and 'O/U' in odds:
        st.divider()
        prob_over = int(d["over25"][1])
        cuota_over = odds['O/U'][0]
        prob_mkt_o = (1 / cuota_over) * 100
        val_o = prob_over - prob_mkt_o
        
        o1, o2, o3 = st.columns(3)
        o1.metric("Over 2.5 (Est.)", f"{prob_over}%")
        o2.metric("Over 2.5 (Odds)", f"{round(prob_mkt_o, 1)}%")
        
        if val_o > 5:
            o3.metric("VALOR", f"+{round(val_o, 1)}%", delta="VALOR")
        else:
            o3.metric("VALOR", f"{round(val_o, 1)}%", delta="BAJO")

    # Mostrar métricas de eficiencia que ya teníamos
    st.divider()
    if d["goles_c"] and d["remates_arco"]:
        ef = round(float(d["remates_arco"][1]) / float(d["goles_c"][1]), 2)
        st.info(f"⚡ Letalidad del Visitante: {ef} remates al arco por gol.")

else:
    st.info("Introduce estadísticas para calcular el valor frente a las cuotas.")
