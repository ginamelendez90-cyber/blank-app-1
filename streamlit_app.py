import pandas as pd
import numpy as np
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==========================================
# 1. EXTRACCIÓN DE DATOS (SELENIUM)
# ==========================================
def extraer_datos_mercado(url):
    print("Iniciando navegador y extrayendo datos...")
    servicio = Service(ChromeDriverManager().install())
    opciones = webdriver.ChromeOptions()
    # opciones.add_argument('--headless') # Ejecutar en segundo plano sin abrir ventana
    
    driver = webdriver.Chrome(service=servicio, options=opciones)
    datos_partidos = []
    
    try:
        driver.get(url)
        
        # Espera explícita para que el DOM cargue las cuotas (max 15 seg)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "clase-contenedor-partido"))
        )
        
        partidos = driver.find_elements(By.CLASS_NAME, "clase-contenedor-partido")
        
        for partido in partidos:
            local = partido.find_element(By.CLASS_NAME, "nombre-local").text
            visitante = partido.find_element(By.CLASS_NAME, "nombre-visitante").text
            
            # Captura obligatoria del mercado 1X2 completo
            cuota_1 = partido.find_element(By.CLASS_NAME, "cuota-1").text
            cuota_x = partido.find_element(By.CLASS_NAME, "cuota-empate").text
            cuota_2 = partido.find_element(By.CLASS_NAME, "cuota-2").text
            
            datos_partidos.append({
                "Local": local,
                "Visitante": visitante,
                "Cuota 1": cuota_1,
                "Cuota X": cuota_x,
                "Cuota 2": cuota_2
            })
            
    except Exception as e:
        print(f"Error durante la extracción: {e}")
    finally:
        driver.quit()
        
    return pd.DataFrame(datos_partidos)

# ==========================================
# 2. PROCESAMIENTO MATEMÁTICO (PANDAS)
# ==========================================
def calcular_valor(df_mercado):
    if df_mercado.empty:
        print("El DataFrame está vacío. No hay datos para procesar.")
        return df_mercado
        
    print("Procesando probabilidades y márgenes...")
    df = df_mercado.copy()
    
    # 2.1 Limpieza: Convertir texto a flotantes (manejando comas si las hay)
    columnas_cuotas = ['Cuota 1', 'Cuota X', 'Cuota 2']
    for col in columnas_cuotas:
        df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
        
    # 2.2 Probabilidades Implícitas
    df['Prob_Imp_1'] = 1 / df['Cuota 1']
    df['Prob_Imp_X'] = 1 / df['Cuota X']
    df['Prob_Imp_2'] = 1 / df['Cuota 2']
    
    # 2.3 Margen de la Casa (Overround basado en los 3 posibles resultados)
    df['Margen_Casa'] = (df['Prob_Imp_1'] + df['Prob_Imp_X'] + df['Prob_Imp_2']) - 1
    
    # 2.4 Probabilidades Reales (sin la comisión)
    df['Prob_Real_1'] = df['Prob_Imp_1'] / (1 + df['Margen_Casa'])
    df['Prob_Real_X'] = df['Prob_Imp_X'] / (1 + df['Margen_Casa'])
    df['Prob_Real_2'] = df['Prob_Imp_2'] / (1 + df['Margen_Casa'])
    
    # 2.5 Cuotas Justas (Fair Odds)
    df['Fair_Odd_1'] = 1 / df['Prob_Real_1']
    df['Fair_Odd_X'] = 1 / df['Prob_Real_X']
    df['Fair_Odd_2'] = 1 / df['Prob_Real_2']
    
    # 2.6 Formato final
    df['Margen_Casa_%'] = (df['Margen_Casa'] * 100).round(2)
    columnas_redondear = ['Fair_Odd_1', 'Fair_Odd_X', 'Fair_Odd_2']
    df[columnas_redondear] = df[columnas_redondear].round(2)
    
    # Retornar el DataFrame organizado
    columnas_finales = ['Local', 'Visitante', 'Margen_Casa_%', 
                        'Cuota 1', 'Fair_Odd_1', 
                        'Cuota X', 'Fair_Odd_X', 
                        'Cuota 2', 'Fair_Odd_2']
    
    return df[columnas_finales]

# ==========================================
# 3. EJECUCIÓN DEL SCRIPT
# ==========================================
if __name__ == "__main__":
    # Reemplaza con la URL real y ajusta las clases CSS en la función extraer_datos_mercado
    URL_OBJETIVO = "https://ejemplo-casa-de-apuestas.com/futbol"
    
    # Ejecutar flujo
    df_crudo = extraer_datos_mercado(URL_OBJETIVO)
    df_procesado = calcular_valor(df_crudo)
    
    print("\n--- RESULTADOS DEL RADAR ---")
    print(df_procesado)
