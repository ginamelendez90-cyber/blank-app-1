from datetime import datetime, timedelta, date
import re
import urllib.parse
import uuid
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# ==========================================
# CONFIGURACIÓN GENERAL Y HELPER DE FECHAS
# ==========================================
TELEFONO_ADMIN = "584123801615"

def es_dia_cobro(fecha_obj):
    if fecha_obj.weekday() == 6: return False
    festivos_fijos = [(1, 1), (19, 4), (1, 5), (24, 6), (5, 7), (24, 7), (12, 10), (24, 12), (25, 12), (31, 12)]
    return (fecha_obj.day, fecha_obj.month) not in festivos_fijos

def calcular_dias_cobro_acumulados(fecha_inicio, fecha_fin):
    if fecha_inicio >= fecha_fin: return 0
    dias_validos = 0
    cur = fecha_inicio + timedelta(days=1)
    while cur <= fecha_fin:
        if es_dia_cobro(cur): dias_validos += 1
        cur += timedelta(days=1)
    return dias_validos

def obtener_tasa_concepto(concepto_str, tasa_defecto):
    match = re.search(r'tasa:\s*([\d\.]+)', str(concepto_str), re.IGNORECASE)
    if match:
        try: return float(match.group(1))
        except: pass
    return tasa_defecto

st.set_page_config(page_title="Sistema de Cobros & Finanzas", page_icon="💳", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)

# ==========================================
# FUNCIONES DE BASE DE DATOS
# ==========================================
def obtener_cliente_gspread():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["connections"]["gsheets"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

def obtener_hoja(nombre_hoja="Sheet1"):
    client = obtener_cliente_gspread()
    url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    sh = client.open_by_url(url)
    try: return sh.worksheet(nombre_hoja)
    except: return sh.get_worksheet(0)

def cargar_configuracion_persistente():
    try:
        ws = obtener_hoja("CONFIGURACION")
        records = ws.get_all_records()
        config_dict = {r["Parametro"]: str(r["Valor"]) for r in records}
        return float(config_dict.get("tasa_bs_usd", 65.0)), config_dict.get("codigos_bs", "CLI-001")
    except: return 65.0, "CLI-001"

def calcular_saldo_cuenta(df, cuenta_nombre):
    if df.empty: return 0.0
    def normalizar(t): return str(t).upper().replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")
    
    df_clean = df.copy()
    df_clean["Codigo_norm"] = df_clean["Codigo"].apply(normalizar)
    cuenta_norm = normalizar(cuenta_nombre)
    
    cond = (df_clean["Codigo_norm"].str.contains(f"CAJA_{cuenta_norm}") | 
            df_clean["Codigo_norm"].str.contains(f"CUENTA_{cuenta_norm}"))
    return float(df_clean[cond]["Abono"].sum() - df_clean[cond]["Cargo"].sum())

# Carga inicial
tasa_bs_usd, codigos_bs_str = cargar_configuracion_persistente()
lista_clientes_bs = [c.strip().upper() for c in codigos_bs_str.split(",")]

# ==========================================
# INTERFAZ PRINCIPAL
# ==========================================
modo_vista = st.sidebar.radio("Navegación:", ["👤 Portal del Cliente", "💼 Panel de Administrador"])

if modo_vista == "💼 Panel de Administrador":
    seccion_admin = st.sidebar.selectbox("Sección:", [
        "📉 Gastos Operativos", "📊 Flujo de Caja", "⏳ Abonos por Verificar"
    ])

    # ------------------------------------------
    # LOGICA DE GASTOS ACTUALIZADA
    # ------------------------------------------
    if seccion_admin == "📉 Gastos Operativos":
        st.subheader("📉 Registrar Gasto Operativo")
        with st.form("form_gastos_op"):
            fga = st.date_input("Fecha", datetime.now())
            cga = st.selectbox("¿De qué cuenta sale el dinero?:", ["Efectivo", "Pago Móvil", "Binance"])
            dga = st.text_input("Detalle del Gasto")
            mga = st.number_input("Monto USD ($):", min_value=0.01)

            if st.form_submit_button("💾 Registrar Gasto y Rebajar de Caja"):
                if dga and mga > 0:
                    try:
                        sheet = obtener_hoja()
                        # Registro 1: El gasto contable
                        sheet.append_row([fga.strftime("%Y-%m-%d"), f"GASTO_{cga.upper()}", f"Gastos ({cga})", dga, float(mga), 0.0])
                        # Registro 2: Descuento real de la cuenta
                        sheet.append_row([fga.strftime("%Y-%m-%d"), f"CUENTA_{cga.upper()}", f"Ajuste por Gasto", f"Rebaja por: {dga}", float(mga), 0.0])
                        
                        st.cache_data.clear()
                        st.success(f"✅ Gasto de ${mga} registrado y descontado de {cga}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    # Resto de secciones (Flujo, Abonos, etc.) se mantienen igual...
    elif seccion_admin == "📊 Flujo de Caja":
        df_existente = conn.read(ttl=0)
        efectivo = calcular_saldo_cuenta(df_existente, "Efectivo")
        pm = calcular_saldo_cuenta(df_existente, "Pago Móvil")
        binance = calcular_saldo_cuenta(df_existente, "Binance")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Efectivo", f"${efectivo:,.2f}")
        c2.metric("Pago Móvil", f"${pm:,.2f}")
        c3.metric("Binance", f"${binance:,.2f}")

else:
    st.title("👤 Portal del Cliente")
    st.info("Funcionalidad de cliente activa.")
