from datetime import datetime
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import streamlit as st
from streamlit_gsheets import (
    GSheetsConnection,  # <--- Make sure this import is present
)

st.set_page_config(page_title="Sistema de Cobros y Finanzas", page_icon="💰")
st.title("Sistema de Gestión Financiera y Cobros")

conn = st.connection("gsheets", type=GSheetsConnection)

tab_cliente, tab_admin = st.tabs(["Consulta de Cliente", "Panel de Administrador"])

# ==========================================
# PESTAÑA 1: CONSULTA DE CLIENTE
# ==========================================
with tab_cliente:
  st.write(
      "Por favor, ingrese su código único para ver su estado de cuenta y"
      " movimientos."
  )
  codigo_cliente = st.text_input("Código de Cliente:")

  if st.button("Consultar"):
    if codigo_cliente:
      try:
        df = conn.read(
            ttl=0,
            usecols=[
                "Fecha",
                "Codigo",
                "Nombre",
                "Concepto",
                "Cuenta",
                "Cargo",
                "Abono",
            ],
        )
      except:
        df = conn.read(
            ttl=0, usecols=["Fecha", "Codigo", "Nombre", "Concepto", "Cargo", "Abono"]
        )
        df["Cuenta"] = "Efectivo"

      df["Codigo"] = df["Codigo"].astype(str).str.strip()
      df["Cargo"] = pd.to_numeric(df["Cargo"], errors="coerce").fillna(0.0)
      df["Abono"] = pd.to_numeric(df["Abono"], errors="coerce").fillna(0.0)

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

        # Protección para evitar saldos negativos
        saldo_pendiente = max(0.0, prestamo_actual - pagos_actual)

        st.subheader(f"Cliente: {nombre}")

        col1, col2, col3 = st.columns(3)
        col1.metric("📌 Préstamo Actual", f"${prestamo_actual:,.2f}")
        col2.metric("💵 Abonado (Actual)", f"${pagos_actual:,.2f}")
        col3.metric("⚠️ Saldo Pendiente", f"${saldo_pendiente:,.2f}")

        st.markdown(
            f"<p style='color: gray; font-size: 14px; margin-bottom: 20px;'>"
            f"<i>📊 Acumulado histórico total prestado:"
            f" ${total_cargos_historico:,.2f}</i>"
            f"</p>",
            unsafe_allow_html=True,
        )

        st.divider()
        st.subheader("Historial del Crédito Vigente")
        if not movimientos_ciclo_actual.empty:
          cols_a_mostrar = [
              c
              for c in ["Fecha", "Concepto", "Cuenta", "Cargo", "Abono"]
              if c in movimientos_ciclo_actual.columns
          ]
          st.dataframe(
              movimientos_ciclo_actual[cols_a_mostrar],
              use_container_width=True,
              hide_index=True,
          )
        else:
          st.info("No hay movimientos activos en este ciclo.")

        if not movimientos_historicos.empty:
          with st.expander(
              "📂 Ver Historial de Créditos Anteriores / Liquidados"
          ):
            cols_hist = [
                c
                for c in ["Fecha", "Concepto", "Cuenta", "Cargo", "Abono"]
                if c in movimientos_historicos.columns
            ]
            st.dataframe(
                movimientos_historicos[cols_hist],
                use_container_width=True,
                hide_index=True,
            )
      else:
        st.error("Código no encontrado. Por favor verifique e intente nuevamente.")
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
        ],
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
              "Cuenta",
              "Cargo",
              "Abono",
          ],
      )
      df_existente["Cuenta"] = (
          df_existente["Cuenta"].astype(str).str.strip().str.title()
      )
    except:
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
        df_existente["Cuenta"] = "Efectivo"
      except:
        df_existente = pd.DataFrame()

    if not df_existente.empty:
      df_existente["Codigo"] = df_existente["Codigo"].astype(str).str.strip()
      df_existente["Nombre"] = df_existente["Nombre"].astype(str).str.strip()
      df_existente["Cargo"] = pd.to_numeric(
          df_existente["Cargo"], errors="coerce"
      ).fillna(0.0)
      df_existente["Abono"] = pd.to_numeric(
          df_existente["Abono"], errors="coerce"
      ).fillna(0.0)

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
    else:
      opciones_clientes = []

    # ------------------------------------------
    # 1. REGISTRAR MOVIMIENTOS
    # ------------------------------------------
    if seccion_admin == "Registrar Movimientos":
      st.subheader("Registrar Cobro (Abono) o Préstamo")

      tipo_movimiento = st.radio(
          "Tipo de movimiento:",
          ["Registrar Abono / Pago", "Registrar Préstamo / Deuda Inicial"],
      )
      usar_dos_cuentas = st.checkbox(
          "🔀 ¿El dinero sale combinando DOS cuentas al mismo tiempo? (Ej:"
          " Efectivo + Binance)"
      )

      if not usar_dos_cuentas:
        if tipo_movimiento == "Registrar Abono / Pago":
          cuenta_afectada = st.selectbox(
              "¿A qué cuenta ingresa el pago?", ["Efectivo", "Pago Móvil", "Binance"]
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
        nuevo_codigo = st.text_input("Código de Cliente (Ej. CLI-002)")
        nuevo_nombre = st.text_input("Nombre del Cliente")

      with st.form("formulario_registro"):
        nueva_fecha = st.date_input("Fecha del movimiento", datetime.now())

        plazo_dias = 30
        if tipo_movimiento == "Registrar Préstamo / Deuda Inicial":
          st.markdown("##### ⚙️ Configuración del Plazo")
          plazo_dias = st.number_input(
              "Plazo del préstamo (en días):", min_value=1, value=30, step=1
          )

        if usar_dos_cuentas:
          st.markdown("##### Distribución del capital entre 2 cuentas:")
          c_1 = st.selectbox(
              "Primera Cuenta", ["Efectivo", "Pago Móvil", "Binance"], key="c1"
          )
          monto_c1 = st.number_input(
              f"Monto salido de {c_1} ($)", min_value=0.0, value=0.0, key="mc1"
          )

          otras_cuentas = [
              c for c in ["Efectivo", "Pago Móvil", "Binance"] if c != c_1
          ]
          c_2 = st.selectbox("Segunda Cuenta", otras_cuentas, key="c2")
          monto_c2 = st.number_input(
              f"Monto salido de {c_2} ($)", min_value=0.0, value=0.0, key="mc2"
          )

          monto_total_deuda = monto_c1 + monto_c2
        else:
          monto_total_deuda = st.number_input(
              "Monto del préstamo / pago ($)", min_value=0.0, value=0.0
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

              spreadsheet_url = st.secrets["connections"]["gsheets"][
                  "spreadsheet"
              ]
              sheet = client.open_by_url(spreadsheet_url).sheet1

              filas_a_agregar = []
              sufijo_prestamo = ""
              if tipo_movimiento == "Registrar Préstamo / Deuda Inicial":
                sufijo_prestamo = f" [Plazo: {plazo_dias} días]"

              if tipo_movimiento == "Registrar Abono / Pago":
                if usar_dos_cuentas:
                  if monto_c1 > 0:
                    filas_a_agregar.append([
                        nueva_fecha.strftime("%Y-%m-%d"),
                        str(nuevo_codigo).strip(),
                        nuevo_nombre,
                        "Abono a cuenta",
                        c_1,
                        0.0,
                        float(monto_c1),
                    ])
                  if monto_c2 > 0:
                    filas_a_agregar.append([
                        nueva_fecha.strftime("%Y-%m-%d"),
                        str(nuevo_codigo).strip(),
                        nuevo_nombre,
                        "Abono a cuenta",
                        c_2,
                        0.0,
                        float(monto_c2),
                    ])
                else:
                  desc_default = (
                      concepto_personalizado
                      if concepto_personalizado
                      else "Abono a cuenta"
                  )
                  filas_a_agregar.append([
                      nueva_fecha.strftime("%Y-%m-%d"),
                      str(nuevo_codigo).strip(),
                      nuevo_nombre,
                      desc_default,
                      cuenta_afectada,
                      0.0,
                      float(monto_total_deuda),
                  ])

              else:  # Préstamo
                if usar_dos_cuentas:
                  if monto_total_deuda <= 0:
                    st.error("⚠️ Los montos deben ser mayores a 0.")
                    st.stop()
                  if monto_c1 > 0:
                    filas_a_agregar.append([
                        nueva_fecha.strftime("%Y-%m-%d"),
                        str(nuevo_codigo).strip(),
                        nuevo_nombre,
                        (
                            "Préstamo inicial"
                            f" (${float(monto_c1):,.2f}){sufijo_prestamo}"
                        ),
                        c_1,
                        float(monto_c1),
                        0.0,
                    ])
                  if monto_c2 > 0:
                    filas_a_agregar.append([
                        nueva_fecha.strftime("%Y-%m-%d"),
                        str(nuevo_codigo).strip(),
                        nuevo_nombre,
                        (
                            "Préstamo inicial"
                            f" (${float(monto_c2):,.2f}){sufijo_prestamo}"
                        ),
                        c_2,
                        float(monto_c2),
                        0.0,
                    ])
                else:
                  if monto_total_deuda <= 0:
                    st.error("⚠️ Ingresa un monto válido mayor a 0.")
                    st.stop()

                  filas_a_agregar.append([
                      nueva_fecha.strftime("%Y-%m-%d"),
                      str(nuevo_codigo).strip(),
                      nuevo_nombre,
                      (
                          "Préstamo inicial"
                          f" (${float(monto_total_deuda):,.2f}){sufijo_prestamo}"
                      ),
                      cuenta_afectada,
                      float(monto_total_deuda),
                      0.0,
                  ])

              for fila in filas_a_agregar:
                sheet.append_row(fila)

              st.success(
                  f"✅ ¡Movimiento registrado correctamente para {nuevo_nombre}!"
              )
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
      with st.form("form_inyectar"):
        fecha_inyeccion = st.date_input("Fecha de inyección", datetime.now())
        cuenta_destino_iny = st.selectbox(
            "¿A qué cuenta ingresa el dinero?", ["Efectivo", "Pago Móvil", "Binance"]
        )
        monto_iny = st.number_input("Monto a inyectar ($)", min_value=0.0, value=0.0)
        desc_iny = st.text_input("Nota / Descripción")
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
              spreadsheet_url = st.secrets["connections"]["gsheets"][
                  "spreadsheet"
              ]
              sheet = client.open_by_url(spreadsheet_url).sheet1

              nota_final = (
                  desc_iny if desc_iny else "Inyección de capital"
              )
              sheet.append_row([
                  fecha_inyeccion.strftime("%Y-%m-%d"),
                  f"CAJA_{cuenta_destino_iny.upper()}",
                  "Inyección de Capital",
                  nota_final,
                  cuenta_destino_iny,
                  0.0,
                  float(monto_iny),
              ])
              st.success("✅ ¡Inyección aplicada con éxito!")
              st.rerun()
            except Exception as e:
              st.error(f"Error: {e}")

    # ------------------------------------------
    # 3. TRANSFERIR ENTRE CUENTAS
    # ------------------------------------------
    elif seccion_admin == "Transferir entre Cuentas":
      st.subheader("Mover Dinero entre Cuentas")
      with st.form("form_transferencia"):
        fecha_trans = st.date_input("Fecha de transferencia", datetime.now())
        cuenta_origen = st.selectbox(
            "Cuenta de ORIGEN:", ["Efectivo", "Pago Móvil", "Binance"]
        )
        cuenta_destino = st.selectbox(
            "Cuenta de DESTINO:", ["Pago Móvil", "Efectivo", "Binance"]
        )
        monto_trans = st.number_input(
            "Monto a transferir ($)", min_value=0.0, value=0.0
        )
        btn_trans = st.form_submit_button("Realizar Transferencia")

        if btn_trans:
          if cuenta_origen == cuenta_destino:
            st.error("⚠️ La cuenta origen y destino no pueden ser iguales.")
          elif monto_trans <= 0:
            st.error("⚠️ Ingresa un monto mayor a 0.")
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
              spreadsheet_url = st.secrets["connections"]["gsheets"][
                  "spreadsheet"
              ]
              sheet = client.open_by_url(spreadsheet_url).sheet1

              sheet.append_row([
                  fecha_trans.strftime("%Y-%m-%d"),
                  f"CUENTA_{cuenta_origen.upper()}",
                  f"Transferencia enviada a {cuenta_destino}",
                  cuenta_origen,
                  float(monto_trans),
                  0.0,
              ])
              sheet.append_row([
                  fecha_trans.strftime("%Y-%m-%d"),
                  f"CUENTA_{cuenta_destino.upper()}",
                  f"Transferencia recibida de {cuenta_origen}",
                  cuenta_destino,
                  0.0,
                  float(monto_trans),
              ])
              st.success("✅ ¡Transferencia exitosa!")
              st.rerun()
            except Exception as e:
              st.error(f"Error: {e}")

    # ------------------------------------------
    # 4. REGISTRAR GASTO
    # ------------------------------------------
    elif seccion_admin == "Registrar Gasto":
      st.subheader("Registrar Gasto")
      with st.form("form_gasto"):
        fecha_gasto = st.date_input("Fecha", datetime.now())
        cuenta_gasto = st.selectbox(
            "Cuenta:", ["Efectivo", "Pago Móvil", "Binance"]
        )
        desc_gasto = st.text_input("Descripción")
        monto_gasto = st.number_input("Monto ($)", min_value=0.0, value=0.0)
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
              spreadsheet_url = st.secrets["connections"]["gsheets"][
                  "spreadsheet"
              ]
              sheet = client.open_by_url(spreadsheet_url).sheet1

              sheet.append_row([
                  fecha_gasto.strftime("%Y-%m-%d"),
                  f"GASTO_{cuenta_gasto.upper()}",
                  desc_gasto,
                  cuenta_gasto,
                  float(monto_gasto),
                  0.0,
              ])
              st.success("✅ ¡Gasto registrado!")
              st.rerun()
            except Exception as e:
              st.error(f"Error: {e}")

    # ------------------------------------------
    # 5. LIQUIDAR / CERRAR CRÉDITO ACTUAL
    # ------------------------------------------
    elif seccion_admin == "Liquidar / Cerrar Crédito":
      st.subheader("Cerrar Ciclo Actual")
      if opciones_clientes:
        cliente_a_liquidar = st.selectbox(
            "Selecciona al Cliente:", opciones_clientes, key="liq_cliente"
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
            spreadsheet_url = st.secrets["connections"]["gsheets"][
                "spreadsheet"
            ]
            sheet = client.open_by_url(spreadsheet_url).sheet1

            sheet.append_row([
                datetime.now().strftime("%Y-%m-%d"),
                str(codigo_liq).strip(),
                nombre_liq,
                "Crédito anterior liquidado / Inicio nuevo ciclo",
                "Efectivo",
                0.0,
                0.0,
            ])
            st.success("✅ ¡Crédito liquidado!")
            st.rerun()
          except Exception as e:
            st.error(f"Error: {e}")
      else:
        st.info("No hay clientes.")

    # ------------------------------------------
    # 6. FLUJO DE CAJA Y CUENTAS
    # ------------------------------------------
    else:
      st.subheader("💰 Flujo de Caja y Saldo en Cuentas")
      try:
        if not df_existente.empty:
          df_clientes = df_existente[
              ~df_existente["Codigo"].str.contains(
                  "CUENTA_|GASTO_|CAJA_", na=False
              )
          ]

          lista_resumen_clientes = []
          for codigo_cliente_val, grupo_c in df_clientes.groupby("Codigo"):
            nombre_c = grupo_c.iloc[0]["Nombre"]
            indices_liq = grupo_c[
                grupo_c["Concepto"].str.contains(
                    "Crédito anterior liquidado", case=False, na=False
                )
            ].index

            if not indices_liq.empty:
              ultimo_corte = indices_liq[-1]
              movs_ciclo = grupo_c.loc[grupo_c.index > ultimo_corte]
            else:
              movs_ciclo = grupo_c

            cargos_ciclo = movs_ciclo["Cargo"].sum()
            abonos_ciclo = movs_ciclo["Abono"].sum()

            # Saldo pendiente real protegido de negativos
            saldo_actual_cli = max(0.0, cargos_ciclo - abonos_ciclo)

            lista_resumen_clientes.append({
                "Codigo": codigo_cliente_val,
                "Nombre": nombre_c,
                "Total_Cargos": cargos_ciclo,
                "Total_Abonos": abonos_ciclo,
                "Saldo_Pendiente": saldo_actual_cli,
            })

          resumen_clientes = pd.DataFrame(lista_resumen_clientes)

          # Suma de la calle protegida
          saldo_en_la_calle = resumen_clientes["Saldo_Pendiente"].sum()

          total_abonos_general = df_existente["Abono"].sum()
          total_gastos = df_existente[
              df_existente["Codigo"].str.contains("GASTO_", na=False)
          ]["Cargo"].sum()

          def calcular_saldo_exacto(nombre_cuenta):
            nc = nombre_cuenta.lower()
            df_c = df_existente[df_existente["Cuenta"].str.lower() == nc]
            if df_c.empty:
              return 0.0
            total_entradas = df_c["Abono"].sum()
            total_salidas = df_c["Cargo"].sum()
            return total_entradas - total_salidas

          efectivo_total = calcular_saldo_exacto("Efectivo")
          pago_movil_total = calcular_saldo_exacto("Pago Móvil")
          binance_total = calcular_saldo_exacto("Binance")

          st.markdown("### 🏦 Dinero Disponible en Cuentas")
          col_c1, col_c2, col_c3 = st.columns(3)
          col_c1.metric("💵 Efectivo", f"${efectivo_total:,.2f}")
          col_c2.metric("📱 Pago Móvil", f"${pago_movil_total:,.2f}")
          col_c3.metric("🪙 Binance", f"${binance_total:,.2f}")

          st.divider()
          col_f1, col_f2, col_f3 = st.columns(3)
          col_f1.metric("📌 Dinero en la Calle", f"${saldo_en_la_calle:,.2f}")
          col_f2.metric("📉 Total Gastos", f"${total_gastos:,.2f}")
          col_f3.metric(
              "💵 Total Histórico Recaudado", f"${total_abonos_general:,.2f}"
          )

          st.divider()
          st.subheader("Estado de Cuenta de Clientes")
          st.dataframe(
              resumen_clientes[[
                  "Codigo",
                  "Nombre",
                  "Total_Cargos",
                  "Total_Abonos",
                  "Saldo_Pendiente",
              ]],
              use_container_width=True,
              hide_index=True,
          )
        else:
          st.info("Aún no hay registros.")
      except Exception as e:
        st.error(f"Error: {e}")

  else:
    if clave_admin != "":
      st.error("Contraseña incorrecta.")
