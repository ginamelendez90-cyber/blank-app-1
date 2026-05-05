import streamlit as st
import pytesseract
from PIL import Image
import shutil
import re

# --- CONFIGURACIÓN DE TESSERACT ---
t_path = shutil.which("tesseract")
if t_path:
    pytesseract.pytesseract.tesseract_cmd = t_path

st.set_page_config(page_title="Radar de Valor Avanzado", layout="wide")

# --- LÓGICA DE EXTRACCIÓN MEJORADA ---
def extraer_datos_avanzados(texto):
    def buscar(patron):
        m = re.search(patron, texto, re.IGNORECASE)
        return m.groups() if m else None

    return {
        "ganar_empate": buscar(r"(\d+)%\s*Empató o Ganó\s*(\d+)%"),
        "goles_c": buscar(r"(\d+\.\d+)\s*Goles convertidos\s*(\d+\.\d+)"),
        "remates_arco": buscar(r"(\d+\.\d+)\s*Remates al arco\s*(\d+\.\d+)"),
        "corners": buscar(r"(\d+\.\d+)\s*Corners\s*(\d+\.\d+)"),
        "tarjetas": buscar(r"(\d+\.\d+)\s*Tarjetas\s*(\d+\.\d+)")
    }

# --- INTERFAZ ---
st.title("⚽ Radar de Valor: Inteligencia de Mercados")
st.sidebar.header("Entrada de Datos")
metodo = st.sidebar.radio("Método:", ["Pegar Texto", "Imagen (OCR)"])

texto_analizar = ""
if metodo == "Pegar Texto":
    texto_analizar = st.sidebar.text_area("Pega los datos de 365Scores aquí:", height=250)
else:
    archivo = st.sidebar.file_uploader("Sube captura", type=['png', 'jpg'])
    if archivo:
        texto_analizar = pytesseract.image_to_string(Image.open(archivo), lang='spa')

if texto_analizar:
    data = extraer_datos_avanzados(texto_analizar)
    
    # --- BLOQUE 1: EFICIENCIA OFENSIVA (NUEVO) ---
    st.subheader("🔥 Eficiencia y Peligrosidad")
    c1, c2, c3 = st.columns(3)
    
    if data["goles_c"] and data["remates_arco"]:
        # Cálculo de Efectividad (Remates al arco para hacer 1 gol)
        ef_loc = round(float(data["remates_arco"][0]) / float(data["goles_c"][0]), 2)
        ef_vis = round(float(data["remates_arco"][1]) / float(data["goles_c"][1]), 2)
        
        c1.metric("Efectividad Local", f"{ef_loc} tiros/gol", delta_color="inverse")
        c2.metric("Efectividad Visita", f"{ef_vis} tiros/gol", delta_color="inverse")
        c3.metric("Peligro Visita", f"{data['remates_arco'][1]} tiros a puerta")

    # --- BLOQUE 2: PROYECCIÓN DE CORNERS Y TARJETAS (NUEVO) ---
    st.divider()
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.write("### 🚩 Mercado de Corners")
        if data["corners"]:
            total_corners = float(data["corners"][0]) + float(data["corners"][1])
            st.write(f"**Promedio Total:** {total_corners} por partido")
            if total_corners > 10.5:
                st.success("Sugerencia: Over 9.5 Corners (Tendencia Alta)")
            else:
                st.info("Sugerencia: Under 11.5 Corners")

    with col_b:
        st.write("### 🟨 Mercado de Disciplina")
        if data["tarjetas"]:
            total_t = float(data["tarjetas"][0]) + float(data["tarjetas"][1])
            st.write(f"**Intensidad:** {total_t} tarjetas/partido")
            if total_t > 4.5:
                st.warning("Sugerencia: Over 3.5 Tarjetas (Partido Friccionado)")

    # --- BLOQUE 3: DECISIÓN FINAL BASADA EN TUS REGLAS ---
    st.divider()
    st.subheader("🤖 Recomendación Estratégica")
    
    if data["ganar_empate"]:
        prob_local = int(data["ganar_empate"][0])
        if prob_local >= 80:
            st.success("🏆 PICK PRINCIPAL: Doble Oportunidad Local (1X)")
            st.write(f"Fundamento: Imbatibilidad del {prob_local}% en casa.")
        elif data["goles_c"] and float(data["goles_c"][1]) > 1.80:
            st.warning("🚀 PICK ALTERNATIVO: Gana Visitante (DNB)")
            st.write("Fundamento: Alta eficiencia goleadora del visitante (1.91 goles/partido).")
else:
    st.info("Sube o pega los datos para iniciar el análisis estadístico.")
