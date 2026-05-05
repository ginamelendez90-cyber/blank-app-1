import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson

st.set_page_config(page_title="Predicción Matemática Pro", layout="wide")

st.title("⚽ Simulador de Probabilidades Poisson & Monte Carlo")

# --- ENTRADA DE DATOS ---
with st.sidebar:
    st.header("Configuración Técnica")
    local = st.text_input("Equipo Local", "Local")
    visita = st.text_input("Equipo Visitante", "Visitante")
    
    # λ (Lambda) representa el promedio de goles esperados
    l_local = st.number_input(f"λ Esperado {local}", value=1.60, step=0.1)
    l_visita = st.number_input(f"λ Esperado {visita}", value=1.20, step=0.1)
    
    iteraciones = st.select_slider("Simulaciones Monte Carlo", 
                                   options=[1000, 5000, 10000], value=10000)

# --- CÁLCULOS MATEMÁTICOS ---

# 1. Matriz de Poisson (Probabilidad Teórica)
goles_rango = np.arange(0, 6)
prob_l = poisson.pmf(goles_rango, l_local)
prob_v = poisson.pmf(goles_rango, l_visita)
matriz = np.outer(prob_l, prob_v)

# 2. Simulación de Monte Carlo (Realismo Dinámico)
# Simulamos el partido miles de veces usando los promedios λ
sim_local = np.random.poisson(l_local, iteraciones)
sim_visita = np.random.poisson(l_visita, iteraciones)

victorias_l = np.sum(sim_local > sim_visita)
empates = np.sum(sim_local == sim_visita)
victorias_v = np.sum(sim_local < sim_visita)

over_25 = np.sum((sim_local + sim_visita) > 2.5)
btts = np.sum((sim_local > 0) & (sim_visita > 0))

# --- INTERFAZ DE RESULTADOS ---
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(f"Victoria {local}", f"{(victorias_l/iteraciones)*100:.1f}%")
    st.write(f"Cuota Justa: {iteraciones/victorias_l:.2f}")

with col2:
    st.metric("Empate", f"{(empates/iteraciones)*100:.1f}%")
    st.write(f"Cuota Justa: {iteraciones/empates:.2f}")

with col3:
    st.metric(f"Victoria {visita}", f"{(victorias_v/iteraciones)*100:.1f}%")
    st.write(f"Cuota Justa: {iteraciones/victorias_v:.2f}")

st.divider()

# --- ANÁLISIS DE GOLES ---
c_goles1, c_goles2 = st.columns(2)

with c_goles1:
    st.subheader("🎯 Mercado de Goles")
    st.write(f"**Over 2.5 Goles:** {(over_25/iteraciones)*100:.1f}%")
    st.write(f"**Ambos Marcan:** {(btts/iteraciones)*100:.1f}%")
    
    # Marcador exacto más probable de la matriz
    idx = np.unravel_index(np.argmax(matriz), matriz.shape)
    st.info(f"**Marcador Exacto Sugerido:** {idx[0]} - {idx[1]}")

with c_goles2:
    st.subheader("📊 Matriz de Probabilidades")
    df_matriz = pd.DataFrame(
        matriz, 
        columns=[f"V{i}" for i in range(6)], 
        index=[f"L{i}" for i in range(6)]
    )
    st.dataframe(df_matriz.style.format("{:.1%}").background_gradient(cmap='Blues'))

st.caption(f"Simulación basada en {iteraciones} iteraciones de eventos independientes.")
