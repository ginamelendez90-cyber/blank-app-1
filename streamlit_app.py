import streamlit as st
import re

st.set_page_config(page_title="Tennis Predictor PRO", page_icon="🎾")

st.title("🎾 Analizador de Tenis: Veredicto y Puntos")
st.markdown("---")

data_entrada = st.text_area("Pega los datos de 365Scores aquí:", height=250)

def procesar_tenis(texto):
    bloques = re.split(r'ÚLTIMOS PARTIDOS:', texto)
    resumen = []
    for bloque in bloques:
        if not bloque.strip(): continue
        lineas = [l.strip() for l in bloque.strip().split('\n') if l.strip()]
        nombre = lineas[0]
        # Extraer marcadores y resultado G/P
        matches = re.findall(r'(\d)\s+(\d)\s+([GP])', bloque)
        if matches:
            victorias = sum(1 for m in matches if m[2] == 'G')
            # Estimación técnica de juegos según el marcador de sets
            # 2-0 promedia ~18.5 juegos | 2-1 promedia ~26.5 juegos
            suma_juegos_estimados = sum(26.5 if (int(m[0]) + int(m[1])) >= 3 else 18.5 for m in matches)
            
            resumen.append({
                "nombre": nombre,
                "win_rate": victorias / len(matches),
                "avg_juegos_hist": suma_juegos_estimados / len(matches),
                "racha": f"{victorias}-{len(matches)-victorias}"
            })
    return resumen

if st.button("GENERAR VEREDICTO FINAL"):
    if data_entrada:
        stats = procesar_tenis(data_entrada)
        if len(stats) >= 2:
            j1, j2 = stats[0], stats[1]
            
            # Lógica de Veredicto
            diff = abs(j1['win_rate'] - j2['win_rate'])
            ganador = j1 if j1['win_rate'] > j2['win_rate'] else j2
            
            # Cálculo de Juegos Totales Esperados
            # Se promedian los históricos y se aplica un factor de competitividad
            base_juegos = (j1['avg_juegos_hist'] + j2['avg_juegos_hist']) / 2
            
            if diff < 0.15: # Partido muy parejo
                sets_final = "2-1"
                puntos_esperados = base_juegos + 3.5 # Bonus por alta probabilidad de 3er set
                confianza_over = "Alta"
            else:
                sets_final = "2-0"
                puntos_esperados = base_juegos - 1.5
                confianza_over = "Baja"

            # INTERFAZ
            st.header("🎯 VEREDICTO FINAL")
            
            # Tarjeta Principal
            st.success(f"**GANADOR PROBABLE:** {ganador['nombre']}")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Marcador Sets", sets_final)
            col2.metric("Total Juegos", f"{round(puntos_esperados, 1)}")
            col3.metric("Probabilidad", f"{round((ganador['win_rate']/ (j1['win_rate']+j2['win_rate']))*100, 1)}%")

            st.markdown("---")
            st.subheader("💡 Análisis de Apuesta")
            st.write(f"🔹 **Puntos (Juegos) esperados en el juego total:** Aproximadamente **{round(puntos_esperados, 1)}** juegos.")
            st.write(f"🔹 **Sugerencia:** {'Over (Más de) ' + str(round(puntos_esperados - 1.5, 1)) if puntos_esperados > 21.5 else 'Under (Menos de) ' + str(round(puntos_esperados + 1.5, 1))}")
            st.write(f"🔹 **Confianza del Over:** {confianza_over}")
            
        else:
            st.error("Error: Se necesitan datos de ambos jugadores.")
    else:
        st.warning("Por favor, pega la información necesaria.")
