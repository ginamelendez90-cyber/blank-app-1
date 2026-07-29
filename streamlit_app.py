import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Sistema de Cobros y Finanzas", page_icon="💰")
st.title("Sistema de Gestión de Cobros")

conn = st.connection("gsheets", type=GSheetsConnection)

# Solo dos pestañas: una para el cliente y otra unificada para ti (Administrador)
tab_cliente, tab_admin = st.tabs(["Consulta de Cliente", "Panel de Administrador"])

# ==========================================
# PESTAÑA 1: CLIENTE
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
                total_cargos = resultado['Cargo'].sum()
                total_pagos = resultado['Abono'].sum()
                saldo_pendiente = total_cargos - total_pagos
                
                st.subheader(f"Cliente: {nombre}")
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Monto Total Préstamo", f"${total_cargos:,.2f}")
                col2.metric("Total Abonado", f"${total_pagos:,.2f}")
                col3.metric("Saldo Pendiente", f"${saldo_pendiente:,.2f}")
                
                st.divider()
                st.subheader("Historial de Movimientos")
                
                historial = resultado[['Fecha', 'Concepto', 'Cargo', 'Abono']]
                st.dataframe(historial, use_container_width=True, hide_index=True)
            else:
                st.error("Código no encontrado. Por favor verifique e intente nuevamente.")
        else:
            st.warning("Por favor ingrese un código válido.")

# ==========================================
# PESTAÑA 2: ADMINISTRADOR (UNIFICADA)
# ==========================================
with tab_admin:
    st.write("Área restringida de control y gestión.")
    clave_admin = st.text_input("Contraseña de Administrador:", type="password", key="clave_admin_unica")
    
    if clave_admin == "admin123":
        st.success("Acceso concedido al panel de control.")
        
        # Sub-secciones o pestañas internas dentro del panel de administrador
        seccion_admin = st.radio("¿Qué deseas hacer?", ["Registrar Movimientos", "Ver Finanzas y Saldo en la Calle"])
        
        st.divider()
        
        # ------------------------------------------
        # SECCIÓN A: REGISTRAR MOVIMIENTOS
        # ------------------------------------------
        if seccion_admin == "Registrar Movimientos":
            st.subheader("Registrar Nuevo Cobro o Préstamo")
            tipo_movimiento = st.radio("Tipo de movimiento:", ["Registrar Abono / Pago", "Registrar Préstamo / Deuda Inicial"])
            
            with st.form("formulario_registro", clear_on_submit=True):
                nueva_fecha = st.date_input("Fecha del movimiento", datetime.now())
                nuevo_codigo = st.text_input("Código del Cliente (Ej. CLI-001)")
                nuevo_nombre = st.text_input("Nombre del Cliente")
                
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
                        st.error("⚠️ Por favor, completa el código y el nombre del cliente.")
        
        # ------------------------------------------
        # SECCIÓN B: FINANZAS Y SALDO EN LA CALLE
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
