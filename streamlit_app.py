import streamlit as st
import pytesseract
from PIL import Image
import subprocess
import shutil
import re

# --- CONFIGURACIÓN DE TESSERACT PARA STREAMLIT CLOUD ---
def get_tesseract_path():
    # 1. Intentar encontrarlo en el PATH del sistema
    path = shutil.which("tesseract")
    if path:
        return path
    
    # 2. Rutas comunes en servidores Linux de Streamlit
    comunes = ["/usr/bin/tesseract", "/usr/local/bin/tesseract"]
    for p in comunes:
        if shutil.which(p):
            return p
    return None

t_path = get_tesseract_path()

if t_path:
    pytesseract.pytesseract.tesseract_cmd = t_path
else:
    st.error("❌ Motor Tesseract no encontrado. Verifica que 'packages.txt' existe y tiene 'tesseract-ocr'.")

# --- INTERFAZ DE STREAMLIT ---
st.set_page_config(page_title="Predicciones 365", layout="centered")
st.title("⚽ Analizador de Decisiones")

archivo = st.file_uploader("Sube la imagen del partido", type=['png', 'jpg', 'jpeg'])

if archivo:
    try:
        img = Image.open(archivo)
        st.image(img, caption="Imagen cargada")
        
        with st.spinner("Analizando datos..."):
            # Extraer texto forzando español
            texto = pytesseract.image_to_string(img, lang='spa')
            
            # Depuración: Ver qué está leyendo el AI (puedes borrar esto luego)
            with st.expander("Ver texto extraído (Debug)"):
                st.code(texto)

            # Lógica de búsqueda mejorada
            # Buscamos el patrón "X (Y%) Empató o Ganó"
            re_empato = re.search(r"(\d+)\s*\((\d+)%\)\s*Empató o Ganó", texto, re.IGNORECASE)
            
            if re_empato:
                porcentaje = int(re_empato.group(2))
                st.metric("Probabilidad No Perder", f"{porcentaje}%")
                
                if porcentaje >= 80:
                    st.success("✅ DECISIÓN: Apuesta por Local o Empate (1X)")
                else:
                    st.warning("⚠️ DECISIÓN: Riesgo moderado, no se recomienda apuesta fija.")
            else:
                st.info("No se detectó la fila 'Empató o Ganó'. Revisa el texto extraído en el botón de arriba.")

    except Exception as e:
        st.error(f"Ocurrió un error inesperado: {e}")
