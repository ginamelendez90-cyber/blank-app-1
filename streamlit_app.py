from datetime import datetime
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Sistema de Cobros y Finanzas", page_icon="💰", layout="wide")
st.title("Sistema de Gestión Financiera y Cobros")

conn = st.connection("gsheets", type=GSheetsConnection)

tab_cliente, tab_admin = st.tabs(["Consulta de Cliente", "Panel de Administrador"])

# ==========================================
# PESTAÑA 1: CONSULTA DE CLIENTE
# ==========================================
with tab_cliente:
    st.write(
        "Por favor, ingrese su código único para ver su estado de cuenta y movimientos."
    )
    codigo_cliente = st.text_input("Código de Cliente:")

    if st.button("Consultar"):
        if codigo_cliente:
            df = conn.read(
                ttl=0,
                usecols=["Fecha", "Codigo", "Nombre", "Concepto", "Cargo", "Abono"],
            )

            df["Codigo"] = df["Codigo"].astype(str).str.strip()
            codigo_buscado = str(codigo_cliente).strip()

            resultado = df[df["Codigo"] == codigo_buscado]

            if not resultado.empty:
                st.success("¡Datos encontrados!")

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

                st.subheader(f"Cliente: {nombre}")

                col1, col2, col3 = st.columns(3)
                col1.metric("📌 Deuda Total Actual", f"${prestamo_actual:,.2f}")
                col2.metric("💵 Abonado (Pagos)", f"${pagos_actual:,.2f}")
                col3.metric("⚠️ Saldo Pendiente", f"${saldo_pendiente:,.2f}")

                st.markdown(
                    f"<p style='color: gray; font-size: 14px; margin-bottom: 20px;'>"
                    f"<i>📊 Acumulado histórico total (Capital + Intereses): ${total_cargos_historico:,.2f}</i>"
                    f"</p>",
                    unsafe_allow_html=True,
                )

                st.divider()
                st.subheader("Historial del Crédito Vigente")
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
                        "📂 Ver Historial de Créditos Anteriores / Liquidados"
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
                    "Código no encontrado. Por favor verifique e intente nuevamente."
                )
        else:
            st.warning("Por favor ingrese un código válido.")

# ==========================================
# PESTAÑA 2: PANEL DE ADMINISTRADOR
# ==========================================
with tab_admin:
    st.write("Área restringida de control y gestión.")
    clave_admin = st.text_input(
        "Contraseña de Administrador:", type="password", key="clave_admin_unica"
    )

    if clave_admin == "admin123":
        st.success("Acceso concedido al panel de control.")

        seccion_admin = st.radio(
            "¿Qué deseas hacer?",
            [
                "Registrar Movimientos",
                "Inyectar Dinero / Alimentar Caja",
                "Transferir entre Cuentas",
                "Registrar Gasto",
                "Liquidar / Cerrar Crédito",
                "Flujo de Caja y Cuentas",
                "Cierre de Mes"
            ],
            horizontal=True
        )

        st.divider()

        try:
            df_existente = conn.read(
                ttl=0,
                usecols=["Fecha", "Codigo", "Nombre", "Concepto", "Cargo", "Abono"],
            )
            df_existente["Codigo"] = df_existente["Codigo"].astype(str).str.strip()
            df_existente["Nombre"] = df_existente["Nombre"].astype(str).str.strip()
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
        # 1. REGISTRAR MOVIMIENTOS (DIARIOS / SEMANALES)
        # ------------------------------------------
        if seccion_admin == "Registrar Movimientos":
            st.subheader("Registrar Cobro (Diario/Semanal) o Préstamo")

            tipo_movimiento = st.radio(
                "Tipo de movimiento:",
                [
                    "Registrar Abono / Pago",
                    "Registrar Préstamo / Deuda Inicial",
                ],
            )

            usar_dos_cuentas = st.checkbox(
                "🔀 ¿El dinero sale/entra combinando DOS cuentas al mismo tiempo? (Ej: Efectivo + Binance)"
            )

            if not usar_dos_cuentas:
                if tipo_movimiento == "Registrar Abono / Pago":
                    cuenta_afectada = st.selectbox(
                        "¿A qué cuenta ingresa el pago?",
                        ["Efectivo", "Pago Móvil", "Binance"],
                    )
                else:
                    cuenta_afectada = st.selectbox(
                        "¿De qué cuenta sale el dinero para este préstamo?",
                        ["Efectivo", "Pago Móvil", "Binance"],
                    )

            es_nuevo_cliente = st.checkbox("➕ Registrar como cliente NUEVO")

            if not es_nuevo_cliente and opciones_clientes:
                cliente_seleccionado = st.selectbox(
                    "Selecciona al Cliente Existente:", opciones_clientes
                )
                nuevo_codigo = cliente_seleccionado.split(" - ")[0]
                nuevo_nombre = cliente_seleccionado.split(" - ")[1]
            else:
                st.info("Ingresa los datos del nuevo cliente:")
                nuevo_codigo = st.text_input("Código del Cliente (Ej. CLI-002)")
                nuevo_nombre = st.text_input("Nombre del Cliente")

            with st.form("formulario_registro"):
                nueva_fecha = st.date_input("Fecha del movimiento", datetime.now())

                # Modalidad de Cobro para Abonos
                tipo_cobro_abono = "Abono General"
                if tipo_movimiento == "Registrar Abono / Pago":
                    tipo_cobro_abono = st.selectbox(
                        "Modalidad de Cobro:",
                        ["Cobro Diario", "Cobro Semanal", "Abono General / Libre"]
                    )

                # Montos
                monto = 0.0
                monto_total_calculado = 0.0
                
                if usar_dos_cuentas:
                    st.markdown("##### Distribución del monto entre 2 cuentas:")
                    c_1 = st.selectbox(
                        "Primera Cuenta",
                        ["Efectivo", "Pago Móvil", "Binance"],
                        key="c1",
                    )
                    monto_c1 = st.number_input(
                        f"Monto correspondiente al {c_1} ($)",
                        min_value=0.0,
                        value=0.0,
                        key="mc1",
                    )

                    otras_cuentas = [
                        c for c in ["Efectivo", "Pago Móvil", "Binance"] if c != c_1
                    ]
                    c_2 = st.selectbox("Segunda Cuenta", otras_cuentas, key="c2")
                    monto_c2 = st.number_input(
                        f"Monto correspondiente al {c_2} ($)",
                        min_value=0.0,
                        value=0.0,
                        key="mc2",
                    )

                    monto_total_calculado = monto_c1 + monto_c2
                else:
                    monto = st.number_input("Monto del Abono / Préstamo ($)", min_value=0.0, value=0.0)

                # Condiciones si es Préstamo (Frecuencia diaria / semanal)
                tasa_interes = 0.0
                dias_prestamo = 0
                monto_interes_calc = 0.0
                frecuencia_pago = "Diario"
                num_cuotas = 1
                valor_cuota_calc = 0.0

                if tipo_movimiento == "Registrar Préstamo / Deuda Inicial":
                    st.markdown("##### 📈 Condiciones y Frecuencia del Préstamo")
                    col_p1, col_p2, col_p3 = st.columns(3)
                    tasa_interes = col_p1.number_input("Tasa de Interés (%)", min_value=0.0, value=0.0, step=1.0)
                    frecuencia_pago = col_p2.selectbox("Frecuencia de Cobro", ["Diario", "Semanal", "Quincenal", "Mensual"])
                    num_cuotas = col_p3.number_input("Número de Cuotas", min_value=1, value=24 if frecuencia_pago=="Diario" else (4 if frecuencia_pago=="Semanal" else 1), step=1)
                    
                    dias_prestamo = num_cuotas if frecuencia_pago == "Diario" else (num_cuotas * 7 if frecuencia_pago == "Semanal" else num_cuotas * 30)

                    monto_base_calc = monto_total_calculado if usar_dos_cuentas else monto
                    monto_interes_calc = monto_base_calc * (tasa_interes / 100)
                    deuda_total_calc = monto_base_calc + monto_interes_calc
                    valor_cuota_calc = deuda_total_calc / num_cuotas if num_cuotas > 0 else 0.0

                    if monto_base_calc > 0:
                        st.info(
                            f"💵 **Capital Prestado:** ${monto_base_calc:,.2f} \n\n"
                            f"📈 **Interés a cobrar:** ${monto_interes_calc:,.2f} \n\n"
                            f"⚠️ **Deuda Total Cliente:** ${deuda_total_calc:,.2f} \n\n"
                            f"📅 **Plan de Cobro:** {num_cuotas} cuotas {frecuencia_pago.lower()}s de **${valor_cuota_calc:,.2f}** c/u"
                        )

                concepto_personalizado = st.text_input(
                    "Concepto / Nota adicional (Opcional)", value=""
                )

                boton_guardar = st.form_submit_button("Guardar en el Sistema")

                if boton_guardar:
                    if nuevo_codigo and nuevo_nombre:
                        try:
                            scope = [
                                "https://www.googleapis.com/auth/spreadsheets",
                                "https://www.googleapis.com/auth/drive",
                            ]
                            creds_dict = dict(st.secrets["connections"]["gsheets"])
                            creds = Credentials.from_service_account_info(
                                creds_dict, scopes=scope
                            )
                            client = gspread.authorize(creds)

                            spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
                            sheet = client.open_by_url(spreadsheet_url).sheet1

                            filas_a_agregar = []
                            
                            if tipo_movimiento == "Registrar Abono / Pago":
                                desc_base = f"{tipo_cobro_abono}" + (f" - {concepto_personalizado}" if concepto_personalizado else "")
                            else:
                                desc_base = f"Préstamo {frecuencia_pago} ({num_cuotas} cuotas de ${valor_cuota_calc:,.2f})" + (f" - {concepto_personalizado}" if concepto_personalizado else "")

                            if usar_dos_cuentas:
                                if monto_total_calculado <= 0:
                                    st.error("⚠️ Los montos combinados deben ser mayores a 0.")
                                    st.stop()

                                if tipo_movimiento == "Registrar Abono / Pago":
                                    if monto_c1 > 0:
                                        filas_a_agregar.append([nueva_fecha.strftime("%Y-%m-%d"), str(nuevo_codigo).strip(), nuevo_nombre, f"{desc_base} ({c_1})", 0.0, float(monto_c1)])
                                    if monto_c2 > 0:
                                        filas_a_agregar.append([nueva_fecha.strftime("%Y-%m-%d"), str(nuevo_codigo).strip(), nuevo_nombre, f"{desc_base} ({c_2})", 0.0, float(monto_c2)])
                                else:
                                    if monto_c1 > 0:
                                        filas_a_agregar.append([nueva_fecha.strftime("%Y-%m-%d"), str(nuevo_codigo).strip(), nuevo_nombre, f"{desc_base} (Salida de {c_1})", float(monto_c1), 0.0])
                                    if monto_c2 > 0:
                                        filas_a_agregar.append([nueva_fecha.strftime("%Y-%m-%d"), str(nuevo_codigo).strip(), nuevo_nombre, f"{desc_base} (Salida de {c_2})", float(monto_c2), 0.0])
                            
                            else:
                                if monto <= 0:
                                    st.error("⚠️ Ingresa un monto válido mayor a 0.")
                                    st.stop()

                                if tipo_movimiento == "Registrar Abono / Pago":
                                    filas_a_agregar.append([nueva_fecha.strftime("%Y-%m-%d"), str(nuevo_codigo).strip(), nuevo_nombre, f"{desc_base} ({cuenta_afectada})", 0.0, float(monto)])
                                else:
                                    filas_a_agregar.append([nueva_fecha.strftime("%Y-%m-%d"), str(nuevo_codigo).strip(), nuevo_nombre, f"{desc_base} (Salida de {cuenta_afectada})", float(monto), 0.0])

                            # REGISTRAR EL INTERÉS COMO LÍNEA SEPARADA (Si es préstamo)
                            if tipo_movimiento == "Registrar Préstamo / Deuda Inicial" and monto_interes_calc > 0:
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

                            st.success(f"✅ ¡Movimiento registrado correctamente para {nuevo_nombre}!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")
                    else:
                        st.error("⚠️ Por favor, completa el código y el nombre del cliente.")

        # ------------------------------------------
        # 2. INYECTAR DINERO / ALIMENTAR CAJA
        # ------------------------------------------
        elif seccion_admin == "Inyectar Dinero / Alimentar Caja":
            st.subheader("Inyectar Dinero / Capital a una Cuenta")
            st.write(
                "Utiliza esta opción para agregar fondos propios o capital externo a tu Efectivo, Pago Móvil o Binance sin afectar cuentas de clientes."
            )

            with st.form("form_inyectar"):
                fecha_inyeccion = st.date_input("Fecha de inyección", datetime.now())
                cuenta_destino_iny = st.selectbox("¿A qué cuenta ingresa el dinero?", ["Efectivo", "Pago Móvil", "Binance"])
                monto_iny = st.number_input("Monto a inyectar ($)", min_value=0.0, value=0.0)
                desc_iny = st.text_input("Nota / Descripción (Ej. Inyección de capital propio, Apertura de fondo, etc.)")

                btn_inyectar = st.form_submit_button("Ingresar Dinero a Caja")

                if btn_inyectar:
                    if monto_iny > 0:
                        try:
                            scope = [
                                "https://www.googleapis.com/auth/spreadsheets",
                                "https://www.googleapis.com/auth/drive",
                            ]
                            creds_dict = dict(st.secrets["connections"]["gsheets"])
                            creds = Credentials.from_service_account_info(
                                creds_dict, scopes=scope
                            )
                            client = gspread.authorize(creds)

                            spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
                            sheet = client.open_by_url(spreadsheet_url).sheet1

                            nota_final = desc_iny if desc_iny else f"Inyección de capital ({cuenta_destino_iny})"
                            fila_inyeccion = [
                                fecha_inyeccion.strftime("%Y-%m-%d"),
                                f"CAJA_{cuenta_destino_iny.upper()}",
                                f"Inyección de Capital ({cuenta_destino_iny})",
                                nota_final,
                                0.0,
                                float(monto_iny),
                            ]

                            sheet.append_row(fila_inyeccion)
                            st.success(f"✅ ¡Inyección de ${monto_iny:,.2f} aplicada con éxito a {cuenta_destino_iny}!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al inyectar dinero: {e}")
                    else:
                        st.error("⚠️ Por favor, ingresa un monto válido mayor a 0.")

        # ------------------------------------------
        # 3. TRANSFERIR ENTRE CUENTAS
        # ------------------------------------------
        elif seccion_admin == "Transferir entre Cuentas":
            st.subheader("Mover Dinero entre Efectivo, Pago Móvil y Binance")

            with st.form("form_transferencia"):
                fecha_trans = st.date_input("Fecha de transferencia", datetime.now())
                cuenta_origen = st.selectbox("Cuenta de ORIGEN (De dónde sale):", ["Efectivo", "Pago Móvil", "Binance"])
                cuenta_destino = st.selectbox("Cuenta de DESTINO (A dónde llega):", ["Pago Móvil", "Efectivo", "Binance"])
                monto_trans = st.number_input("Monto a transferir ($)", min_value=0.0, value=0.0)

                btn_trans = st.form_submit_button("Realizar Transferencia")

                if btn_trans:
                    if cuenta_origen == cuenta_destino:
                        st.error("⚠️ La cuenta de origen y destino no pueden ser iguales.")
                    elif monto_trans <= 0:
                        st.error("⚠️ Ingresa un monto válido mayor a 0.")
                    else:
                        try:
                            scope = [
                                "https://www.googleapis.com/auth/spreadsheets",
                                "https://www.googleapis.com/auth/drive",
                            ]
                            creds_dict = dict(st.secrets["connections"]["gsheets"])
                            creds = Credentials.from_service_account_info(
                                creds_dict, scopes=scope
                            )
                            client = gspread.authorize(creds)

                            spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
                            sheet = client.open_by_url(spreadsheet_url).sheet1

                            fila_mov_1 = [
                                fecha_trans.strftime("%Y-%m-%d"),
                                f"CUENTA_{cuenta_origen.upper()}",
                                f"Sistema ({cuenta_origen})",
                                f"Transferencia enviada a {cuenta_destino}",
                                float(monto_trans),
                                0.0,
                            ]
                            fila_mov_2 = [
                                fecha_trans.strftime("%Y-%m-%d"),
                                f"CUENTA_{cuenta_destino.upper()}",
                                f"Sistema ({cuenta_destino})",
                                f"Transferencia recibida de {cuenta_origen}",
                                0.0,
                                float(monto_trans),
                            ]

                            sheet.append_row(fila_mov_1)
                            sheet.append_row(fila_mov_2)

                            st.success(f"✅ ¡Transferencia de ${monto_trans:,.2f} de {cuenta_origen} a {cuenta_destino} registrada con éxito!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al registrar la transferencia: {e}")

        # ------------------------------------------
        # 4. REGISTRAR GASTO
        # ------------------------------------------
        elif seccion_admin == "Registrar Gasto":
            st.subheader("Registrar Salida de Dinero / Gasto")

            with st.form("form_gasto"):
                fecha_gasto = st.date_input("Fecha del gasto", datetime.now())
                cuenta_gasto = st.selectbox("Cuenta de donde se paga el gasto:", ["Efectivo", "Pago Móvil", "Binance"])
                desc_gasto = st.text_input("Descripción del Gasto (Ej. Alquiler, Servicios, etc.)")
                monto_gasto = st.number_input("Monto del Gasto ($)", min_value=0.0, value=0.0)

                btn_gasto = st.form_submit_button("Guardar Gasto")

                if btn_gasto:
                    if desc_gasto and monto_gasto > 0:
                        try:
                            scope = [
                                "https://www.googleapis.com/auth/spreadsheets",
                                "https://www.googleapis.com/auth/drive",
                            ]
                            creds_dict = dict(st.secrets["connections"]["gsheets"])
                            creds = Credentials.from_service_account_info(
                                creds_dict, scopes=scope
                            )
                            client = gspread.authorize(creds)

                            spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
                            sheet = client.open_by_url(spreadsheet_url).sheet1

                            fila_gasto = [
                                fecha_gasto.strftime("%Y-%m-%d"),
                                f"GASTO_{cuenta_gasto.upper()}",
                                f"Gastos del Negocio ({cuenta_gasto})",
                                desc_gasto,
                                float(monto_gasto),
                                0.0,
                            ]

                            sheet.append_row(fila_gasto)
                            st.success(f"✅ ¡Gasto de ${monto_gasto:,.2f} registrado exitosamente!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al registrar el gasto: {e}")
                    else:
                        st.error("⚠️ Por favor, ingresa una descripción y un monto válido.")

        # ------------------------------------------
        # 5. LIQUIDAR / CERRAR CRÉDITO ACTUAL
        # ------------------------------------------
        elif seccion_admin == "Liquidar / Cerrar Crédito":
            st.subheader("Cerrar Ciclo Actual para Nuevo Préstamo")

            if opciones_clientes:
                cliente_a_liquidar = st.selectbox(
                    "Selecciona al Cliente a Liquidar:",
                    opciones_clientes,
                    key="liq_cliente",
                )
                codigo_liq = cliente_a_liquidar.split(" - ")[0]
                nombre_liq = cliente_a_liquidar.split(" - ")[1]

                if st.button("✂️ Liquidar Crédito y Abrir Nuevo Ciclo"):
                    try:
                        scope = [
                            "https://www.googleapis.com/auth/spreadsheets",
                            "https://www.googleapis.com/auth/drive",
                        ]
                        creds_dict = dict(st.secrets["connections"]["gsheets"])
                        creds = Credentials.from_service_account_info(
                            creds_dict, scopes=scope
                        )
                        client = gspread.authorize(creds)

                        spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
                        sheet = client.open_by_url(spreadsheet_url).sheet1

                        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
                        fila_corte = [
                            fecha_hoy,
                            str(codigo_liq).strip(),
                            nombre_liq,
                            "Crédito anterior liquidado / Inicio nuevo ciclo",
                            0.0,
                            0.0,
                        ]

                        sheet.append_row(fila_corte)
                        st.success(f"✅ ¡Crédito liquidado con éxito para {nombre_liq}!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al liquidar el crédito: {e}")
            else:
                st.info("No hay clientes registrados.")

        # ------------------------------------------
        # 6. CIERRE DE MES
        # ------------------------------------------
        elif seccion_admin == "Cierre de Mes":
            st.subheader("📅 Cierre de Mes y Reportes")
            st.write("Genera un resumen financiero mensual para ver tu rendimiento, ganancias reales y gastos incurridos.")

            if not df_existente.empty:
                df_existente['Fecha'] = pd.to_datetime(df_existente['Fecha'], errors='coerce')
                df_valido = df_existente.dropna(subset=['Fecha']).copy()
                
                df_valido['Mes_Año'] = df_valido['Fecha'].dt.strftime('%Y-%m')
                meses_disponibles = sorted(df_valido['Mes_Año'].unique(), reverse=True)

                if meses_disponibles:
                    mes_seleccionado = st.selectbox("Selecciona el mes a evaluar:", meses_disponibles)
                    df_mes = df_valido[df_valido['Mes_Año'] == mes_seleccionado]

                    gastos_mes = df_mes[df_mes["Codigo"].str.contains("GASTO_", na=False)]["Cargo"].sum()
                    intereses_mes = df_mes[df_mes["Concepto"].str.contains("Interés aplicado", case=False, na=False)]["Cargo"].sum()
                    
                    prestamos_mes = df_mes[
                        (~df_mes["Codigo"].str.contains("CUENTA_|GASTO_|CAJA_", na=False)) & 
                        (~df_mes["Concepto"].str.contains("Interés aplicado", case=False, na=False))
                    ]["Cargo"].sum()

                    cobrado_mes = df_mes[
                        ~df_mes["Codigo"].str.contains("CUENTA_|GASTO_|CAJA_", na=False)
                    ]["Abono"].sum()

                    inyecciones_mes = df_mes[df_mes["Codigo"].str.contains("CAJA_", na=False)]["Abono"].sum()
                    ganancia_neta_estimada = intereses_mes - gastos_mes

                    st.markdown(f"### 📊 Resumen Financiero de **{mes_seleccionado}**")
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("📈 Intereses Generados", f"${intereses_mes:,.2f}")
                    c2.metric("📉 Gastos del Mes", f"${gastos_mes:,.2f}")
                    c3.metric("💰 Ganancia Neta (Mes)", f"${ganancia_neta_estimada:,.2f}", 
                              delta=f"${ganancia_neta_estimada:,.2f}", delta_color="normal")

                    st.divider()
                    
                    c4, c5, c6 = st.columns(3)
                    c4.metric("📤 Capital Prestado", f"${prestamos_mes:,.2f}")
                    c5.metric("📥 Dinero Recaudado", f"${cobrado_mes:,.2f}")
                    c6.metric("💼 Inyecciones de Capital", f"${inyecciones_mes:,.2f}")

                    st.divider()
                    st.subheader("📝 Detalle de Gastos del Mes")
                    df_gastos_mes = df_mes[df_mes["Codigo"].str.contains("GASTO_", na=False)]
                    if not df_gastos_mes.empty:
                        df_gastos_mes['Fecha'] = df_gastos_mes['Fecha'].dt.strftime('%Y-%m-%d')
                        st.dataframe(df_gastos_mes[["Fecha", "Concepto", "Cargo"]], use_container_width=True, hide_index=True)
                    else:
                        st.info("¡Excelente! No hubo gastos registrados este mes.")

                else:
                    st.info("No hay fechas válidas para agrupar.")
            else:
                st.info("Aún no hay registros en la base de datos para generar un cierre de mes.")

        # ------------------------------------------
        # 7. FLUJO DE CAJA Y CUENTAS
        # ------------------------------------------
        else:
            st.subheader("💰 Flujo de Caja y Cartera Total")
            try:
                if not df_existente.empty:
                    df_clientes = df_existente[
                        ~df_existente["Codigo"].str.contains("CUENTA_|GASTO_|CAJA_", na=False)
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
                        resumen_clientes["Total_Cargos"] - resumen_clientes["Total_Abonos"]
                    )
                    saldo_en_la_calle = resumen_clientes["Saldo_Pendiente"].sum()

                    total_abonos_general = df_existente["Abono"].sum()

                    efectivo_total = (
                        df_existente[
                            df_existente["Concepto"].str.contains("Efectivo", case=False, na=False) |
                            df_existente["Codigo"].str.contains("CAJA_EFECTIVO", case=False, na=False)
                        ]["Abono"].sum()
                        - df_existente[
                            df_existente["Concepto"].str.contains("Efectivo", case=False, na=False) |
                            df_existente["Codigo"].str.contains("GASTO_EFECTIVO", case=False, na=False)
                        ]["Cargo"].sum()
                    )

                    pago_movil_total = (
                        df_existente[
                            df_existente["Concepto"].str.contains("Pago Móvil|Pago Movil", case=False, na=False) |
                            df_existente["Codigo"].str.contains("CAJA_PAGO MÓVIL|CAJA_PAGO MOVIL", case=False, na=False)
                        ]["Abono"].sum()
                        - df_existente[
                            df_existente["Concepto"].str.contains("Pago Móvil|Pago Movil", case=False, na=False) |
                            df_existente["Codigo"].str.contains("GASTO_PAGO MÓVIL|GASTO_PAGO MOVIL", case=False, na=False)
                        ]["Cargo"].sum()
                    )

                    binance_total = (
                        df_existente[
                            df_existente["Concepto"].str.contains("Binance", case=False, na=False) |
                            df_existente["Codigo"].str.contains("CAJA_BINANCE", case=False, na=False)
                        ]["Abono"].sum()
                        - df_existente[
                            df_existente["Concepto"].str.contains("Binance", case=False, na=False) |
                            df_existente["Codigo"].str.contains("GASTO_BINANCE", case=False, na=False)
                        ]["Cargo"].sum()
                    )

                    total_gastos = df_existente[
                        df_existente["Codigo"].str.contains("GASTO_", na=False)
                    ]["Cargo"].sum()

                    total_caja = efectivo_total + pago_movil_total + binance_total
                    cartera_total = total_caja + saldo_en_la_calle

                    st.markdown("### 💎 Valor Total de la Cartera (Patrimonio)")
                    col_w1, col_w2, col_w3 = st.columns(3)
                    col_w1.metric(
                        "💎 Todo tu Capital", 
                        f"${cartera_total:,.2f}", 
                        help="Es la suma del dinero que tienes en bancos/efectivo MÁS el dinero que te deben en la calle."
                    )
                    col_w2.metric("🏦 Total en Cajas / Cuentas", f"${total_caja:,.2f}")
                    col_w3.metric("📌 Dinero en la Calle", f"${saldo_en_la_calle:,.2f}")

                    st.divider()
                    st.markdown("### 🏦 Detalle de Cuentas *(Ya descuentan los gastos)*")
                    col_c1, col_c2, col_c3 = st.columns(3)
                    col_c1.metric("💵 Efectivo", f"${efectivo_total:,.2f}")
                    col_c2.metric("📱 Pago Móvil", f"${pago_movil_total:,.2f}")
                    col_c3.metric("🪙 Binance", f"${binance_total:,.2f}")

                    st.divider()
                    col_f2, col_f3 = st.columns(2)
                    col_f2.metric("📉 Gastos Históricos Totales", f"${total_gastos:,.2f}")
                    col_f3.metric("💵 Total Histórico Recaudado", f"${total_abonos_general:,.2f}")

                    st.divider()
                    st.subheader("Estado de Cuenta de Clientes")
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
                st.error(f"Error al calcular el flujo de caja: {e}")

    elif clave_admin != "":
        st.error("Contraseña incorrecta.")
