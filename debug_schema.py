import pandas as pd
from google.cloud import bigquery

def debug_schema():
    client = bigquery.Client(project='vibra-dtan-spoke-eso-dev', location='us-central1')
    
    query = """
    SELECT column_name, data_type 
    FROM `vibra-dtan-spoke-eso-dev.rw_mdriver`.INFORMATION_SCHEMA.COLUMNS 
    WHERE table_name = 'programacao_compartimento'
    """
    for row in client.query(query).result():
        print(f"{row['column_name']}: {row['data_type']}")

if __name__ == "__main__":
    debug_schema()
