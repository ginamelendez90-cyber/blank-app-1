import streamlit as st
import pytesseract
from PIL import Image
import shutil
import re

# --- CONFIGURACIÓN DE MOTOR ---
t_path = shutil.which("tesseract")
if t_path:
    pytesseract.pytesseract.tesseract_cmd = t_path

st.set_page_config(page_title="Radar de Valor Total", layout="wide")

def extraer_todo(texto):
    def buscar(patron):
        m = re.search(patron, texto, re.IGNORECASE)
        return m.groups() if m else None

    return {
        "ganar_empate": buscar(r"(\d+)\s*\((\d+)%\)\s*Empató o Ganó"),
        "btts": buscar(r"(\d+)\s*\((\d+)%\)\s*Ambos equipos marcaron"),
        "over25": buscar(r"(\d+)\s*\((\d+)%\)\s*Más de 2\.5 goles"),
        "invicta": buscar(r"(\d+)\s*\((\d+)%\)\s*Valla invicta"),
        "goles_c": buscar(r"(\d+\.\d+)\s*Goles convertidos\s*(\d+\.\d+)"),
        "remates_arco": buscar(r"(\d+\.\d+)\s*Remates al arco\s*(\d+\.\d+)"),
        "corners": buscar(r"(\d+\.\d+)\s*Corners\s*(\d+\.\d+)"),
        "tarjetas": buscar(r"(\d+\.\d+)\s*Tarjetas\s*(\d+\.\d+)")
    }

st.title("⚽ Consola de Predicción Integral")

# Entrada de datos
metodo = st.radio("Entrada:", ["Pegar Texto", "Imagen (OCR)"], horizontal=True)
texto_input = ""

if metodo == "Pegar Texto":
    texto_input = st.text_area("Pega los datos aquí:", height=150)
else:
    archivo = st.file_uploader("Sube captura", type=['png', 'jpg'])
    if archivo:
        texto_input = pytesseract.image_to_string(Image.open(archivo), lang='spa')

if texto_input:
    d = extraer_todo(texto_input)
    
    # --- FILA 1: PROBABILIDADES DE MERCADO (LO QUE TENÍAS ANTES) ---
    st.subheader("📈 Probabilidades de Mercado")
    f1_c1, f1_c2, f1_c3, f1_c4 = st.columns(4)
    
    with f1_c1:
        if d["ganar_empate"]:
            st.metric("1X (Local)", f"{d['ganar_empate'][1]}%")
    with f1_c2:
        if d["btts"]:
            st.metric("Ambos Marcan", f"{d['btts'][1]}%")
    with f1_c3:
        if d["over25"]:
            st.metric("Over 2.5 Goles", f"{d['over25'][1]}%")
    with f1_c4:
        if d["invicta"]:
            st.metric("Valla Invicta L", f"{d['invicta'][1]}%")

    # --- FILA 2: EFICIENCIA Y VOLUMEN (LO NUEVO) ---
    st.divider()
    st.subheader("🎯 Análisis de Desempeño")
    f2_c1, f2_c2, f2_c3 = st.columns(3)

    if d["goles_c"] and d["remates_arco"]:
        ef_vis = round(float(d["remates_arco"][1]) / float(d["goles_c"][1]), 2)
        f2_c1.metric("Letalidad Visita", f"{ef_vis} tiros/gol")
        f2_c2.metric("Goles Promedio V", d["goles_c"][1])
        f2_c3.metric("Remates Arco V", d["remates_arco"][1])

    # --- FILA 3: CORNERS Y TARJETAS ---
    st.divider()
    f3_c1, f3_c2 = st.columns(2)
    
    with f3_c1:
        if d["corners"]:
            total_c = float(d["corners"][0]) + float(d["corners"][1])
            st.write(f"🚩 **Corners Totales:** {total_c}")
            st.progress(min(total_c/15, 1.0)) # Barra visual de volumen
    
    with f3_c2:
        if d["tarjetas"]:
            total_t = float(d["tarjetas"][0]) + float(d["tarjetas"][1])
            st.write(f"🟨 **Intensidad de Tarjetas:** {total_t}")
            st.progress(min(total_t/8, 1.0))

    # --- RECOMENDACIÓN FINAL ---
    st.divider()
    if d["ganar_empate"] and int(d["ganar_empate"][1]) >= 85:
        st.success("🏆 **RECOMENDACIÓN:** Doble Oportunidad Local (1X). Seguridad alta por racha imbatida.")
    elif d["over25"] and int(d["over25"][1]) >= 55:
        st.warning("🔥 **RECOMENDACIÓN:** Over 2.5 Goles. El volumen de remates y tendencia lo respaldan.")
    else:
        st.info("⚖️ **RECOMENDACIÓN:** Sin tendencia clara para mercados principales. Revisa Corners.")

else:
    st.info("Introduce datos para ver el análisis completo.")
