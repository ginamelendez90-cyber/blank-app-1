import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Gestión de Cobros", page_icon="💰")
st.title("Sistema de Cobros y Pagos")

# Conectar usando los secretos configurados en Streamlit
conn = st.connection("gsheets", type=GSheetsConnection)

tab_cliente, tab_admin = st.tabs(["Consulta de Cliente", "Administrador (Registrar Movimiento)"])

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
                col1.metric("Total Cargos (Deuda)", f"${total_cargos:,.2f}")
                col2.metric("Total Pagos", f"${total_pagos:,.2f}")
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
# PESTAÑA 2: ADMINISTRADOR
# ==========================================
with tab_admin:
    st.write("Área restringida para registrar nuevos cobros o pagos en la base de datos.")
    clave = st.text_input("Contraseña de Administrador:", type="password")
    
    if clave == "admin123":
        st.info("Acceso concedido. Completa los datos para registrar un movimiento.")
        
        with st.form("formulario_registro", clear_on_submit=True):
            nueva_fecha = st.date_input("Fecha del movimiento", datetime.now())
            nuevo_codigo = st.text_input("Código del Cliente (Ej. CLI-001)")
            nuevo_nombre = st.text_input("Nombre del Cliente")
            nuevo_concepto = st.text_input("Concepto (Ej. Pago de cuota, Nuevo servicio)")
            
            col_cargo, col_abono = st.columns(2)
            nuevo_cargo = col_cargo.number_input("Cargo / Nueva Deuda ($)", min_value=0.0, value=0.0)
            nuevo_abono = col_abono.number_input("Abono / Pago Recibido ($)", min_value=0.0, value=0.0)
            
            boton_guardar = st.form_submit_button("Guardar Registro")
            
            if boton_guardar:
                if nuevo_codigo and nuevo_nombre and nuevo_concepto:
                    try:
                        # Autenticación directa con gspread usando los secretos de Streamlit
                        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
                        creds_dict = dict(st.secrets["connections"]["gsheets"])
                        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
                        client = gspread.authorize(creds)
                        
                        # Abrir la hoja por la URL configurada en los secretos
                        spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
                        sheet = client.open_by_url(spreadsheet_url).sheet1
                        
                        # Preparar la fila exacta
                        fila_nueva = [
                            nueva_fecha.strftime("%Y-%m-%d"),
                            str(nuevo_codigo).strip(),
                            nuevo_nombre,
                            nuevo_concepto,
                            float(nuevo_cargo),
                            float(nuevo_abono)
                        ]
                        
                        # Agregar la fila al final de la hoja de forma limpia y directa
                        sheet.append_row(fila_nueva)
                        
                        st.success(f"✅ ¡Movimiento registrado exitosamente para {nuevo_nombre}!")
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")
                else:
                    st.error("⚠️ Por favor, completa el código, nombre y concepto.")
    elif clave != "":
        st.error("Contraseña incorrecta.")
