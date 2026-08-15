from datetime import date, datetime, timedelta
import re
import urllib.parse
import uuid

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from streamlit_gsheets import GSheetsConnection


# ==========================================
# CONFIGURACIÓN
# ==========================================

TELEFONO_ADMIN = "584123801615"
CLAVE_ADMIN = "Kilometro12@"
DEFAULT_TASA = 65.0
DEFAULT_CODIGOS_BS = "CLI-001, CLI-002"

COLUMNAS_MOVIMIENTOS = [
    "Fecha",
    "Codigo",
    "Nombre",
    "Concepto",
    "Cargo",
    "Abono",
]

CUENTAS = ["Efectivo", "Pago Móvil", "Binance"]

st.set_page_config(
    page_title="Sistema de Cobros & Finanzas",
    page_icon="💹",
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
    </style>
    """,
    unsafe_allow_html=True,
)

conn = st.connection("gsheets", type=GSheetsConnection)


# ==========================================
# UTILIDADES
# ==========================================

def normalizar_texto(valor):
    """Normaliza texto para búsquedas y comparaciones."""
    if pd.isna(valor):
        return ""

    return (
        str(valor)
        .strip()
        .upper()
        .translate(str.maketrans("ÁÉÍÓÚ", "AEIOU"))
    )


def normalizar_codigo(valor):
    return normalizar_texto(valor)


def obtener_tasa_concepto(concepto, tasa_defecto):
    match = re.search(r"tasa:\s*([\d.]+)", str(concepto), re.IGNORECASE)
    return float(match.group(1)) if match else tasa_defecto


def es_dia_cobro(fecha_obj):
    if fecha_obj.weekday() == 6:
        return False

    festivos = {
        (1, 1), (19, 4), (1, 5), (24, 6), (5, 7),
        (24, 7), (12, 10), (24, 12), (25, 12), (31, 12),
    }

    return (fecha_obj.day, fecha_obj.month) not in festivos


def calcular_dias_cobro(fecha_inicio, fecha_fin):
    if fecha_inicio >= fecha_fin:
        return 0

    fechas = pd.date_range(
        fecha_inicio + timedelta(days=1),
        fecha_fin,
        freq="D",
    )

    return sum(es_dia_cobro(fecha.date()) for fecha in fechas)


def limpiar_datos(df):
    if df.empty:
        return pd.DataFrame(columns=COLUMNAS_MOVIMIENTOS)

    df = df.copy()

    for columna in COLUMNAS_MOVIMIENTOS:
        if columna not in df.columns:
            df[columna] = 0 if columna in ("Cargo", "Abono") else ""

    df["Codigo"] = df["Codigo"].map(normalizar_codigo)
    df["Nombre"] = df["Nombre"].fillna("").astype(str).str.strip()
    df["Concepto"] = df["Concepto"].fillna("").astype(str)
    df["Cargo"] = pd.to_numeric(df["Cargo"], errors="coerce").fillna(0.0)
    df["Abono"] = pd.to_numeric(df["Abono"], errors="coerce").fillna(0.0)
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")

    return df[COLUMNAS_MOVIMIENTOS]


def cliente_es_bs(codigo, codigos_bs):
    return normalizar_codigo(codigo) in codigos_bs


def convertir_monto_vista(row, columna, es_bs, tasa):
    monto = float(row[columna])
    if not es_bs:
        return monto

    tasa_registro = obtener_tasa_concepto(row["Concepto"], tasa)

    if columna == "Cargo" and "interés aplicado" in normalizar_texto(row["Concepto"]).lower():
        return round(monto * 1.75 * tasa_registro, 2)

    return round(monto * tasa_registro, 2)


def separar_credito_vigente(df_cliente):
    if df_cliente.empty:
        return df_cliente.copy(), df_cliente.copy()

    liquidaciones = df_cliente[
        df_cliente["Concepto"].str.contains(
            "Crédito anterior liquidado",
            case=False,
            na=False,
        )
    ]

    if liquidaciones.empty:
        return df_cliente.copy(), pd.DataFrame(columns=df_cliente.columns)

    ultimo_indice = liquidaciones.index[-1]

    return (
        df_cliente.loc[df_cliente.index > ultimo_indice].copy(),
        df_cliente.loc[df_cliente.index <= ultimo_indice].copy(),
    )


def calcular_saldo_cuenta(df, cuenta):
    if df.empty:
        return 0.0

    cuenta_norm = normalizar_texto(cuenta)
    codigo = df["Codigo"].map(normalizar_texto)
    concepto = df["Concepto"].map(normalizar_texto)

    mascara = (
        codigo.str.contains(
            rf"CAJA_{re.escape(cuenta_norm)}|"
            rf"GASTO_{re.escape(cuenta_norm)}|"
            rf"CUENTA_{re.escape(cuenta_norm)}",
            regex=True,
            na=False,
        )
        |
        (
            ~codigo.str.contains("CUENTA_", na=False)
            & concepto.str.contains(
                rf"\({re.escape(cuenta_norm)}\)|SALIDA DE "
                rf"{re.escape(cuenta_norm)}",
                regex=True,
                na=False,
            )
        )
    )

    movimientos = df[mascara]
    return float(movimientos["Abono"].sum() - movimientos["Cargo"].sum())


def texto_whatsapp(mensaje):
    return urllib.parse.quote(mensaje)


def invalidar_cache():
    st.cache_data.clear()


# ==========================================
# GOOGLE SHEETS
# ==========================================

def obtener_cliente_gspread():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    secretos = dict(st.secrets["connections"]["gsheets"])
    credenciales = Credentials.from_service_account_info(
        secretos,
        scopes=scopes,
    )

    return gspread.authorize(credenciales)


def obtener_hoja(nombre="Sheet1"):
    cliente = obtener_cliente_gspread()
    url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    archivo = cliente.open_by_url(url)

    try:
        return archivo.worksheet(nombre)
    except gspread.WorksheetNotFound:
        if nombre == "CONFIGURACION":
            hoja = archivo.add_worksheet(
                title=nombre,
                rows=10,
                cols=2,
            )
            hoja.append_rows(
                [
                    ["Parametro", "Valor"],
                    ["tasa_bs_usd", str(DEFAULT_TASA)],
                    ["codigos_bs", DEFAULT_CODIGOS_BS],
                ]
            )
            return hoja

        if nombre == "PAGOS_PENDIENTES":
            hoja = archivo.add_worksheet(
                title=nombre,
                rows=1000,
                cols=8,
            )
            hoja.append_row(
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
            return hoja

        try:
            return archivo.worksheet("Hoja 1")
        except gspread.WorksheetNotFound:
            return archivo.get_worksheet(0)


@st.cache_data(ttl=60, show_spinner=False)
def cargar_movimientos():
    try:
        return limpiar_datos(
            conn.read(
                ttl=60,
                usecols=COLUMNAS_MOVIMIENTOS,
            )
        )
    except Exception:
        return pd.DataFrame(columns=COLUMNAS_MOVIMIENTOS)


@st.cache_data(ttl=300, show_spinner=False)
def cargar_configuracion():
    try:
        registros = obtener_hoja("CONFIGURACION").get_all_records()
        configuracion = {
            str(registro.get("Parametro", "")).strip():
            str(registro.get("Valor", "")).strip()
            for registro in registros
        }

        tasa = float(configuracion.get("tasa_bs_usd", DEFAULT_TASA))
        codigos = configuracion.get("codigos_bs", DEFAULT_CODIGOS_BS)

        return tasa, {
            normalizar_codigo(codigo)
            for codigo in codigos.split(",")
            if codigo.strip()
        }

    except Exception:
        return DEFAULT_TASA, {
            normalizar_codigo(codigo)
            for codigo in DEFAULT_CODIGOS_BS.split(",")
        }


def guardar_configuracion(tasa, codigos):
    hoja = obtener_hoja("CONFIGURACION")
    hoja.update_cell(2, 2, str(tasa))
    hoja.update_cell(3, 2, str(codigos))
    invalidar_cache()


def agregar_movimientos(filas):
    if not filas:
        return

    hoja = obtener_hoja()
    hoja.append_rows(filas, value_input_option="USER_ENTERED")
    invalidar_cache()


# ==========================================
# DATOS GLOBALES
# ==========================================

tasa_bs_usd, codigos_bs = cargar_configuracion()
df_movimientos = cargar_movimientos()


# ==========================================
# SIDEBAR
# ==========================================

st.sidebar.image(
    "https://img.icons8.com/?size=100&id=51oKaN3XSMKu&format=png&color=000000",
    width=80,
)
st.sidebar.title("Control Financiero")
st.sidebar.caption("Gestión de Cobros, Cuentas y Préstamos")
st.sidebar.divider()

clave_admin = st.sidebar.text_input(
    "Contraseña de administrador:",
    type="password",
)

es_admin = clave_admin == CLAVE_ADMIN

if es_admin:
    st.sidebar.success("🟢 Sesión activa")

    with st.sidebar.form("configuracion"):
        nueva_tasa = st.number_input(
            "Tasa Bs / $:",
            min_value=1.0,
            value=float(tasa_bs_usd),
            step=0.5,
        )
        nuevos_codigos = st.text_input(
            "Códigos Bs:",
            value=", ".join(sorted(codigos_bs)),
        )

        if st.form_submit_button("💾 Guardar configuración"):
            try:
                guardar_configuracion(nueva_tasa, nuevos_codigos)
                st.sidebar.success("Configuración guardada")
                st.rerun()
            except Exception as error:
                st.sidebar.error(f"Error: {error}")

elif clave_admin:
    st.sidebar.error("🔴 Clave incorrecta")

modo = st.sidebar.radio(
    "Navegación:",
    ["👥 Portal del Cliente", "💼 Panel de Administrador"],
)


# ==========================================
# PORTAL DEL CLIENTE
# ==========================================

def mostrar_portal_cliente():
    st.title("👥 Portal de Atención al Cliente")

    parametros = st.query_params
    codigo_url = normalizar_codigo(parametros.get("cliente", ""))
    accion_url = str(parametros.get("accion", "")).lower()

    opciones = [
        "🔎 Consultar Estado de Cuenta",
        "📲 Reportar un Pago",
    ]

    opcion = st.segmented_control(
        "¿Qué deseas realizar?",
        opciones,
        default=opciones[1] if accion_url == "reportar" else opciones[0],
    )

    if opcion == opciones[0]:
        consultar_estado_cliente(codigo_url)
    else:
        reportar_pago(codigo_url)


def consultar_estado_cliente(codigo_url):
    codigo = st.text_input(
        "Código de Cliente:",
        value=codigo_url,
        placeholder="Ej. CLI-001",
    ).strip().upper()

    if not st.button("🔎 Consultar", use_container_width=True):
        if not codigo_url:
            return

    if not codigo:
        st.warning("Ingrese un código de cliente.")
        return

    resultado = df_movimientos[
        df_movimientos["Codigo"] == normalizar_codigo(codigo)
    ]

    if resultado.empty:
        st.error("❌ Código no encontrado.")
        return

    nombre = resultado.iloc[0]["Nombre"]
    es_bs = cliente_es_bs(codigo, codigos_bs)
    moneda = "Bs." if es_bs else "$"

    actuales, historicos = separar_credito_vigente(resultado)

    if actuales.empty:
        st.info("No hay movimientos para el crédito vigente.")
        return

    actuales = actuales.copy()
    actuales["Cargo_Vis"] = actuales.apply(
        lambda fila: convertir_monto_vista(
            fila, "Cargo", es_bs, tasa_bs_usd
        ),
        axis=1,
    )
    actuales["Abono_Vis"] = actuales.apply(
        lambda fila: convertir_monto_vista(
            fila, "Abono", es_bs, tasa_bs_usd
        ),
        axis=1,
    )

    cargos = actuales["Cargo_Vis"].sum()
    abonos = actuales["Abono_Vis"].sum()
    saldo = cargos - abonos

    st.subheader(f"Bienvenido/a, **{nombre}**")

    col1, col2, col3 = st.columns(3)
    col1.metric("📌 Deuda total", f"{moneda} {cargos:,.2f}")
    col2.metric("💵 Total abonado", f"{moneda} {abonos:,.2f}")
    col3.metric("⚠️ Saldo pendiente", f"{moneda} {saldo:,.2f}")

    if saldo <= 0:
        st.success("✅ Crédito liquidado.")
    else:
        st.warning("⚠️ Crédito pendiente.")

    st.subheader("📋 Movimientos del crédito vigente")

    st.dataframe(
        actuales[
            ["Fecha", "Concepto", "Cargo_Vis", "Abono_Vis"]
        ],
        column_config={
            "Fecha": st.column_config.DateColumn("Fecha"),
            "Concepto": "Concepto / Detalle",
            "Cargo_Vis": st.column_config.NumberColumn(
                f"Monto ({moneda})",
                format=f"{moneda} %.2f",
            ),
            "Abono_Vis": st.column_config.NumberColumn(
                f"Abonado ({moneda})",
                format=f"{moneda} %.2f",
            ),
        },
        use_container_width=True,
        hide_index=True,
    )

    if not historicos.empty:
        with st.expander("📂 Ver créditos anteriores"):
            st.dataframe(
                historicos[
                    ["Fecha", "Concepto", "Cargo", "Abono"]
                ],
                use_container_width=True,
                hide_index=True,
            )


def reportar_pago(codigo_url):
    st.subheader("📲 Reportar un Pago")

    with st.form("reporte_pago"):
        col1, col2 = st.columns(2)

        codigo = col1.text_input(
            "Código de Cliente:",
            value=codigo_url,
        )
        nombre = col2.text_input("Nombre completo:")

        fecha_pago = st.date_input("Fecha del pago", value=date.today())
        moneda = st.selectbox(
            "Moneda:",
            ["Bolívares (Bs.)", "Dólares ($)"],
        )
        monto = st.number_input(
            "Monto:",
            min_value=0.01,
            value=100.0,
            step=10.0,
        )
        cuenta = st.selectbox("Medio de pago:", CUENTAS)
        referencia = st.text_input("Referencia:")

        enviar = st.form_submit_button(
            "💾 Registrar pago",
            use_container_width=True,
        )

    if not enviar:
        return

    codigo = normalizar_codigo(codigo)

    if not codigo or not nombre.strip() or not referencia.strip():
        st.warning("Complete todos los campos obligatorios.")
        return

    es_bs = cliente_es_bs(codigo, codigos_bs)

    if es_bs and "Bolívares" in moneda:
        monto_usd = round(monto / tasa_bs_usd, 4)
        referencia_final = (
            f"{referencia.strip()} "
            f"(Bs. {monto:,.2f} a tasa {tasa_bs_usd})"
        )
    else:
        monto_usd = round(monto, 2)
        referencia_final = referencia.strip()

    pago_id = f"PAG-{uuid.uuid4().hex[:6].upper()}"

    try:
        obtener_hoja("PAGOS_PENDIENTES").append_row(
            [
                pago_id,
                fecha_pago.strftime("%Y-%m-%d"),
                codigo,
                nombre.strip(),
                cuenta,
                referencia_final,
                monto_usd,
                "PENDIENTE",
            ]
        )

        invalidar_cache()

        mensaje = (
            f"*NUEVO PAGO REPORTADO*\n\n"
            f"*ID:* {pago_id}\n"
            f"*Cliente:* {nombre.strip()} ({codigo})\n"
            f"*Monto:* {monto:,.2f}\n"
            f"*Equivalente:* ${monto_usd:,.2f}\n"
            f"*Medio:* {cuenta}\n"
            f"*Referencia:* {referencia.strip()}"
        )

        enlace = (
            f"https://wa.me/{TELEFONO_ADMIN}"
            f"?text={texto_whatsapp(mensaje)}"
        )

        st.success(f"✅ Pago registrado. ID: `{pago_id}`")
        st.link_button("📤 Enviar por WhatsApp", enlace)

    except Exception as error:
        st.error(f"Error al registrar el pago: {error}")


# ==========================================
# ADMINISTRACIÓN
# ==========================================

def obtener_clientes():
    if df_movimientos.empty:
        return pd.DataFrame(columns=["Codigo", "Nombre"])

    excluir = r"CUENTA_|GASTO_|CAJA_|PASIVO_EXT"

    return (
        df_movimientos[
            ~df_movimientos["Codigo"].str.contains(
                excluir,
                regex=True,
                na=False,
            )
        ][["Codigo", "Nombre"]]
        .drop_duplicates()
        .sort_values("Codigo")
    )


def aprobar_pago(fila):
    hoja_principal = obtener_hoja()
    hoja_pendientes = obtener_hoja("PAGOS_PENDIENTES")

    es_bs = cliente_es_bs(fila["Codigo"], codigos_bs)
    tasa = f" (Tasa: {tasa_bs_usd})" if es_bs else ""

    hoja_principal.append_row(
        [
            fila["Fecha"],
            fila["Codigo"],
            fila["Nombre"],
            f"Abono verificado Ref: {fila['Referencia']} "
            f"({fila['Cuenta']}){tasa}",
            0.0,
            float(fila["Monto"]),
        ]
    )

    celda = hoja_pendientes.find(str(fila["ID"]))
    hoja_pendientes.update_cell(celda.row, 8, "APROBADO")
    invalidar_cache()


def mostrar_pagos_pendientes():
    st.subheader("⏳ Abonos por Verificar")

    try:
        datos = obtener_hoja("PAGOS_PENDIENTES").get_all_records()
        pendientes = pd.DataFrame(datos)

        if pendientes.empty:
            st.success("🎉 No hay pagos pendientes.")
            return

        pendientes = pendientes[
            pendientes["Estado"].eq("PENDIENTE")
        ]

        if pendientes.empty:
            st.success("🎉 No hay pagos pendientes.")
            return

        st.info(f"Hay {len(pendientes)} pago(s) pendiente(s).")

        for _, fila in pendientes.iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns(3)

                col1.markdown(
                    f"👤 **{fila['Nombre']}**\n\n"
                    f"`{fila['Codigo']}`"
                )
                col2.markdown(
                    f"💵 **${float(fila['Monto']):,.2f} USD**\n\n"
                    f"Vía: {fila['Cuenta']}"
                )
                col3.markdown(
                    f"🔢 `{fila['Referencia']}`\n\n"
                    f"Fecha: {fila['Fecha']}"
                )

                aprobar, rechazar = st.columns(2)

                if aprobar.button(
                    "✅ Aprobar",
                    key=f"aprobar_{fila['ID']}",
                    use_container_width=True,
                ):
                    try:
                        aprobar_pago(fila)
                        st.success("Pago aprobado.")
                        st.rerun()
                    except Exception as error:
                        st.error(f"Error: {error}")

                if rechazar.button(
                    "❌ Rechazar",
                    key=f"rechazar_{fila['ID']}",
                    use_container_width=True,
                ):
                    try:
                        hoja = obtener_hoja("PAGOS_PENDIENTES")
                        celda = hoja.find(str(fila["ID"]))
                        hoja.update_cell(celda.row, 8, "RECHAZADO")
                        invalidar_cache()
                        st.success("Pago rechazado.")
                        st.rerun()
                    except Exception as error:
                        st.error(f"Error: {error}")


def registrar_movimiento():
    st.subheader("➕ Registrar Movimiento")

    clientes = obtener_clientes()
    nombres_clientes = [
        f"{fila.Codigo} - {fila.Nombre}"
        for fila in clientes.itertuples()
    ]

    tipo = st.radio(
        "Tipo de movimiento:",
        ["Abono / Pago", "Préstamo"],
        horizontal=True,
    )

    moneda = st.radio(
        "Moneda:",
        ["Dólares ($)", "Bolívares (Bs.)"],
        horizontal=True,
    )

    nuevo_cliente = st.checkbox("➕ Cliente nuevo")

    if nuevo_cliente or not nombres_clientes:
        col1, col2 = st.columns(2)
        codigo = col1.text_input("Código")
        nombre = col2.text_input("Nombre")
    else:
        seleccionado = st.selectbox("Cliente:", nombres_clientes)
        codigo, nombre = seleccionado.split(" - ", 1)

    cuenta = st.selectbox("Cuenta:", CUENTAS)
    fecha_movimiento = st.date_input("Fecha:", value=date.today())
    monto = st.number_input(
        "Monto:",
        min_value=0.01,
        value=100.0,
        step=10.0,
    )

    frecuencia = "General"
    cuotas = 1
    interes = 0.0

    if tipo == "Préstamo":
        col1, col2, col3 = st.columns(3)

        frecuencia = col1.selectbox(
            "Frecuencia:",
            ["Diario", "Semanal", "Quincenal", "Mensual"],
        )
        cuotas = col2.number_input(
            "Cuotas:",
            min_value=1,
            value=24,
            step=1,
        )

        if moneda == "Dólares ($)":
            interes = col3.number_input(
                "Interés (%):",
                min_value=0.0,
                value=20.0,
                step=1.0,
            )
        else:
            interes = 35.0

    nota = st.text_input("Nota opcional:")

    if not st.button("💾 Guardar movimiento", use_container_width=True):
        return

    if not codigo.strip() or not nombre.strip():
        st.warning("Complete el código y el nombre.")
        return

    codigo = normalizar_codigo(codigo)
    es_bs = moneda == "Bolívares (Bs.)"
    monto_usd = monto / tasa_bs_usd if es_bs else monto

    if tipo == "Abono / Pago":
        concepto = f"Abono General ({cuenta})"
        cargo = 0.0
        abono = monto_usd
    else:
        concepto = (
            f"Préstamo {frecuencia} "
            f"({int(cuotas)} cuotas) ({cuenta})"
        )
        cargo = monto_usd
        abono = 0.0

    if nota.strip():
        concepto += f" - {nota.strip()}"

    tasa = f" (Tasa: {tasa_bs_usd})" if es_bs else ""

    filas = [
        [
            fecha_movimiento.strftime("%Y-%m-%d"),
            codigo,
            nombre.strip(),
            concepto + tasa,
            cargo,
            abono,
        ]
    ]

    if tipo == "Préstamo" and interes > 0:
        filas.append(
            [
                fecha_movimiento.strftime("%Y-%m-%d"),
                codigo,
                nombre.strip(),
                f"Interés aplicado ({interes}%){tasa}",
                monto_usd * interes / 100,
                0.0,
            ]
        )

    try:
        agregar_movimientos(filas)
        st.success("✅ Movimiento guardado.")
        st.rerun()
    except Exception as error:
        st.error(f"Error al guardar: {error}")


def mostrar_flujo_caja():
    st.subheader("📊 Flujo de Caja")

    if df_movimientos.empty:
        st.info("No hay movimientos registrados.")
        return

    saldo_cuentas = {
        cuenta: calcular_saldo_cuenta(df_movimientos, cuenta)
        for cuenta in CUENTAS
    }

    total_caja = sum(saldo_cuentas.values())

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💵 Efectivo", f"${saldo_cuentas['Efectivo']:,.2f}")
    col2.metric("📱 Pago Móvil", f"${saldo_cuentas['Pago Móvil']:,.2f}")
    col3.metric("🪙 Binance", f"${saldo_cuentas['Binance']:,.2f}")
    col4.metric("💎 Total en Caja", f"${total_caja:,.2f}")

    datos = df_movimientos.copy()
    datos["Fecha"] = datos["Fecha"].dt.strftime("%Y-%m-%d")

    resumen = (
        datos.groupby("Fecha")
        .agg(
            Cobros=("Abono", "sum"),
            Gastos=("Cargo", "sum"),
        )
        .assign(
            Flujo_Neto=lambda tabla: tabla["Cobros"] - tabla["Gastos"]
        )
        .sort_index(ascending=False)
        .reset_index()
    )

    st.dataframe(
        resumen,
        column_config={
            "Fecha": st.column_config.TextColumn("Fecha"),
            "Cobros": st.column_config.NumberColumn(
                "Cobros ($)",
                format="$%.2f",
            ),
            "Gastos": st.column_config.NumberColumn(
                "Gastos ($)",
                format="$%.2f",
            ),
            "Flujo_Neto": st.column_config.NumberColumn(
                "Flujo neto ($)",
                format="$%.2f",
            ),
        },
        use_container_width=True,
        hide_index=True,
    )

    if not resumen.empty:
        st.line_chart(
            resumen.set_index("Fecha")[["Cobros", "Gastos"]]
        )


def mostrar_admin():
    st.title("💼 Dashboard de Administración")

    if not es_admin:
        st.warning(
            "🔒 El panel está bloqueado. Ingrese la contraseña en la barra lateral."
        )
        return

    secciones = [
        "⏳ Abonos por Verificar",
        "➕ Registrar Movimiento",
        "📊 Flujo de Caja",
    ]

    seccion = st.segmented_control(
        "Seleccione una sección:",
        secciones,
        default=secciones[0],
    )

    if seccion == secciones[0]:
        mostrar_pagos_pendientes()
    elif seccion == secciones[1]:
        registrar_movimiento()
    else:
        mostrar_flujo_caja()


# ==========================================
# EJECUCIÓN
# ==========================================

if modo == "👥 Portal del Cliente":
    mostrar_portal_cliente()
else:
    mostrar_admin()
