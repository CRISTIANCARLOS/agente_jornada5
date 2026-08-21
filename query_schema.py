from google.cloud import bigquery

def check_schemas():
    client = bigquery.Client(project='vibra-dtan-spoke-eso-dev', location='us-central1')
    
    try:
        print("Schema programacao:")
        query = "SELECT * FROM `vibra-dtan-spoke-eso-dev.rw_mdriver.programacao` LIMIT 1"
        for row in client.query(query).result():
            print(row.keys())
            break
            
        print("\nSchema programacao_compartimento:")
        query = "SELECT * FROM `vibra-dtan-spoke-eso-dev.rw_mdriver.programacao_compartimento` LIMIT 1"
        for row in client.query(query).result():
            print(row.keys())
            break
            
        print("\nSchema produto:")
        query = "SELECT * FROM `vibra-dtan-spoke-eso-dev.rw_mdriver.produto` LIMIT 1"
        for row in client.query(query).result():
            print(row.keys())
            break

    except Exception as e:
        print(f"Erro: {e}")

check_schemas()
