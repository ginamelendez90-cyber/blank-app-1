import streamlit as st
import pytesseract
from PIL import Image
import shutil
import re

# --- CONFIGURACIÓN DE MOTOR ---
t_path = shutil.which("tesseract")
if t_path:
    pytesseract.pytesseract.tesseract_cmd = t_path

st.set_page_config(page_title="Radar de Valor Pro", layout="wide")

# --- FUNCIONALIDAD DE BORRADO ---
if 'texto_pegar' not in st.session_state:
    st.session_state['texto_pegar'] = ""

def borrar_texto():
    st.session_state['texto_pegar'] = ""

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
metodo = st.radio("Método de entrada:", ["Pegar Texto", "Imagen (OCR)"], horizontal=True)
texto_input = ""

if metodo == "Pegar Texto":
    # Contenedor para los botones de acción rápida
    col_btn1, col_btn2 = st.columns([1, 5])
    with col_btn1:
        if st.button("🗑️ Borrar todo"):
            borrar_texto()
            st.rerun() # Recarga para limpiar el área inmediatamente
    
    texto_input = st.text_area(
        "Pega los datos de 365Scores aquí:", 
        value=st.session_state['texto_pegar'],
        height=200,
        key="area_datos"
    )
    # Actualizamos el estado con lo que se escriba
    st.session_state['texto_pegar'] = texto_input

else:
    archivo = st.file_uploader("Sube captura del partido", type=['png', 'jpg', 'jpeg'])
    if archivo:
        with st.spinner("Leyendo imagen..."):
            texto_input = pytesseract.image_to_string(Image.open(archivo), lang='spa')

# --- PROCESAMIENTO Y VISUALIZACIÓN ---
if texto_input:
    d = extraer_todo(texto_input)
    
    # Fila 1: Probabilidades de Mercado
    st.subheader("📈 Probabilidades de Mercado")
    f1_c1, f1_c2, f1_c3, f1_c4 = st.columns(4)
    
    with f1_c1:
        if d["ganar_empate"]: st.metric("1X (Local)", f"{d['ganar_empate'][1]}%")
    with f1_c2:
        if d["btts"]: st.metric("Ambos Marcan", f"{d['btts'][1]}%")
    with f1_c3:
        if d["over25"]: st.metric("Over 2.5 Goles", f"{d['over25'][1]}%")
    with f1_c4:
        if d["invicta"]: st.metric("Valla Invicta L", f"{d['invicta'][1]}%")

    # Fila 2: Análisis de Desempeño
    st.divider()
    st.subheader("🎯 Análisis de Eficiencia")
    f2_c1, f2_c2, f2_c3 = st.columns(3)

    if d["goles_c"] and d["remates_arco"]:
        ef_vis = round(float(d["remates_arco"][1]) / float(d["goles_c"][1]), 2)
        f2_c1.metric("Letalidad Visita", f"{ef_vis} tiros/gol")
        f2_c2.metric("Goles Promedio V", d["goles_c"][1])
        f2_c3.metric("Remates Arco V", d["remates_arco"][1])

    # Fila 3: Otros Mercados
    st.divider()
    f3_c1, f3_c2 = st.columns(2)
    with f3_c1:
        if d["corners"]:
            total_c = float(d["corners"][0]) + float(d["corners"][1])
            st.write(f"🚩 **Corners Totales proyectados:** {total_c}")
            st.progress(min(total_c/15, 1.0))
    with f3_c2:
        if d["tarjetas"]:
            total_t = float(d["tarjetas"][0]) + float(d["tarjetas"][1])
            st.write(f"🟨 **Intensidad de Tarjetas:** {total_t}")
            st.progress(min(total_t/8, 1.0))

    # Recomendación Final
    st.divider()
    if d["ganar_empate"] and int(d["ganar_empate"][1]) >= 85:
        st.success(f"🏆 **PICK:** Doble Oportunidad Local (1X) - Confianza {d['ganar_empate'][1]}%")
    elif d["over25"] and int(d["over25"][1]) >= 55:
        st.warning("🔥 **PICK:** Over 2.5 Goles - Basado en tendencia y remates.")
    else:
        st.info("⚖️ **ESTADO:** Sin tendencia fija. Mercado de Corners sugerido.")

else:
    st.info("💡 Consejo: Usa el botón 'Borrar todo' para limpiar el campo antes de pegar datos de un nuevo partido.")
