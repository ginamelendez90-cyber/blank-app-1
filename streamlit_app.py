import pandas as pd
from supabase import create_client
from sklearn.ensemble import RandomForestRegressor
import numpy as np

# --- CONFIGURACIÓN ---
URL_SUPABASE = "https://netrbgledrnsjjuyhpui.supabase.co"
KEY_SUPABASE = "sb_publishable_qH4a5QFumA-zqXfhZD6l-w_r5gTLRie"
supabase = create_client(URL_SUPABASE, KEY_SUPABASE)

def obtener_contexto_ia(texto_noticias):
    """
    SIMULACIÓN OPCIÓN 2: 
    Aquí conectarías con la API de Gemini para analizar noticias.
    Retorna un valor entre -1.0 (muy negativo) y 1.0 (muy positivo).
    """
    # Lógica simplificada: busca palabras clave para el ejemplo
    palabras_positivas = ['ganador', 'estable', 'crecimiento', 'favorable']
    if any(word in texto_noticias.lower() for word in palabras_positivas):
        return 0.85
    return -0.42

def entrenar_y_predecir(datos_historicos, nuevos_datos, contexto_ia):
    """
    OPCIÓN 3: Machine Learning.
    Entrena un modelo rápido con lo que hay en Supabase y predice.
    """
    df = pd.DataFrame(datos_historicos)
    
    # Definimos variables X (técnicas + contexto) y Y (resultado real pasado)
    X = df[['dato_tecnico_1', 'dato_tecnico_2', 'puntaje_contexto_ia']]
    y = df['resultado_numerico'] # Ej: 1 para éxito, 0 para fallo
    
    modelo = RandomForestRegressor(n_estimators=100)
    modelo.fit(X, y)
    
    # Predecir con los datos de hoy + el sentimiento de la IA
    nuevos_datos['puntaje_contexto_ia'] = contexto_ia
    prediccion = modelo.predict([list(nuevos_datos.values())])
    
    return float(prediccion[0])

# --- FLUJO PRINCIPAL ---

# 1. Obtener históricos de Supabase para entrenar
res = supabase.table("predicciones_inteligentes").select("*").execute()
historicos = res.data

# 2. Datos del evento actual (Ejemplo)
noticia_hoy = "El mercado muestra un crecimiento favorable para esta semana"
datos_hoy = {
    "dato_tecnico_1": 1.5,
    "dato_tecnico_2": 2.8
}

# 3. Ejecutar Inteligencia
print("Analizando contexto con IA...")
puntuacion = obtener_contexto_ia(noticia_hoy)

print("Calculando predicción con ML...")
# Si no hay históricos, usamos una base por defecto
if len(historicos) > 5:
    resultado = entrenar_y_predecir(historicos, datos_hoy, puntuacion)
else:
    # Lógica inicial si la base está vacía
    resultado = (datos_hoy['dato_tecnico_1'] + datos_hoy['dato_tecnico_2']) * 0.1 + puntuacion

# 4. Guardar en Supabase para aprender después
registro = {
    "nombre_evento": "Evento Beta 01",
    "dato_tecnico_1": datos_hoy['dato_tecnico_1'],
    "dato_tecnico_2": datos_hoy['dato_tecnico_2'],
    "puntaje_contexto_ia": puntuacion,
    "prediccion_final_ml": resultado
}

supabase.table("predicciones_inteligentes").insert(registro).execute()

print(f"--- PROCESO COMPLETADO ---")
print(f"Confianza de la predicción: {resultado:.2f}")
