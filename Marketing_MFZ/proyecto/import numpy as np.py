import numpy as np
import pandas as pd

# ============================================================
# 1. CARGAR LOS CSV
# ============================================================
users = pd.read_csv("C:\\Users\\malco\\OneDrive\\Documentos\\Marketing_MFZ\\proyecto\\users.csv")
access_logs = pd.read_csv("C:\\Users\\malco\\OneDrive\\Documentos\\Marketing_MFZ\\proyecto\\access_logs.csv")
app_logs = pd.read_csv("C:\\Users\\malco\\OneDrive\\Documentos\\Marketing_MFZ\\proyecto\\app_logs.csv")          # ← necesario para engagement

# Convertir fechas
users['created_at'] = pd.to_datetime(users['created_at'])
access_logs['timestamp'] = pd.to_datetime(access_logs['timestamp'])
app_logs['timestamp'] = pd.to_datetime(app_logs['timestamp'])

# ============================================================
# 2. CALCULAR MÉTRICAS
# ============================================================
fecha_analisis = pd.Timestamp("2026-08-15")

# --- Frecuencia total (asistencias físicas) ---
frecuencia = (
    access_logs
    .groupby('user_id')
    .size()
    .reset_index(name='frecuencia_total')
)

# --- Recencia (días desde última asistencia) ---
ultima_asistencia = (
    access_logs
    .groupby('user_id')['timestamp']
    .max()
    .reset_index(name='ultima_asistencia')
)
ultima_asistencia['recencia_dias'] = (fecha_analisis - ultima_asistencia['ultima_asistencia']).dt.days

# --- Engagement (días distintos con actividad en la app) ---
engagement = (
    app_logs
    .groupby('user_id')['timestamp']
    .apply(lambda x: x.dt.date.nunique())   # días únicos de uso de la app
    .reset_index(name='engagement_dias')
)

# ============================================================
# 3. CONSTRUIR modelo_rfm_final
# ============================================================
modelo_rfm_final = (
    users[['user_id', 'plan_type', 'branch_id']]
    .merge(frecuencia, on='user_id', how='left')
    .merge(ultima_asistencia[['user_id', 'recencia_dias']], on='user_id', how='left')
    .merge(engagement, on='user_id', how='left')
)

# Rellenar nulos
modelo_rfm_final['frecuencia_total'] = modelo_rfm_final['frecuencia_total'].fillna(0).astype(int)
modelo_rfm_final['recencia_dias'] = modelo_rfm_final['recencia_dias'].fillna(999).astype(int)
modelo_rfm_final['engagement_dias'] = modelo_rfm_final['engagement_dias'].fillna(0).astype(int)

# ============================================================
# 4. CORRELACIÓN DE SPEARMAN (solo las 3 variables pedidas)
# ============================================================
variables_analiticas = modelo_rfm_final[['recencia_dias', 'frecuencia_total', 'engagement_dias']]

matriz_spearman = variables_analiticas.corr(method='spearman')

print("=== Matriz de Correlación de Spearman ===")
print(matriz_spearman.round(3))