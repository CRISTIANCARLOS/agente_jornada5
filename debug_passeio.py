import pandas as pd
from google.cloud import bigquery

def debug_passeio():
    client = bigquery.Client(project='vibra-dtan-spoke-eso-dev', location='us-central1')
    
    query = """
    SELECT programacao, placa, baia, data, sequencia_publicacao
    FROM `vibra-dtan-spoke-eso-dev.rw_mdriver.programacao`
    WHERE placa = 'FKQ4D71' AND cod_centro = '5064'
    ORDER BY data DESC, sequencia_publicacao DESC
    LIMIT 20
    """
    
    df = client.query(query).to_dataframe()
    print(df.to_string())

if __name__ == "__main__":
    debug_passeio()
