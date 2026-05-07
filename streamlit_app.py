import streamlit as st
import re
from datetime import datetime

# Configuración inicial
st.set_page_config(page_title="Multi-Sport Predictor", page_icon="🏆", layout="centered")

# --- INICIALIZACIÓN DE ESTADOS ---
if 'historial' not in st.session_state:
    st.session_state['historial'] = []

# --- FUNCIONES DE LÓGICA ---
def limpiar_entrada_tenis():
    st.session_state["texto_tenis"] = ""

def limpiar_entrada_futbol():
    st.session_state["texto_futbol"] = ""

def procesar_datos(texto, deporte):
    bloques = re.split(r'ÚLTIMOS PARTIDOS:', texto)
    resumen = []
    for bloque in bloques:
        if not bloque.strip(): continue
        lineas = [l.strip() for l in bloque.strip().split('\n') if l.strip()]
        if not lineas: continue
        nombre = lineas[0]
        
        # Regex para capturar marcadores (ej. 2 1 G o 1 1 E)
        matches = re.findall(r'(\d)\s+(\d)\s+([GEP])', bloque)
        
        if matches:
            victorias = sum(1 for m in matches if m[2] == 'G')
            total_goles = sum(int(m[0]) + int(m[1]) for m in matches)
            
            # Cálculo específico por deporte
            if deporte == "Tenis":
                # Estimación de juegos: 2-0 ~18.5j, 2-1 ~26.5j
                valor_metrica = sum(26.5 if (int(m[0]) + int(m[1])) >= 3 else 18.5 for m in matches) / len(matches)
            else:
                # Promedio de goles por partido
                valor_metrica = total_goles / len(matches)
                
            resumen.append({
                "nombre": nombre,
                "win_rate": victorias / len(matches),
                "metrica_promedio": valor_metrica,
                "racha": f"{victorias}-{sum(1 for m in matches if m[2] == 'E')}-{sum(1 for m in matches if m[2] == 'P')}" if deporte == "Futbol" else f"{victorias}-{len(matches)-victorias}"
            })
    return resumen

# --- INTERFAZ DE PESTAÑAS ---
tab1, tab2, tab3 = st.tabs(["🎾 Tenis", "⚽ Fútbol", "📜 Historial"])

# --- PESTAÑA TENIS ---
with tab1:
    st.header("Análisis de Tenis")
    data_tenis = st.text_area("Datos de Tenis:", height=150, key="texto_tenis")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🚀 ANALIZAR TENIS", use_container_width=True):
            stats = procesar_datos(data_tenis, "Tenis")
            if len(stats) >= 2:
                j1, j2 = stats[0], stats[1]
                ganador = j1 if j1['win_rate'] > j2['win_rate'] else j2
                sets = "2-1" if abs(j1['win_rate'] - j2['win_rate']) < 0.15 else "2-0"
                puntos = round(j1['metrica_promedio'] + 3.5 if sets == "2-1" else j1['metrica_promedio'] - 1.5, 1)
                
                st.success(f"**Ganador Probable:** {ganador['nombre']}")
                st.info(f"**Sets:** {sets} | **Juegos:** {puntos}")
                
                st.session_state['historial'].insert(0, {"fecha": datetime.now().strftime("%H:%M"), "msg": f"🎾 {j1['nombre']} vs {j2['nombre']}: Gana {ganador['nombre']} ({puntos}j)"})
    with c2:
        st.button("🗑️ BORRAR TENIS", on_click=limpiar_entrada_tenis, use_container_width=True)

# --- PESTAÑA FÚTBOL ---
with tab2:
    st.header("Análisis de Fútbol")
    data_futbol = st.text_area("Datos de Fútbol:", height=150, key="texto_futbol")
    f1, f2 = st.columns(2)
    with f1:
        if st.button("🚀 ANALIZAR FÚTBOL", use_container_width=True):
            stats = procesar_datos(data_futbol, "Futbol")
            if len(stats) >= 2:
                e1, e2 = stats[0], stats[1]
                ganador = e1 if e1['win_rate'] > e2['win_rate'] else e2
                goles_esperados = round((e1['metrica_promedio'] + e2['metrica_promedio']) / 2, 2)
                
                st.success(f"**Favorito:** {ganador['nombre']}")
                st.info(f"**Goles Promedio:** {goles_esperados}")
                veredicto_gol = "Over 2.5" if goles_esperados > 2.3 else "Under 2.5"
                st.warning(f"**Veredicto:** {veredicto_gol} goles")
                
                st.session_state['historial'].insert(0, {"fecha": datetime.now().strftime("%H:%M"), "msg": f"⚽ {e1['nombre']} vs {e2['nombre']}: {veredicto_gol}"})
    with f2:
        st.button("🗑️ BORRAR FÚTBOL", on_click=limpiar_entrada_futbol, use_container_width=True)

# --- PESTAÑA HISTORIAL ---
with tab3:
    st.header("Historial de Análisis")
    if st.session_state['historial']:
        for h in st.session_state['historial']:
            st.write(f"🕒 {h['fecha']} | {h['msg']}")
    else:
        st.write("Sin registros.")
