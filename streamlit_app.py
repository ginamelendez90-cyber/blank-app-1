import streamlit as st
import pytesseract
from PIL import Image
import re

st.title("⚽ Analizador de Resultados")

# Subir imagen
archivo = st.file_uploader("Sube tu captura", type=['png', 'jpg', 'jpeg'])

if archivo:
    img = Image.open(archivo)
    st.image(img)
    
    # Extraer texto
    texto = pytesseract.image_to_string(img, lang='spa')
    
    # Lógica de búsqueda simplificada para evitar errores de comillas
    # Buscamos el porcentaje de "Empató o Ganó"
    match_win = re.search(r"(\d+)%", texto) 
    
    if match_win:
        probabilidad = int(match_win.group(1))
        st.write(f"### Probabilidad detectada: {probabilidad}%")
        
        if probabilidad > 80:
            st.success("✅ Recomendación: Apuesta de alta seguridad (1X)")
        else:
            st.warning("⚠️ Recomendación: Riesgo moderado")
    else:
        st.error("No se pudo leer el porcentaje de la imagen.")
