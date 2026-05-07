import streamlit as st
import re
from datetime import datetime

st.set_page_config(page_title="Tennis Predictor PRO + Historial", page_icon="🎾")

# --- INICIALIZACIÓN DEL ESTADO DE SESIÓN ---
if 'historial' not in st.session_state:
    st.session_state['historial'] = []

# --- FUNCIONES DE LÓGICA ---
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
            # Estimación técnica de juegos
            suma_juegos_estimados = sum(26.5 if (int(m[0]) + int(m[1])) >= 3 else 18.5 for m in matches)
            resumen.append({
                "nombre": nombre,
                "win_rate": victorias / len(matches),
                "avg_juegos_hist": suma_juegos_estimados / len(matches),
                "racha": f"{victorias}-{len(matches)-victorias}"
            })
    return resumen

# --- INTERFAZ DE USUARIO ---
st.title("🎾 Analizador Pro con Historial")

# Cuadro de texto con clave para poder borrarlo
if 'input_text' not in st.session_state:
    st.session_state['input_text'] = ""

def borrar_texto():
    st.session_state['input_text'] = ""

data_entrada = st.text_area("Pega los datos de 365Scores:", 
                            value=st.session_state['input_text'], 
                            height=200, 
                            key="text_area_input")

col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    btn_analizar = st.button("🚀 GENERAR VEREDICTO", use_container_width=True)

with col_btn2:
    # Este botón limpia el estado y recarga la página
    if st.button("🗑️ BORRAR TEXTO", use_container_width=True, on_click=borrar_texto):
        st.rerun()

st.markdown("---")

# --- PROCESAMIENTO Y RESULTADO ---
if btn_analizar:
    if data_entrada:
        stats = procesar_tenis(data_entrada)
        if len(stats) >= 2:
            j1, j2 = stats[0], stats[1]
            diff = abs(j1['win_rate'] - j2['win_rate'])
            ganador = j1 if j1['win_rate'] > j2['win_rate'] else j2
            
            # Cálculos de Verdecito
            base_juegos = (j1['avg_juegos_hist'] + j2['avg_juegos_hist']) / 2
            sets_final = "2-1" if diff < 0.15 else "2-0"
            puntos_esperados = round(base_juegos + 3.5 if sets_final == "2-1" else base_juegos - 1.5, 1)
            prob = round((ganador['win_rate'] / (j1['win_rate'] + j2['win_rate'])) * 100, 1)

            # Guardar en Historial
            nuevo_registro = {
                "fecha": datetime.now().strftime("%H:%M:%S"),
                "enfrentamiento": f"{j1['nombre']} vs {j2['nombre']}",
                "ganador": ganador['nombre'],
                "sets": sets_final,
                "puntos": puntos_esperados
            }
            st.session_state['historial'].insert(0, nuevo_registro)

            # Mostrar Veredicto Actual
            st.subheader("🎯 Resultado del Análisis")
            st.success(f"**Ganador Probable:** {ganador['nombre']} ({prob}%)")
            st.info(f"**Sets:** {sets_final} | **Juegos Totales Esperados:** {puntos_esperados}")
        else:
            st.error("Error: Se necesitan datos de ambos jugadores.")
    else:
        st.warning("Pega información para analizar.")

# --- SECCIÓN DE HISTORIAL ---
st.markdown("---")
st.subheader("📜 Historial de Análisis")
if st.session_state['historial']:
    for item in st.session_state['historial']:
        with st.expander(f"🕒 {item['fecha']} - {item['enfrentamiento']}"):
            st.write(f"🏆 **Ganador:** {item['ganador']}")
            st.write(f"🎾 **Sets:** {item['sets']}")
            st.write(f"🔢 **Juegos Totales:** {item['puntos']}")
else:
    st.write("No hay análisis en el historial todavía.")
