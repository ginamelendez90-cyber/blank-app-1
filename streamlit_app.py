import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

st.set_page_config(page_title="Gestión de Cobros", page_icon="💰")
st.title("Sistema de Cobros y Pagos")

# Conectar con la Hoja Maestra de Google Sheets
url_hoja = "https://docs.google.com/spreadsheets/d/1S_Cs4B9d3HcSoYN0_28YUZHe6txGUsJwq3TwFzJsPiY/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

# MANTENEMOS TODAS LAS OPCIONES ANTERIORES: 
# Creamos dos pestañas para no sobreescribir ni quitar la consulta del cliente
tab_cliente, tab_admin = st.tabs(["Consulta de Cliente", "Administrador (Registrar Movimiento)"])

# ==========================================
# PESTAÑA 1: LO QUE VE EL CLIENTE (INTACTO)
# ==========================================
with tab_cliente:
    st.write("Por favor, ingrese su código único para ver su estado de cuenta y movimientos.")
    codigo_cliente = st.text_input("Código de Cliente:")

    if st.button("Consultar"):
        if codigo_cliente:
            df = conn.read(spreadsheet=url_hoja)
            df['Codigo'] = df['Codigo'].astype(str)
            resultado = df[df['Codigo'] == str(codigo_cliente)]
            
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
# PESTAÑA 2: LO QUE VES TÚ (NUEVO REGISTRO)
# ==========================================
with tab_admin:
    st.write("Área restringida para registrar nuevos cobros o pagos en la base de datos.")
    clave = st.text_input("Contraseña de Administrador:", type="password")
    
    # Protegemos el formulario con una clave sencilla (puedes cambiar "admin123")
    if clave == "admin123":
        st.info("Acceso concedido. Completa los datos para registrar un movimiento.")
        
        # Usamos clear_on_submit=True SOLO para limpiar estos campos de texto después de guardar, 
        # sin afectar para nada el historial de consulta ni la pestaña del cliente.
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
                    # 1. Leemos la base de datos actual
                    df_actual = conn.read(spreadsheet=url_hoja)
                    
                    # 2. Creamos la nueva fila con los datos ingresados
                    nuevo_registro = pd.DataFrame([{
                        "Fecha": nueva_fecha.strftime("%Y-%m-%d"),
                        "Codigo": nuevo_codigo,
                        "Nombre": nuevo_nombre,
                        "Concepto": nuevo_concepto,
                        "Cargo": float(nuevo_cargo),
                        "Abono": float(nuevo_abono)
                    }])
                    
                    # 3. Añadimos la nueva fila al final de los datos existentes
                    df_actualizado = pd.concat([df_actual, nuevo_registro], ignore_index=True)
                    
                    # 4. Actualizamos el Google Sheet (esto reemplaza la necesidad de hacerlo manual)
                    conn.update(spreadsheet=url_hoja, data=df_actualizado)
                    
                    st.success(f"✅ ¡Movimiento registrado exitosamente para {nuevo_nombre}!")
                else:
                    st.error("⚠️ Por favor, completa el código, nombre y concepto.")
    elif clave != "":
        st.error("Contraseña incorrecta.")
