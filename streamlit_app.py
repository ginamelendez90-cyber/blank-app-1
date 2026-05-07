import streamlit as st
import re

# Título simple
st.title("🎾 Tennis Predictor")

# Entrada de datos
texto = st.text_area("Pega aquí los datos de 365Scores", height=200)

if st.button("Analizar"):
    if texto:
        # Buscamos los bloques de cada jugador
        bloques = re.split(r'ÚLTIMOS PARTIDOS:', texto)
        
        # Filtrar bloques vacíos
        bloques = [b for b in bloques if b.strip()]
        
        if len(bloques) >= 2:
            for b in bloques:
                lineas = b.strip().split('\n')
                nombre = lineas[0]
                partidos = re.findall(r'([GP])', b) # Buscamos las letras G o P
                ganados = partidos.count('G')
                total = len(partidos)
                
                st.subheader(f"👤 {nombre}")
                st.write(f"Racha: {ganados} victorias de {total} partidos")
                st.progress(ganados/total if total > 0 else 0)
        else:
            st.error("Pega los datos de al menos 2 jugadores.")
    else:
        st.info("Esperando datos...")
