import streamlit as st
import pytesseract
from PIL import Image
import re

# Configuración de la página
st.set_page_config(page_title="Analizador de Apuestas AI", page_icon="⚽")

st.title("⚽ Decision Maker: Análisis de Estadísticas")
st.write("Sube una captura de pantalla de las estadísticas para obtener una recomendación.")

# 1. Cargador de archivos
archivo_subido = st.file_uploader("Elige una imagen...", type=["png", "jpg", "jpeg"])

if archivo_subido is not None:
    # Mostrar la imagen subida
    imagen = Image.open(archivo_subido)
    st.image(imagen, caption='Captura analizada', use_container_width=True)
    
    with st.spinner('Extrayendo datos de la imagen...'):
        # 2. OCR - Extraer texto
        # Tip: Usar psm 6 ayuda a Tesseract a leer bloques de texto uniformes
        texto = pytesseract.image_to_string(imagen, lang='spa', config='--psm 6')
        
        # 3. Lógica de extracción de datos (Basada en image.png)
        def extraer_valor(patron, texto_fuente):
            match = re.search(patron, texto_fuente, re.IGNORECASE)
            if match:
                return match.groups()
            return None

        # Buscamos los porcentajes y valores de las filas clave
        datos = {
            "Empató o Ganó": extraer_valor(r"(\d+)\s*\((\d+)%\)\s*Empató o Ganó\s*(\d+)\s*\((\d+)%\)", texto),
            "Más de 2.5": extraer_valor(r"(\d+)\s*\((\d+)%\)\s*Más de 2\.5 goles\s*(\d+)\s*\((\d+)%\)", texto),
            "Valla Invicta": extraer_valor(r"(\d+)\s*\((\d+)%\)\s*Valla invicta\s*(\d+)\s*\((\d+)%\)", texto)
        }

    # 4. Mostrar Resultados y Decisión
    st.subheader("📊 Análisis de Probabilidades")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("**Equipo Local (Izq)**")
        if datos["Empató o Ganó"]:
            st.metric("Prob. No Perder", f"{datos['Empató o Ganó'][1]}%")
        if datos["Valla Invicta"]:
            st.write(f"Valla invicta: {datos['Valla Invicta'][1]}%")

    with col2:
        st.info("**Equipo Visitante (Der)**")
        if datos["Más de 2.5"]:
            st.metric("Tendencia Over 2.5", f"{datos['Más de 2.5'][3]}%")

    # 5. Lógica de Decisión Final
    st.divider()
    st.header("🤖 Decisión del Script")

    if datos["Empató o Ganó"] and int(datos["Empató o Ganó'][1]) >= 80:
        st.success("✅ **APUESTA RECOMENDADA:** Doble Oportunidad: Local o Empate (1X)")
        st.write("Razón: El equipo local tiene una racha de imbatibilidad muy alta (89%).")
    elif datos["Más de 2.5"] and int(datos["Más de 2.5"][3]) >= 55:
        st.warning("🔥 **APUESTA RECOMENDADA:** Más de 2.5 Goles")
        st.write("Razón: El equipo visitante tiende a participar en partidos con muchos goles.")
    else:
        st.write("⚠️ Los datos no son lo suficientemente concluyentes para una apuesta de alta confianza.")
