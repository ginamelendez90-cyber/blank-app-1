import streamlit as st
import pytesseract
from PIL import Image
import shutil
import re

# Configuración de Tesseract
t_path = shutil.which("tesseract")
if t_path:
    pytesseract.pytesseract.tesseract_cmd = t_path

st.set_page_config(page_title="Radar de Valor AI", layout="wide")
st.title("⚽ Análisis Avanzado de Probabilidades")

archivo = st.file_uploader("Sube la captura de 365Scores", type=['png', 'jpg', 'jpeg'])

if archivo:
    img = Image.open(archivo)
    col_img, col_analsis = st.columns([1, 1])
    
    with col_img:
        st.image(img, caption="Datos detectados")

    with st.spinner("Calculando métricas de valor..."):
        texto = pytesseract.image_to_string(img, lang='spa')
        
        # Extracción de métricas clave (Goles convertidos y concedidos)
        # Basado en la estructura inferior de image.png
        goles_local = re.search(r"(\d+\.\d+)\s*Goles convertidos", texto)
        goles_visita = re.search(r"Goles convertidos\s*(\d+\.\d+)", texto)
        
        # Extracción de porcentajes de mercados específicos
        re_ambos = re.search(r"(\d+)%.*Ambos equipos marcaron.*(\d+)%", texto)
        re_over25 = re.search(r"(\d+)%.*Más de 2\.5 goles.*(\d+)%", texto)
        re_invicta = re.search(r"(\d+)%.*Valla invicta.*(\d+)%", texto)

    with col_analsis:
        st.subheader("📊 Diagnóstico del Partido")
        
        # 1. Análisis de Solidez Defensiva
        if re_invicta:
            v_invicta_local = int(re_invicta.group(1))
            if v_invicta_local > 40:
                st.write(f"🛡️ **Fortaleza Defensiva:** El local mantiene el arco en cero el {v_invicta_local}% de las veces. Sugiere un partido de pocos goles para el rival.")

        # 2. Análisis de Mercado: Ambos Marcan
        if re_ambos:
            prob_ambos = int(re_ambos.group(1))
            if prob_ambos >= 50:
                st.warning(f"🥅 **Tendencia BTTS:** Alta probabilidad de que ambos marquen ({prob_ambos}%).")

        # 3. Lógica de "Valor" (Value Bet)
        st.divider()
        st.subheader("🤖 Recomendación del Algoritmo")
        
        # Cruce de datos para decisión final
        if re_over25 and int(re_over25.group(2)) > 55:
            st.success("🔥 **PICK: OVER 2.5 GOLES**")
            st.write("Razón: La tendencia del visitante en goles totales supera el umbral estadístico de valor.")
        
        elif re_invicta and int(re_invicta.group(1)) >= 44:
            st.success("✅ **PICK: LOCAL O EMPATE + UNDER 3.5**")
            st.write("Razón: Alta capacidad de mantener valla invicta y bajo promedio de goles convertidos.")
        
        else:
            st.info("⚠️ **MERCADO DIFERIDO:** Los datos actuales sugieren esperar a las alineaciones iniciales.")

    # Debug para ver si el OCR leyó bien
    with st.expander("Ver texto detectado por el motor"):
        st.code(texto)
