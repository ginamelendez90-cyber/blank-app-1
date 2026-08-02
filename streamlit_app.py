from datetime import datetime
import urllib.parse
import uuid
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# ==========================================
# CONFIGURACIÓN GENERAL
# ==========================================
TELEFONO_ADMIN = "584123801615"  # Tu número de contacto sin '+'

st.set_page_config(
    page_title="Sistema de Cobros & Finanzas",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
    </style>
    """,
    unsafe_allow_html=True,
)

conn = st.connection("gsheets", type=GSheetsConnection)


# ==========================================
# VENTANA EMERGENTE (MODAL) DE DETALLE DE GASTOS
# ==========================================
@st.dialog("📋 Detalle de Gastos Operativos del Mes")
def mostrar_detalle_gastos(df_gastos_mes):
    st.write("A continuación se muestra el desglose de todos los gastos del mes seleccionado:")
    if not df_gastos_mes.empty:
        df_det = df_gastos_mes[["Fecha", "Nombre", "Concepto", "Cargo"]].copy()
        df_det["Fecha"] = pd.to_datetime(df_det["Fecha"]).dt.strftime("%Y-%m-%d")
        st.dataframe(
            df_det,
            column_config={
                "Fecha": st.column_config.TextColumn("Fecha"),
                "Nombre": st.column_config.TextColumn("Cuenta Origen"),
                "Concepto": st.column_config.TextColumn("Detalle / Concepto"),
                "Cargo": st.column_config.NumberColumn("Monto ($)", format="$%.2f"),
            },
            use_container_width=True,
            hide_index=True,
        )
        st.info(f"💰 **Total en Gastos del Mes:** ${df_gastos_mes['Cargo'].sum():,.2f}")
    else:
        st.info("💡 No hay registros de gastos para este mes.")


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
# BARRA LATERAL (CONFIGURACIÓN DE MONEDAS)
# ==========================================
st.sidebar.image(
    "https://img.icons8.com/fluency/96/money-bag-with-card.png", width=80
)
st.sidebar.title("Control Financiero")
st.sidebar.caption("Gestión de Cobros, Cuentas y Préstamos v3.5")
st.sidebar.divider()

# CONFIGURACIÓN DE CLIENTES EN BOLÍVARES
st.sidebar.subheader("💱 Clientes en Bolívares (Bs)")

tasa_bs_usd = st.sidebar.number_input(
    "Tasa cobrada en Bs / $:",
    min_value=1.0,
    value=65.0,
    step=0.5,
    help="Tasa especial que se aplicará únicamente a los clientes configurados abajo.",
)

codigos_bs_input = st.sidebar.text_input(
    "Códigos en Bs (separados por coma):",
    value="CLI-001, CLI-002",
    help="Ingresa los códigos de los clientes que verán su cuenta en Bs. Los demás verán en $.",
)

# Convertir la lista ingresada a códigos limpios en mayúsculas
lista_clientes_bs = [
    c.strip().upper() for c in codigos_bs_input.split(",") if c.strip()
]

st.sidebar.divider()

st.sidebar.subheader("🔒 Acceso Admin")
clave_admin = st.sidebar.text_input(
    "Contraseña:", type="password", key="clave_admin_sidebar"
)
es_admin_autenticado = clave_admin == "Kilometro12@"

if es_admin_autenticado:
    st.sidebar.success("🟢 Sesión Activa")
elif clave_admin != "":
    st.sidebar.error("🔴 Clave incorrecta")

st.sidebar.divider()

modo_vista = st.sidebar.radio(
    "Navegación Principal:",
    ["👤 Portal del Cliente", "💼 Panel de Administrador"],
    index=0,
)

# ==========================================
# PESTAÑA 1: PORTAL DEL CLIENTE
# ==========================================
if modo_vista == "👤 Portal del Cliente":
    st.title("👤 Portal de Atención al Cliente")

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
        st.write("Consulta el estado actual de tu crédito y tu historial.")

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

                    # EVALUACIÓN DE MONEDA PARA ESTE CLIENTE
                    es_cliente_bs = cod_clean in lista_clientes_bs
                    factor_conversion = tasa_bs_usd if es_cliente_bs else 1.0
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

                    # Cálculos base en USD
                    prestamo_actual_usd = mov_actuales["Cargo"].sum()
                    pagos_actual_usd = mov_actuales["Abono"].sum()
                    saldo_pendiente_usd = prestamo_actual_usd - pagos_actual_usd

                    # Conversión adaptativa (si es cliente en Bs se multiplica, si es en $ queda igual)
                    prestamo_vis = prestamo_actual_usd * factor_conversion
                    pagos_vis = pagos_actual_usd * factor_conversion
                    saldo_vis = saldo_pendiente_usd * factor_conversion

                    st.subheader(f"Bienvenido/a, **{nombre}**")

                    m1, m2, m3 = st.columns(3)
                    m1.metric("📌 Deuda Total Actual", f"{moneda_label} {prestamo_vis:,.2f}")
                    m2.metric("💵 Total Abonado", f"{moneda_label} {pagos_vis:,.2f}")
                    m3.metric(
                        "⚠️ Saldo Pendiente",
                        f"{moneda_label} {saldo_vis:,.2f}",
                        delta=f"-{moneda_label} {saldo_vis:,.2f}",
                        delta_color="inverse",
                    )

                    st.divider()
                    st.subheader(f"📋 Historial del Crédito Vigente ({'en Bolívares' if es_cliente_bs else 'en Dólares'})")
                    
                    if not mov_actuales.empty:
                        df_vista_cli = mov_actuales[["Fecha", "Concepto", "Cargo", "Abono"]].copy()
                        df_vista_cli[f"Monto ({moneda_label})"] = df_vista_cli["Cargo"] * factor_conversion
                        df_vista_cli[f"Abonado ({moneda_label})"] = df_vista_cli["Abono"] * factor_conversion

                        st.dataframe(
                            df_vista_cli[["Fecha", "Concepto", f"Monto ({moneda_label})", f"Abonado ({moneda_label})"]],
                            column_config={
                                f"Monto ({moneda_label})": st.column_config.NumberColumn(format=f"{moneda_label} %.2f"),
                                f"Abonado ({moneda_label})": st.column_config.NumberColumn(format=f"{moneda_label} %.2f"),
                            },
                            use_container_width=True,
                            hide_index=True,
                        )

                    if not mov_historicos.empty:
                        with st.expander("📂 Ver Historial de Créditos Liquidados"):
                            df_hist_cli = mov_historicos[["Fecha", "Concepto", "Cargo", "Abono"]].copy()
                            df_hist_cli[f"Monto ({moneda_label})"] = df_hist_cli["Cargo"] * factor_conversion
                            df_hist_cli[f"Abonado ({moneda_label})"] = df_hist_cli["Abono"] * factor_conversion

                            st.dataframe(
                                df_hist_cli[["Fecha", "Concepto", f"Monto ({moneda_label})", f"Abonado ({moneda_label})"]],
                                column_config={
                                    f"Monto ({moneda_label})": st.column_config.NumberColumn(format=f"{moneda_label} %.2f"),
                                    f"Abonado ({moneda_label})": st.column_config.NumberColumn(format=f"{moneda_label} %.2f"),
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
        st.caption("Registra tu transferencia o pago móvil.")

        if codigo_url:
            st.info(f"✨ **Formulario activado para el cliente:** `{codigo_url}`")

        with st.form("form_reportar_pago_cliente", border=True):
            col_p1, col_p2 = st.columns(2)

            cod_cli_rep = col_p1.text_input(
                "Tu Código de Cliente:",
                value=codigo_url,
                placeholder="Ej. CLI-001",
                disabled=True if codigo_url else False,
            )
            nom_cli_rep = col_p2.text_input(
                "Tu Nombre Completo:",
                value=nombre_autocompletado,
                placeholder="Ej. Juan Pérez",
            )

            col_p3, col_p4 = st.columns(2)
            f_pago = col_p3.date_input("Fecha del Pago", datetime.now())
            moneda_pago = col_p4.selectbox(
                "Moneda del Pago:",
                ["Bolívares (Bs.)", "Dólares ($ / Binance / Efectivo)"],
            )

            col_p5, col_p6 = st.columns(2)
            
            monto_reportado = col_p5.number_input(
                "Monto Transferido / Pagado:", min_value=0.01, value=100.0, step=10.0
            )

            cuenta_destino = col_p6.selectbox(
                "Medio de Pago Utilizado:",
                ["Pago Móvil", "Efectivo", "Binance"],
            )

            num_ref = st.text_input(
                "Número de Referencia / Comprobante:",
                placeholder="Ej. 849302",
            )

            btn_enviar_reporte = st.form_submit_button(
                "💾 Registrar Pago y Preparar WhatsApp",
                use_container_width=True,
            )

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

                    # Lógica de Conversión al reportar:
                    # Si el cliente es de la lista en Bs Y paga en Bolívares -> Se divide entre la tasa.
                    # Si no, se toma tal cual como Dólares.
                    if es_cliente_bs and "Bolívares" in moneda_pago:
                        monto_usd_convertido = round(monto_reportado / tasa_bs_usd, 2)
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
                            float(monto_usd_convertido),  # Se guarda en USD
                            "PENDIENTE",
                        ]
                    )

                    st.cache_data.clear()

                    st.success(
                        f"🎉 **¡Pago registrado en el sistema con éxito!**\n\n"
                        f"📌 **Monto ingresado:** {'Bs. ' + f'{monto_reportado:,.2f}' if ('Bolívares' in moneda_pago) else '$' + f'{monto_reportado:,.2f}'}\n"
                        f"📌 **Abono a abonar en sistema ($):** `${monto_usd_convertido:,.2f} USD`\n"
                        f"📌 **ID de Registro:** `{id_pago}`"
                    )

                    mensaje_wa = (
                        f"👋 *NUEVO PAGO REPORTADO*\n\n"
                        f"📌 *ID:* {id_pago}\n"
                        f"👤 *Cliente:* {nombre_clean} ({codigo_final})\n"
                        f"💵 *Monto:* {'Bs. ' + f'{monto_reportado:,.2f}' if ('Bolívares' in moneda_pago) else '$' + f'{monto_reportado:,.2f}'}\n"
                        f"💱 *Equivalente en Sistema:* ${monto_usd_convertido:,.2f} USD\n"
                        f"🏦 *Medio:* {cuenta_destino}\n"
                        f"🔢 *Referencia:* {ref_clean}\n"
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
                                📤 Enviar Comprobante por WhatsApp 📲
                            </div>
                        </a>
                        """,
                        unsafe_allow_html=True,
                    )

                except Exception as e:
                    st.error(f"Error al enviar el reporte: {e}")
            else:
                st.warning(
                    "⚠️ Por favor completa todos los campos obligatorios (Nombre, Monto y Referencia)."
                )

# ==========================================
# PESTAÑA 2: PANEL DE ADMINISTRADOR
# ==========================================
else:
    st.title("💼 Dashboard de Administración")

    if not es_admin_autenticado:
        st.warning(
            "🔒 El panel de administración está bloqueado. Por favor ingrese la contraseña en la barra lateral."
        )
    else:
        seccion_admin = st.segmented_control(
            "Seleccione una sección:",
            [
                "⏳ Abonos por Verificar",
                "📊 Flujo de Caja",
                "➕ Registrar Movimiento Directo",
                "🤝 Préstamos Externos",
                "💼 Aportes / Retiros Dueño",
                "🔄 Transferencias",
                "📉 Gastos Operativos",
                "✂️ Liquidar Crédito",
                "📅 Cierre de Mes",
            ],
            default="⏳ Abonos por Verificar",
        )

        st.divider()

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
        # 1. ABONOS POR VERIFICAR
        # ------------------------------------------
        if seccion_admin == "⏳ Abonos por Verificar":
            st.subheader("⏳ Confirmación de Pagos Reportados por Clientes")
            st.caption(
                "Verifica las transferencias reportadas contra tu banco/wallet antes de sumarlas al sistema."
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
                            f"📬 Tienes **{len(df_filtrado)} pago(s) pendiente(s)** por revisar."
                        )

                        for idx, fila in df_filtrado.iterrows():
                            with st.container(border=True):
                                c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
                                c1.markdown(f"👤 **Cliente:**\n{fila['Nombre']}")
                                c1.caption(f"Código: {fila['Codigo']}")

                                c2.markdown(
                                    f"💵 **Monto a Abonar:**\n${float(fila['Monto']):,.2f} USD"
                                )
                                c2.caption(f"Vía: {fila['Cuenta']}")

                                c3.markdown(
                                    f"🔢 **Referencia / Nota:**\n`{fila['Referencia']}`"
                                )
                                c3.caption(f"Fecha: {fila['Fecha']}")

                                col_b1, col_b2 = c4.columns(2)

                                if col_b1.button(
                                    "✅ Aprobar",
                                    key=f"app_{fila['ID']}",
                                    use_container_width=True,
                                ):
                                    try:
                                        sheet_principal = obtener_hoja()
                                        sheet_principal.append_row(
                                            [
                                                str(fila["Fecha"]),
                                                str(fila["Codigo"]),
                                                str(fila["Nombre"]),
                                                f"Abono verificado Ref: {fila['Referencia']} ({fila['Cuenta']})",
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
                                            f"✅ Pago de {fila['Nombre']} por ${fila['Monto']} aprobado",
                                            icon="🎉",
                                        )
                                        st.rerun()
                                    except Exception as ex:
                                        st.error(f"Error al aprobar: {ex}")

                                if col_b2.button(
                                    "❌ Rechazar",
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
                                            f"❌ Pago de {fila['Nombre']} rechazado.",
                                            icon="⚠️",
                                        )
                                        st.rerun()
                                    except Exception as ex:
                                        st.error(f"Error al rechazar: {ex}")
                    else:
                        st.success(
                            "🎉 ¡Todo al día! No hay pagos pendientes por verificar."
                        )
                else:
                    st.success(
                        "🎉 ¡Todo al día! No hay pagos pendientes por verificar."
                    )
            except Exception as e:
                st.error(f"Error al cargar pagos pendientes: {e}")

        # ------------------------------------------
        # 2. FLUJO DE CAJA Y CARTERA
        # ------------------------------------------
        elif seccion_admin == "📊 Flujo de Caja":
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

                    c_car1, c_car2, c_car3, c_car4 = st.columns(4)
                    c_car1.metric(
                        "💎 Capital Bruto Operativo",
                        f"${cartera_bruta:,.2f}",
                    )
                    c_car2.metric(
                        "🤝 Deuda Externa (Pasivos)",
                        f"${deuda_externa_total:,.2f}",
                        delta=f"-${deuda_externa_total:,.2f}" if deuda_externa_total > 0 else "$0.00",
                        delta_color="inverse",
                    )
                    c_car3.metric(
                        "🏛️ Patrimonio Neto Real",
                        f"${patrimonio_neto:,.2f}",
                    )
                    c_car4.metric(
                        "📌 Prestado a Clientes",
                        f"${saldo_en_la_calle:,.2f}",
                    )

                    st.divider()

                    st.subheader("📅 Resumen Diario de Flujo de Caja")
                    st.caption(
                        "Registro acumulado día a día de cobros recibidos, gastos operativos y préstamos entregados."
                    )

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
                        .rename("Cobros del Día ($)")
                    )

                    gastos_df = (
                        df_diario_raw[es_gas]
                        .groupby("Fecha_Clean")["Cargo"]
                        .sum()
                        .rename("Gastos del Día ($)")
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
                        .rename("Préstamos Entregados ($)")
                    )

                    df_resumen_diario = pd.concat(
                        [cobros_df, gastos_df, prestamos_df], axis=1
                    ).fillna(0)

                    df_resumen_diario["Flujo Neto ($)"] = (
                        df_resumen_diario["Cobros del Día ($)"]
                        - df_resumen_diario["Gastos del Día ($)"]
                        - df_resumen_diario["Préstamos Entregados ($)"]
                    )

                    df_resumen_diario = df_resumen_diario.sort_index(
                        ascending=False
                    )

                    hoy_str = datetime.now().strftime("%Y-%m-%d")
                    cobros_hoy = (
                        df_resumen_diario.loc[hoy_str, "Cobros del Día ($)"]
                        if hoy_str in df_resumen_diario.index
                        else 0.0
                    )
                    gastos_hoy = (
                        df_resumen_diario.loc[hoy_str, "Gastos del Día ($)"]
                        if hoy_str in df_resumen_diario.index
                        else 0.0
                    )
                    neto_hoy = (
                        df_resumen_diario.loc[hoy_str, "Flujo Neto ($)"]
                        if hoy_str in df_resumen_diario.index
                        else 0.0
                    )

                    with st.container(border=True):
                        st.markdown(f"#### 🟢 Jornada de Hoy (`{hoy_str}`)")
                        d_col1, d_col2, d_col3 = st.columns(3)
                        d_col1.metric("💵 Cobrado Hoy", f"${cobros_hoy:,.2f}")
                        d_col2.metric("📉 Gastado Hoy", f"${gastos_hoy:,.2f}")
                        d_col3.metric(
                            "💰 Flujo Neto de Hoy",
                            f"${neto_hoy:,.2f}",
                            delta=f"${neto_hoy:,.2f}",
                        )

                    col_tabla_d, col_grafico_d = st.columns([1.3, 1])

                    with col_tabla_d:
                        with st.container(border=True):
                            st.markdown("#### 📋 Histórico Diario")
                            st.dataframe(
                                df_resumen_diario.reset_index().rename(
                                    columns={"Fecha_Clean": "Fecha"}
                                ),
                                column_config={
                                    "Fecha": st.column_config.TextColumn("Fecha"),
                                    "Cobros del Día ($)": st.column_config.NumberColumn(
                                        format="$%.2f"
                                    ),
                                    "Gastos del Día ($)": st.column_config.NumberColumn(
                                        format="$%.2f"
                                    ),
                                    "Préstamos Entregados ($)": st.column_config.NumberColumn(
                                        format="$%.2f"
                                    ),
                                    "Flujo Neto ($)": st.column_config.NumberColumn(
                                        format="$%.2f"
                                    ),
                                },
                                use_container_width=True,
                                hide_index=True,
                            )

                    with col_grafico_d:
                        with st.container(border=True):
                            st.markdown("#### 📈 Tendencia: Cobros vs Gastos")
                            if not df_resumen_diario.empty:
                                st.line_chart(
                                    df_resumen_diario[
                                        ["Cobros del Día ($)", "Gastos del Día ($)"]
                                    ]
                                )

                    st.divider()

                    col_chart, col_cuentas = st.columns([1.2, 1])
                    with col_chart:
                        with st.container(border=True):
                            st.subheader("📊 Distribución de Cajas")
                            df_cuentas_chart = pd.DataFrame(
                                {
                                    "Cuenta": [
                                        "Efectivo",
                                        "Pago Móvil",
                                        "Binance",
                                    ],
                                    "Monto ($)": [
                                        max(0, efectivo_total),
                                        max(0, pago_movil_total),
                                        max(0, binance_total),
                                    ],
                                }
                            ).set_index("Cuenta")
                            st.bar_chart(df_cuentas_chart)

                    with col_cuentas:
                        with st.container(border=True):
                            st.subheader("🏦 Saldos Por Cuenta")
                            st.metric(
                                "💵 Efectivo Físico", f"${efectivo_total:,.2f}"
                            )
                            st.metric(
                                "📱 Pago Móvil", f"${pago_movil_total:,.2f}"
                            )
                            st.metric(
                                "🪙 Binance (Crypto)", f"${binance_total:,.2f}"
                            )

                    st.divider()
                    st.subheader("👥 Cartera de Clientes y Enlaces Directos")
                    st.dataframe(
                        resumen_clientes[
                            [
                                "Codigo",
                                "Nombre",
                                "Total_Cargos",
                                "Total_Abonos",
                                "Saldo_Pendiente",
                                "Enlace_Reporte",
                            ]
                        ],
                        column_config={
                            "Total_Cargos": st.column_config.NumberColumn("Cargos ($)", format="$%.2f"),
                            "Total_Abonos": st.column_config.NumberColumn("Abonos ($)", format="$%.2f"),
                            "Saldo_Pendiente": st.column_config.NumberColumn("Saldo ($)", format="$%.2f"),
                            "Enlace_Reporte": st.column_config.LinkColumn(
                                "Link de Reporte Pago",
                                display_text="Copiar Link 🔗",
                            ),
                        },
                        use_container_width=True,
                        hide_index=True,
                    )
            except Exception as e:
                st.error(f"Error al calcular flujo de caja: {e}")

        # ------------------------------------------
        # 3. REGISTRAR MOVIMIENTO DIRECTO
        # ------------------------------------------
        elif seccion_admin == "➕ Registrar Movimiento Directo":
            with st.container(border=True):
                st.subheader(
                    "📝 Registrar Crédito o Pago Directo (Sin Verificación previa)"
                )

                tipo_movimiento = st.radio(
                    "Operación a realizar:",
                    [
                        "Registrar Abono / Pago Directo",
                        "Registrar Préstamo / Deuda Inicial",
                    ],
                    horizontal=True,
                )

                usar_dos_cuentas = st.checkbox(
                    "🔀 Dividir monto entre DOS cuentas (Ej. Efectivo + Binance)"
                )

                if not usar_dos_cuentas:
                    cuenta_afectada = st.selectbox(
                        "Cuenta asociada:",
                        ["Efectivo", "Pago Móvil", "Binance"],
                    )

                es_nuevo_cliente = st.checkbox("➕ Es cliente NUEVO")

                if not es_nuevo_cliente and opciones_clientes:
                    cliente_seleccionado = st.selectbox(
                        "Seleccionar Cliente Existente:", opciones_clientes
                    )
                    nuevo_codigo = cliente_seleccionado.split(" - ")[0]
                    nuevo_nombre = cliente_seleccionado.split(" - ")[1]
                else:
                    col_nc1, col_nc2 = st.columns(2)
                    nuevo_codigo = col_nc1.text_input(
                        "Código (Ej. CLI-002)", key="nc_cod"
                    )
                    nuevo_nombre = col_nc2.text_input(
                        "Nombre Completo", key="nc_nom"
                    )

                with st.form("form_nuevo_registro", border=False):
                    nueva_fecha = st.date_input(
                        "Fecha de Operación", datetime.now()
                    )

                    tipo_cobro_abono = "Abono General"
                    if tipo_movimiento == "Registrar Abono / Pago Directo":
                        tipo_cobro_abono = st.selectbox(
                            "Frecuencia/Modalidad del Cobro:",
                            [
                                "Cobro Diario",
                                "Cobro Semanal",
                                "Abono General / Libre",
                            ],
                        )

                    monto = 0.0
                    monto_total_calculado = 0.0

                    if usar_dos_cuentas:
                        col_m1, col_m2 = st.columns(2)
                        c_1 = col_m1.selectbox(
                            "Primera Cuenta",
                            ["Efectivo", "Pago Móvil", "Binance"],
                            key="c1",
                        )
                        monto_c1 = col_m1.number_input(
                            f"Monto USD ({c_1}) ($)",
                            min_value=0.0,
                            value=0.0,
                            key="mc1",
                        )
                        otras_cuentas = [
                            c
                            for c in ["Efectivo", "Pago Móvil", "Binance"]
                            if c != c_1
                        ]
                        c_2 = col_m2.selectbox(
                            "Segunda Cuenta", otras_cuentas, key="c2"
                        )
                        monto_c2 = col_m2.number_input(
                            f"Monto USD ({c_2}) ($)",
                            min_value=0.0,
                            value=0.0,
                            key="mc2",
                        )
                        monto_total_calculado = monto_c1 + monto_c2
                    else:
                        monto = st.number_input(
                            "Monto USD ($)", min_value=0.0, value=0.0
                        )

                    tasa_interes, monto_interes_calc = 0.0, 0.0
                    frecuencia_pago, num_cuotas, valor_cuota_calc = (
                        "Diario",
                        1,
                        0.0,
                    )

                    if tipo_movimiento == "Registrar Préstamo / Deuda Inicial":
                        st.markdown("---")
                        cp1, cp2, cp3 = st.columns(3)
                        tasa_interes = cp1.number_input(
                            "Interés (%)", min_value=0.0, value=15.0, step=1.0
                        )
                        frecuencia_pago = cp2.selectbox(
                            "Frecuencia",
                            ["Diario", "Semanal", "Quincenal", "Mensual"],
                        )
                        num_cuotas = cp3.number_input(
                            "Cant. Cuotas",
                            min_value=1,
                            value=24 if frecuencia_pago == "Diario" else 4,
                            step=1,
                        )

                        monto_base_calc = (
                            monto_total_calculado if usar_dos_cuentas else monto
                        )
                        monto_interes_calc = monto_base_calc * (
                            tasa_interes / 100
                        )
                        deuda_total_calc = (
                            monto_base_calc + monto_interes_calc
                        )
                        valor_cuota_calc = (
                            deuda_total_calc / num_cuotas
                            if num_cuotas > 0
                            else 0.0
                        )

                        if monto_base_calc > 0:
                            st.info(
                                f"💵 **Capital ($):** ${monto_base_calc:,.2f} | 📈 **Interés ($):** ${monto_interes_calc:,.2f} | ⚠️ **Total ($):** ${deuda_total_calc:,.2f}\n\n"
                                f"👉 **{num_cuotas} cuotas {frecuencia_pago.lower()}s** de **${valor_cuota_calc:,.2f} USD** (Bs. {valor_cuota_calc * tasa_bs_usd:,.2f})"
                            )

                    concepto_personalizado = st.text_input(
                        "Notas u observaciones (Opcional)"
                    )
                    btn_guardar = st.form_submit_button(
                        "💾 Guardar Movimiento", use_container_width=True
                    )

                    if btn_guardar:
                        if nuevo_codigo and nuevo_nombre:
                            try:
                                sheet = obtener_hoja()
                                filas_a_agregar = []

                                desc_base = (
                                    f"{tipo_cobro_abono}"
                                    if tipo_movimiento
                                    == "Registrar Abono / Pago Directo"
                                    else f"Préstamo {frecuencia_pago} ({num_cuotas} cuotas de ${valor_cuota_calc:,.2f})"
                                )
                                if concepto_personalizado:
                                    desc_base += f" - {concepto_personalizado}"

                                if usar_dos_cuentas:
                                    if monto_total_calculado <= 0:
                                        st.error(
                                            "⚠️ Ingrese un monto mayor a cero."
                                        )
                                        st.stop()
                                    is_abono = (
                                        tipo_movimiento
                                        == "Registrar Abono / Pago Directo"
                                    )
                                    if monto_c1 > 0:
                                        filas_a_agregar.append(
                                            [
                                                nueva_fecha.strftime(
                                                    "%Y-%m-%d"
                                                ),
                                                str(nuevo_codigo).strip(),
                                                nuevo_nombre,
                                                f"{desc_base} ({c_1 if is_abono else 'Salida de ' + c_1})",
                                                0.0 if is_abono else float(monto_c1),
                                                float(monto_c1) if is_abono else 0.0,
                                            ]
                                        )
                                    if monto_c2 > 0:
                                        filas_a_agregar.append(
                                            [
                                                nueva_fecha.strftime(
                                                    "%Y-%m-%d"
                                                ),
                                                str(nuevo_codigo).strip(),
                                                nuevo_nombre,
                                                f"{desc_base} ({c_2 if is_abono else 'Salida de ' + c_2})",
                                                0.0 if is_abono else float(monto_c2),
                                                float(monto_c2) if is_abono else 0.0,
                                            ]
                                        )
                                else:
                                    if monto <= 0:
                                        st.error(
                                            "⚠️ Ingrese un monto mayor a cero."
                                        )
                                        st.stop()
                                    is_abono = (
                                        tipo_movimiento
                                        == "Registrar Abono / Pago Directo"
                                    )
                                    filas_a_agregar.append(
                                        [
                                            nueva_fecha.strftime("%Y-%m-%d"),
                                            str(nuevo_codigo).strip(),
                                            nuevo_nombre,
                                            f"{desc_base} ({cuenta_afectada if is_abono else 'Salida de ' + cuenta_afectada})",
                                            0.0 if is_abono else float(monto),
                                            float(monto) if is_abono else 0.0,
                                        ]
                                    )

                                if (
                                    tipo_movimiento
                                    == "Registrar Préstamo / Deuda Inicial"
                                    and monto_interes_calc > 0
                                ):
                                    filas_a_agregar.append(
                                        [
                                            nueva_fecha.strftime("%Y-%m-%d"),
                                            str(nuevo_codigo).strip(),
                                            nuevo_nombre,
                                            f"Interés aplicado ({tasa_interes}%)",
                                            float(monto_interes_calc),
                                            0.0,
                                        ]
                                    )

                                for fila in filas_a_agregar:
                                    sheet.append_row(fila)

                                st.cache_data.clear()

                                st.toast(
                                    f"🎉 Movimiento guardado para {nuevo_nombre}",
                                    icon="✅",
                                )
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al guardar: {e}")

        # ------------------------------------------
        # 4. PRÉSTAMOS EXTERNOS (PASIVOS)
        # ------------------------------------------
        elif seccion_admin == "🤝 Préstamos Externos":
            st.subheader("🤝 Gestión de Préstamos Recibidos de Personas Externas")
            st.caption(
                "Registra el dinero que te prestan terceros (aumenta tu caja) y las devoluciones que realizas (descuenta de tu caja)."
            )

            col_ext1, col_ext2 = st.columns([1, 1])

            with col_ext1:
                with st.container(border=True):
                    st.markdown("### 📥 Recibir Préstamo (+)")
                    with st.form("form_recibir_prestamo_ext"):
                        f_pe = st.date_input("Fecha de Recepción", datetime.now(), key="f_pe")
                        nom_pe = st.text_input("Nombre del Prestamista Externa:", placeholder="Ej. Pedro Pérez")
                        cta_pe = st.selectbox("Cuenta donde ingresa el dinero:", ["Efectivo", "Pago Móvil", "Binance"], key="cta_pe")
                        monto_pe = st.number_input("Monto Recibido ($):", min_value=0.01, value=100.0, step=10.0, key="m_pe")
                        obs_pe = st.text_input("Observación / Términos:", placeholder="Ej. A pagar en 30 días", key="o_pe")

                        if st.form_submit_button("📥 Registrar Dinero Recibido", use_container_width=True):
                            if nom_pe:
                                try:
                                    sheet = obtener_hoja()
                                    desc = f"Préstamo externo recibido de {nom_pe.strip()} ({cta_pe})"
                                    if obs_pe:
                                        desc += f" - {obs_pe.strip()}"
                                    
                                    sheet.append_row([
                                        f_pe.strftime("%Y-%m-%d"),
                                        "PASIVO_EXT",
                                        nom_pe.strip(),
                                        desc,
                                        0.0,
                                        float(monto_pe)
                                    ])
                                    st.cache_data.clear()
                                    st.toast(f"✅ Préstamo de ${monto_pe} registrado en {cta_pe}", icon="🤝")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
                            else:
                                st.warning("⚠️ Ingresa el nombre del prestamista.")

            with col_ext2:
                with st.container(border=True):
                    st.markdown("### 📤 Devolver / Pagar Préstamo (-)")
                    
                    df_ext_prestamistas = df_existente[df_existente["Codigo"] == "PASIVO_EXT"]
                    prestamistas_lista = df_ext_prestamistas["Nombre"].unique().tolist() if not df_ext_prestamistas.empty else []

                    with st.form("form_pagar_prestamo_ext"):
                        f_dev = st.date_input("Fecha de Devolución", datetime.now(), key="f_dev")
                        
                        if prestamistas_lista:
                            nom_dev = st.selectbox("Seleccionar Prestamista:", prestamistas_lista)
                        else:
                            nom_dev = st.text_input("Nombre del Prestamista:", placeholder="Ej. Pedro Pérez")

                        cta_dev = st.selectbox("Cuenta de donde sale el dinero:", ["Efectivo", "Pago Móvil", "Binance"], key="cta_dev")
                        monto_dev = st.number_input("Monto a Devolver ($):", min_value=0.01, value=50.0, step=10.0, key="m_dev")
                        obs_dev = st.text_input("Observación / Comprobante:", placeholder="Ej. Abono parcial", key="o_dev")

                        if st.form_submit_button("📤 Registrar Pago / Devolución", use_container_width=True):
                            if nom_dev:
                                try:
                                    sheet = obtener_hoja()
                                    desc = f"Devolución de préstamo a {nom_dev.strip()} (Salida de {cta_dev})"
                                    if obs_dev:
                                        desc += f" - {obs_dev.strip()}"

                                    sheet.append_row([
                                        f_dev.strftime("%Y-%m-%d"),
                                        "PASIVO_EXT",
                                        nom_dev.strip(),
                                        desc,
                                        float(monto_dev),
                                        0.0
                                    ])
                                    st.cache_data.clear()
                                    st.toast(f"✅ Devolución de ${monto_dev} registrada desde {cta_dev}", icon="💸")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
                            else:
                                st.warning("⚠️ Selecciona o escribe un prestamista.")

            st.divider()
            st.subheader("📋 Resumen de Deudas con Personas Externas")

            if not df_ext_prestamistas.empty:
                resumen_ext = df_ext_prestamistas.groupby("Nombre").agg(
                    Total_Prestado=("Abono", "sum"),
                    Total_Devuelto=("Cargo", "sum")
                ).reset_index()

                resumen_ext["Saldo_Pendiente_Deuda"] = resumen_ext["Total_Prestado"] - resumen_ext["Total_Devuelto"]

                m_ext_tot, m_ext_dev, m_ext_pen = st.columns(3)
                m_ext_tot.metric("📥 Total Recibido de Terceros", f"${resumen_ext['Total_Prestado'].sum():,.2f}")
                m_ext_dev.metric("📤 Total Devuelto a Terceros", f"${resumen_ext['Total_Devuelto'].sum():,.2f}")
                m_ext_pen.metric(
                    "⚠️ Deuda Externa Pendiente",
                    f"${resumen_ext['Saldo_Pendiente_Deuda'].sum():,.2f}",
                    delta=f"-${resumen_ext['Saldo_Pendiente_Deuda'].sum():,.2f}" if resumen_ext['Saldo_Pendiente_Deuda'].sum() > 0 else "$0.00",
                    delta_color="inverse"
                )

                st.dataframe(
                    resumen_ext,
                    column_config={
                        "Nombre": "Prestamista Externa",
                        "Total_Prestado": st.column_config.NumberColumn("Total Recibido ($)", format="$%.2f"),
                        "Total_Devuelto": st.column_config.NumberColumn("Total Devuelto ($)", format="$%.2f"),
                        "Saldo_Pendiente_Deuda": st.column_config.NumberColumn("Deuda Pendiente ($)", format="$%.2f"),
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("💡 Aún no se han registrado préstamos de personas externas.")

        # ------------------------------------------
        # 5. APORTES / RETIROS DUEÑO
        # ------------------------------------------
        elif seccion_admin == "💼 Aportes / Retiros Dueño":
            with st.container(border=True):
                st.subheader("💼 Movimientos de Capital Propio")
                st.caption(
                    "Retira dinero para uso personal o aporta saldo sin generar gastos ni afectar la utilidad del negocio."
                )

                tipo_op_capital = st.radio(
                    "Operación:",
                    [
                        "📥 Inyectar Capital (Ingresar dinero)",
                        "📤 Retirar Capital (Uso Personal)",
                    ],
                    horizontal=True,
                )

                with st.form("form_capital_dueno"):
                    f_cap = st.date_input("Fecha", datetime.now())
                    c_cap = st.selectbox(
                        "Cuenta:", ["Efectivo", "Pago Móvil", "Binance"]
                    )
                    m_cap = st.number_input(
                        "Monto USD ($)", min_value=0.01, value=10.0
                    )
                    d_cap = st.text_input("Nota / Observación")

                    if st.form_submit_button(
                        "💾 Registrar Capital", use_container_width=True
                    ):
                        try:
                            sheet = obtener_hoja()
                            is_inyeccion = "Inyectar" in tipo_op_capital

                            fila = [
                                f_cap.strftime("%Y-%m-%d"),
                                f"CAJA_{c_cap.upper()}",
                                f"Dueño ({c_cap})",
                                f"{'Inyección' if is_inyeccion else 'Retiro Personal'} de Capital ({c_cap})"
                                + (f" - {d_cap}" if d_cap else ""),
                                0.0 if is_inyeccion else float(m_cap),
                                float(m_cap) if is_inyeccion else 0.0,
                            ]
                            sheet.append_row(fila)
                            st.cache_data.clear()

                            st.toast("✅ Capital registrado", icon="💼")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

        # ------------------------------------------
        # 6. TRANSFERENCIAS
        # ------------------------------------------
        elif seccion_admin == "🔄 Transferencias":
            with st.container(border=True):
                st.subheader("🔄 Mover Dinero Entre Cuentas")
                with st.form("form_trans"):
                    ftr = st.date_input("Fecha", datetime.now())
                    cor = st.selectbox(
                        "Origen:", ["Efectivo", "Pago Móvil", "Binance"]
                    )
                    cde = st.selectbox(
                        "Destino:", ["Pago Móvil", "Efectivo", "Binance"]
                    )
                    mtr = st.number_input("Monto USD ($)", min_value=0.01)

                    if st.form_submit_button(
                        "Transferir", use_container_width=True
                    ):
                        if cor == cde:
                            st.error("⚠️ Las cuentas deben ser distintas.")
                        else:
                            try:
                                sheet = obtener_hoja()
                                sheet.append_row(
                                    [
                                        ftr.strftime("%Y-%m-%d"),
                                        f"CUENTA_{cor.upper()}",
                                        f"Sistema ({cor})",
                                        f"Transferencia enviada a {cde}",
                                        float(mtr),
                                        0.0,
                                    ]
                                )
                                sheet.append_row(
                                    [
                                        ftr.strftime("%Y-%m-%d"),
                                        f"CUENTA_{cde.upper()}",
                                        f"Sistema ({cde})",
                                        f"Transferencia recibida de {cor}",
                                        0.0,
                                        float(mtr),
                                    ]
                                )
                                st.cache_data.clear()

                                st.toast("✅ Transferencia realizada", icon="🔄")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

        # ------------------------------------------
        # 7. GASTOS OPERATIVOS
        # ------------------------------------------
        elif seccion_admin == "📉 Gastos Operativos":
            with st.container(border=True):
                st.subheader("📉 Registrar Gasto Operativo Real")
                with st.form("form_gastos_op"):
                    fga = st.date_input("Fecha", datetime.now())
                    cga = st.selectbox(
                        "Pagado con:", ["Efectivo", "Pago Móvil", "Binance"]
                    )
                    dga = st.text_input("Detalle del Gasto")
                    mga = st.number_input("Monto USD ($)", min_value=0.01)

                    if st.form_submit_button(
                        "Guardar Gasto", use_container_width=True
                    ):
                        if dga:
                            try:
                                sheet = obtener_hoja()
                                sheet.append_row(
                                    [
                                        fga.strftime("%Y-%m-%d"),
                                        f"GASTO_{cga.upper()}",
                                        f"Gastos ({cga})",
                                        dga,
                                        float(mga),
                                        0.0,
                                    ]
                                )
                                st.cache_data.clear()

                                st.toast("✅ Gasto registrado", icon="📉")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

        # ------------------------------------------
        # 8. LIQUIDAR CRÉDITO
        # ------------------------------------------
        elif seccion_admin == "✂️ Liquidar Crédito":
            with st.container(border=True):
                st.subheader("✂️ Cerrar Ciclo de Crédito")
                if opciones_clientes:
                    cli_liq = st.selectbox(
                        "Cliente a Liquidar:", opciones_clientes
                    )
                    cod_liq = cli_liq.split(" - ")[0]
                    nom_liq = cli_liq.split(" - ")[1]

                    if st.button(
                        "✂️ Finalizar Crédito Vigente",
                        use_container_width=True,
                    ):
                        try:
                            sheet = obtener_hoja()
                            sheet.append_row(
                                [
                                    datetime.now().strftime("%Y-%m-%d"),
                                    str(cod_liq).strip(),
                                    nom_liq,
                                    "Crédito anterior liquidado / Inicio nuevo ciclo",
                                    0.0,
                                    0.0,
                                ]
                            )
                            st.cache_data.clear()

                            st.toast(
                                f"✅ Crédito cerrado para {nom_liq}", icon="✂️"
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

        # ------------------------------------------
        # 9. CIERRE DE MES (CON VENTANA EMERGENTE PARA DETALLE DE GASTOS)
        # ------------------------------------------
        elif seccion_admin == "📅 Cierre de Mes":
            st.subheader("📅 Reporte Financiero Mensual")
            if not df_existente.empty:
                df_existente["Fecha"] = pd.to_datetime(
                    df_existente["Fecha"], errors="coerce"
                )
                df_valido = df_existente.dropna(subset=["Fecha"]).copy()
                df_valido["Mes_Año"] = df_valido["Fecha"].dt.strftime("%Y-%m")
                meses = sorted(df_valido["Mes_Año"].unique(), reverse=True)

                if meses:
                    mes_sel = st.selectbox("Seleccionar Mes:", meses)
                    df_mes = df_valido[df_valido["Mes_Año"] == mes_sel]

                    df_gastos_mes = df_mes[
                        df_mes["Codigo"].str.contains("GASTO_", na=False)
                    ]
                    gastos_mes = df_gastos_mes["Cargo"].sum()

                    intereses_mes = df_mes[
                        df_mes["Concepto"].str.contains(
                            "Interés aplicado", case=False, na=False
                        )
                    ]["Cargo"].sum()

                    df_clientes_mes = df_mes[
                        ~df_mes["Codigo"].str.contains("CUENTA_|GASTO_|CAJA_|PASIVO_EXT", na=False)
                    ]
                    prestado_mes = df_clientes_mes[
                        ~df_clientes_mes["Concepto"].str.contains("Interés aplicado", case=False, na=False)
                    ]["Cargo"].sum()

                    ganancia_neta = intereses_mes - gastos_mes

                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("💸 Capital Prestado", f"${prestado_mes:,.2f}")
                    m2.metric("📈 Intereses Generados", f"${intereses_mes:,.2f}")
                    
                    with m3:
                        st.metric("📉 Gastos Operativos", f"${gastos_mes:,.2f}")
                        if st.button("🔍 Ver Detalle", key="btn_ver_gastos_modal", use_container_width=True):
                            mostrar_detalle_gastos(df_gastos_mes)

                    m4.metric(
                        "💰 Ganancia Neta",
                        f"${ganancia_neta:,.2f}",
                        delta=f"${ganancia_neta:,.2f}",
                    )
