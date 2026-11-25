import numpy as np
import pandas as pd

# 1. Ingesta de datos
users = pd.read_csv("users.csv")
app_logs = pd.read_csv("app_logs.csv")
access_logs = pd.read_csv("access_logs.csv")

# 2. Conversión de fechas a zona horaria local
users["created_at"] = pd.to_datetime(users["created_at"])
app_logs["timestamp"] = pd.to_datetime(app_logs["timestamp"])
access_logs["timestamp"] = pd.to_datetime(access_logs["timestamp"])

# 3. Cruce relacional (LEFT JOIN) especificando sufijos en ambos merges
df_merged = users.merge(
    access_logs, on="user_id", how="left"
).merge(
    app_logs, on="user_id", how="left", suffixes=("_access", "_app")
)

# 4. Imputación de nulos
# Al especificar los sufijos, las columnas resultantes son 'branch_id_access' y 'event_name_app'
df_merged["branch_id_access"] = df_merged["branch_id_access"].fillna(
    df_merged["branch_id"]
)

df_merged["event_name_app"] = df_merged["event_name_app"].fillna("no_app_activity")