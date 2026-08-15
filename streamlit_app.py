from datetime import datetime, timedelta
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

def verificar_actualizacion_medianoche():
    ahora = datetime.now()
    hoy_str = ahora.strftime("%Y-%m-%d")
    if st.session_state.get("ultima_fecha_verificacion") != hoy_str:
        st.toast(f"🔄 Se detectó el cambio de día a las 12:00 AM. Actualizando sistema...", icon="🕛")
        st.session_state["ultima_fecha_verificacion"] = hoy_str
        st.cache_data.clear()

def es_dia_cobro(fecha_obj):
    if fecha_obj.weekday() == 6: return False
    festivos_fijos = [(1, 1), (19, 4), (1, 5), (24, 6), (5, 7), (24, 7), (12, 10), (24, 12), (25, 12), (31, 12)]
    return (fecha_obj.day, fecha_obj.month) not in festivos_fijos

def calcular_dias_cobro_acumulados(fecha_inicio, fecha_fin):
    if fecha_inicio >= fecha_fin: return 0
    return sum(1 for d in range(1, (fecha_fin - fecha_inicio).days + 1) if es_dia_cobro(fecha_inicio + timedelta(days=d)))

def obtener_tasa_concepto(concepto_str, tasa_defecto):
    match = re.search(r'tasa:\s*([\d\.]+)', str(concepto_str), re.IGNORECASE)
    return float(match.group(1)) if match else tasa_defecto

# ==========================================
# NUEVAS FUNCIONES DE NEGOCIO REFACTORIZADAS
# ==========================================
def separar_movimientos(df_cliente):
    """Separa el historial del crédito activo actual de los ya liquidados."""
    indices_liq = df_cliente[df_cliente["Concepto"].str.contains("Crédito anterior liquidado", case=False, na=False)].index
    if not indices_liq.empty:
        ult_idx = indices_liq[-1]
        return df_cliente.loc[df_cliente.index > ult_idx].copy(), df_cliente.loc[df_cliente.index <= ult_idx].copy()
    return df_cliente.copy(), pd.DataFrame()

def calcular_visuales(df_mov, es_cliente_bs, tasa_bs_usd):
    """Calcula el Cargo y Abono visual (Bs. o $) según la moneda del cliente."""
    if df_mov.empty: return df_mov
    
    def calc_cargo(row):
        cargo, concepto = float(row["Cargo"]), str(row["Concepto"])
        if es_cliente_bs:
            tasa_fija = obtener_tasa_concepto(concepto, tasa_bs_usd)
            multiplicador = 1.75 if "interés aplicado" in concepto.lower() or "interes aplicado" in concepto.lower() else 1.0
            return round(cargo * multiplicador * tasa_fija, 2)
        return cargo

    def calc_abono(row):
        return round(float(row["Abono"]) * obtener_tasa_concepto(str(row["Concepto"]), tasa_bs_usd), 2) if es_cliente_bs else float(row["Abono"])
    
    df_mov["Cargo_Vis"] = df_mov.apply(calc_cargo, axis=1)
    df_mov["Abono_Vis"] = df_mov.apply(calc_abono, axis=1)
    return df_mov

def evaluar_estado_credito(mov_actuales, es_cliente_bs, tasa_bs_usd):
    """Centraliza la lógica para calcular mora, saldo pendiente y estado del crédito."""
    mov_actuales = calcular_visuales(mov_actuales, es_cliente_bs, tasa_bs_usd)
    prestamo_vis = mov_actuales["Cargo_Vis"].sum() if not mov_actuales.empty else 0.0
    pagos_vis = mov_actuales["Abono_Vis"].sum() if not mov_actuales.empty else 0.0
    saldo_vis = prestamo_vis - pagos_vis

    res = {
        "prestamo_vis": prestamo_vis, "pagos_vis": pagos_vis, "saldo_vis": saldo_vis,
        "estado": "🟢 AL DÍA", "detalle": "Crédito activo o sin deuda.", "color": "info",
        "cuotas_atrasadas": 0, "monto_atraso": 0.0, "cuota_monto_vis": 0.0, "df_vista": mov_actuales
    }

    if saldo_vis <= 0 and not mov_actuales.empty:
        res.update({"estado": "✅ LIQUIDADO", "detalle": "No tienes deudas pendientes.", "color": "success"})
        return res

    fila_prestamo = mov_actuales[mov_actuales["Concepto"].str.contains("Préstamo", case=False, na=False)]
    if not fila_prestamo.empty and saldo_vis > 0:
        f_inicio = pd.to_datetime(str(fila_prestamo.iloc[0]["Fecha"])).date()
        concepto_p = str(fila_prestamo.iloc[0]["Concepto"])
        
        match_c = re.search(r'\((\d+)\s*cuotas', concepto_p, re.IGNORECASE)
        num_cuotas_p = int(match_c.group(1)) if match_c else 24
        res["cuota_monto_vis"] = prestamo_vis / num_cuotas_p if num_cuotas_p > 0 else prestamo_vis
        
        dias_cobro = max(0, calcular_dias_cobro_acumulados(f_inicio, datetime.now().date()) - 1)
        
        divisores = {"semanal": 6, "quincenal": 12, "mensual": 24}
        divisor = next((v for k, v in divisores.items() if k in concepto_p.lower()), 1)
        cuotas_esperadas = min(dias_cobro // divisor, num_cuotas_p)
        
        diferencia_pago = pagos_vis - (cuotas_esperadas * res["cuota_monto_vis"])
        
        if diferencia_pago >= -0.05:
            res.update({"estado": "🟢 AL DÍA", "detalle": "Has cubierto tus cuotas a la fecha.", "color": "success"})
        else:
            res["monto_atraso"] = abs(diferencia_pago)
            res["cuotas_atrasadas"] = max(1, int(res["monto_atraso"] // res["cuota_monto_vis"]) if res["cuota_monto_vis"] > 0 else 1)
            res.update({
                "estado": "🔴 ATRASADO", 
                "detalle": f"Presentas un retraso de {res['cuotas_atrasadas']} cuota(s) equivalente a {res['monto_atraso']:,.2f}.", 
                "color": "error"
            })
    return res

def generar_boton_wa(link_wa, texto, color="#25D366"):
    """Genera el botón HTML consistente para WhatsApp."""
    return f"""
    <a href="{link_wa}" target="_blank" style="text-decoration: none;">
        <div style="background-color: {color}; color: white; padding: 10px 20px; text-align: center; 
                    font-weight: bold; border-radius: 8px; margin-top: 10px; cursor: pointer;">
            {texto}
        </div>
    </a>"""

# ==========================================
# CONFIGURACIÓN Y CONEXIÓN
# ==========================================
st.set_page_config(page_title="Sistema de Cobros & Finanzas", page_icon="💹", layout="wide", initial_sidebar_state="expanded")
verificar_actualizacion_medianoche()
conn = st.connection("gsheets", type=GSheetsConnection)

# (Aquí irían tus funciones de DB originales: obtener_hoja, cargar_configuracion_persistente, calcular_saldo_cuenta)
# Omitidas temporalmente por brevedad, usa las que ya tienes.
tasa_bs_usd, codigos_bs_str = 65.0, "CLI-001, CLI-002" # Ejemplo, reemplazar con cargar_configuracion_persistente()
lista_clientes_bs = [c.strip().upper() for c in codigos_bs_str.split(",") if c.strip()]

# ==========================================
# BARRA LATERAL
# ==========================================
# (Misma barra lateral de tu script original)
clave_admin = st.sidebar.text_input("Contraseña:", type="password")
es_admin_autenticado = clave_admin == "Kilometro12@"
modo_vista = st.sidebar.radio("Navegación Principal:", ["👥 Portal del Cliente", "💼 Panel de Administrador"])

# ==========================================
# FLUJO PRINCIPAL
# ==========================================
if modo_vista == "👥 Portal del Cliente":
    st.title("👥 Portal de Atención al Cliente")
    # ... (lectura de parámetros) ...
    codigo_url = "CLI-001" # Simulado
    
    opcion_cliente = st.segmented_control("¿Qué deseas realizar?:", ["🔎 Consultar Estado de Cuenta", "📲 Reportar un Pago"])
    
    if opcion_cliente == "🔎 Consultar Estado de Cuenta":
        codigo_cliente = st.text_input("Ingrese su Código de Cliente:", value=codigo_url).strip().upper()
        if st.button("🔎 Consultar") or codigo_url:
            df = conn.read(ttl=0, usecols=["Fecha", "Codigo", "Nombre", "Concepto", "Cargo", "Abono"])
            df["Codigo"] = df["Codigo"].astype(str).str.strip().str.upper()
            resultado = df[df["Codigo"] == codigo_cliente]

            if not resultado.empty:
                nombre = resultado.iloc[0]["Nombre"]
                es_cliente_bs = codigo_cliente in lista_clientes_bs
                moneda_label = "Bs." if es_cliente_bs else "$"

                # USO DE LAS NUEVAS FUNCIONES REFACTORIZADAS:
                mov_actuales, mov_historicos = separar_movimientos(resultado)
                estado_info = evaluar_estado_credito(mov_actuales, es_cliente_bs, tasa_bs_usd)

                st.subheader(f"Bienvenido/a, **{nombre}**")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("📌 Deuda Total Actual", f"{moneda_label} {estado_info['prestamo_vis']:,.2f}")
                m2.metric("💵 Total Abonado", f"{moneda_label} {estado_info['pagos_vis']:,.2f}")
                m3.metric("⚠️ Saldo Pendiente", f"{moneda_label} {estado_info['saldo_vis']:,.2f}", delta=f"-{moneda_label} {estado_info['saldo_vis']:,.2f}", delta_color="inverse")
                m4.metric("Estatus del Crédito", estado_info['estado'])

                if estado_info['color'] == "error": st.error(f"⚠️ **Estatus:** {estado_info['estado']} — {estado_info['detalle']}")
                elif estado_info['color'] == "success": st.success(f"🎉 **Estatus:** {estado_info['estado']} — {estado_info['detalle']}")
                else: st.info(f"ℹ️ **Estatus:** {estado_info['estado']} — {estado_info['detalle']}")

                # Renderizar DataFrames...

    elif opcion_cliente == "📲 Reportar un Pago":
        # ... formulario original ...
        if st.button("Registrar Pago"):
            # Generar enlace WA usando función genérica
            link_wame = f"https://wa.me/{TELEFONO_ADMIN}?text=Prueba"
            st.markdown(generar_boton_wa(link_wame, "📤 Enviar Comprobante por WhatsApp 📲"), unsafe_allow_html=True)

else:
    st.title("💼 Dashboard de Administración")
    if es_admin_autenticado:
        seccion_admin = st.segmented_control("Seleccione:", ["⏳ Abonos por Verificar", "🚨 Clientes Atrasados", "📊 Flujo de Caja"])
        
        if seccion_admin == "🚨 Clientes Atrasados":
            df_existente = conn.read(ttl=0)
            df_clientes = df_existente[~df_existente["Codigo"].str.contains("CUENTA_|GASTO_|CAJA_|PASIVO_EXT", na=False)]
            lista_atrasados = []

            for cod in df_clientes["Codigo"].unique():
                cod_clean = str(cod).strip().upper()
                resultado = df_clientes[df_clientes["Codigo"] == cod_clean]
                es_cliente_bs = cod_clean in lista_clientes_bs
                
                # REUTILIZACIÓN DE LA MISMA LÓGICA DE ESTADO:
                mov_actuales, _ = separar_movimientos(resultado)
                if mov_actuales.empty: continue
                
                estado_info = evaluar_estado_credito(mov_actuales, es_cliente_bs, tasa_bs_usd)
                
                if estado_info["estado"] == "🔴 ATRASADO":
                    moneda_label = "Bs." if es_cliente_bs else "$"
                    msg_wa = urllib.parse.quote(f"Hola, presentas un retraso de {estado_info['cuotas_atrasadas']} cuota(s).")
                    
                    lista_atrasados.append({
                        "Código": cod_clean, "Cliente": resultado.iloc[0]["Nombre"],
                        "Moneda": "Bolívares" if es_cliente_bs else "Dólares",
                        "Cuotas Atrasadas": estado_info["cuotas_atrasadas"],
                        "Monto Atraso": estado_info["monto_atraso"],
                        "Saldo Pendiente": estado_info["saldo_vis"],
                        "Valor Cuota": estado_info["cuota_monto_vis"],
                        "Símbolo": moneda_label, "WhatsApp_Msg": msg_wa
                    })
            
            # (Renderizado de métricas y botones de cobro usando generar_boton_wa)
