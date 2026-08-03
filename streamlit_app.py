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

# ==========================================
# CONFIGURACIÓN DE LA PÁGINA Y NUEVA INTERFAZ VISUAL
# ==========================================
st.set_page_config(
    page_title="Taller & Finanzas - Panel de Control",
    page_icon="🏍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS Personalizado para un diseño moderno e "industrial"
st.markdown(
    """
    <style>
    /* Fondo y estructura general */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Tarjetas de Métricas mejoradas */
    div[data-testid="metric-container"] {
        background-color: #1e2129;
        padding: 20px;
        border-radius: 12px;
        border-left: 5px solid #ff4b4b;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        transition: transform 0.2s ease-in-out;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-3px);
    }
    
    /* Botones estilizados */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        border-color: #ff4b4b;
        color: #ff4b4b;
    }
    
    /* Contenedores con borde suave */
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        border-radius: 12px !important;
        border-color: #2d323c !important;
        background-color: #16181d;
    }
    
    /* Alineación de Sidebar */
    div[data-testid="stSidebarNav"] {
        padding-top: 10px;
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
            ws.append_row(["codigos_bs", "TRAB-001, CLI-002"])
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
        codigos = config_dict.get("codigos_bs", "TRAB-001, CLI-002")
        return tasa, codigos
    except Exception:
        return 65.0, "TRAB-001, CLI-002"


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


def registrar_codigo_bs_si_no_existe(codigo, lista_actual_str, tasa_actual):
    cod_clean = str(codigo).strip().upper()
    lista_cods = [c.strip().upper() for c in lista_actual_str.split(",") if c.strip()]
    if cod_clean not in lista_cods:
        lista_cods.append(cod_clean)
        nueva_str = ", ".join(lista_cods)
        guardar_configuracion_persistente(tasa_actual, nueva_str)


def calcular_saldo_cuenta(df, cuenta_nombre):
    if df.empty:
        return 0.0

    def normalizar(texto):
        if not isinstance(texto, str):
            return ""
        t = texto.upper()
        return (
            t.replace("Á", "A")
            .replace("É", "E")
            .replace("Í", "I")
            .replace("Ó", "O")
            .replace("Ú", "U")
        )

    df_clean = df.copy()
    df_clean["Codigo_norm"] = (
        df_clean["Codigo"].astype(str).apply(normalizar)
    )
    df_clean["Concepto_norm"] = (
        df_clean["Concepto"].astype(str).apply(normalizar)
    )

    cuenta_norm = normalizar(cuenta_nombre)

    cond_codigo = (
        df_clean["Codigo_norm"].str.contains(f"CAJA_{cuenta_norm}")
        | df_clean["Codigo_norm"].str.contains(f"GASTO_{cuenta_norm}")
        | df_clean["Codigo_norm"].str.contains(f"CUENTA_{cuenta_norm}")
    )

    cond_concepto = (~df_clean["Codigo_norm"].str.contains("CUENTA_")) & (
        df_clean["Concepto_norm"].str.contains(f"\\({cuenta_norm}\\)")
        | df_clean["Concepto_norm"].str.contains(f"SALIDA DE {cuenta_norm}")
    )

    df_cuenta = df_clean[cond_codigo | cond_concepto]
    return float(df_cuenta["Abono"].sum() - df_cuenta["Cargo"].sum())


# ==========================================
# CARGAR CONFIGURACIÓN DESDE GOOGLE SHEETS
# ==========================================
tasa_bs_usd, codigos_bs_str = cargar_configuracion_persistente()
lista_clientes_bs = [
    c.strip().upper() for c in codigos_bs_str.split(",") if c.strip()
]


# ==========================================
# BARRA LATERAL (AUTENTICACIÓN Y NAVEGACIÓN)
# ==========================================
st.sidebar.image(
    "https://img.icons8.com/fluency/96/motorcycle.png", width=90
)
st.sidebar.title("MotorControl Pro")
st.sidebar.caption("Gestión de Trabajadores, Anticipos y Taller v5.0")
st.sidebar.divider()

st.sidebar.subheader("🔒 Acceso Admin")
clave_admin = st.sidebar.text_input(
    "Contraseña Maestra:", type="password", key="clave_admin_sidebar"
)
es_admin_autenticado = clave_admin == "Kilometro12@"

if es_admin_autenticado:
    st.sidebar.success("🟢 Sesión de Administrador Activa")
    st.sidebar.divider()

    st.sidebar.subheader("💱 Ajustes de Moneda (Bs)")

    with st.sidebar.form("form_config_bs_admin"):
        nueva_tasa = st.number_input(
            "Tasa del día (Bs / $):",
            min_value=1.0,
            value=float(tasa_bs_usd),
            step=0.5,
        )

        nuevos_codigos = st.text_input(
            "Códigos en Bs (separados por coma):",
            value=codigos_bs_str,
            help="Ej: TRAB-001, CLI-005"
        )

        btn_guardar_config = st.form_submit_button(
            "💾 Guardar Tasa y Códigos", use_container_width=True
        )

        if btn_guardar_config:
            if guardar_configuracion_persistente(nueva_tasa, nuevos_codigos):
                st.sidebar.success("✅ ¡Configuración de moneda actualizada!")
                st.rerun()

elif clave_admin != "":
    st.sidebar.error("🔴 Clave incorrecta")

st.sidebar.divider()

modo_vista = st.sidebar.radio(
    "Navegación Principal:",
    ["👤 Portal Trabajador / Cliente", "💼 Panel de Administración"],
    index=0,
)


# ==========================================
# VENTANA EMERGENTE (MODAL) DE DETALLE DE GASTOS
# ==========================================
@st.dialog("📋 Detalle Operativo del Taller")
def mostrar_detalle_gastos(df_gastos_mes):
    st.write("Desglose detallado de gastos e insumos del mes:")
    if not df_gastos_mes.empty:
        df_det = df_gastos_mes[["Fecha", "Nombre", "Concepto", "Cargo"]].copy()
        df_det["Fecha"] = pd.to_datetime(df_det["Fecha"]).dt.strftime("%Y-%m-%d")
        st.dataframe(
            df_det,
            column_config={
                "Fecha": st.column_config.TextColumn("Fecha"),
                "Nombre": st.column_config.TextColumn("Cuenta Origen"),
                "Concepto": st.column_config.TextColumn("Detalle de la Operación"),
                "Cargo": st.column_config.NumberColumn("Costo ($)", format="$%.2f"),
            },
            use_container_width=True,
            hide_index=True,
        )
        st.info(f"💰 **Total Invertido en el Mes:** ${df_gastos_mes['Cargo'].sum():,.2f}")
    else:
        st.info("💡 No hay registros de gastos operativos para este mes.")


# ==========================================
# PESTAÑA 1: PORTAL DEL TRABAJADOR / CLIENTE
# ==========================================
if modo_vista == "👤 Portal Trabajador / Cliente":
    st.title("👤 Portal de Consulta y Generación")
    st.markdown("Consulta tus adelantos, saldos pendientes y registra los pagos o dinero generado.")

    query_params = st.query_params
    codigo_url = query_params.get("cliente", "").strip().upper()
    accion_url = query_params.get("accion", "").strip().lower()

    index_defecto = 1 if accion_url == "reportar" else 0
    opciones_menu = ["🔎 Consultar Saldo y Anticipos", "📲 Reportar Pago / Generación"]

    opcion_cliente = st.segmented_control(
        "Selecciona la operación:",
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

    if opcion_cliente == "🔎 Consultar Saldo y Anticipos":
        with st.container(border=True):
            col_busq1, col_busq2 = st.columns([3, 1])
            codigo_cliente = col_busq1.text_input(
                "Ingrese su Código Asignado (Trabajador/Cliente):",
                value=codigo_url,
                placeholder="Ej. TRAB-001 o CLI-002",
            )
            btn_consultar = col_busq2.button(
                "🔎 Consultar Registro", use_container_width=True
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

                    estado_cliente = "🟢 AL DÍA"
                    detalle_estatus = "No hay deudas o retrasos pendientes."
                    color_estatus = "success"

                    fila_prestamo = mov_actuales[mov_actuales["Concepto"].str.contains("Préstamo", case=False, na=False)]

                    if not fila_prestamo.empty and saldo_vis > 0:
                        try:
                            f_str = str(fila_prestamo.iloc[0]["Fecha"])
                            f_inicio = pd.to_datetime(f_str).date()
                            f_hoy = datetime.now().date()
                            concepto_p = str(fila_prestamo.iloc[0]["Concepto"])

                            match_c = re.search(r'\((\d+)\s*cuotas', concepto_p, re.IGNORECASE)
                            num_cuotas_p = int(match_c.group(1)) if match_c else 24
                            cuota_monto_vis = prestamo_vis / num_cuotas_p if num_cuotas_p > 0 else prestamo_vis

                            frecuencia_lower = concepto_p.lower()

                            dias_cobro = max(0, calcular_dias_cobro_acumulados(f_inicio, f_hoy) - 1)

                            if "semanal" in frecuencia_lower:
                                cuotas_esperadas = min(dias_cobro // 6, num_cuotas_p)
                            elif "quincenal" in frecuencia_lower:
                                cuotas_esperadas = min(dias_cobro // 12, num_cuotas_p)
                            elif "mensual" in frecuencia_lower:
                                cuotas_esperadas = min(dias_cobro // 24, num_cuotas_p)
                            else:
                                cuotas_esperadas = min(dias_cobro, num_cuotas_p)

                            monto_esperado_hoy = cuotas_esperadas * cuota_monto_vis
                            diferencia_pago = pagos_vis - monto_esperado_hoy

                            if diferencia_pago >= -0.05:
                                estado_cliente = "🟢 AL DÍA"
                                detalle_estatus = f"Has cubierto tus pagos o cuotas generadas a la fecha."
                                color_estatus = "success"
                            else:
                                monto_atraso = abs(diferencia_pago)
                                cuotas_atrasadas = max(1, int(monto_atraso // cuota_monto_vis) if cuota_monto_vis > 0 else 1)
                                estado_cliente = "🔴 PENDIENTE"
                                detalle_estatus = f"Presentas un retraso o saldo pendiente de {cuotas_atrasadas} cuota(s) equivalente a {moneda_label} {monto_atraso:,.2f}."
                                color_estatus = "error"
                        except Exception:
                            estado_cliente = "🟢 AL DÍA"
                            detalle_estatus = "Cuenta activa."
                            color_estatus = "info"
                    elif saldo_vis <= 0 and not mov_actuales.empty:
                        estado_cliente = "✅ SALDADO"
                        detalle_estatus = "No hay deudas de adelantos pendientes."
                        color_estatus = "success"

                    st.subheader(f"Perfil de: **{nombre}**")

                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("📌 Adelantos / Deuda Total", f"{moneda_label} {prestamo_vis:,.2f}")
                    m2.metric("💵 Total Abonado / Generado", f"{moneda_label} {pagos_vis:,.2f}")
                    m3.metric(
                        "⚠️ Saldo Restante",
                        f"{moneda_label} {saldo_vis:,.2f}",
                        delta=f"-{moneda_label} {saldo_vis:,.2f}",
                        delta_color="inverse",
                    )
                    m4.metric("Estatus Actual", estado_cliente)

                    if color_estatus == "error":
                        st.error(f"⚠️ **Atención:** {estado_cliente} — {detalle_estatus}")
                    elif color_estatus == "success":
                        st.success(f"🎉 **Excelente:** {estado_cliente} — {detalle_estatus}")
                    else:
                        st.info(f"ℹ️ **Información:** {estado_cliente} — {detalle_estatus}")

                    st.divider()
                    st.subheader(f"📋 Registro de Movimientos Activos ({'en Bolívares' if es_cliente_bs else 'en Dólares'})")

                    if not mov_actuales.empty:
                        df_vista_cli = mov_actuales[["Fecha", "Concepto", "Cargo_Vis", "Abono_Vis"]].copy()

                        st.dataframe(
                            df_vista_cli,
                            column_config={
                                "Fecha": st.column_config.TextColumn("Fecha"),
                                "Concepto": st.column_config.TextColumn("Detalle de Operación"),
                                "Cargo_Vis": st.column_config.NumberColumn(f"Retiro ({moneda_label})", format=f"{moneda_label} %.2f"),
                                "Abono_Vis": st.column_config.NumberColumn(f"Abono ({moneda_label})", format=f"{moneda_label} %.2f"),
                            },
                            use_container_width=True,
                            hide_index=True,
                        )

                    if not mov_historicos.empty:
                        mov_historicos["Cargo_Vis"] = mov_historicos.apply(calcular_cargo_vista, axis=1)
                        mov_historicos["Abono_Vis"] = mov_historicos.apply(calcular_abono_vista, axis=1)

                        with st.expander("📂 Consultar Historial de Registros Liquidados"):
                            df_hist_cli = mov_historicos[["Fecha", "Concepto", "Cargo_Vis", "Abono_Vis"]].copy()

                            st.dataframe(
                                df_hist_cli,
                                column_config={
                                    "Fecha": st.column_config.TextColumn("Fecha"),
                                    "Concepto": st.column_config.TextColumn("Detalle de Operación"),
                                    "Cargo_Vis": st.column_config.NumberColumn(f"Retiro ({moneda_label})", format=f"{moneda_label} %.2f"),
                                    "Abono_Vis": st.column_config.NumberColumn(f"Abono ({moneda_label})", format=f"{moneda_label} %.2f"),
                                },
                                use_container_width=True,
                                hide_index=True,
                            )
                else:
                    st.error("❌ Código no encontrado en la base de datos del taller.")
            except Exception as e:
                st.error(f"Error de conexión con el servidor: {e}")

    elif opcion_cliente == "📲 Reportar Pago / Generación":
        st.subheader("📲 Reporte de Pagos o Ingresos Generados")
        st.caption("Registra pagos móviles, entregas de efectivo o ingresos reportados al taller.")

        if codigo_url:
            st.info(f"✨ **Autocompletado activado para:** `{codigo_url}`")

        with st.form("form_reportar_pago_cliente", border=True):
            col_p1, col_p2 = st.columns(2)

            cod_cli_rep = col_p1.text_input(
                "Código Identificador:",
                value=codigo_url,
                placeholder="Ej. TRAB-001",
                disabled=True if codigo_url else False,
            )
            nom_cli_rep = col_p2.text_input(
                "Nombre Completo:",
                value=nombre_autocompletado,
                placeholder="Ej. Juan Pérez",
            )

            col_p3, col_p4 = st.columns(2)
            f_pago = col_p3.date_input("Fecha de Registro", datetime.now())
            moneda_pago = col_p4.selectbox(
                "Moneda a Registrar:",
                ["Bolívares (Bs.)", "Dólares ($ / Binance / Efectivo)"],
            )

            col_p5, col_p6 = st.columns(2)

            monto_reportado = col_p5.number_input(
                "Monto Entregado / Generado:", min_value=0.01, value=100.0, step=10.0
            )

            cuenta_destino = col_p6.selectbox(
                "Medio de Ingreso:",
                ["Efectivo", "Pago Móvil", "Binance"],
            )

            num_ref = st.text_input(
                "Referencia / Nota del ingreso:",
                placeholder="Ej. 849302 o 'Reparación Moto Yamaha'",
            )

            btn_enviar_reporte = st.form_submit_button(
                "🚀 Enviar al Sistema y Preparar WhatsApp",
                use_container_width=True,
            )

        codigo_final = str(codigo_url if codigo_url else cod_cli_rep).strip().upper()

        if btn_enviar_reporte:
            if codigo_final and nom_cli_rep and num_ref and monto_reportado > 0:
                try:
                    sheet_pendientes = obtener_hoja("PAGOS_PENDIENTES")
                    id_pago = f"ING-{str(uuid.uuid4())[:6].upper()}"
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

                    sheet_pendientes.append_row(
                        [
                            id_pago,
                            fecha_str,
                            codigo_final,
                            nombre_clean,
                            cuenta_destino,
                            detalle_referencia,
                            float(monto_usd_convertido),
                            "PENDIENTE",
                        ]
                    )

                    st.cache_data.clear()

                    st.success(
                        f"🎉 **¡Ingreso reportado en el taller con éxito!**\n\n"
                        f"📌 **Monto registrado:** {'Bs. ' + f'{monto_reportado:,.2f}' if ('Bolívares' in moneda_pago) else '$' + f'{monto_reportado:,.2f}'}\n"
                        f"📌 **Equivalente en Caja Principal ($):** `${monto_usd_convertido:,.2f} USD`\n"
                        f"📌 **ID de Registro:** `{id_pago}`"
                    )

                    mensaje_wa = (
                        f"👋 *NUEVO INGRESO REPORTADO AL TALLER*\n\n"
                        f"📌 *ID:* {id_pago}\n"
                        f"👤 *Trabajador/Cliente:* {nombre_clean} ({codigo_final})\n"
                        f"💵 *Monto:* {'Bs. ' + f'{monto_reportado:,.2f}' if ('Bolívares' in moneda_pago) else '$' + f'{monto_reportado:,.2f}'}\n"
                        f"💱 *Equivalente USD:* ${monto_usd_convertido:,.2f}\n"
                        f"🏦 *Medio:* {cuenta_destino}\n"
                        f"📝 *Detalle/Ref:* {ref_clean}\n"
                        f"📅 *Fecha:* {fecha_str}"
                    )
                    mensaje_encoded = urllib.parse.quote(mensaje_wa)
                    link_wame = f"https://wa.me/{TELEFONO_ADMIN}?text={mensaje_encoded}"

                    st.markdown(
                        f"""
                        <a href="{link_wame}" target="_blank" style="text-decoration: none;">
                            <div style="
                                background-color: #25D366;
                                color: white;
                                padding: 14px 20px;
                                text-align: center;
                                font-weight: bold;
                                font-size: 16px;
                                border-radius: 8px;
                                margin-top: 10px;
                                cursor: pointer;">
                                📤 Enviar Notificación al Admin por WhatsApp 📲
                            </div>
                        </a>
                        """,
                        unsafe_allow_html=True,
                    )

                except Exception as e:
                    st.error(f"Error al procesar el reporte: {e}")
            else:
                st.warning(
                    "⚠️ Por favor completa todos los campos (Nombre, Monto y Referencia)."
                )

# ==========================================
# PESTAÑA 2: PANEL DE ADMINISTRACIÓN
# ==========================================
else:
    st.title("💼 Panel Maestro del Taller")

    if not es_admin_autenticado:
        st.warning(
            "🔒 El panel maestro está bloqueado. Por favor ingresa la contraseña en la barra lateral para acceder a la gestión de finanzas y trabajadores."
        )
    else:
        # Se organizó en pestañas en vez de radio buttons para mejor UI
        tabs_admin = st.tabs([
            "⏳ Por Verificar", 
            "🚨 Seguimiento", 
            "📊 Caja Central", 
            "➕ Nuevo Registro", 
            "💼 Mov. Capital", 
            "⚙️ Operaciones"
        ])

        try:
            df_existente = conn.read(
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
            df_existente["Codigo"] = (
                df_existente["Codigo"].astype(str).str.strip()
            )
            df_existente["Nombre"] = (
                df_existente["Nombre"].astype(str).str.strip()
            )

            clientes_unicos = (
                df_existente[
                    ~df_existente["Codigo"].str.contains(
                        "CUENTA_|GASTO_|CAJA_|PASIVO_EXT", na=False
                    )
                ]
                .drop_duplicates(subset=["Codigo"])
                .to_dict(orient="records")
            )
            opciones_clientes = [
                f"{c['Codigo']} - {c['Nombre']}" for c in clientes_unicos
            ]
        except Exception:
            opciones_clientes = []
            df_existente = pd.DataFrame()

        # ------------------------------------------
        # TAB 1: ABONOS POR VERIFICAR
        # ------------------------------------------
        with tabs_admin[0]:
            st.subheader("⏳ Validación de Ingresos de Trabajadores y Clientes")
            st.caption(
                "Revisa los comprobantes o el efectivo reportado antes de sumarlo oficialmente a la caja."
            )

            try:
                sheet_pendientes = obtener_hoja("PAGOS_PENDIENTES")
                datos_pendientes = sheet_pendientes.get_all_records()
                df_pendientes = pd.DataFrame(datos_pendientes)

                if (
                    not df_pendientes.empty
                    and "Estado" in df_pendientes.columns
                ):
                    df_filtrado = df_pendientes[
                        df_pendientes["Estado"] == "PENDIENTE"
                    ]

                    if not df_filtrado.empty:
                        st.info(
                            f"📬 Tienes **{len(df_filtrado)} ingreso(s)** pendiente(s) por revisión."
                        )

                        for idx, fila in df_filtrado.iterrows():
                            with st.container(border=True):
                                c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
                                c1.markdown(f"👤 **Persona:**\n{fila['Nombre']}")
                                c1.caption(f"ID: {fila['Codigo']}")

                                c2.markdown(
                                    f"💵 **Monto a Ingresar:**\n${float(fila['Monto']):,.2f} USD"
                                )
                                c2.caption(f"Caja: {fila['Cuenta']}")

                                c3.markdown(
                                    f"📝 **Detalle / Ref:**\n`{fila['Referencia']}`"
                                )
                                c3.caption(f"Fecha: {fila['Fecha']}")

                                col_b1, col_b2 = c4.columns(2)

                                if col_b1.button(
                                    "✅ Ingresar",
                                    key=f"app_{fila['ID']}",
                                    use_container_width=True,
                                ):
                                    try:
                                        sheet_principal = obtener_hoja()
                                        es_cli_bs = str(fila["Codigo"]).strip().upper() in lista_clientes_bs
                                        tag_tasa_pago = f" (Tasa: {tasa_bs_usd})" if es_cli_bs else ""
                                        
                                        sheet_principal.append_row(
                                            [
                                                str(fila["Fecha"]),
                                                str(fila["Codigo"]),
                                                str(fila["Nombre"]),
                                                f"Ingreso confirmado Ref: {fila['Referencia']} ({fila['Cuenta']}){tag_tasa_pago}",
                                                0.0,
                                                float(fila["Monto"]),
                                            ]
                                        )

                                        cell = sheet_pendientes.find(
                                            str(fila["ID"])
                                        )
                                        sheet_pendientes.update_cell(
                                            cell.row, 8, "APROBADO"
                                        )
                                        st.cache_data.clear()

                                        st.toast(
                                            f"✅ Ingreso de {fila['Nombre']} aprobado",
                                            icon="🎉",
                                        )
                                        st.rerun()
                                    except Exception as ex:
                                        st.error(f"Error al aprobar: {ex}")

                                if col_b2.button(
                                    "❌ Descartar",
                                    key=f"rej_{fila['ID']}",
                                    use_container_width=True,
                                ):
                                    try:
                                        cell = sheet_pendientes.find(
                                            str(fila["ID"])
                                        )
                                        sheet_pendientes.update_cell(
                                            cell.row, 8, "RECHAZADO"
                                        )
                                        st.cache_data.clear()
                                        st.toast(
                                            f"❌ Registro de {fila['Nombre']} descartado.",
                                            icon="⚠️",
                                        )
                                        st.rerun()
                                    except Exception as ex:
                                        st.error(f"Error al descartar: {ex}")
                    else:
                        st.success(
                            "🎉 No tienes reportes pendientes. La caja está al día."
                        )
                else:
                    st.success(
                        "🎉 No tienes reportes pendientes. La caja está al día."
                    )
            except Exception as e:
                st.error(f"Error al cargar reportes: {e}")

        # ------------------------------------------
        # TAB 2: SEGUIMIENTO ATRASOS
        # ------------------------------------------
        with tabs_admin[1]:
            st.subheader("🚨 Seguimiento de Adelantos Pendientes y Retrasos")
            
            try:
                if not df_existente.empty:
                    df_clientes = df_existente[
                        ~df_existente["Codigo"].str.contains(
                            "CUENTA_|GASTO_|CAJA_|PASIVO_EXT", na=False
                        )
                    ]

                    codigos_unicos = df_clientes["Codigo"].unique()
                    lista_atrasados = []
                    f_hoy = datetime.now().date()

                    for cod in codigos_unicos:
                        cod_clean = str(cod).strip().upper()
                        resultado = df_clientes[df_clientes["Codigo"] == cod_clean]

                        if resultado.empty:
                            continue

                        nombre = resultado.iloc[0]["Nombre"]
                        es_cliente_bs = cod_clean in lista_clientes_bs
                        moneda_label = "Bs." if es_cliente_bs else "$"

                        indices_liq = resultado[
                            resultado["Concepto"].str.contains("Crédito anterior liquidado", case=False, na=False)
                        ].index

                        if not indices_liq.empty:
                            ult_idx = indices_liq[-1]
                            mov_actuales = resultado.loc[resultado.index > ult_idx].copy()
                        else:
                            mov_actuales = resultado.copy()

                        if mov_actuales.empty:
                            continue

                        def calc_cargo(row):
                            cargo = float(row["Cargo"])
                            c_str = str(row["Concepto"])
                            c_lower = c_str.lower()
                            if es_cliente_bs:
                                tasa_fija = obtener_tasa_concepto(c_str, tasa_bs_usd)
                                if "interés aplicado" in c_lower or "interes aplicado" in c_lower:
                                    return round(cargo * 1.75 * tasa_fija, 2)
                                return round(cargo * tasa_fija, 2)
                            return cargo

                        def calc_abono(row):
                            abono = float(row["Abono"])
                            c_str = str(row["Concepto"])
                            if es_cliente_bs:
                                tasa_reg = obtener_tasa_concepto(c_str, tasa_bs_usd)
                                return round(abono * tasa_reg, 2)
                            return abono

                        mov_actuales["Cargo_Vis"] = mov_actuales.apply(calc_cargo, axis=1)
                        mov_actuales["Abono_Vis"] = mov_actuales.apply(calc_abono, axis=1)

                        prestamo_vis = mov_actuales["Cargo_Vis"].sum()
                        pagos_vis = mov_actuales["Abono_Vis"].sum()
                        saldo_vis = prestamo_vis - pagos_vis

                        fila_prestamo = mov_actuales[mov_actuales["Concepto"].str.contains("Préstamo", case=False, na=False)]

                        if not fila_prestamo.empty and saldo_vis > 0:
                            try:
                                f_str = str(fila_prestamo.iloc[0]["Fecha"])
                                f_inicio = pd.to_datetime(f_str).date()
                                concepto_p = str(fila_prestamo.iloc[0]["Concepto"])

                                match_c = re.search(r'\((\d+)\s*cuotas', concepto_p, re.IGNORECASE)
                                num_cuotas_p = int(match_c.group(1)) if match_c else 24
                                cuota_monto_vis = prestamo_vis / num_cuotas_p if num_cuotas_p > 0 else prestamo_vis

                                frecuencia_lower = concepto_p.lower()

                                dias_cobro = max(0, calcular_dias_cobro_acumulados(f_inicio, f_hoy) - 1)

                                if "semanal" in frecuencia_lower:
                                    cuotas_esperadas = min(dias_cobro // 6, num_cuotas_p)
                                elif "quincenal" in frecuencia_lower:
                                    cuotas_esperadas = min(dias_cobro // 12, num_cuotas_p)
                                elif "mensual" in frecuencia_lower:
                                    cuotas_esperadas = min(dias_cobro // 24, num_cuotas_p)
                                else:
                                    cuotas_esperadas = min(dias_cobro, num_cuotas_p)

                                monto_esperado_hoy = cuotas_esperadas * cuota_monto_vis
                                diferencia_pago = pagos_vis - monto_esperado_hoy

                                if diferencia_pago < -0.05:
                                    monto_atraso = abs(diferencia_pago)
                                    cuotas_atrasadas = max(1, int(monto_atraso // cuota_monto_vis) if cuota_monto_vis > 0 else 1)

                                    msg_wa = urllib.parse.quote(
                                        f"Hola {nombre}, te recordamos desde el taller que hay un saldo/cuota pendiente en tus registros de {cuotas_atrasadas} pago(s) ({moneda_label} {monto_atraso:,.2f}). Por favor avísanos apenas lo cubras. ¡Saludos!"
                                    )

                                    lista_atrasados.append({
                                        "Código": cod_clean,
                                        "Cliente": nombre,
                                        "Moneda": "Bolívares" if es_cliente_bs else "Dólares",
                                        "Cuotas Atrasadas": cuotas_atrasadas,
                                        "Monto Atraso": monto_atraso,
                                        "Saldo Pendiente": saldo_vis,
                                        "Valor Cuota": cuota_monto_vis,
                                        "Símbolo": moneda_label,
                                        "WhatsApp_Msg": msg_wa
                                    })
                            except Exception:
                                pass

                    if lista_atrasados:
                        c1, c2, c3 = st.columns(3)
                        c1.metric("👥 Trabajadores/Clientes Pendientes", f"{len(lista_atrasados)}")
                        c2.metric(
                            "💵 Total Retrasado USD",
                            f"${sum(x['Monto Atraso'] if x['Símbolo'] == '$' else x['Monto Atraso']/tasa_bs_usd for x in lista_atrasados):,.2f}"
                        )
                        c3.metric(
                            "🇻🇪 Total Retrasado Bs",
                            f"Bs. {sum(x['Monto Atraso'] if x['Símbolo'] == 'Bs.' else x['Monto Atraso']*tasa_bs_usd for x in lista_atrasados):,.2f}"
                        )

                        st.divider()

                        for atr in lista_atrasados:
                            with st.container(border=True):
                                col_a1, col_a2, col_a3, col_a4 = st.columns([2, 2, 2, 2])

                                col_a1.markdown(f"👤 **{atr['Cliente']}**\n`{atr['Código']}`")
                                col_a1.caption(f"Moneda: {atr['Moneda']}")

                                col_a2.markdown(f"🔴 **En Mora:** {atr['Cuotas Atrasadas']} pago(s)")
                                col_a2.caption(f"Monto esperado: {atr['Símbolo']} {atr['Valor Cuota']:,.2f}")

                                col_a3.markdown(f"⚠️ **Faltante Calculado:**\n**{atr['Símbolo']} {atr['Monto Atraso']:,.2f}**")
                                col_a3.caption(f"Deuda global: {atr['Símbolo']} {atr['Saldo Pendiente']:,.2f}")

                                link_cobro_wa = f"https://wa.me/?text={atr['WhatsApp_Msg']}"
                                col_a4.markdown(
                                    f"""
                                    <a href="{link_cobro_wa}" target="_blank" style="text-decoration: none;">
                                        <div style="
                                            background-color: #e53e3e;
                                            color: white;
                                            padding: 10px;
                                            text-align: center;
                                            font-weight: bold;
                                            font-size: 13px;
                                            border-radius: 6px;
                                            margin-top: 5px;">
                                            📲 Recordar Saldo
                                        </div>
                                    </a>
                                    """,
                                    unsafe_allow_html=True
                                )
                    else:
                        st.success("🎉 Todo el personal y clientes están al día con sus asignaciones.")
            except Exception as e:
                st.error(f"Error procesando morosidad: {e}")

        # ------------------------------------------
        # TAB 3: FLUJO DE CAJA CENTRAL
        # ------------------------------------------
        with tabs_admin[2]:
            try:
                if not df_existente.empty:
                    df_clientes = df_existente[
                        ~df_existente["Codigo"].str.contains(
                            "CUENTA_|GASTO_|CAJA_|PASIVO_EXT", na=False
                        )
                    ]

                    resumen_clientes = (
                        df_clientes.groupby(["Codigo", "Nombre"])
                        .agg(
                            Total_Cargos=("Cargo", "sum"),
                            Total_Abonos=("Abono", "sum"),
                        )
                        .reset_index()
                    )
                    resumen_clientes["Saldo_Pendiente"] = (
                        resumen_clientes["Total_Cargos"]
                        - resumen_clientes["Total_Abonos"]
                    )
                    saldo_en_la_calle = resumen_clientes[
                        "Saldo_Pendiente"
                    ].sum()

                    efectivo_total = calcular_saldo_cuenta(
                        df_existente, "Efectivo"
                    )
                    pago_movil_total = calcular_saldo_cuenta(
                        df_existente, "Pago Móvil"
                    )
                    binance_total = calcular_saldo_cuenta(
                        df_existente, "Binance"
                    )

                    total_caja = (
                        efectivo_total + pago_movil_total + binance_total
                    )
                    cartera_bruta = total_caja + saldo_en_la_calle

                    df_ext = df_existente[df_existente["Codigo"] == "PASIVO_EXT"]
                    deuda_externa_total = float(
                        df_ext["Abono"].sum() - df_ext["Cargo"].sum()
                    ) if not df_ext.empty else 0.0

                    patrimonio_neto = cartera_bruta - deuda_externa_total

                    URL_BASE_APP = "https://blank-app-0gbuv8hf31pb.streamlit.app/"
                    resumen_clientes["Enlace_Reporte"] = (
                        URL_BASE_APP
                        + "/?cliente="
                        + resumen_clientes["Codigo"]
                        + "&accion=reportar"
                    )

                    st.markdown("### 🏛️ Capital del Taller")
                    c_car1, c_car2, c_car3, c_car4 = st.columns(4)
                    c_car1.metric("💎 Capital Operativo (Caja + Adelantos)", f"${cartera_bruta:,.2f}")
                    c_car2.metric(
                        "🤝 Obligaciones a Terceros",
                        f"${deuda_externa_total:,.2f}",
                        delta=f"-${deuda_externa_total:,.2f}" if deuda_externa_total > 0 else "$0.00",
                        delta_color="inverse",
                    )
                    c_car3.metric("🏛️ Patrimonio Neto", f"${patrimonio_neto:,.2f}")
                    c_car4.metric("📌 Dinero en Calle (Adelantos)", f"${saldo_en_la_calle:,.2f}")

                    st.divider()

                    st.subheader("📅 Resumen Diario de Flujo de Caja")
                    
                    df_diario_raw = df_existente.copy()
                    df_diario_raw["Fecha_Clean"] = pd.to_datetime(
                        df_diario_raw["Fecha"], errors="coerce"
                    ).dt.strftime("%Y-%m-%d")

                    es_cli = ~df_diario_raw["Codigo"].str.contains(
                        "CUENTA_|GASTO_|CAJA_|PASIVO_EXT", na=False
                    )
                    es_gas = df_diario_raw["Codigo"].str.contains(
                        "GASTO_", na=False
                    )

                    cobros_df = (
                        df_diario_raw[es_cli]
                        .groupby("Fecha_Clean")["Abono"]
                        .sum()
                        .rename("Ingresos/Generado ($)")
                    )

                    gastos_df = (
                        df_diario_raw[es_gas]
                        .groupby("Fecha_Clean")["Cargo"]
                        .sum()
                        .rename("Gastos Taller ($)")
                    )

                    prestamos_df = (
                        df_diario_raw[
                            es_cli
                            & (
                                ~df_diario_raw["Concepto"].str.contains(
                                    "Interés aplicado", case=False, na=False
                                )
                            )
                        ]
                        .groupby("Fecha_Clean")["Cargo"]
                        .sum()
                        .rename("Dinero Adelantado ($)")
                    )

                    df_resumen_diario = pd.concat(
                        [cobros_df, gastos_df, prestamos_df], axis=1
                    ).fillna(0)

                    df_resumen_diario["Flujo Neto Diario ($)"] = (
                        df_resumen_diario["Ingresos/Generado ($)"]
                        - df_resumen_diario["Gastos Taller ($)"]
                        - df_resumen_diario["Dinero Adelantado ($)"]
                    )

                    df_resumen_diario = df_resumen_diario.sort_index(
                        ascending=False
                    )

                    hoy_str = datetime.now().strftime("%Y-%m-%d")
                    cobros_hoy = df_resumen_diario.loc[hoy_str, "Ingresos/Generado ($)"] if hoy_str in df_resumen_diario.index else 0.0
                    gastos_hoy = df_resumen_diario.loc[hoy_str, "Gastos Taller ($)"] if hoy_str in df_resumen_diario.index else 0.0
                    neto_hoy = df_resumen_diario.loc[hoy_str, "Flujo Neto Diario ($)"] if hoy_str in df_resumen_diario.index else 0.0

                    with st.container(border=True):
                        st.markdown(f"#### 🟢 Jornada de Hoy (`{hoy_str}`)")
                        d_col1, d_col2, d_col3 = st.columns(3)
                        d_col1.metric("💵 Ingresos Hoy", f"${cobros_hoy:,.2f}")
                        d_col2.metric("📉 Gastos Hoy", f"${gastos_hoy:,.2f}")
                        d_col3.metric("💰 Flujo Neto", f"${neto_hoy:,.2f}", delta=f"${neto_hoy:,.2f}")

                    col_tabla_d, col_grafico_d = st.columns([1.3, 1])

                    with col_tabla_d:
                        with st.container(border=True):
                            st.markdown("#### 📋 Histórico Diario")
                            st.dataframe(
                                df_resumen_diario.reset_index().rename(columns={"Fecha_Clean": "Fecha"}),
                                hide_index=True,
                                use_container_width=True
                            )

                    with col_grafico_d:
                        with st.container(border=True):
                            st.markdown("#### 📈 Ingresos vs Gastos")
                            if len(df_resumen_diario) > 0:
                                df_graf = df_resumen_diario.head(7).sort_index(ascending=True)
                                st.bar_chart(df_graf[["Ingresos/Generado ($)", "Gastos Taller ($)"]])
                            else:
                                st.info("No hay datos suficientes para graficar.")

            except Exception as e:
                st.error(f"Error procesando flujo de caja: {e}")
