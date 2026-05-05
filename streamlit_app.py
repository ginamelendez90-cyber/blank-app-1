import streamlit as st
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import numpy as np

st.set_page_config(page_title="Predicciones de Fútbol Inteligentes", layout="centered")

st.title("⚽ Analizador de Fútbol Inteligente")
st.markdown("""
Este script utiliza **IA (Contexto)** y **Machine Learning (Estadística)** para predecir probabilidades.
*Sin conexión a base de datos externa.*
""")

# --- FORMULARIO DE ENTRADA ---
with st.form("prediccion_form"):
    col1, col2 = st.columns(2)
    with col1:
        local = st.text_input("Equipo Local", value="Local")
        xg_l = st.number_input("xG (Goles Esperados) Local", min_value=0.0, value=1.5, step=0.1)
    with col2:
        visitante = st.text_input("Equipo Visitante", value="Visitante")
        xg_v = st.number_input("xG (Goles Esperados) Visitante", min_value=0.0, value=1.2, step=0.1)
    
    noticias = st.text_area("Análisis de Contexto (Opción 2 - IA)", 
                           placeholder="Ej: El equipo local tiene 3 bajas importantes y el clima será lluvioso...")
    
    boton = st.form_submit_button("Calcular Predicción Inteligente")

if boton:
    # --- 1. LÓGICA DE IA (ANÁLISIS DE TEXTO SIMULADO) ---
    # Evaluamos el impacto de las noticias en la probabilidad
    impacto_ia = 0.0
    texto = noticias.lower()
    
    # Factores negativos
    if any(word in texto for word in ["baja", "lesion", "suspendido", "cansancio"]):
        impacto_ia -= 0.15
    # Factores positivos
    if any(word in texto for word in ["titular", "completo", "favorito", "racha"]):
        impacto_ia += 0.10
    # Factor clima
    if "lluvia" in texto or "tormenta" in texto:
        impacto_ia -= 0.05 # Generalmente beneficia al underdog o reduce goles

    # --- 2. LÓGICA DE MACHINE LEARNING (OPCIÓN 3) ---
    # Como no hay base de datos, generamos un modelo sintético basado en xG + Impacto IA
    # Esto simula cómo un modelo de ML procesaría los pesos
    
    def simulador_ml(xl, xv, ia):
        # Base matemática (Poisson simplificado)
        base = xl / (xl + xv) if (xl + xv) > 0 else 0.5
        # Ajuste con el contexto de la IA
        resultado_final = base + ia
        return np.clip(resultado_final, 0.05, 0.95) # Limitamos entre 5% y 95%

    probabilidad = simulador_ml(xg_l, xg_v, impacto_ia)

    # --- 3. RESULTADOS ---
    st.divider()
    st.subheader(f"Resultado del Análisis: {local} vs {visitante}")
    
    m1, m2 = st.columns(2)
    m1.metric("Probabilidad Victoria Local", f"{probabilidad*100:.1f}%")
    m2.metric("Ajuste por Contexto (IA)", f"{impacto_ia:+.2f}")

    # Visualización
    st.progress(probabilidad)
    
    if probabilidad > 0.65:
        st.success(f"🔥 **Alta probabilidad:** El análisis sugiere una ventaja clara para {local}.")
    elif probabilidad < 0.35:
        st.info(f"🚩 **Oportunidad:** El contexto favorece a {visitante} o un posible empate.")
    else:
        st.warning("⚖️ **Partido Equilibrado:** Los datos técnicos y de contexto no muestran un favorito claro.")

    st.caption("Nota: Este análisis es estadístico y no garantiza resultados. Juega con responsabilidad.")
