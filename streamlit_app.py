from datetime import datetime
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
# LÓGICA DE CÁLCULO DE SALDOS
# ==========================================
def calcular_saldo_cuenta(df, cuenta_nombre):
    """Calcula el saldo exacto (Abonos - Cargos) para una cuenta específica

    sin falsos positivos en transferencias.
    """
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
# BARRA LATERAL (NAVEGACIÓN Y AUTENTICACIÓN)
# ==========================================
st.sidebar.image(
    "https://img.icons8.com/fluency/96/money-bag-with-card.png", width=80
)
st.sidebar.title("Control Financiero")
st.sidebar.caption("Gestión de Cobros, Cuentas y Préstamos v2.6")
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
    st.title("👤 Consulta de Estado de Cuenta")
    st.write("Consulta el estado actual de tu crédito y el historial de pagos.")

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
                codigo_buscado = str(codigo_cliente).strip()

                resultado = df[df["Codigo"] == codigo_buscado]

                if not resultado.empty:
                    nombre = resultado.iloc[0]["Nombre"]
                    total_cargos_historico = resultado["Cargo"].sum()

                    indices_liquidacion = resultado[
                        resultado["Concepto"].str.contains(
                            "Crédito anterior liquidado", case=False, na=False
                        )
                    ].index

                    if not indices_liquidacion.empty:
                        ultimo_corte_idx = indices_liquidacion[-1]
                        movimientos_ciclo_actual = resultado.loc[
                            resultado.index > ultimo_corte_idx
                        ]
                        movimientos_historicos = resultado.loc[
                            resultado.index <= ultimo_corte_idx
                        ]
                    else:
                        movimientos_ciclo_actual = resultado
                        movimientos_historicos = pd.DataFrame()

                    prestamo_actual = movimientos_ciclo_actual["Cargo"].sum()
                    pagos_actual = movimientos_ciclo_actual["Abono"].sum()
                    saldo_pendiente = prestamo_actual - pagos_actual

                    st.subheader(f"Bienvenido/a, **{nombre}**")

                    m1, m2, m3 = st.columns(3)
                    with m1:
                        with st.container(border=True):
                            st.metric(
                                "📌 Deuda Total Actual",
                                f"${prestamo_actual:,.2f}",
                            )
                    with m2:
                        with st.container(border=True):
                            st.metric(
                                "💵 Total Abonado", f"${pagos_actual:,.2f}"
                            )
                    with m3:
                        with st.container(border=True):
                            st.metric(
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
                    if not movimientos_ciclo_actual.empty:
                        st.dataframe(
                            movimientos_ciclo_actual[
                                ["Fecha", "Concepto", "Cargo", "Abono"]
                            ],
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.info("No hay movimientos activos en este ciclo.")

                    if not movimientos_historicos.empty:
                        with st.expander(
                            "📂 Ver Historial de Créditos Liquidados"
                        ):
                            st.dataframe(
                                movimientos_historicos[
                                    ["Fecha", "Concepto", "Cargo", "Abono"]
                                ],
                                use_container_width=True,
                                hide_index=True,
                            )
                else:
                    st.error(
                        "❌ Código no encontrado. Verifique e intente nuevamente."
                    )
            except Exception as e:
                st.error(f"Error al conectar con la base de datos: {e}")
        else:
            st.warning("⚠️ Por favor ingrese un código válido.")

# ==========================================
# PESTAÑA 2: PANEL DE ADMINISTRADOR
# ==========================================
else:
    st.title("💼 Dashboard de Administración")

    if not es_admin_autenticado:
        st.warning(
            "🔒 El panel de administración está bloqueado. Por favor ingrese la contraseña en la barra lateral izquierda."
        )
    else:
        seccion_admin = st.segmented_control(
            "Seleccione una sección:",
            [
                "📊 Flujo de Caja",
                "➕ Registrar Movimiento",
                "💼 Aportes / Retiros Dueño",
                "🔄 Transferencias",
                "📉 Gastos Operativos",
                "✂️ Liquidar Crédito",
                "📅 Cierre de Mes",
            ],
            default="📊 Flujo de Caja",
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
        # 1. FLUJO DE CAJA Y DASHBOARD
        # ------------------------------------------
        if seccion_admin == "📊 Flujo de Caja":
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
                    with c_car1:
                        with st.container(border=True):
                            st.metric(
                                "💎 Capital Total (Patrimonio)",
                                f"${cartera_total:,.2f}",
                            )
                    with c_car2:
                        with st.container(border=True):
                            st.metric(
                                "🏦 Total Líquido en Cajas",
                                f"${total_caja:,.2f}",
                            )
                    with c_car3:
                        with st.container(border=True):
                            st.metric(
                                "📌 Dinero Prestado en Calle",
                                f"${saldo_en_la_calle:,.2f}",
                            )

                    st.divider()

                    # NUEVO APARTADO: RESUMEN DE MOVIMIENTOS PERSONALES DEL DUEÑO
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
                        expanded=True,
                    ):
                        cd1, cd2, cd3 = st.columns(3)
                        cd1.metric(
                            "📥 Capital Inyectado (Ingresado)",
                            f"${total_inyecciones_dueno:,.2f}",
                        )
                        cd2.metric(
                            "📤 Capital Retirado (Uso Personal)",
                            f"${total_retiros_dueno:,.2f}",
                        )
                        cd3.metric(
                            "⚖️ Aporte Neto del Dueño",
                            f"${balance_dueno:,.2f}",
                            delta=f"${balance_dueno:,.2f}",
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
                else:
                    st.info("Aún no hay registros en la base de datos.")
            except Exception as e:
                st.error(f"Error al calcular flujo de caja: {e}")

        # ------------------------------------------
        # 2. REGISTRAR MOVIMIENTOS
        # ------------------------------------------
        elif seccion_admin == "➕ Registrar Movimiento":
            with st.container(border=True):
                st.subheader("📝 Nuevo Registro (Cobro o Préstamo)")

                tipo_movimiento = st.radio(
                    "Operación a realizar:",
                    [
                        "Registrar Abono / Pago",
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
                    if tipo_movimiento == "Registrar Abono / Pago":
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

                    tasa_interes = 0.0
                    monto_interes_calc = 0.0
                    frecuencia_pago = "Diario"
                    num_cuotas = 1
                    valor_cuota_calc = 0.0

                    if tipo_movimiento == "Registrar Préstamo / Deuda Inicial":
                        st.markdown("---")
                        st.markdown("##### 📈 Calculadora de Cuotas y Frecuencia")
                        cp1, cp2, cp3 = st.columns(3)
                        tasa_interes = cp1.number_input(
                            "Interés (%)", min_value=0.0, value=15.0, step=1.0
                        )
                        frecuencia_pago = cp2.selectbox(
                            "Frecuencia de Cobro",
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
                                f"💵 **Capital:** ${monto_base_calc:,.2f} | "
                                f"📈 **Interés:** ${monto_interes_calc:,.2f} | "
                                f"⚠️ **Total Deuda:** ${deuda_total_calc:,.2f}\n\n"
                                f"👉 **{num_cuotas} cuotas {frecuencia_pago.lower()}s** de **${valor_cuota_calc:,.2f}** c/u"
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
                                scope = [
                                    "https://www.googleapis.com/auth/spreadsheets",
                                    "https://www.googleapis.com/auth/drive",
                                ]
                                creds_dict = dict(
                                    st.secrets["connections"]["gsheets"]
                                )
                                creds = Credentials.from_service_account_info(
                                    creds_dict, scopes=scope
                                )
                                client = gspread.authorize(creds)

                                spreadsheet_url = st.secrets["connections"][
                                    "gsheets"
                                ]["spreadsheet"]
                                sheet = client.open_by_url(
                                    spreadsheet_url
                                ).sheet1

                                filas_a_agregar = []

                                if tipo_movimiento == "Registrar Abono / Pago":
                                    desc_base = f"{tipo_cobro_abono}" + (
                                        f" - {concepto_personalizado}"
                                        if concepto_personalizado
                                        else ""
                                    )
                                else:
                                    desc_base = (
                                        f"Préstamo {frecuencia_pago} ({num_cuotas} cuotas de ${valor_cuota_calc:,.2f})"
                                        + (
                                            f" - {concepto_personalizado}"
                                            if concepto_personalizado
                                            else ""
                                        )
                                    )

                                if usar_dos_cuentas:
                                    if monto_total_calculado <= 0:
                                        st.error(
                                            "⚠️ Ingrese un monto mayor a cero."
                                        )
                                        st.stop()

                                    if (
                                        tipo_movimiento
                                        == "Registrar Abono / Pago"
                                    ):
                                        if monto_c1 > 0:
                                            filas_a_agregar.append(
                                                [
                                                    nueva_fecha.strftime(
                                                        "%Y-%m-%d"
                                                    ),
                                                    str(nuevo_codigo).strip(),
                                                    nuevo_nombre,
                                                    f"{desc_base} ({c_1})",
                                                    0.0,
                                                    float(monto_c1),
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
                                                    f"{desc_base} ({c_2})",
                                                    0.0,
                                                    float(monto_c2),
                                                ]
                                            )
                                    else:
                                        if monto_c1 > 0:
                                            filas_a_agregar.append(
                                                [
                                                    nueva_fecha.strftime(
                                                        "%Y-%m-%d"
                                                    ),
                                                    str(nuevo_codigo).strip(),
                                                    nuevo_nombre,
                                                    f"{desc_base} (Salida de {c_1})",
                                                    float(monto_c1),
                                                    0.0,
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
                                                    f"{desc_base} (Salida de {c_2})",
                                                    float(monto_c2),
                                                    0.0,
                                                ]
                                            )
                                else:
                                    if monto <= 0:
                                        st.error(
                                            "⚠️ Ingrese un monto mayor a cero."
                                        )
                                        st.stop()

                                    if (
                                        tipo_movimiento
                                        == "Registrar Abono / Pago"
                                    ):
                                        filas_a_agregar.append(
                                            [
                                                nueva_fecha.strftime(
                                                    "%Y-%m-%d"
                                                ),
                                                str(nuevo_codigo).strip(),
                                                nuevo_nombre,
                                                f"{desc_base} ({cuenta_afectada})",
                                                0.0,
                                                float(monto),
                                            ]
                                        )
                                    else:
                                        filas_a_agregar.append(
                                            [
                                                nueva_fecha.strftime(
                                                    "%Y-%m-%d"
                                                ),
                                                str(nuevo_codigo).strip(),
                                                nuevo_nombre,
                                                f"{desc_base} (Salida de {cuenta_afectada})",
                                                float(monto),
                                                0.0,
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
                                            f"Interés aplicado al préstamo ({tasa_interes}% - {frecuencia_pago})",
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
                        else:
                            st.error(
                                "⚠️ Ingrese el código y nombre del cliente."
                            )

        # ------------------------------------------
        # 3. APORTES Y RETIROS DE CAPITAL (DUEÑO)
        # ------------------------------------------
        elif seccion_admin == "💼 Aportes / Retiros Dueño":
            with st.container(border=True):
                st.subheader("💼 Gestión de Capital Propio (Aportes y Retiros)")
                st.caption(
                    "Ingresa o retira dinero de tus cajas para uso personal sin afectar los gastos operativos del negocio ni generar recargos."
                )

                tipo_op_capital = st.radio(
                    "Seleccione la operación a realizar:",
                    [
                        "📥 Inyectar Capital (Ingresar plata propia)",
                        "📤 Retirar Capital (Sacar plata sin generar gasto)",
                    ],
                    horizontal=True,
                )

                with st.form("form_capital_dueno"):
                    f_cap = st.date_input("Fecha", datetime.now())
                    c_cap = st.selectbox(
                        "Cuenta afectada:",
                        ["Efectivo", "Pago Móvil", "Binance"],
                    )
                    m_cap = st.number_input(
                        "Monto ($)", min_value=0.0, value=0.0
                    )
                    d_cap = st.text_input("Nota / Observación (Opcional)")

                    if st.form_submit_button(
                        "💾 Registrar Movimiento de Capital",
                        use_container_width=True,
                    ):
                        if m_cap <= 0:
                            st.error("⚠️ El monto debe ser mayor a 0.")
                        else:
                            try:
                                scope = [
                                    "https://www.googleapis.com/auth/spreadsheets",
                                    "https://www.googleapis.com/auth/drive",
                                ]
                                creds = Credentials.from_service_account_info(
                                    dict(st.secrets["connections"]["gsheets"]),
                                    scopes=scope,
                                )
                                client = gspread.authorize(creds)
                                sheet = client.open_by_url(
                                    st.secrets["connections"]["gsheets"][
                                        "spreadsheet"
                                    ]
                                ).sheet1

                                if (
                                    "Inyectar" in tipo_op_capital
                                ):  # Suma a la caja
                                    cargo_val = 0.0
                                    abono_val = float(m_cap)
                                    concepto_final = (
                                        f"Inyección de Capital ({c_cap})"
                                        + (f" - {d_cap}" if d_cap else "")
                                    )
                                else:  # Resta de la caja (Retiro personal)
                                    cargo_val = float(m_cap)
                                    abono_val = 0.0
                                    concepto_final = (
                                        f"Retiro de Capital Personal ({c_cap})"
                                        + (f" - {d_cap}" if d_cap else "")
                                    )

                                fila = [
                                    f_cap.strftime("%Y-%m-%d"),
                                    f"CAJA_{c_cap.upper()}",
                                    f"Dueño ({c_cap})",
                                    concepto_final,
                                    cargo_val,
                                    abono_val,
                                ]
                                sheet.append_row(fila)
                                st.toast(
                                    "✅ Movimiento de capital registrado correctamente",
                                    icon="💼",
                                )
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al conectar con la hoja: {e}")

        # ------------------------------------------
        # 4. TRANSFERENCIAS ENTRE CUENTAS
        # ------------------------------------------
        elif seccion_admin == "🔄 Transferencias":
            with st.container(border=True):
                st.subheader("🔄 Mover Dinero Entre Cuentas")

                with st.form("form_trans"):
                    ftr = st.date_input("Fecha", datetime.now())
                    cor = st.selectbox(
                        "Origen (Sale de:)",
                        ["Efectivo", "Pago Móvil", "Binance"],
                    )
                    cde = st.selectbox(
                        "Destino (Entra a:)",
                        ["Pago Móvil", "Efectivo", "Binance"],
                    )
                    mtr = st.number_input("Monto ($)", min_value=0.0)

                    if st.form_submit_button(
                        "Realizar Transferencia", use_container_width=True
                    ):
                        if cor == cde:
                            st.error("⚠️ Las cuentas deben ser distintas.")
                        elif mtr <= 0:
                            st.error("⚠️ Ingrese un monto mayor a cero.")
                        else:
                            try:
                                scope = [
                                    "https://www.googleapis.com/auth/spreadsheets",
                                    "https://www.googleapis.com/auth/drive",
                                ]
                                creds = Credentials.from_service_account_info(
                                    dict(st.secrets["connections"]["gsheets"]),
                                    scopes=scope,
                                )
                                client = gspread.authorize(creds)
                                sheet = client.open_by_url(
                                    st.secrets["connections"]["gsheets"][
                                        "spreadsheet"
                                    ]
                                ).sheet1

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

                                st.toast(
                                    f"✅ Transferencia de ${mtr:,.2f} efectuada ({cor} ➡️ {cde})",
                                    icon="🔄",
                                )
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

        # ------------------------------------------
        # 5. REGISTRAR GASTOS OPERATIVOS
        # ------------------------------------------
        elif seccion_admin == "📉 Gastos Operativos":
            with st.container(border=True):
                st.subheader("📉 Registrar Gasto Operativo del Negocio")
                st.caption(
                    "Utiliza esta sección únicamente para gastos reales de la empresa (papelería, transporte, nómina, servicios)."
                )

                with st.form("form_gastos_op"):
                    fga = st.date_input("Fecha", datetime.now())
                    cga = st.selectbox(
                        "Pagado con:", ["Efectivo", "Pago Móvil", "Binance"]
                    )
                    dga = st.text_input("Concepto / Detalle del Gasto")
                    mga = st.number_input("Monto ($)", min_value=0.0)

                    if st.form_submit_button(
                        "Guardar Gasto", use_container_width=True
                    ):
                        if dga and mga > 0:
                            try:
                                scope = [
                                    "https://www.googleapis.com/auth/spreadsheets",
                                    "https://www.googleapis.com/auth/drive",
                                ]
                                creds = Credentials.from_service_account_info(
                                    dict(st.secrets["connections"]["gsheets"]),
                                    scopes=scope,
                                )
                                client = gspread.authorize(creds)
                                sheet = client.open_by_url(
                                    st.secrets["connections"]["gsheets"][
                                        "spreadsheet"
                                    ]
                                ).sheet1

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
        # 6. LIQUIDAR CRÉDITOS
        # ------------------------------------------
        elif seccion_admin == "✂️ Liquidar Crédito":
            with st.container(border=True):
                st.subheader("✂️ Cerrar Ciclo de Crédito")

                if opciones_clientes:
                    cli_liq = st.selectbox(
                        "Seleccionar Cliente a Liquidar:", opciones_clientes
                    )
                    cod_liq = cli_liq.split(" - ")[0]
                    nom_liq = cli_liq.split(" - ")[1]

                    if st.button(
                        "✂️ Finalizar Crédito Vigente",
                        use_container_width=True,
                    ):
                        try:
                            scope = [
                                "https://www.googleapis.com/auth/spreadsheets",
                                "https://www.googleapis.com/auth/drive",
                            ]
                            creds = Credentials.from_service_account_info(
                                dict(st.secrets["connections"]["gsheets"]),
                                scopes=scope,
                            )
                            client = gspread.authorize(creds)
                            sheet = client.open_by_url(
                                st.secrets["connections"]["gsheets"][
                                    "spreadsheet"
                                ]
                            ).sheet1

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
        # 7. CIERRE DE MES Y ANALÍTICA
        # ------------------------------------------
        elif seccion_admin == "📅 Cierre de Mes":
            st.subheader("📅 Reporte Financiero Mensual")

            if not df_existente.empty:
                df_existente["Fecha"] = pd.to_datetime(
                    df_existente["Fecha"], errors="coerce"
                )
                df_valido = df_existente.dropna(subset=["Fecha"]).copy()

                df_valido["Mes_Año"] = df_valido["Fecha"].dt.strftime("%Y-%m")
                meses_disponibles = sorted(
                    df_valido["Mes_Año"].unique(), reverse=True
                )

                if meses_disponibles:
                    mes_sel = st.selectbox(
                        "Seleccionar Mes:", meses_disponibles
                    )
                    df_mes = df_valido[df_valido["Mes_Año"] == mes_sel]

                    gastos_mes = df_mes[
                        df_mes["Codigo"].str.contains("GASTO_", na=False)
                    ]["Cargo"].sum()
                    intereses_mes = df_mes[
                        df_mes["Concepto"].str.contains(
                            "Interés aplicado", case=False, na=False
                        )
                    ]["Cargo"].sum()
                    prestamos_mes = df_mes[
                        (
                            ~df_mes["Codigo"].str.contains(
                                "CUENTA_|GASTO_|CAJA_", na=False
                            )
                        )
                        & (
                            ~df_mes["Concepto"].str.contains(
                                "Interés aplicado", case=False, na=False
                            )
                        )
                    ]["Cargo"].sum()

                    cobrado_mes = df_mes[
                        ~df_mes["Codigo"].str.contains(
                            "CUENTA_|GASTO_|CAJA_", na=False
                        )
                    ]["Abono"].sum()
                    ganancia_neta = intereses_mes - gastos_mes

                    m1, m2, m3 = st.columns(3)
                    with m1:
                        with st.container(border=True):
                            st.metric(
                                "📈 Intereses Generados",
                                f"${intereses_mes:,.2f}",
                            )
                    with m2:
                        with st.container(border=True):
                            st.metric(
                                "📉 Gastos Operativos", f"${gastos_mes:,.2f}"
                            )
                    with m3:
                        with st.container(border=True):
                            st.metric(
                                "💰 Ganancia Neta",
                                f"${ganancia_neta:,.2f}",
                                delta=f"${ganancia_neta:,.2f}",
                            )

                    st.divider()

                    df_bar_mes = pd.DataFrame(
                        {
                            "Categoría": [
                                "Capital Prestado",
                                "Recaudado",
                                "Intereses",
                                "Gastos",
                            ],
                            "Monto ($)": [
                                prestamos_mes,
                                cobrado_mes,
                                intereses_mes,
                                gastos_mes,
                            ],
                        }
                    ).set_index("Categoría")
                    st.bar_chart(df_bar_mes)
