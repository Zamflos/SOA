import pandas as pd
import numpy as np

path = "C:/Users/malco/OneDrive/Documentos/Marketing_MFZ/"

users_df = pd.read_csv(path + "Users.csv")
events_df = pd.read_csv(path + "Events.csv")

print("--- ESTRUCTURA DE USERS ---")
print(users_df.info())

print("\n--- ESTRUCTURA DE EVENTS ---")
print(events_df.info())

events_df['event_timestamp'] = pd.to_datetime(events_df['event_timestamp'])

print("\n--- VALORES NULOS POR COLUMNA ---")
print(events_df.isnull().sum())

print(events_df.head(2))
print(users_df['email'].value_counts())


df_combinado = pd.merge(users_df, events_df, on='user_id')
df_combinado.columns = df_combinado.columns.str.strip()
col_evento = [col for col in df_combinado.columns if 'event' in col.lower() and col != 'event_timestamp'][0]
df_filtrado = df_combinado[df_combinado[col_evento] == 'create_project']
print("\n--- CORREOS CON EVENTO CREATE_PROJECT ---")
print(df_filtrado['email'])


users_df['created_at'] = pd.to_datetime(users_df['created_at'])
events_df['event_timestamp'] = pd.to_datetime(events_df['event_timestamp'])
df_tiempo = pd.merge(users_df, events_df, on='user_id')
df_tiempo['dias_enteros'] = (df_tiempo['event_timestamp'] - df_tiempo['created_at']).dt.days
df_filtrado_tiempo = df_tiempo[df_tiempo['dias_enteros'] <= 1]
print("\n--- CANTIDAD DE REGISTROS CON DÍAS ENTEROS <= 1 ---")
print(len(df_filtrado_tiempo))


# --- BLOQUE NUEVO: Cálculo de WAU (Weekly Active Users) ---
events_df['semana_evento'] = events_df['event_timestamp'].dt.isocalendar().week
wau_df = events_df.groupby('semana_evento')['user_id'].nunique().reset_index()

print("\n--- USUARIOS ÚNICOS POR SEMANA (WAU) ---")
print(wau_df)