import streamlit as st
import pandas as pd
from supabase import create_client
from sklearn.ensemble import RandomForestClassifier
import numpy as np

# --- CONEXIÓN ---
URL = st.secrets["https://netrbgledrnsjjuyhpui.supabase.co"]
KEY = st.secrets["sb_publishable_qH4a5QFumA-zqXfhZD6l-w_r5gTLRie"]
supabase = create_client(URL, KEY)

st.title("⚽ Radar de Valor Inteligente")

# --- FORMULARIO DE ENTRADA ---
with st.form("prediccion_form"):
    col1, col2 = st.columns(2)
    with col1:
        local = st.text_input("Equipo Local")
        xg_l = st.number_input("xG Promedio Local", value=1.5)
    with col2:
        visitante = st.text_input("Equipo Visitante")
        xg_v = st.number_input("xG Promedio Visitante", value=1.2)
    
    noticias = st.text_area("Contexto (Noticias, bajas, clima)", 
                           placeholder="Ej: El goleador local está lesionado. Clima lluvioso.")
    
    boton = st.form_submit_button("Analizar Partido")

if boton:
    # --- PASO 1: ANÁLISIS DE IA (OPCIÓN 2) ---
    # Simulamos el análisis de sentimiento de la noticia
    # Un valor > 0 favorece al local, < 0 favorece al visitante
    puntos_ia = 0.0
    if "lesionado" in noticias.lower() or "baja" in noticias.lower():
        puntos_ia -= 0.3
    if "motivación" in noticias.lower() or "favorito" in noticias.lower():
        puntos_ia += 0.2
    
    # --- PASO 2: MACHINE LEARNING (OPCIÓN 3) ---
    # Traemos históricos para entrenar el modelo
    res = supabase.table("predicciones_futbol").select("*").execute()
    historicos = res.data

    if len(historicos) > 10:
        df = pd.DataFrame(historicos)
        # Entrenamos con xG y el sentimiento que hubo en ese momento
        X = df[['xg_local', 'xg_visitante', 'sentimiento_noticias']]
        # Convertimos resultado a números (1: Local, 0: Empate/Visita)
        y = df['resultado_final'].apply(lambda x: 1 if x == 'Local' else 0)
        
        modelo = RandomForestClassifier()
        modelo.fit(X, y)
        
        # Predicción actual
        entrada = np.array([[xg_l, xg_v, puntos_ia]])
        probabilidad = modelo.predict_proba(entrada)[0][1]
    else:
        # Lógica estadística base si no hay suficiente historial
        st.warning("Pocos datos históricos. Usando cálculo estadístico base.")
        probabilidad = (xg_l / (xg_l + xg_v)) + puntos_ia

    # --- PASO 3: GUARDAR Y MOSTRAR ---
    registro = {
        "equipo_local": local,
        "equipo_visitante": visitante,
        "xg_local": float(xg_l),
        "xg_visitante": float(xg_v),
        "sentimiento_noticias": float(puntos_ia),
        "probabilidad_victoria": float(probabilidad)
    }

    try:
        supabase.table("predicciones_futbol").insert(registro).execute()
        st.success(f"Análisis completado para {local} vs {visitante}")
        
        # Mostrar resultado con métricas
        st.metric("Probabilidad Victoria Local", f"{probabilidad*100:.1f}%")
        st.progress(probabilidad)
        
    except Exception as e:
        st.error(f"Error al guardar: {e}")
