import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

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
            df = conn.read(ttl=0) # Lee los datos frescos sin caché
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
                    # 1. Leemos los datos actuales
                    df_actual = conn.read(ttl=0)
                    
                    # 2. Creamos la nueva fila
                    nuevo_registro = pd.DataFrame([{
                        "Fecha": nueva_fecha.strftime("%Y-%m-%d"),
                        "Codigo": nuevo_codigo,
                        "Nombre": nuevo_nombre,
                        "Concepto": nuevo_concepto,
                        "Cargo": float(nuevo_cargo),
                        "Abono": float(nuevo_abono)
                    }])
                    
                    # 3. Concatenamos
                    df_actualizado = pd.concat([df_actual, nuevo_registro], ignore_index=True)
                    
                    # 4. Actualizamos Google Sheets usando la API de servicio autorizada
                    conn.update(data=df_actualizado)
                    
                    st.success(f"✅ ¡Movimiento registrado exitosamente para {nuevo_nombre}!")
                else:
                    st.error("⚠️ Por favor, completa el código, nombre y concepto.")
    elif clave != "":
        st.error("Contraseña incorrecta.")
