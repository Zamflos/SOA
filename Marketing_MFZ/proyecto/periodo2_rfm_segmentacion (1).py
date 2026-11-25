import numpy as np
import pandas as pd

# ============================================================
# PERIODO 2 - Ingeniería de Características y Correlación
# Smart Fit - Modelo RFM + Engagement
# ============================================================

# 1. CARGAR DATOS
# Ajusta las rutas a tus archivos reales
users = pd.read_csv("users.csv")
access_logs = pd.read_csv("access_logs.csv")
app_logs = pd.read_csv("app_logs.csv")

# Convertir fechas
users["created_at"] = pd.to_datetime(users["created_at"])
access_logs["timestamp"] = pd.to_datetime(access_logs["timestamp"])
app_logs["timestamp"] = pd.to_datetime(app_logs["timestamp"])

# Fecha de análisis (ajusta según tu ventana de datos)
fecha_analisis = pd.Timestamp("2026-08-15")

# ============================================================
# 2. INGENIERÍA DE CARACTERÍSTICAS (RFM + Engagement)
# ============================================================

# --- Frequency: Volumen total de accesos físicos (qr_scan_entry) ---
frecuencia = (
    access_logs[access_logs["event_name"] == "qr_scan_entry"]
    .groupby("user_id")
    .size()
    .reset_index(name="frequency")
)

# --- Recency: Días desde el último acceso físico ---
ultima_asistencia = (
    access_logs[access_logs["event_name"] == "qr_scan_entry"]
    .groupby("user_id")["timestamp"]
    .max()
    .reset_index(name="ultima_asistencia")
)
ultima_asistencia["recency"] = (fecha_analisis - ultima_asistencia["ultima_asistencia"]).dt.days

# --- Engagement: Días únicos con actividad en la app ---
engagement = (
    app_logs
    .groupby("user_id")["timestamp"]
    .apply(lambda x: x.dt.date.nunique())
    .reset_index(name="engagement")
)

# --- Días de vida (días desde registro hasta fecha de análisis) ---
users["dias_vida"] = (fecha_analisis - users["created_at"]).dt.days

# ============================================================
# 3. CONSTRUIR MODELO FINAL
# ============================================================
modelo = (
    users[["user_id", "plan_type", "branch_id", "created_at", "dias_vida"]]
    .merge(frecuencia, on="user_id", how="left")
    .merge(ultima_asistencia[["user_id", "recency"]], on="user_id", how="left")
    .merge(engagement, on="user_id", how="left")
)

# Imputación de nulos (usuarios sin actividad)
modelo["frequency"] = modelo["frequency"].fillna(0).astype(int)
modelo["recency"] = modelo["recency"].fillna(999).astype(int)   # 999 = nunca asistió
modelo["engagement"] = modelo["engagement"].fillna(0).astype(int)

print("=== Resumen del modelo RFM + Engagement ===")
print(modelo[["recency", "frequency", "engagement", "dias_vida"]].describe().round(2))
print()

# ============================================================
# 4. MATRIZ DE CORRELACIÓN (Pearson y Spearman)
# ============================================================
vars_analiticas = modelo[["recency", "frequency", "engagement", "dias_vida"]]

matriz_pearson = vars_analiticas.corr(method="pearson")
matriz_spearman = vars_analiticas.corr(method="spearman")

print("=== Matriz de Correlación de Pearson ===")
print(matriz_pearson.round(3))
print()
print("=== Matriz de Correlación de Spearman ===")
print(matriz_spearman.round(3))
print()

# ============================================================
# 5. SEGMENTACIÓN POR PERCENTILES (Puntos de corte)
# ============================================================
# Usamos percentiles para definir umbrales robustos (no afectados por outliers)

# Frequency: cuartiles
q_freq = modelo["frequency"].quantile([0.25, 0.50, 0.75]).to_dict()
print("Percentiles Frequency:", {k: round(v, 1) for k, v in q_freq.items()})

# Recency: cuartiles (menor = mejor)
q_rec = modelo["recency"].quantile([0.25, 0.50, 0.75]).to_dict()
print("Percentiles Recency:", {k: round(v, 1) for k, v in q_rec.items()})

# Engagement: cuartiles
q_eng = modelo["engagement"].quantile([0.25, 0.50, 0.75]).to_dict()
print("Percentiles Engagement:", {k: round(v, 1) for k, v in q_eng.items()})

# --- Función de scoring RFM (1=bajo, 4=alto) ---
def score_frequency(x):
    if x <= q_freq[0.25]:
        return 1
    elif x <= q_freq[0.50]:
        return 2
    elif x <= q_freq[0.75]:
        return 3
    else:
        return 4

def score_recency(x):
    # Invertido: menor recency = mejor score
    if x <= q_rec[0.25]:
        return 4
    elif x <= q_rec[0.50]:
        return 3
    elif x <= q_rec[0.75]:
        return 2
    else:
        return 1

def score_engagement(x):
    if x <= q_eng[0.25]:
        return 1
    elif x <= q_eng[0.50]:
        return 2
    elif x <= q_eng[0.75]:
        return 3
    else:
        return 4

modelo["R_score"] = modelo["recency"].apply(score_recency)
modelo["F_score"] = modelo["frequency"].apply(score_frequency)
modelo["E_score"] = modelo["engagement"].apply(score_engagement)

# RFM combinado (promedio ponderado simple)
modelo["RFM_score"] = (modelo["R_score"] + modelo["F_score"] + modelo["E_score"]) / 3

# ============================================================
# 6. SEGMENTACIÓN FINAL (3 segmentos para campañas)
# ============================================================
def asignar_segmento(row):
    # Lógica alineada con la hipótesis del Aha! Moment
    if row["R_score"] >= 3 and row["F_score"] >= 3 and row["E_score"] >= 3:
        return "Champions"          # Alta retención potencial
    elif row["R_score"] >= 2 and row["F_score"] >= 2:
        return "Potenciales"        # En camino al hábito
    else:
        return "En riesgo"          # Baja actividad / alto riesgo de churn

modelo["segmento"] = modelo.apply(asignar_segmento, axis=1)

print("\n=== Distribución de segmentos ===")
print(modelo["segmento"].value_counts())
print()
print(modelo["segmento"].value_counts(normalize=True).round(3) * 100)

# ============================================================
# 7. EXPORTAR BASE FINAL SEGMENTADA
# ============================================================
columnas_export = [
    "user_id", "plan_type", "branch_id", "dias_vida",
    "recency", "frequency", "engagement",
    "R_score", "F_score", "E_score", "RFM_score", "segmento"
]

modelo[columnas_export].to_csv("modelo_rfm_segmentado.csv", index=False)
print("\n✓ Archivo exportado: modelo_rfm_segmentado.csv")
print(f"  Total usuarios: {len(modelo)}")
print(f"  Columnas: {columnas_export}")
