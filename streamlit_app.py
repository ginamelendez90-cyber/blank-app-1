import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Sistema de Cobros y Finanzas", page_icon="💰")
st.title("Sistema de Gestión de Cobros")

conn = st.connection("gsheets", type=GSheetsConnection)

tab_cliente, tab_admin = st.tabs(["Consulta de Cliente", "Panel de Administrador"])

# ==========================================
# PESTAÑA 1: CONSULTA DE CLIENTE
# ==========================================
with tab_cliente:
    st.write("Por favor, ingrese su código único para ver su estado de cuenta y movimientos.")
    codigo_cliente = st.text_input("Código de Cliente:")

    if st.button("Consultar"):
        if codigo_cliente:
            df = conn.read(ttl=0, usecols=['Fecha', 'Codigo', 'Nombre', 'Concepto', 'Cargo', 'Abono'])
            
            df['Codigo'] = df['Codigo'].astype(str).str.strip()
            codigo_buscado = str(codigo_cliente).strip()
            
            resultado = df[df['Codigo'] == codigo_buscado]
            
            if not resultado.empty:
                st.success("¡Datos encontrados!")
                
                nombre = resultado.iloc[0]['Nombre']
                
                # Cálculos globales históricos
                total_cargos_historico = resultado['Cargo'].sum()
                total_pagos_historico = resultado['Abono'].sum()
                
                # Detectar si hay un punto de liquidación o corte anterior
                indices_liquidacion = resultado[resultado['Concepto'].str.contains("Crédito anterior liquidado", case=False, na=False)].index
                
                if not indices_liquidacion.empty:
                    ultimo_corte_idx = indices_liquidacion[-1]
                    movimientos_ciclo_actual = resultado.loc[resultado.index > ultimo_corte_idx]
                    movimientos_historicos = resultado.loc[resultado.index <= ultimo_corte_idx]
                else:
                    movimientos_ciclo_actual = resultado
                    movimientos_historicos = pd.DataFrame()
                
                prestamo_actual = movimientos_ciclo_actual['Cargo'].sum()
                pagos_actual = movimientos_ciclo_actual['Abono'].sum()
                saldo_pendiente = prestamo_actual - pagos_actual

                st.subheader(f"Cliente: {nombre}")
                
                col1, col2, col3 = st.columns(3)
                col1.metric("📌 Préstamo Actual", f"${prestamo_actual:,.2f}")
                col2.metric("💵 Abonado (Actual)", f"${pagos_actual:,.2f}")
                col3.metric("⚠️ Saldo Pendiente", f"${saldo_pendiente:,.2f}")
                
                st.markdown(
                    f"<p style='color: gray; font-size: 14px; margin-bottom: 20px;'>"
                    f"<i>📊 Acumulado histórico total prestado: ${total_cargos_historico:,.2f}</i>"
                    f"</p>", 
                    unsafe_allow_html=True
                )
                
                st.divider()
                st.subheader("Historial del Crédito Vigente")
                if not movimientos_ciclo_actual.empty:
                    st.dataframe(movimientos_ciclo_actual[['Fecha', 'Concepto', 'Cargo', 'Abono']], use_container_width=True, hide_index=True)
                else:
                    st.info("No hay movimientos activos en este ciclo.")

                # Apartado de Historial de Créditos Anteriores
                if not movimientos_historicos.empty:
                    with st.expander("📂 Ver Historial de Créditos Anteriores / Liquidados"):
                        st.write("Movimientos de préstamos y pagos de ciclos pasados ya saldados:")
                        st.dataframe(movimientos_historicos[['Fecha', 'Concepto', 'Cargo', 'Abono']], use_container_width=True, hide_index=True)
            else:
                st.error("Código no encontrado. Por favor verifique e intente nuevamente.")
        else:
            st.warning("Por favor ingrese un código válido.")

# ==========================================
# PESTAÑA 2: PANEL DE ADMINISTRADOR
# ==========================================
with tab_admin:
    st.write("Área restringida de control y gestión.")
    clave_admin = st.text_input("Contraseña de Administrador:", type="password", key="clave_admin_unica")
    
    if clave_admin == "admin123":
        st.success("Acceso concedido al panel de control.")
        
        seccion_admin = st.radio("¿Qué deseas hacer?", [
            "Registrar Movimientos", 
            "Liquidar / Cerrar Crédito Actual", 
            "Ver Finanzas y Saldo en la Calle"
        ])
        
        st.divider()
        
        try:
            df_existente = conn.read(ttl=0, usecols=['Codigo', 'Nombre'])
            df_existente['Codigo'] = df_existente['Codigo'].astype(str).str.strip()
            df_existente['Nombre'] = df_existente['Nombre'].astype(str).str.strip()
            clientes_unicos = df_existente.drop_duplicates(subset=['Codigo']).to_dict(orient='records')
            opciones_clientes = [f"{c['Codigo']} - {c['Nombre']}" for c in clientes_unicos]
        except Exception:
            opciones_clientes = []

        # ------------------------------------------
        # SECCIÓN A: REGISTRAR MOVIMIENTOS
        # ------------------------------------------
        if seccion_admin == "Registrar Movimientos":
            st.subheader("Registrar Nuevo Cobro o Préstamo")
            
            tipo_movimiento = st.radio("Tipo de movimiento:", ["Registrar Abono / Pago", "Registrar Préstamo / Deuda Inicial"])
            es_nuevo_cliente = st.checkbox("➕ Registrar como cliente NUEVO")
            
            if not es_nuevo_cliente and opciones_clientes:
                cliente_seleccionado = st.selectbox("Selecciona al Cliente Existente:", opciones_clientes)
                nuevo_codigo = cliente_seleccionado.split(" - ")[0]
                nuevo_nombre = cliente_seleccionado.split(" - ")[1]
            else:
                st.info("Ingresa los datos del nuevo cliente:")
                nuevo_codigo = st.text_input("Código del Cliente (Ej. CLI-002)")
                nuevo_nombre = st.text_input("Nombre del Cliente")
            
            with st.form("formulario_registro"):
                nueva_fecha = st.date_input("Fecha del movimiento", datetime.now())
                
                if tipo_movimiento == "Registrar Abono / Pago":
                    nuevo_concepto = st.text_input("Concepto", value="Abono a cuenta")
                    monto = st.number_input("Monto del Abono ($)", min_value=0.0, value=0.0)
                    cargo_val = 0.0
                    abono_val = float(monto)
                else:
                    nuevo_concepto = st.text_input("Concepto", value="Préstamo inicial / Deuda")
                    monto = st.number_input("Monto del Préstamo/Deuda ($)", min_value=0.0, value=0.0)
                    cargo_val = float(monto)
                    abono_val = 0.0
                
                boton_guardar = st.form_submit_button("Guardar en el Sistema")
                
                if boton_guardar:
                    if nuevo_codigo and nuevo_nombre:
                        try:
                            scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
                            creds_dict = dict(st.secrets["connections"]["gsheets"])
                            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
                            client = gspread.authorize(creds)
                            
                            spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
                            sheet = client.open_by_url(spreadsheet_url).sheet1
                            
                            fila_nueva = [
                                nueva_fecha.strftime("%Y-%m-%d"),
                                str(nuevo_codigo).strip(),
                                nuevo_nombre,
                                nuevo_concepto,
                                cargo_val,
                                abono_val
                            ]
                            
                            sheet.append_row(fila_nueva)
                            st.success(f"✅ ¡Registrado correctamente para {nuevo_nombre}!")
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")
                    else:
                        st.error("⚠️ Por favor, asegúrate de colocar el código y el nombre del cliente.")

        # ------------------------------------------
        # SECCIÓN B: LIQUIDAR / CERRAR CRÉDITO ACTUAL
        # ------------------------------------------
        elif seccion_admin == "Liquidar / Cerrar Crédito Actual":
            st.subheader("Cerrar Ciclo Actual para Nuevo Préstamo")
            st.write("Usa esta opción cuando el cliente termine de pagar su préstamo. Esto archivará los movimientos viejos en su historial y dejará su cuenta en cero, lista para registrarle un nuevo préstamo.")
            
            if opciones_clientes:
                cliente_a_liquidar = st.selectbox("Selecciona al Cliente a Liquidar:", opciones_clientes, key="liq_cliente")
                codigo_liq = cliente_a_liquidar.split(" - ")[0]
                nombre_liq = cliente_a_liquidar.split(" - ")[1]
                
                if st.button("✂️ Liquidar Crédito y Abrir Nuevo Ciclo"):
                    try:
                        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
                        creds_dict = dict(st.secrets["connections"]["gsheets"])
                        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
                        client = gspread.authorize(creds)
                        
                        spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
                        sheet = client.open_by_url(spreadsheet_url).sheet1
                        
                        # Agregamos una fila de corte que divide el ciclo viejo del nuevo
                        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
                        fila_corte = [
                            fecha_hoy,
                            str(codigo_liq).strip(),
                            nombre_liq,
                            "Crédito anterior liquidado / Inicio nuevo ciclo",
                            0.0,
                            0.0
                        ]
                        
                        sheet.append_row(fila_corte)
                        st.success(f"✅ ¡Crédito liquidado con éxito para {nombre_liq}! Ya puedes ir a 'Registrar Movimientos' y ponerle su nuevo préstamo.")
                    except Exception as e:
                        st.error(f"Error al liquidar el crédito: {e}")
            else:
                st.info("No hay clientes registrados en el sistema.")

        # ------------------------------------------
        # SECCIÓN C: FINANZAS Y SALDO EN LA CALLE
        # ------------------------------------------
        else:
            st.subheader("Resumen Financiero General")
            try:
                df_finanzas = conn.read(ttl=0, usecols=['Fecha', 'Codigo', 'Nombre', 'Concepto', 'Cargo', 'Abono'])
                
                if not df_finanzas.empty:
                    resumen_clientes = df_finanzas.groupby(['Codigo', 'Nombre']).agg(
                        Total_Cargos=('Cargo', 'sum'),
                        Total_Abonos=('Abono', 'sum')
                    ).reset_index()
                    
                    resumen_clientes['Saldo_Pendiente'] = resumen_clientes['Total_Cargos'] - resumen_clientes['Total_Abonos']
                    
                    saldo_en_la_calle = resumen_clientes['Saldo_Pendiente'].sum()
                    total_recaudado = resumen_clientes['Total_Abonos'].sum()
                    
                    col_f1, col_f2 = st.columns(2)
                    col_f1.metric("💰 Dinero Total en la Calle (Por Cobrar)", f"${saldo_en_la_calle:,.2f}")
                    col_f2.metric("💵 Total Histórico Recaudado", f"${total_recaudado:,.2f}")
                    
                    st.divider()
                    st.subheader("Estado de Cuenta de Todos los Clientes")
                    st.dataframe(resumen_clientes[['Codigo', 'Nombre', 'Total_Cargos', 'Total_Abonos', 'Saldo_Pendiente']], use_container_width=True, hide_index=True)
                else:
                    st.info("Aún no hay registros en la base de datos.")
                    
            except Exception as e:
                st.error(f"No se pudieron cargar los datos financieros: {e}")
                
    elif clave_admin != "":
        st.error("Contraseña incorrecta.")
