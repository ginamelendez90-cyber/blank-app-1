import streamlit as st
import re
import numpy as np
from scipy.stats import poisson

st.set_page_config(page_title="Radar de Valor Ultra", layout="wide")

# --- LÓGICA MATEMÁTICA MEJORADA ---

def calcular_poisson(lambda_local, lambda_visita):
    """Calcula probabilidades de victoria y goles usando Poisson."""
    max_goles = 6
    prob_matrix = np.outer(poisson.pmf(range(max_goles), lambda_local), 
                           poisson.pmf(range(max_goles), lambda_visita))
    
    empate = np.sum(np.diag(prob_matrix))
    gana_local = np.sum(np.tril(prob_matrix, -1))
    prob_1x = (gana_local + empate) * 100
    return round(prob_1x, 2)

def aplicar_ajustes(prob_base, nivel_rival, peso_recencia=1.1):
    """Aplica Time Decay (Recencia) y Strength of Schedule (SOS)."""
    # Time Decay: Multiplicador por inercia de resultados recientes
    prob_temp = prob_base * peso_recencia
    # SOS: Ajuste según dificultad del oponente
    prob_final = prob_temp * nivel_rival
    return round(min(prob_final, 99.9), 2)

# --- GESTIÓN DE BORRADO ---
if 'contador' not in st.session_state:
    st.session_state.contador = 0

def borrar_todo():
    st.session_state.contador += 1

# --- INTERFAZ ---
st.title("⚽ Radar de Valor: Inteligencia Predictiva")

st.sidebar.header("🛡️ Parámetros SOS")
sos_factor = st.sidebar.select_slider(
    "Nivel del Rival Próximo:",
    options=[0.8, 0.9, 1.0, 1.1, 1.2],
    value=1.0,
    help="0.8: Rival muy fuerte | 1.2: Rival muy débil"
)

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("📋 Estadísticas 365")
    txt_stats = st.text_area("Pega datos aquí:", height=150, key=f"s_{st.session_state.contador}")
with col_b:
    st.subheader("💰 Cuotas")
    txt_odds = st.text_area("Pega cuotas:", height=150, key=f"o_{st.session_state.contador}")

if st.button("🗑️ Borrar Todo", use_container_width=True):
    borrar_todo()
    st.rerun()

# --- PROCESAMIENTO AVANZADO ---
if txt_stats:
    # Extracción de promedios de goles
    goles = re.findall(r"(\d+\.\d+)\s*Goles convertidos\s*(\d+\.\d+)", txt_stats)
    datos_mkt = re.search(r"(\d+)\s*\((\d+)%\)\s*Empató o Ganó", txt_stats)
    
    if goles and datos_mkt:
        l_local, l_visita = float(goles[0][0]), float(goles[0][1])
        prob_estatica = int(datos_mkt[1])
        
        # 1. Cálculo Poisson (Probabilidad Matemática Pura)
        prob_poisson = calcular_poisson(l_local, l_visita)
        
        # 2. Aplicación de SOS y Recencia
        prob_final = aplicar_ajustes(prob_poisson, sos_factor)
        
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Prob. Poisson (Goles)", f"{prob_poisson}%")
        c2.metric("Prob. Real Ajustada", f"{prob_final}%", 
                  delta=f"{round(prob_final - prob_estatica, 1)}% vs 365")
        
        # 3. Identificación de Valor (Odds)
        odds = re.findall(r"\d+\.\d+", txt_odds)
        if odds:
            cuota_mkt = float(odds[0])
            prob_mkt = (1/cuota_mkt) * 100
            edge = prob_final - prob_mkt
            
            c3.metric("Edge (Ventaja)", f"{round(edge, 1)}%", 
                      delta="VALOR" if edge > 5 else "BAJO")
            
            if edge > 5:
                st.success(f"🎯 VALUE BET: Tu modelo indica un {prob_final}% contra un {round(prob_mkt, 1)}% de la casa.")

    st.divider()
    st.info("💡 El cálculo ahora utiliza Distribución de Poisson para proyectar resultados basados en la media de goles.")
