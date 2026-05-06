import streamlit as st
import re
import numpy as np
from scipy.stats import poisson
import pytesseract
from PIL import Image
import shutil

# --- MOTOR OCR ---
t_path = shutil.which("tesseract")
if t_path:
    pytesseract.pytesseract.tesseract_cmd = t_path

st.set_page_config(page_title="Radar de Valor: Veredicto Final", layout="wide")

# --- FUNCIONES DE CÁLCULO ---

def calcular_poisson(l_local, l_visita):
    max_goles = 7
    prob_matrix = np.outer(poisson.pmf(range(max_goles), l_local), 
                           poisson.pmf(range(max_goles), l_visita))
    empate = np.sum(np.diag(prob_matrix))
    gana_local = np.sum(np.tril(prob_matrix, -1))
    return (gana_local + empate) * 100

def ajustar(prob, sos, recencia=1.1):
    return round(min((prob * recencia) * sos, 99.0), 2)

# --- ESTADO DE BORRADO ---
if 'contador' not in st.session_state:
    st.session_state.contador = 0

def borrar():
    st.session_state.contador += 1

# --- INTERFAZ ---
st.title("⚽ Veredicto Final: Radar de Valor")

st.sidebar.header("🛡️ Ajuste SOS")
sos = st.sidebar.select_slider("Rival de hoy:", options=[0.8, 0.9, 1.0, 1.1, 1.2], value=1.0)

col_a, col_b = st.columns(2)
with col_a:
    txt_stats = st.text_area("Datos 365Scores:", height=150, key=f"s_{st.session_state.contador}")
with col_b:
    txt_odds = st.text_area("Cuotas (1.80 3.50...):", height=150, key=f"o_{st.session_state.contador}")

if st.button("🗑️ Borrar y Siguiente", use_container_width=True):
    borrar()
    st.rerun()

# --- MOTOR DE DECISIÓN ---
if txt_stats:
    # Extracción
    goles = re.findall(r"(\d+\.\d+)\s*Goles convertidos\s*(\d+\.\d+)", txt_stats)
    datos_mkt = re.search(r"(\d+)\s*\((\d+)%\)\s*Empató o Ganó", txt_stats)
    odds = re.findall(r"\d+\.\d+", txt_odds)

    if goles and datos_mkt:
        l_loc, l_vis = float(goles[0][0]), float(goles[0][1])
        prob_base = int(datos_mkt[1])
        
        # Cálculos Pro
        p_poisson = calcular_poisson(l_loc, l_vis)
        p_real = ajustar(p_poisson, sos)
        
        st.divider()
        
        # --- SECCIÓN DEL VEREDICTO ---
        st.subheader("🏁 Veredicto del Algoritmo")
        
        if odds:
            cuota = float(odds[0])
            prob_mkt = (1/cuota) * 100
            edge = p_real - prob_mkt
            
            # Lógica de veredicto
            if edge > 7:
                st.success(f"✅ **APUESTA RECOMENDADA:** Doble Oportunidad 1X")
                st.info(f"**Razón:** Ventaja masiva del {round(edge, 1)}% sobre la casa. La cuota de {cuota} paga demasiado para el riesgo real.")
            elif edge > 3:
                st.warning(f"🟡 **OPCIÓN SECUNDARIA:** 1X (Valor ajustado)")
                st.write("Hay ventaja, pero el margen es estrecho. Solo entrar si la alineación confirma titulares.")
            else:
                st.error(f"❌ **NO APOSTAR:** No hay valor en la cuota")
                st.write(f"La probabilidad de la casa ({round(prob_mkt, 1)}%) es muy similar o mayor a la nuestra ({p_real}%).")
        else:
            st.info("Pega las cuotas para recibir el veredicto final.")

        # --- DETALLES TÉCNICOS ---
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Prob. Poisson", f"{round(p_poisson,1)}%")
        c2.metric("Prob. Real (SOS)", f"{p_real}%")
        if odds:
            c3.metric("Edge (Ventaja)", f"{round(p_real - (1/float(odds[0]))*100, 1)}%")

    # Corners y Letalidad (Rápido)
    corners = re.findall(r"(\d+\.\d+)\s*Corners\s*(\d+\.\d+)", txt_stats)
    if corners:
        st.caption(f"🚩 Proyección de Corners: {float(corners[0][0]) + float(corners[0][1])}")
else:
    st.info("Esperando datos para dar el veredicto...")
