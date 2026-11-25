import numpy as np
import pandas as pd

# 1. Cargar los datos desde el archivo CSV
users_df = pd.read_csv("M/users_ampliado.csv")

# 2. Asegurar que la columna created_at esté en formato de fecha
users_df["created_at"] = pd.to_datetime(users_df["created_at"])

# 3. Extraer el mes de registro
users_df["mes_registro"] = users_df["created_at"].dt.month

# 4. Crear la segmentación algorítmica con np.where()
users_df["tipo_cliente"] = np.where(
    users_df["mes_registro"] <= 7, "Pionero", "Novato"
)

# 5. Imprimir el conteo total de cada segmento
print(users_df["tipo_cliente"].value_counts())