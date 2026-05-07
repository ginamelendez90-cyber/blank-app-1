import streamlit as st
import re
from datetime import datetime

# Configuración inicial
st.set_page_config(page_title="Tennis Analizador", page_icon="🎾", layout="centered")

# --- INICIALIZACIÓN DE ESTADOS ---
if 'historial' not in st.session_state:
    st.session_state['historial'] = []

# --- FUNCIONES DE LÓGICA ---
def limpiar_entrada():
    """Función para resetear el cuadro de texto"""
    st.session_state["texto_entrada"] = ""

def procesar_tenis(texto):
    bloques = re.split(r'ÚLTIMOS PARTIDOS:', texto)
    resumen = []
    for bloque in bloques:
        if not bloque.strip(): continue
        lineas = [l.strip() for l in bloque.strip().split('\n') if l.strip()]
        if not lineas: continue
        nombre = lineas[0]
        matches = re.findall(r'(\d)\s+(\d)\s+([GP])', bloque)
        if matches:
            victorias = sum(1 for m in matches if m[2] == 'G')
            # 2-0 promedia ~18.5 juegos | 2-1 promedia ~26.5 juegos
            suma_juegos = sum(26.5 if (int(m[0]) + int(m[1])) >= 3 else 18.5 for m in matches)
            resumen.append({
                "nombre": nombre,
                "win_rate": victorias / len(matches),
                "avg_juegos_hist": suma_juegos / len(matches),
                "racha": f"{victorias}-{len(matches)-victorias}"
            })
    return resumen

# --- INTERFAZ ---
st.title("🎾 Analizador con Borrador e Historial")

# Cuadro de texto vinculado a la key "texto_entrada"
data_entrada = st.text_area(
    "Pega los datos aquí:", 
    height=200, 
    key="texto_entrada",
    placeholder="ÚLTIMOS PARTIDOS: JUGADOR A..."
)

col1, col2 = st.columns(2)

with col1:
    btn_analizar = st.button("🚀 ANALIZAR", use_container_width=True, type="primary")

with col2:
    # El botón llama a la función limpiar_entrada al hacer click
    st.button("🗑️ BORRAR TEXTO", use_container_width=True, on_click=limpiar_entrada)

st.markdown("---")

# --- LÓGICA DE RESULTADOS ---
if btn_analizar:
    if data_entrada:
        stats = procesar_tenis(data_entrada)
        if len(stats) >= 2:
            j1, j2 = stats[0], stats[1]
            diff = abs(j1['win_rate'] - j2['win_rate'])
            ganador = j1 if j1['win_rate'] > j2['win_rate'] else j2
            
            # Cálculos de Veredicto
            base_juegos = (j1['avg_juegos_hist'] + j2['avg_juegos_hist']) / 2
            sets_final = "2-1" if diff < 0.15 else "2-0"
            puntos_esperados = round(base_juegos + 3.5 if sets_final == "2-1" else base_juegos - 1.5, 1)
            prob = round((ganador['win_rate'] / (j1['win_rate'] + j2['win_rate'])) * 100, 1)

            # Guardar en Historial
            st.session_state['historial'].insert(0, {
                "fecha": datetime.now().strftime("%H:%M:%S"),
                "enfrentamiento": f"{j1['nombre']} vs {j2['nombre']}",
                "ganador": ganador['nombre'],
                "sets": sets_final,
                "puntos": puntos_esperados,
                "prob": prob
            })

            # Mostrar Veredicto Actual
            st.subheader("🎯 Veredicto Actual")
            st.success(f"**Ganador:** {ganador['nombre']} ({prob}%)")
            st.info(f"**Sets:** {sets_final} | **Juegos Totales:** {puntos_esperados}")
        else:
            st.error("Error: Se necesitan datos de ambos jugadores.")
    else:
        st.warning("El campo de texto está vacío.")

# --- SECCIÓN DE HISTORIAL ---
if st.session_state['historial']:
    st.markdown("---")
    st.subheader("📜 Historial de Sesión")
    for item in st.session_state['historial']:
        with st.expander(f"🕒 {item['fecha']} - {item['enfrentamiento']}"):
            st.write(f"🏆 **Predicción:** {item['ganador']} ({item['prob']}%)")
            st.write(f"🎾 **Sets:** {item['sets']} | 🔢 **Juegos:** {item['puntos']}")
