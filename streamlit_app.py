import streamlit as st
import numpy as np
from scipy.stats import poisson

st.set_page_config(page_title="Predicción Matemática Pro", layout="wide")

st.title("⚽ Análisis Estadístico: Distribución de Poisson")

with st.sidebar:
    st.header("Parámetros del Modelo")
    # El xG ajustado sirve como el parámetro 'lambda' (λ) de Poisson
    lambda_local = st.number_input("λ Local (Goles esperados ajustados)", value=1.65, step=0.1)
    lambda_visita = st.number_input("λ Visita (Goles esperados ajustados)", value=1.20, step=0.1)

def calcular_probabilidades_goles(l_local, l_visita):
    # Calculamos probabilidades de 0 a 5 goles para cada equipo
    prob_goles_local = [poisson.pmf(i, l_local) for i in range(6)]
    prob_goles_visita = [poisson.pmf(i, l_visita) for i in range(6)]
    
    # Matriz de marcadores exactos
    matriz_marcadores = np.outer(prob_goles_local, prob_goles_visita)
    
    # Probabilidades principales
    prob_over_2_5 = 0
    prob_ambos_marcan = (1 - prob_goles_local[0]) * (1 - prob_goles_visita[0])
    
    for i in range(6):
        for j in range(6):
            if (i + j) > 2.5:
                prob_over_2_5 += matriz_marcadores[i, j]
                
    return matriz_marcadores, prob_over_2_5, prob_ambos_marcan

# --- CÁLCULOS ---
matriz, over25, btts = calcular_probabilidades_goles(lambda_local, lambda_visita)

# --- VISUALIZACIÓN ---
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Probabilidad Over 2.5 Goles", f"{over25*100:.1f}%")
    st.write("Cuota Justa O2.5:", f"{1/over25:.2f}" if over25 > 0 else "0")

with col2:
    st.metric("Probabilidad Ambos Marcan (BTTS)", f"{btts*100:.1f}%")
    st.write("Cuota Justa BTTS:", f"{1/btts:.2f}" if btts > 0 else "0")

with col3:
    # Encontrar el marcador más probable
    idx = np.unravel_index(np.argmax(matriz), matriz.shape)
    st.metric("Marcador más Probable", f"{idx[0]} - {idx[1]}")
    st.write("Confianza del marcador:", f"{matriz[idx]*100:.1f}%")

st.divider()

# --- TABLA DE PROBABILIDADES DE MARCADOR EXACTO ---
st.subheader("📊 Matriz de Probabilidades (Marcador Exacto)")
df_matriz = pd.DataFrame(
    matriz, 
    columns=[f"Visita {i}" for i in range(6)], 
    index=[f"Local {i}" for i in range(6)]
)
st.dataframe(df_matriz.style.format("{:.2%}").background_gradient(cmap='Greens'))

st.info("""
**¿Cómo leer esto?**
La Distribución de Poisson calcula la probabilidad de que un equipo anote 'X' goles basándose en su promedio (λ). 
La matriz muestra la intersección de ambos equipos; las celdas más oscuras indican los resultados más probables matemáticamente.
""")
