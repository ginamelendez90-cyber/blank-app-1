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

def verificar_actualizacion_medianoche():
    """Verifica si ha cruzado las 12:00 AM para ejecutar procesos o limpieza diaria."""
    ahora = datetime.now()
    hoy_str = ahora.strftime("%Y-%m-%d")
    
    if "ultima_fecha_verificacion" not in st.session_state:
        st.session_state["ultima_fecha_verificacion"] = hoy_str
    
    if st.session_state["ultima_fecha_verificacion"] != hoy_str:
        st.toast(f"🔄 Se detectó el cambio de día a las 12:00 AM. Actualizando sistema...", icon="🕛")
        st.session_state["ultima_fecha_verificacion"] = hoy_str
        st.cache_data.clear()

def es_dia_cobro(fecha_obj):
    """Devuelve False si es Domingo o Feriado Nacional."""
    if fecha_obj.weekday() == 6:  # 6 = Domingo
        return False
    
    festivos_fijos = [
        (1, 1),   # Año Nuevo
        (19, 4),  # Declaración de Independencia
        (1, 5),   # Día del Trabajador
        (24, 6),  # Batalla de Carabobo
        (5, 7),   # Día de la Independencia
        (24, 7),  # Natalicio de Simón Bolívar
        (12, 10), # Día de la Resistencia Indígena
        (24, 12), # Nochebuena
        (25, 12), # Navidad
        (31, 12)  # Fin de Año
    ]
    if (fecha_obj.day, fecha_obj.month) in festivos_fijos:
        return False
        
    return True

def calcular_dias_cobro_acumulados(fecha_inicio, fecha_fin):
    """Cuenta los días hábiles de cobro transcurridos excluyendo domingos y feriados."""
    if fecha_inicio >= fecha_fin:
        return 0
    dias_validos = 0
    cur = fecha_inicio + timedelta(days=1)
    while cur <= fecha_fin:
        if es_dia_cobro(cur):
            dias_validos += 1
        cur += timedelta(days=1)
    return dias_validos

def obtener_tasa_concepto(concepto_str, tasa_defecto):
    """Extrae la tasa fija registrada en la descripción del concepto si existe."""
    match = re.search(r'tasa:\s*([\d\.]+)', str(concepto_str), re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return tasa_defecto

st.set_page_config(
    page_title="Sistema de Cobros & Finanzas",
    page_icon="💹",
    layout="wide",
    initial_sidebar_state="expanded",
)

verificar_actualizacion_medianoche()

st.markdown(
    """
    <style>
    .stMetric {
        background-color: #1e222b;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #2e3440;
    }
    div[data-testid="stSidebarNav"] {
        padding-top: 10px;
    }
    div[data-testid="stForm"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 15px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

conn = st.connection("gsheets", type=GSheetsConnection)

# ==========================================
# FUNCIONES AUXILIARES DE BASE DE DATOS
# ==========================================
def obtener_cliente_gspread():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds_dict = dict(st.secrets["connections"]["gsheets"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

def obtener_hoja(nombre_hoja="Sheet1"):
    client = obtener_cliente_gspread()
    url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    sh = client.open_by_url(url)

    if nombre_hoja == "CONFIGURACION":
        try:
            return sh.worksheet("CONFIGURACION")
        except Exception:
            ws = sh.add_worksheet(title="CONFIGURACION", rows="10", cols="2")
            ws.append_row(["Parametro", "Valor"])
            ws.append_row(["tasa_bs_usd", "65.0"])
            ws.append_row(["codigos_bs", "CLI-001, CLI-002"])
            return ws

    if nombre_hoja == "PAGOS_PENDIENTES":
        try:
            return sh.worksheet("PAGOS_PENDIENTES")
        except Exception:
            ws = sh.add_worksheet(
                title="PAGOS_PENDIENTES", rows="1000", cols="10"
            )
            ws.append_row(
                [
                    "ID",
                    "Fecha",
                    "Codigo",
                    "Nombre",
                    "Cuenta",
                    "Referencia",
                    "Monto",
                    "Estado",
                ]
            )
            return ws

    try:
        return sh.worksheet(nombre_hoja)
    except Exception:
        try:
            return sh.worksheet("Hoja 1")
        except Exception:
            return sh.get_worksheet(0)

def cargar_configuracion_persistente():
    try:
        ws = obtener_hoja("CONFIGURACION")
        records = ws.get_all_records()
        config_dict = {r["Parametro"]: str(r["Valor"]) for r in records}

        tasa = float(config_dict.get("tasa_bs_usd", 65.0))
        codigos = config_dict.get("codigos_bs", "CLI-001, CLI-002")
        return tasa, codigos
    except Exception:
        return 65.0, "CLI-001, CLI-002"

def guardar_configuracion_persistente(nueva_tasa, nuevos_codigos):
    try:
        ws = obtener_hoja("CONFIGURACION")
        ws.update_cell(2, 2, str(nueva_tasa))
        ws.update_cell(3, 2, str(nuevos_codigos))
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error al guardar configuración: {e}")
        return False

tasa_bs_usd, codigos_bs_str = cargar_configuracion_persistente()
lista_clientes_bs = [
    c.strip().upper() for c in codigos_bs_str.split(",") if c.strip()
]

# ==========================================
# BARRA LATERAL (AUTENTICACIÓN Y NAVEGACIÓN)
# ==========================================
st.sidebar.image(
    "https://img.icons8.com/?size=100&id=51oKaN3XSMKu&format=png&color=000000", width=80
)
st.sidebar.title("Control Financiero")
st.sidebar.caption("Gestión de Cobros, Cuentas y Préstamos v4.3")
st.sidebar.divider()

st.sidebar.subheader("🔒 Acceso Admin")
clave_admin = st.sidebar.text_input(
    "Contraseña:", type="password", key="clave_admin_sidebar"
)
es_admin_autenticado = clave_admin == "Kilometro12@"

if es_admin_autenticado:
    st.sidebar.success("🟢 Sesión Activa")
    st.sidebar.divider()

    with st.sidebar.expander("💱 Configuración Bs (Admin)", expanded=False):
        with st.form("form_config_bs_admin"):
            nueva_tasa = st.number_input(
                "Tasa cobrada en Bs / $:",
                min_value=1.0,
                value=float(tasa_bs_usd),
                step=0.5,
            )

            nuevos_codigos = st.text_input(
                "Códigos en Bs (separados por coma):",
                value=codigos_bs_str,
            )

            btn_guardar_config = st.form_submit_button(
                "💾 Guardar Cambios Permanentes", use_container_width=True
            )

            if btn_guardar_config:
                if guardar_configuracion_persistente(nueva_tasa, nuevos_codigos):
                    st.sidebar.success("✅ ¡Configuración guardada!")
                    st.rerun()

elif clave_admin != "":
    st.sidebar.error("🔴 Clave incorrecta")

st.sidebar.divider()

modo_vista = st.sidebar.radio(
    "Navegación Principal:",
    ["👥 Portal del Cliente", "💼 Panel de Administrador"],
    index=0,
)

# ==========================================
# PESTAÑA 1: PORTAL DEL CLIENTE (CON CUADRO DE DÍAS HÁBILES)
# ==========================================
if modo_vista == "👥 Portal del Cliente":
    st.title("👥 Portal de Atención al Cliente")

    query_params = st.query_params
    codigo_url = query_params.get("cliente", "").strip().upper()
    accion_url = query_params.get("accion", "").strip().lower()

    index_defecto = 1 if accion_url == "reportar" else 0
    opciones_menu = ["🔎 Consultar Estado de Cuenta", "📲 Reportar un Pago"]

    opcion_cliente = st.segmented_control(
        "¿Qué deseas realizar?:",
        opciones_menu,
        default=opciones_menu[index_defecto],
    )
    st.divider()

    nombre_autocompletado = ""
    if codigo_url:
        try:
            df_temp = conn.read(ttl=0, usecols=["Codigo", "Nombre"])
            df_temp["Codigo"] = (
                df_temp["Codigo"].astype(str).str.strip().str.upper()
            )
            match = df_temp[df_temp["Codigo"] == codigo_url]
            if not match.empty:
                nombre_autocompletado = match.iloc[0]["Nombre"]
        except Exception:
            pass

    if opcion_cliente == "🔎 Consultar Estado de Cuenta":
        st.write("Consulta el estado actual de tu crédito y tu cronograma de días hábiles de pago.")

        with st.container(border=True):
            col_busq1, col_busq2 = st.columns([3, 1])
            codigo_cliente = col_busq1.text_input(
                "Ingrese su Código de Cliente:",
                value=codigo_url,
                placeholder="Ej. CLI-001",
            )
            btn_consultar = col_busq2.button(
                "🔎 Consultar", use_container_width=True
            )

        hacer_busqueda = btn_consultar or (codigo_url != "")

        if hacer_busqueda and codigo_cliente:
            try:
                cod_clean = str(codigo_cliente).strip().upper()
                df = conn.read(
                    ttl=0,
                    usecols=[
                        "Fecha",
                        "Codigo",
                        "Nombre",
                        "Concepto",
                        "Cargo",
                        "Abono",
                    ],
                )
                df["Codigo"] = df["Codigo"].astype(str).str.strip().str.upper()
                resultado = df[df["Codigo"] == cod_clean]

                if not resultado.empty:
                    nombre = resultado.iloc[0]["Nombre"]
                    es_cliente_bs = cod_clean in lista_clientes_bs
                    moneda_label = "Bs." if es_cliente_bs else "$"

                    indices_liq = resultado[
                        resultado["Concepto"].str.contains(
                            "Crédito anterior liquidado",
                            case=False,
                            na=False,
                        )
                    ].index

                    if not indices_liq.empty:
                        ult_idx = indices_liq[-1]
                        mov_actuales = resultado.loc[resultado.index > ult_idx].copy()
                        mov_historicos = resultado.loc[resultado.index <= ult_idx].copy()
                    else:
                        mov_actuales = resultado.copy()
                        mov_historicos = pd.DataFrame()

                    def calcular_cargo_vista(row):
                        cargo = float(row["Cargo"])
                        concepto = str(row["Concepto"])
                        concepto_lower = concepto.lower()
                        if es_cliente_bs:
                            tasa_fija = obtener_tasa_concepto(concepto, tasa_bs_usd)
                            if "interés aplicado" in concepto_lower or "interes aplicado" in concepto_lower:
                                return round(cargo * 1.75 * tasa_fija, 2)
                            return round(cargo * tasa_fija, 2)
                        return cargo

                    def calcular_abono_vista(row):
                        abono = float(row["Abono"])
                        concepto = str(row["Concepto"])
                        if es_cliente_bs:
                            tasa_registro = obtener_tasa_concepto(concepto, tasa_bs_usd)
                            return round(abono * tasa_registro, 2)
                        return abono

                    if not mov_actuales.empty:
                        mov_actuales["Cargo_Vis"] = mov_actuales.apply(calcular_cargo_vista, axis=1)
                        mov_actuales["Abono_Vis"] = mov_actuales.apply(calcular_abono_vista, axis=1)

                        prestamo_vis = mov_actuales["Cargo_Vis"].sum()
                        pagos_vis = mov_actuales["Abono_Vis"].sum()
                        saldo_vis = prestamo_vis - pagos_vis
                    else:
                        prestamo_vis, pagos_vis, saldo_vis = 0.0, 0.0, 0.0

                    st.subheader(f"Bienvenido/a, **{nombre}**")

                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("📌 Deuda Total Actual", f"{moneda_label} {prestamo_vis:,.2f}")
                    m2.metric("💵 Total Abonado", f"{moneda_label} {pagos_vis:,.2f}")
                    m3.metric("⚠️ Saldo Pendiente", f"{moneda_label} {saldo_vis:,.2f}")

                    # ==========================================
                    # APARTADO: CUADRO DE DÍAS HÁBILES DE PAGO
                    # ==========================================
                    st.divider()
                    st.subheader("📅 Cuadro de Días Hábiles de Pago")
                    st.caption("Cronograma de cuotas y rango de días hábiles (excluyendo domingos y feriados nacionales)[cite: 1].")

                    fila_prestamo = mov_actuales[mov_actuales["Concepto"].str.contains("Préstamo", case=False, na=False)]

                    if not fila_prestamo.empty:
                        f_str = str(fila_prestamo.iloc[0]["Fecha"])
                        f_inicio = pd.to_datetime(f_str).date()
                        concepto_p = str(fila_prestamo.iloc[0]["Concepto"])

                        match_c = re.search(r'\((\d+)\s*cuotas', concepto_p, re.IGNORECASE)
                        num_cuotas_p = int(match_c.group(1)) if match_c else 24
                        cuota_monto_vis = prestamo_vis / num_cuotas_p if num_cuotas_p > 0 else prestamo_vis
                        frecuencia_lower = concepto_p.lower()

                        cronograma_data = []
                        cur_fecha = f_inicio
                        cuotas_generadas = 0

                        while cuotas_generadas < num_cuotas_p:
                            cur_fecha += timedelta(days=1)
                            if es_dia_cobro(cur_fecha):
                                cuotas_generadas += 1

                                incluir_cuota = False
                                if "semanal" in frecuencia_lower:
                                    if cuotas_generadas % 6 == 0 or cuotas_generadas == num_cuotas_p:
                                        incluir_cuota = True
                                elif "quincenal" in frecuencia_lower:
                                    if cuotas_generadas % 12 == 0 or cuotas_generadas == num_cuotas_p:
                                        incluir_cuota = True
                                elif "mensual" in frecuencia_lower:
                                    if cuotas_generadas % 24 == 0 or cuotas_generadas == num_cuotas_p:
                                        incluir_cuota = True
                                else:  # Diario
                                    incluir_cuota = True

                                if incluir_cuota or "diario" in frecuencia_lower:
                                    estado_cuota = "✅ Pagada / Al Día" if cuotas_generadas * cuota_monto_vis <= pagos_vis else "⏳ Pendiente"
                                    cronograma_data.append({
                                        "Cuota #": cuotas_generadas,
                                        "Fecha Hábil": cur_fecha.strftime("%Y-%m-%d"),
                                        "Monto Cuota": f"{moneda_label} {cuota_monto_vis:,.2f}",
                                        "Estatus": estado_cuota
                                    })

                        if cronograma_data:
                            df_cronograma = pd.DataFrame(cronograma_data)
                            st.dataframe(df_cronograma, use_container_width=True, hide_index=True)
                        else:
                            st.info("💡 No se pudo generar el cuadro de días hábiles.")
                    else:
                        st.info("💡 No hay un préstamo activo registrado para proyectar el cuadro de días.")

                    st.divider()
                    st.subheader(f"📋 Historial del Crédito Vigente")

                    if not mov_actuales.empty:
                        df_vista_cli = mov_actuales[["Fecha", "Concepto", "Cargo_Vis", "Abono_Vis"]].copy()

                        st.dataframe(
                            df_vista_cli,
                            column_config={
                                "Fecha": st.column_config.TextColumn("Fecha"),
                                "Concepto": st.column_config.TextColumn("Concepto / Detalle"),
                                "Cargo_Vis": st.column_config.NumberColumn(f"Monto ({moneda_label})", format=f"{moneda_label} %.2f"),
                                "Abono_Vis": st.column_config.NumberColumn(f"Abonado ({moneda_label})", format=f"{moneda_label} %.2f"),
                            },
                            use_container_width=True,
                            hide_index=True,
                        )
                else:
                    st.error("❌ Código no encontrado.")
            except Exception as e:
                st.error(f"Error de conexión: {e}")

    elif opcion_cliente == "📲 Reportar un Pago":
        st.subheader("📲 Formulario de Reporte de Pago")
        with st.form("form_reportar_pago_cliente", border=True):
            col_p1, col_p2 = st.columns(2)
            cod_cli_rep = col_p1.text_input("Tu Código de Cliente:", value=codigo_url, disabled=True if codigo_url else False)
            nom_cli_rep = col_p2.text_input("Tu Nombre Completo:", value=nombre_autocompletado)

            col_p3, col_p4 = st.columns(2)
            f_pago = col_p3.date_input("Fecha del Pago", datetime.now())
            moneda_pago = col_p4.selectbox("Moneda del Pago:", ["Bolívares (Bs.)", "Dólares ($ / Binance / Efectivo)"])

            col_p5, col_p6 = st.columns(2)
            monto_reportado = col_p5.number_input("Monto Transferido / Pagado:", min_value=0.01, value=100.0)
            cuenta_destino = col_p6.selectbox("Medio de Pago Utilizado:", ["Pago Móvil", "Efectivo", "Binance"])

            num_ref = st.text_input("Número de Referencia / Comprobante:")
            btn_enviar_reporte = st.form_submit_button("💾 Registrar Pago y Preparar WhatsApp", use_container_width=True)

        codigo_final = str(codigo_url if codigo_url else cod_cli_rep).strip().upper()

        if btn_enviar_reporte:
            if codigo_final and nom_cli_rep and num_ref and monto_reportado > 0:
                try:
                    sheet_pendientes = obtener_hoja("PAGOS_PENDIENTES")
                    id_pago = f"PAG-{str(uuid.uuid4())[:6].upper()}"
                    nombre_clean = nom_cli_rep.strip()
                    ref_clean = str(num_ref).strip()
                    fecha_str = f_pago.strftime("%Y-%m-%d")

                    es_cliente_bs = codigo_final in lista_clientes_bs
                    if es_cliente_bs and "Bolívares" in moneda_pago:
                        monto_usd_convertido = round(monto_reportado / tasa_bs_usd, 4)
                        detalle_referencia = f"{ref_clean} (Bs. {monto_reportado:,.2f} a tasa {tasa_bs_usd})"
                    else:
                        monto_usd_convertido = round(monto_reportado, 2)
                        detalle_referencia = ref_clean

                    sheet_pendientes.append_row([
                        id_pago, fecha_str, codigo_final, nombre_clean, cuenta_destino, detalle_referencia, float(monto_usd_convertido), "PENDIENTE"
                    ])
                    st.cache_data.clear()
                    st.success(f"🎉 **¡Pago registrado con éxito!** ID: `{id_pago}`")
                except Exception as e:
                    st.error(f"Error al enviar el reporte: {e}")
            else:
                st.warning("⚠️ Por favor completa todos los campos obligatorios.")

# ==========================================
# PESTAÑA 2: PANEL DE ADMINISTRADOR (COMPLETO)
# ==========================================
else:
    st.title("💼 Panel de Administración")
    if not es_admin_autenticado:
        st.warning("🔒 Acceso restringido. Por favor, ingresa la clave de administrador en la barra lateral.")
    else:
        tab_admin1, tab_admin2, tab_admin3, tab_admin4 = st.tabs([
            "📥 Registrar Transacción", 
            "📋 Gestión de Clientes", 
            "🔔 Pagos Pendientes", 
            "📊 Caja y Reportes"
        ])

        with tab_admin1:
            st.subheader("Registrar Nuevo Cargo o Abono")
            with st.form("form_reg_admin"):
                col_a, col_b = st.columns(2)
                codigo_reg = col_a.text_input("Código de Cliente (Ej. CLI-001):").strip().upper()
                fecha_reg = col_b.date_input("Fecha de Operación", datetime.now())
                
                col_c, col_d = st.columns(2)
                tipo_op = col_c.selectbox("Tipo de Operación:", ["Cargo (Préstamo / Interés)", "Abono (Pago Recibido)"])
                monto_op = col_d.number_input("Monto en Dólares ($):", min_value=0.01, value=50.0)
                
                concepto_op = st.text_input("Concepto / Detalle:", placeholder="Ej. Préstamo inicial (24 cuotas) / Abono cuota diaria")
                btn_guardar_op = st.form_submit_button("💾 Guardar Transacción", use_container_width=True)

                if btn_guardar_op:
                    if codigo_reg and concepto_op:
                        try:
                            sheet_prin = obtener_hoja("Sheet1")
                            # Intentar buscar nombre del cliente
                            df_cli = conn.read(ttl=0, usecols=["Codigo", "Nombre"])
                            df_cli["Codigo"] = df_cli["Codigo"].astype(str).str.strip().str.upper()
                            match_n = df_cli[df_cli["Codigo"] == codigo_reg]
                            nombre_reg = match_n.iloc[0]["Nombre"] if not match_n.empty else "Cliente General"

                            cargo_val = monto_op if "Cargo" in tipo_op else 0.0
                            abono_val = monto_op if "Abono" in tipo_op else 0.0

                            sheet_prin.append_row([
                                fecha_reg.strftime("%Y-%m-%d"),
                                codigo_reg,
                                nombre_reg,
                                concepto_op,
                                float(cargo_val),
                                float(abono_val)
                            ])
                            st.cache_data.clear()
                            st.success("✅ ¡Operación registrada correctamente en la hoja!")
                        except Exception as e:
                            st.error(f"Error al registrar la transacción: {e}")
                    else:
                        st.warning("⚠️ Ingresa el código y el concepto.")

        with tab_admin2:
            st.subheader("Directorio y Estado Global de Clientes")
            try:
                df_global = conn.read(ttl=0)
                if not df_global.empty and "Codigo" in df_global.columns:
                    st.dataframe(df_global, use_container_width=True, hide_index=True)
                else:
                    st.info("No hay datos suficientes en la hoja principal.")
            except Exception as e:
                st.error(f"Error al cargar el directorio: {e}")

        with tab_admin3:
            st.subheader("Verificación de Pagos Pendientes por Aprobar")
            try:
                sheet_pend = obtener_hoja("PAGOS_PENDIENTES")
                data_pend = sheet_pend.get_all_records()
                if data_pend:
                    df_pend = pd.DataFrame(data_pend)
                    st.dataframe(df_pend, use_container_width=True, hide_index=True)
                    
                    st.markdown("---")
                    id_revisar = st.text_input("ID de Pago a Gestionar (Ej. PAG-1234):").strip().upper()
                    col_acc1, col_acc2 = st.columns(2)
                    
                    if col_acc1.button("✅ Aprobar e Integrar a Cuenta", use_container_width=True):
                        st.info(f"Funcionalidad de aprobación para {id_revisar} lista para procesar.")
                    if col_acc2.button("❌ Rechazar Pago", use_container_width=True):
                        st.info(f"Funcionalidad de rechazo para {id_revisar} lista para procesar.")
                else:
                    st.success("🎉 No hay pagos pendientes por revisar.")
            except Exception as e:
                st.info("Aún no se ha creado la pestaña de pagos pendientes o está vacía.")

        with tab_admin4:
            st.subheader("Flujo de Caja, Resumen y Estadísticas")
            try:
                df_caja = conn.read(ttl=0)
                if not df_caja.empty and "Abono" in df_caja.columns and "Cargo" in df_caja.columns:
                    total_ingresos = df_caja["Abono"].sum()
                    total_egresos_cargos = df_caja["Cargo"].sum()
                    
                    col_r1, col_r2 = st.columns(2)
                    col_r1.metric("💵 Total Ingresos Históricos (Abonos)", f"$ {total_ingresos:,.2f}")
                    col_r2.metric("📦 Total Capital Colocado (Cargos)", f"$ {total_egresos_cargos:,.2f}")
                else:
                    st.info("Faltan columnas de Cargo/Abono para calcular las métricas.")
            except Exception as e:
                st.error(f"Error al calcular reportes: {e}")
