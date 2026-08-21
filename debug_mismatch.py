import pandas as pd
from google.cloud import bigquery

def debug_mismatch():
    client = bigquery.Client(project='vibra-dtan-spoke-eso-dev', location='us-central1')
    
    # Get distinct baias from DB for centro 5064
    query = """
    SELECT DISTINCT baia
    FROM `vibra-dtan-spoke-eso-dev.rw_mdriver.programacao`
    WHERE cod_centro = '5064'
      AND DATE(SAFE_CAST(data AS TIMESTAMP)) BETWEEN '2025-01-01' AND '2025-12-31'
      AND baia IS NOT NULL AND TRIM(baia) != ''
    """
    db_baias = []
    for row in client.query(query).result():
        db_baias.append(row["baia"])
        
    print("Baias no BQ (Centro 5064):")
    print(sorted(db_baias))
    
    # Get presets from CSV for centro 5064
    file_path = "C:/Users/ce9x/agente_jornada_5/data/config_mdriver_tratado_clean.csv"
    df = pd.read_csv(file_path, sep=';', encoding='utf-8-sig')
    df_base = df[df["CodCentro"].astype(str) == '5064']
    csv_presets = df_base["Preset"].tolist()
    print("\nPresets no CSV (Centro 5064):")
    print(sorted(csv_presets))
    
    # Check matching
    db_clean = [b.strip() for b in db_baias]
    csv_clean = [str(p).strip() for p in csv_presets]
    
    matches = set(db_clean).intersection(set(csv_clean))
    print(f"\nMatches: {len(matches)}")
    print(matches)

if __name__ == "__main__":
    debug_mismatch()
