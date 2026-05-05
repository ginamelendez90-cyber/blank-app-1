import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Radar de Valor V9.1 - Monte Carlo", layout="wide")

if 'historial' not in st.session_state:
    st.session_state.historial = []

class EngineMonteCarlo:
    def simular_partido(self, l_xg, v_xg, h_adv, sims=10000):
        # Ajuste de lambdas (Goles esperados ajustados)
        l_lamb = (l_xg * (1 + h_adv))
        v_lamb = v_xg 
        
        # Simulación de goles usando distribución de Poisson
        goles_l = np.random.poisson(l_lamb, sims)
        goles_v = np.random.poisson(v_lamb, sims)
        
        resultados = pd.DataFrame({'L': goles_l, 'V': goles_v})
        
        # Calcular probabilidades desde la simulación
        p_1 = np.mean(resultados['L'] > resultados['V'])
        p_x = np.mean(resultados['L'] == resultados['V'])
        p_2 = np.mean(resultados['L'] < resultados['V'])
        p_o25 = np.mean((resultados['L'] + resultados['V']) > 2.5)
        p_btts = np.mean((resultados['L'] > 0) & (resultados['V'] > 0))
        
        # Encontrar el marcador más repetido (Moda)
        marcador_top = resultados.groupby(['L', 'V']).size().idxmax()
        
        return {
            "p_1": p_1, "p_x": p_x, "p_2": p_2,
            "p_o25": p_o25, "p_btts": p_btts,
            "top_score": f"{marcador_top[0]} - {marcador_top[1]}"
        }

# --- INTERFAZ ---
st.title("🛰️ Radar de Valor V9.1: Simulación de Monte Carlo")

t1, t2, t3 = st.tabs(["📥 Datos 365Scores", "🧪 Simulación Pro", "📂 Historial"])

with t1:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Local")
        n_l = st.text_input("Local", "Bournemouth")
        xg_l = st.number_input("xG Promedio", value=1.70)
        c_l = st.number_input("Cuota Local", value=1.75)
    with c2:
        st.subheader("Visitante")
        n_v = st.text_input("Visitante", "Crystal Palace")
        xg_v = st.number_input("xG Promedio", value=1.05)
        c_v = st.number_input("Cuota Visita", value=4.50)
    
    st.divider()
    col_ext = st.columns(4)
    c_x = col_ext[0].number_input("Cuota X", value=3.80)
    c_o = col_ext[1].number_input("Cuota O2.5", value=1.85)
    c_b = col_ext[3].number_input("Cuota BTTS", value=1.70)

with t2:
    if st.button("🎲 EJECUTAR 10,000 SIMULACIONES", use_container_width=True):
        engine = EngineMonteCarlo()
        # Usamos el xG directamente para la simulación
        res = engine.simular_partido(xg_l, xg_v, 0.10)
        
        st.success(f"🎯 **Marcador más probable según simulación:** {res['top_score']}")
        
        mercados = [
            (f"Victoria {n_l}", res['p_1'], c_l), ("Empate", res['p_x'], c_x),
            (f"Victoria {n_v}", res['p_2'], c_v), ("Over 2.5", res['p_o25'], c_o),
            ("Ambos Anotan", res['p_btts'], c_b)
        ]
        
        filas, opciones = [], []
        for nombre, prob, cuota in mercados:
            ev = (prob * cuota) - 1
            filas.append({
                "Mercado": nombre, 
                "Prob. Simulada": f"{prob:.1%}", 
                "Cuota Justa": round(1/prob, 2) if prob > 0 else 0,
                "Estado": "POSITIVO" if ev > 0 else "negativo"
            })
            opciones.append(f"{nombre} (@{cuota})")

        st.table(pd.DataFrame(filas).style.map(
            lambda x: 'background-color: #1a237e; color: white' if x == "POSITIVO" else 'color: #757575',
            subset=['Estado']
        ))

        # SECCIÓN DE GUARDADO
        st.divider()
        sel1, sel2 = st.columns(2)
        j1 = sel1.selectbox("Elegir Jugada 1:", ["Ninguna"] + opciones)
        j2 = sel2.selectbox("Elegir Jugada 2:", ["Ninguna"] + opciones)
        
        if st.button("💾 GUARDAR SELECCIÓN"):
            st.session_state.historial.append({
                "Fecha": datetime.now().strftime("%d/%m %H:%M"),
                "Partido": f"{n_l} vs {n_v}",
                "Score Sugerido": res['top_score'],
                "J1": j1, "J2": j2
            })
            st.toast("Simulación guardada")

with t3:
    if st.session_state.historial:
        st.dataframe(pd.DataFrame(st.session_state.historial), use_container_width=True)
        if st.button("🗑️ Limpiar"):
            st.session_state.historial = []
            st.rerun()
