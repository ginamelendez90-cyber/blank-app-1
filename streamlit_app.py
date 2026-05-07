import streamlit as st
import re

st.set_page_config(page_title="Tennis Verdict Pro", page_icon="🎾")

st.title("🎾 Analizador y Veredicto Final")
st.markdown("---")

# Entrada de datos
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
            # Estimación de juegos por set
            total_sets = sum(int(m[0]) + int(m[1]) for m in matches)
            resumen.append({
                "nombre": nombre,
                "win_rate": victorias / len(matches),
                "sets_avg": total_sets / len(matches),
                "racha": f"{victorias}-{len(matches)-victorias}"
            })
    return resumen

if st.button("GENERAR VEREDICTO"):
    if data_entrada:
        stats = procesar_tenis(data_entrada)
        if len(stats) >= 2:
            j1, j2 = stats[0], stats[1]
            
            # LÓGICA DEL VEREDICTO
            diff = j1['win_rate'] - j2['win_rate']
            ganador = j1 if diff > 0 else j2
            prob = (max(j1['win_rate'], j2['win_rate']) / (j1['win_rate'] + j2['win_rate'])) * 100
            
            # Determinar Sets y Riesgo
            if abs(diff) < 0.15:
                sets_final = "2-1"
                riesgo = "ALTO (Partido muy parejo)"
                pick = "Over 21.5 Juegos"
            else:
                sets_final = "2-0"
                riesgo = "MEDIO"
                pick = f"Gana {ganador['nombre']} simple"

            # INTERFAZ DE RESULTADOS
            st.subheader("📊 Comparativa de Rendimiento")
            col1, col2 = st.columns(2)
            col1.metric(j1['nombre'], j1['racha'], f"{int(j1['win_rate']*100)}% Win")
            col2.metric(j2['nombre'], j2['racha'], f"{int(j2['win_rate']*100)}% Win")

            st.markdown("---")
            st.header("🎯 VEREDICTO FINAL")
            
            with st.container():
                st.info(f"**GANADOR PREVISTO:** {ganador['nombre']}")
                st.write(f"**Marcador Probable:** {sets_final} sets")
                st.write(f"**Probabilidad Estadística:** {round(prob, 1)}%")
                st.write(f"**Nivel de Riesgo:** {riesgo}")
                st.success(f"✅ **PICK RECOMENDADO:** {pick}")
        else:
            st.error("Error: Asegúrate de pegar los datos de AMBOS jugadores.")
    else:
        st.warning("Pega los datos antes de continuar.")
