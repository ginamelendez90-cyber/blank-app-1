import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Predicciones Pro", layout="wide")

st.title("⚽ Sistema de Predicción de Fútbol Avanzado")

with st.form("analisis_avanzado"):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("🏠 Local")
        local = st.text_input("Nombre", value="Equipo A")
        xg_l = st.number_input("xG (Goles Esperados)", value=1.6, step=0.1)
        forma_l = st.slider("Forma (0-100%)", 0, 100, 50, key="fl")
        bajas_l = st.multiselect("Bajas Locales", ["Portero Titular", "Defensa Central", "Goleador", "Mediocentro Creativo"])

    with col2:
        st.subheader("🚀 Visitante")
        visitante = st.text_input("Nombre ", value="Equipo B")
        xg_v = st.number_input("xG (Goles Esperados) ", value=1.1, step=0.1)
        forma_v = st.slider("Forma (0-100%)", 0, 100, 50, key="fv")
        bajas_v = st.multiselect("Bajas Visitantes", ["Portero Titular", "Defensa Central", "Goleador", "Mediocentro Creativo"])

    with col3:
        st.subheader("🧠 Contexto e IA")
        importancia = st.select_slider("Importancia del Partido", options=["Baja", "Media", "Alta", "Crítica"])
        clima = st.selectbox("Clima", ["Despejado", "Lluvia", "Calor Extremo", "Nieve"])
        motivacion = st.radio("Motivación Extra", ["Ninguna", "Clásico/Derbi", "Pelea Descenso", "Pelea Título"])

    boton_pro = st.form_submit_button("Ejecutar Análisis de Valor")

if boton_pro:
    # --- PROCESAMIENTO DE IA (PONDERACIÓN DE VARIABLES) ---
    # Calculamos penalizaciones por bajas
    penalizacion_l = len(bajas_l) * 0.08
    penalizacion_v = len(bajas_v) * 0.08
    
    # Ajuste por forma y motivación (Simulando lógica de ML)
    ajuste_forma = (forma_l - forma_v) / 200 # Max +/- 0.5
    
    # Impacto del clima (La lluvia suele reducir la brecha técnica)
    ajuste_clima = -0.05 if clima == "Lluvia" and xg_l > xg_v else 0
    
    # --- CÁLCULO DE PROBABILIDAD (MODELO HÍBRIDO) ---
    base_stats = (xg_l - penalizacion_l) / ((xg_l - penalizacion_l) + (xg_v - penalizacion_v))
    prob_final = base_stats + ajuste_forma + ajuste_clima
    
    if motivacion == "Clásico/Derbi":
        prob_final = (prob_final + 0.5) / 2 # Tiende al equilibrio (50/50)

    prob_final = np.clip(prob_final, 0.01, 0.99)

    # --- DESPLIEGUE DE RESULTADOS ---
    st.divider()
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.metric("Prob. Victoria Local", f"{prob_final*100:.1f}%")
    with c2:
        st.metric("Prob. Empate/Visita", f"{(1-prob_final)*100:.1f}%")
    with c3:
        # Cálculo de cuota justa (Fair Odds)
        cuota_justa = 1 / prob_final if prob_final > 0 else 0
        st.metric("Cuota Justa Sugerida", f"{cuota_justa:.2f}")

    # Mensaje Inteligente
    if prob_final > 0.70:
        st.success(f"✅ FUERTE: {local} llega con métricas dominantes.")
    elif prob_final < 0.40:
        st.warning(f"⚠️ ALERTA: {visitante} tiene valor estadístico o el contexto le favorece.")
    else:
        st.info("⚖️ EQUILIBRIO: Las variables sugieren un partido cerrado.")

    st.progress(prob_final)
