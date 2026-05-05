import streamlit as st
import pytesseract
from PIL import Image
import re

# Configuración de la página
st.set_page_config(page_title="Analizador de Apuestas", page_icon="⚽")

st.title("⚽ Decision Maker: Análisis de 365Scores")
st.write("Sube la captura de pantalla para procesar los datos.")

# 1. Subida de archivo
archivo_subido = st.file_uploader("Subir imagen (ej. image.png)", type=["png", "jpg", "jpeg"])

if archivo_subido is not None:
    imagen = Image.open(archivo_subido)
    st.image(imagen, caption='Imagen detectada', use_container_width=True)
    
    with st.spinner('Procesando imagen con OCR...'):
        # Extraer texto con configuración para bloques
        texto = pytesseract.image_to_string(imagen, lang='spa', config='--psm 6')
        
        # Diccionario para almacenar los datos extraídos
        datos = {}
        
        # Patrones de búsqueda (basados en la estructura de tu imagen)
        patrones = {
            "Empato_Gano": r"(\d+)\s*\((\d+)%\)\s*Empató o Ganó",
            "Mas_25": r"Más de 2\.5 goles\s*(\d+)\s*\((\d+)%\)",
            "Valla_Invicta": r"(\d+)\s*\((\d+)%\)\s*Valla invicta"
        }

        for clave, regex in patrones.items():
            match = re.search(regex, texto, re.IGNORECASE)
            if match:
                datos[clave] = match.groups()

    # 2. Mostrar Estadísticas Detectadas
    st.subheader("📊 Datos Extraídos")
    col1, col2 = st.columns(2)

    with col1:
        if "Empato_Gano" in datos:
            valor = datos["Empato_Gano"][1]
            st.metric("Prob. Imbatibilidad (Local)", f"{valor}%")
        else:
            st.warning("No se detectó 'Empató o Ganó'")

    with col2:
        if "Mas_25" in datos:
            valor = datos["Mas_25"][1]
            st.metric("Prob. Over 2.5 (Visita)", f"{valor}%")
        else:
            st.warning("No se detectó '+2.5 Goles'")

    # 3. Lógica de Decisión Corregida
    st.divider()
    st.header("🤖 Recomendación")

    # Validamos existencia antes de operar
    if "Empato_Gano" in datos:
        porcentaje_local = int(datos["Empato_Gano"][1])
        
        if porcentaje_local >= 85:
            st.success("✅ **ALTA CONFIANZA:** Apuesta a 'Doble Oportunidad (1X)'.")
            st.write(f"Razón: El local tiene un {porcentaje_local}% de imbatibilidad.")
        elif "Mas_25" in datos and int(datos["Mas_25"][1]) >= 55:
            st.warning("🔥 **MODERADA:** Apuesta a 'Más de 2.5 Goles'.")
            st.write("Razón: Tendencia alta de goles en el equipo visitante.")
        else:
            st.info("ℹ️ Datos insuficientes para una apuesta clara. Se recomienda prudencia.")
    else:
        st.error("Error: No se pudieron extraer datos clave de la imagen.")
