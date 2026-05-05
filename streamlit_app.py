import streamlit as st
import pytesseract
from PIL import Image
import shutil
import re

# Configuración del motor OCR
t_path = shutil.which("tesseract")
if t_path:
    pytesseract.pytesseract.tesseract_cmd = t_path

st.set_page_config(page_title="Radar de Valor Pro", layout="wide")
st.title("⚽ Analizador Estadístico Multimodal")

# --- BARRA LATERAL PARA ENTRADA DE DATOS ---
st.sidebar.header("📥 Entrada de Datos")
metodo = st.sidebar.radio("Selecciona método:", ["Imagen (OCR)", "Pegar Texto"])

texto_final = ""

if metodo == "Imagen (OCR)":
    archivo = st.sidebar.file_uploader("Sube la captura", type=['png', 'jpg', 'jpeg'])
    if archivo:
        img = Image.open(archivo)
        st.image(img, width=400)
        with st.spinner("Procesando imagen..."):
            texto_final = pytesseract.image_to_string(img, lang='spa')
else:
    texto_pepago = st.sidebar.text_area("Pega aquí los datos copiados:", height=300, placeholder="Todas las competiciones...")
    if texto_pepago:
        texto_final = texto_pepago

# --- LÓGICA DE PROCESAMIENTO ---
if texto_final:
    st.subheader("📝 Análisis de Resultados")
    
    # Función para extraer datos con Regex
    def buscar(patron, string):
        m = re.search(patron, string, re.IGNORECASE)
        return m.groups() if m else None

    # Extracción de porcentajes y promedios
    # Adaptado para el formato de texto pegado que enviaste
    datos = {
        "btts": buscar(r"(\d+)\s*\((\d+)%\)\s*Ambos equipos marcaron", texto_final),
        "over25": buscar(r"(\d+)\s*\((\d+)%\)\s*Más de 2\.5 goles", texto_final),
        "invicta": buscar(r"(\d+)\s*\((\d+)%\)\s*Valla invicta", texto_final),
        "goles_c": buscar(r"(\d+\.\d+)\s*Goles convertidos\s*(\d+\.\d+)", texto_final),
        "remates": buscar(r"(\d+\.\d+)\s*Remates\s*(\d+\.\d+)", texto_final)
    }

    col1, col2, col3 = st.columns(3)

    # Mostrar Métricas en pantalla
    with col1:
        if datos["btts"]:
            st.metric("BTTS (Local)", f"{datos['btts'][1]}%")
        if datos["goles_c"]:
            st.metric("Goles Conv. (Local)", datos["goles_c"][0])

    with col2:
        if datos["over25"]:
            st.metric("Over 2.5 (Local)", f"{datos['over25'][1]}%")
        if datos["goles_c"]:
            st.metric("Goles Conv. (Visita)", datos["goles_c"][1])

    with col3:
        if datos["invicta"]:
            st.metric("Valla Invicta (Local)", f"{datos['invicta'][1]}%")
        if datos["remates"]:
            st.metric("Remates (Visita)", datos["remates"][1])

    # --- RECOMENDACIÓN FINAL ---
    st.divider()
    st.subheader("🤖 Recomendación Estratégica")
    
    # Ejemplo de lógica basada en tus preferencias de apuestas
    if datos["invicta"] and int(datos["invicta"][1]) >= 25 and datos["goles_c"] and float(datos["goles_c"][1]) > 1.80:
        st.success("🎯 **OPCIÓN DE VALOR:** Gana Visitante o Empate + Over 1.5 goles")
        st.write("Razón: El visitante tiene un promedio de gol muy alto (1.91) frente a una defensa local moderada.")
    elif datos["btts"] and int(datos["btts"][1]) >= 60:
        st.warning("⚽ **ALTA PROBABILIDAD:** Ambos Equipos Marcan")
        st.write("Razón: Historial reciente muestra una tendencia clara de intercambio de goles.")
    else:
        st.info("⚖️ **ESTADO:** Partido equilibrado. Se recomienda mercado de Corners o esperar al Live.")

else:
    st.info("Esperando datos... Por favor, sube una imagen o pega el texto en la barra lateral.")
