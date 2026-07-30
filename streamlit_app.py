from datetime import datetime
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import plotly.express as px
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
# LÓGICA DE CÁLCULO DE SALDOS (CORREGIDA)
# ==========================================
def calcular_saldo_cuenta(df, cuenta_nombre):
    """Calcula el saldo exacto (Abonos - Cargos) para una cuenta específica

    (Efectivo, Pago Móvil, Binance) sin falsos positivos en transferencias.
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

    # 1. Filtro por código explícito (CAJA_EFECTIVO, CUENTA_EFECTIVO, GASTO_EFECTIVO)
    cond_codigo = (
        df_clean["Codigo_norm"].str.contains(f"CAJA_{cuenta_norm}")
        | df_clean["Codigo_norm"].str.contains(f"GASTO_{cuenta_norm}")
        | df_clean["Codigo_norm"].str.contains(f"CUENTA_{cuenta_norm}")
    )

    # 2. Filtro por movimientos de clientes con etiqueta de cuenta (ej. "(EFECTIVO)", "SALIDA DE EFECTIVO")
    # Se excluye "CUENTA_" para no registrar las descripciones cruzadas de transferencias.
    cond_concepto = (~df_clean["Codigo_norm"].str.contains("CUENTA_")) & (
        df_clean["Concepto_norm"].str.contains(f"\\({cuenta_norm}\\)")
        | df_clean["Concepto_norm"].str.contains(f"SALIDA DE {cuenta_norm}")
    )

    df_cuenta = df_clean[cond_codigo | cond_concepto]

    # Saldo neto = Abonos (Entradas) - Cargos (Salidas)
    return float(df_cuenta["Abono"].sum() - df_cuenta["Cargo"].sum())


# ==========================================
# BARRA LATERAL (NAVEGACIÓN Y AUTENTICACIÓN)
# ==========================================
st.sidebar.image(
    "https://img.icons8.com/fluency/96/money-bag-with-card.png", width=80
)
st.sidebar.title("Control Financiero")
st.sidebar.caption("Gestión de Cobros, Cuentas y Préstamos v2.5")
st.sidebar.divider()

# Autenticación Admin en la Barra Lateral
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
                        f"📊 *Acumulado histórico total (Capital + Intereses): ${total_cargos_historico:,.2f}*"
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
                "💼 Alimentar Cajas",
                "🔄 Transferencias",
                "📉 Gastos",
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

                    # Cálculos con la función corregida
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

                    col_chart, col_cuentas = st.columns([1.2, 1])

                    with col_chart:
                        with st.container(border=True):
                            st.subheader("📊 Distribución de Cajas")
                            df_pie = pd.DataFrame(
                                {
                                    "Cuenta": [
                                        "Efectivo",
                                        "Pago Móvil",
                                        "Binance",
                                    ],
                                    "Monto": [
                                        max(0, efectivo_total),
                                        max(0, pago_movil_total),
                                        max(0, binance_total),
                                    ],
                                }
                            )
                            fig = px.pie(
                                df_pie,
                                values="Monto",
                                names="Cuenta",
                                hole=0.45,
                                color="Cuenta",
                                color_discrete_map={
                                    "Efectivo": "#2ecc71",
                                    "Pago Móvil": "#3498db",
                                    "Binance": "#f1c40f",
                                },
                            )
                            fig.update_layout(
                                margin=dict(t=20, b=20, l=10, r=10),
                                height=260,
                            )
                            st.plotly_chart(fig, use_container_width=True)

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
        # 3. ALIMENTAR CAJAS
        # ------------------------------------------
        elif seccion_admin == "💼 Alimentar Cajas":
            with st.container(border=True):
                st.subheader("💼 Inyección de Capital a Cajas")
                st.caption(
                    "Agrega fondos propios directamente a tus cuentas sin alterar saldos de clientes."
                )

                with st.form("form_inyectar"):
                    fin = st.date_input("Fecha", datetime.now())
                    cin = st.selectbox(
                        "Cuenta destino", ["Efectivo", "Pago Móvil", "Binance"]
                    )
                    miny = st.number_input(
                        "Monto a Inyectar ($)", min_value=0.0
                    )
                    din = st.text_input("Nota / Origen de los fondos")

                    if st.form_submit_button(
                        "Ingresar Fondos", use_container_width=True
                    ):
                        if miny > 0:
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

                                fila = [
                                    fin.strftime("%Y-%m-%d"),
                                    f"CAJA_{cin.upper()}",
                                    f"Inyección de Capital ({cin})",
                                    din if din else f"Inyección a {cin}",
                                    0.0,
                                    float(miny),
                                ]
                                sheet.append_row(fila)
                                st.toast(
                                    "✅ Capital ingresado con éxito", icon="🎉"
                                )
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

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

                                # Fila 1: Salida del Origen (CARGO)
                                sheet.append_row(
                                    [
                                        ftr.strftime("%Y-%m-%d"),
                                        f"CUENTA_{cor.upper()}",
                                        f"Sistema ({cor})",
                                        f"Transferencia enviada a {cde}",
                                        float(mtr),  # Salida
                                        0.0,
                                    ]
                                )

                                # Fila 2: Entrada al Destino (ABONO)
                                sheet.append_row(
                                    [
                                        ftr.strftime("%Y-%m-%d"),
                                        f"CUENTA_{cde.upper()}",
                                        f"Sistema ({cde})",
                                        f"Transferencia recibida de {cor}",
                                        0.0,
                                        float(mtr),  # Entrada
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
        # 5. REGISTRAR GASTOS
        # ------------------------------------------
        elif seccion_admin == "📉 Gastos":
            with st.container(border=True):
                st.subheader("📉 Registrar Gasto Operativo")

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
                st.caption(
                    "Genera una marca de corte para reiniciar la cuenta del cliente sin perder su historial."
                )

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
                                "Recaudado (Abonos)",
                                "Intereses",
                                "Gastos",
                            ],
                            "Monto": [
                                prestamos_mes,
                                cobrado_mes,
                                intereses_mes,
                                gastos_mes,
                            ],
                        }
                    )
                    fig_mes = px.bar(
                        df_bar_mes,
                        x="Categoría",
                        y="Monto",
                        color="Categoría",
                        text_auto=".2f",
                        title=f"Rendimiento de {mes_sel}",
                    )
                    fig_mes.update_layout(height=320, showlegend=False)
                    st.plotly_chart(fig_mes, use_container_width=True)
