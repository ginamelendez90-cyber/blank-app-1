from datetime import datetime
import uuid
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# ==========================================
# CONFIGURACIÓN DE PÁGINA Y ESTILOS
# ==========================================
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

    # Búsqueda adaptativa para la hoja principal (evita errores por idioma)
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
# BARRA LATERAL (NAVEGACIÓN)
# ==========================================
st.sidebar.image(
    "https://img.icons8.com/fluency/96/money-bag-with-card.png", width=80
)
st.sidebar.title("Control Financiero")
st.sidebar.caption("Gestión de Cobros, Cuentas y Préstamos v2.8")
st.sidebar.divider()

st.sidebar.subheader("🔒 Acceso Admin")
clave_admin = st.sidebar.text_input(
    "Contraseña:", type="password", key="clave_admin_sidebar"
)
es_admin_autenticado = clave_admin == "admin123"

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

    opcion_cliente = st.segmented_control(
        "¿Qué deseas realizar?:",
        ["🔎 Consultar Estado de Cuenta", "📲 Reportar un Pago"],
        default="🔎 Consultar Estado de Cuenta",
    )
    st.divider()

    # --- SUB-SECCIÓN: CONSULTAR ESTADO ---
    if opcion_cliente == "🔎 Consultar Estado de Cuenta":
        st.write("Consulta el estado actual de tu crédito y tu historial.")

        with st.container(border=True):
            col_busq1, col_busq2 = st.columns([3, 1])
            codigo_cliente = col_busq1.text_input(
                "Ingrese su Código de Cliente:", placeholder="Ej. CLI-001"
            )
            btn_consultar = col_busq2.button(
                "🔎 Consultar", use_container_width=True
            )

        if btn_consultar or codigo_cliente:
            if codigo_cliente:
                try:
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
                    df["Codigo"] = df["Codigo"].astype(str).str.strip()
                    resultado = df[df["Codigo"] == str(codigo_cliente).strip()]

                    if not resultado.empty:
                        nombre = resultado.iloc[0]["Nombre"]
                        total_cargos_historico = resultado["Cargo"].sum()

                        indices_liq = resultado[
                            resultado["Concepto"].str.contains(
                                "Crédito anterior liquidado",
                                case=False,
                                na=False,
                            )
                        ].index

                        if not indices_liq.empty:
                            ult_idx = indices_liq[-1]
                            mov_actuales = resultado.loc[
                                resultado.index > ult_idx
                            ]
                            mov_historicos = resultado.loc[
                                resultado.index <= ult_idx
                            ]
                        else:
                            mov_actuales = resultado
                            mov_historicos = pd.DataFrame()

                        prestamo_actual = mov_actuales["Cargo"].sum()
                        pagos_actual = mov_actuales["Abono"].sum()
                        saldo_pendiente = prestamo_actual - pagos_actual

                        st.subheader(f"Bienvenido/a, **{nombre}**")

                        m1, m2, m3 = st.columns(3)
                        m1.metric(
                            "📌 Deuda Total Actual", f"${prestamo_actual:,.2f}"
                        )
                        m2.metric("💵 Total Abonado", f"${pagos_actual:,.2f}")
                        m3.metric(
                            "⚠️ Saldo Pendiente",
                            f"${saldo_pendiente:,.2f}",
                            delta=f"-${saldo_pendiente:,.2f}",
                            delta_color="inverse",
                        )

                        st.caption(
                            f"📊 *Acumulado histórico total: ${total_cargos_historico:,.2f}*"
                        )

                        st.divider()
                        st.subheader("📋 Historial del Crédito Vigente")
                        if not mov_actuales.empty:
                            st.dataframe(
                                mov_actuales[
                                    ["Fecha", "Concepto", "Cargo", "Abono"]
                                ],
                                use_container_width=True,
                                hide_index=True,
                            )

                        if not mov_historicos.empty:
                            with st.expander(
                                "📂 Ver Historial de Créditos Liquidados"
                            ):
                                st.dataframe(
                                    mov_historicos[
                                        ["Fecha", "Concepto", "Cargo", "Abono"]
                                    ],
                                    use_container_width=True,
                                    hide_index=True,
                                )
                    else:
                        st.error("❌ Código no encontrado.")
                except Exception as e:
                    st.error(f"Error de conexión: {e}")

    # --- SUB-SECCIÓN: REPORTAR PAGO ---
    elif opcion_cliente == "📲 Reportar un Pago":
        st.subheader("📲 Formulario de Reporte de Pago")
        st.caption(
            "Registra tu transferencia o pago móvil aquí para que sea validado por el administrador."
        )

        with st.form("form_reportar_pago_cliente", border=True):
            col_p1, col_p2 = st.columns(2)
            cod_cli_rep = col_p1.text_input(
                "Tu Código de Cliente (Ej: CLI-001):"
            )
            nom_cli_rep = col_p2.text_input("Tu Nombre Completo:")

            col_p3, col_p4 = st.columns(2)
            f_pago = col_p3.date_input("Fecha del Pago", datetime.now())
            cuenta_destino = col_p4.selectbox(
                "Medio de Pago Utilizado:",
                ["Pago Móvil", "Efectivo", "Binance"],
            )

            col_p5, col_p6 = st.columns(2)
            monto_rep = col_p5.number_input(
                "Monto Transferido ($)", min_value=0.01, value=10.0, step=1.0
            )
            num_ref = col_p6.text_input(
                "Número de Referencia / Comprobante:",
                placeholder="Ej. 849302",
            )

            btn_enviar_reporte = st.form_submit_button(
                "📤 Enviar Comprobante para Verificación",
                use_container_width=True,
            )

            if btn_enviar_reporte:
                if cod_cli_rep and nom_cli_rep and num_ref and monto_rep > 0:
                    try:
                        sheet_pendientes = obtener_hoja("PAGOS_PENDIENTES")
                        id_pago = f"PAG-{str(uuid.uuid4())[:6].upper()}"

                        sheet_pendientes.append_row(
                            [
                                id_pago,
                                f_pago.strftime("%Y-%m-%d"),
                                str(cod_cli_rep).strip().upper(),
                                nom_cli_rep.strip(),
                                cuenta_destino,
                                str(num_ref).strip(),
                                float(monto_rep),
                                "PENDIENTE",
                            ]
                        )

                        st.success(
                            f"🎉 **¡Pago registrado con éxito!**\n\n"
                            f"📌 **ID de Registro:** `{id_pago}`\n\n"
                            f"Tu abono de **${monto_rep:,.2f}** está en proceso de verificación por el administrador."
                        )
                    except Exception as e:
                        st.error(f"Error al enviar reporte: {e}")
                else:
                    st.warning(
                        "⚠️ Por favor complete todos los campos obligatorios (Código, Nombre, Monto y Referencia)."
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
                "💼 Aportes / Retiros Dueño",
                "🔄 Transferencias",
                "📉 Gastos Operativos",
                "✂️ Liquidar Crédito",
                "📅 Cierre de Mes",
            ],
            default="⏳ Abonos por Verificar",
        )

        st.divider()

        # Cargar datos base
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
                        "CUENTA_|GASTO_|CAJA_", na=False
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
        # 1. ABONOS POR VERIFICAR (APROBACIÓN DE CLIENTES)
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
                                    f"💵 **Monto:**\n# ${float(fila['Monto']):,.2f}"
                                )
                                c2.caption(f"Vía: {fila['Cuenta']}")

                                c3.markdown(
                                    f"🔢 **Referencia:**\n`{fila['Referencia']}`"
                                )
                                c3.caption(f"Fecha: {fila['Fecha']}")

                                col_b1, col_b2 = c4.columns(2)

                                # BOTÓN APROBAR
                                if col_b1.button(
                                    "✅ Aprobar",
                                    key=f"app_{fila['ID']}",
                                    use_container_width=True,
                                ):
                                    try:
                                        # 1. Agregar a la hoja principal de datos
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

                                        # 2. Marcar como APROBADO en PAGOS_PENDIENTES
                                        cell = sheet_pendientes.find(
                                            str(fila["ID"])
                                        )
                                        sheet_pendientes.update_cell(
                                            cell.row, 8, "APROBADO"
                                        )

                                        st.toast(
                                            f"✅ Pago de {fila['Nombre']} por ${fila['Monto']} aprobado",
                                            icon="🎉",
                                        )
                                        st.rerun()
                                    except Exception as ex:
                                        st.error(f"Error al aprobar: {ex}")

                                # BOTÓN RECHAZAR
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
                st.error(
                    f"Error al cargar la hoja de PAGOS_PENDIENTES: {e}. "
                    "Asegúrate de que la segunda pestaña exista en Google Sheets."
                )

        # ------------------------------------------
        # 2. FLUJO DE CAJA Y DASHBOARD
        # ------------------------------------------
        elif seccion_admin == "📊 Flujo de Caja":
            try:
                if not df_existente.empty:
                    df_clientes = df_existente[
                        ~df_existente["Codigo"].str.contains(
                            "CUENTA_|GASTO_|CAJA_", na=False
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
                    cartera_total = total_caja + saldo_en_la_calle

                    c_car1, c_car2, c_car3 = st.columns(3)
                    c_car1.metric(
                        "💎 Capital Total (Patrimonio)",
                        f"${cartera_total:,.2f}",
                    )
                    c_car2.metric(
                        "🏦 Total Líquido en Cajas", f"${total_caja:,.2f}"
                    )
                    c_car3.metric(
                        "📌 Dinero Prestado en Calle",
                        f"${saldo_en_la_calle:,.2f}",
                    )

                    st.divider()

                    # MOVIMIENTOS PERSONALES DEL DUEÑO
                    df_caja_dueno = df_existente[
                        df_existente["Codigo"].str.contains("CAJA_", na=False)
                    ]
                    total_inyecciones_dueno = df_caja_dueno["Abono"].sum()
                    total_retiros_dueno = df_caja_dueno["Cargo"].sum()
                    balance_dueno = (
                        total_inyecciones_dueno - total_retiros_dueno
                    )

                    with st.expander(
                        "👤 Ver Histórico de Movimientos de Capital del Dueño (Aportes vs Retiros)",
                        expanded=False,
                    ):
                        cd1, cd2, cd3 = st.columns(3)
                        cd1.metric(
                            "📥 Capital Inyectado",
                            f"${total_inyecciones_dueno:,.2f}",
                        )
                        cd2.metric(
                            "📤 Capital Retirado (Personal)",
                            f"${total_retiros_dueno:,.2f}",
                        )
                        cd3.metric(
                            "⚖️ Balance Neto Dueño", f"${balance_dueno:,.2f}"
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
                    st.subheader("👥 Cartera de Clientes y Saldos")
                    st.dataframe(
                        resumen_clientes[
                            [
                                "Codigo",
                                "Nombre",
                                "Total_Cargos",
                                "Total_Abonos",
                                "Saldo_Pendiente",
                            ]
                        ],
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
                            f"Monto ({c_1}) ($)",
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
                            f"Monto ({c_2}) ($)",
                            min_value=0.0,
                            value=0.0,
                            key="mc2",
                        )
                        monto_total_calculado = monto_c1 + monto_c2
                    else:
                        monto = st.number_input(
                            "Monto ($)", min_value=0.0, value=0.0
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
                                f"💵 **Capital:** ${monto_base_calc:,.2f} | 📈 **Interés:** ${monto_interes_calc:,.2f} | ⚠️ **Total:** ${deuda_total_calc:,.2f}\n\n"
                                f"👉 **{num_cuotas} cuotas {frecuencia_pago.lower()}s** de **${valor_cuota_calc:,.2f}**"
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

                                st.toast(
                                    f"🎉 Movimiento guardado para {nuevo_nombre}",
                                    icon="✅",
                                )
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al guardar: {e}")

        # ------------------------------------------
        # 4. APORTES / RETIROS DUEÑO
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
                        "📤 Retirar Capital (Uso Personal sin recargo)",
                    ],
                    horizontal=True,
                )

                with st.form("form_capital_dueno"):
                    f_cap = st.date_input("Fecha", datetime.now())
                    c_cap = st.selectbox(
                        "Cuenta:", ["Efectivo", "Pago Móvil", "Binance"]
                    )
                    m_cap = st.number_input(
                        "Monto ($)", min_value=0.01, value=10.0
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
                            st.toast("✅ Capital registrado", icon="💼")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

        # ------------------------------------------
        # 5. TRANSFERENCIAS
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
                    mtr = st.number_input("Monto ($)", min_value=0.01)

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
                                st.toast("✅ Transferencia realizada", icon="🔄")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

        # ------------------------------------------
        # 6. GASTOS OPERATIVOS
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
                    mga = st.number_input("Monto ($)", min_value=0.01)

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
                                st.toast("✅ Gasto registrado", icon="📉")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

        # ------------------------------------------
        # 7. LIQUIDAR CRÉDITO
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
                            st.toast(
                                f"✅ Crédito cerrado para {nom_liq}", icon="✂️"
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

        # ------------------------------------------
        # 8. CIERRE DE MES
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

                    gastos_mes = df_mes[
                        df_mes["Codigo"].str.contains("GASTO_", na=False)
                    ]["Cargo"].sum()
                    intereses_mes = df_mes[
                        df_mes["Concepto"].str.contains(
                            "Interés aplicado", case=False, na=False
                        )
                    ]["Cargo"].sum()
                    ganancia_neta = intereses_mes - gastos_mes

                    m1, m2, m3 = st.columns(3)
                    m1.metric("📈 Intereses Generados", f"${intereses_mes:,.2f}")
                    m2.metric("📉 Gastos Operativos", f"${gastos_mes:,.2f}")
                    m3.metric(
                        "💰 Ganancia Neta",
                        f"${ganancia_neta:,.2f}",
                        delta=f"${ganancia_neta:,.2f}",
                    )
