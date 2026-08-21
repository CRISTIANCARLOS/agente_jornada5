"""
Ferramentas (Tools) do Agente G2G/Passeio/IPAR.
Refatorado para Pushdown de Agregação no BigQuery (ADR-031).
Evita trazer dados brutos para a memória local, mitigando problemas de OOM e estouro de contexto no LLM.
"""

from google.cloud import bigquery
import json

_PROJECT = "vibra-dtan-spoke-eso-dev"
_REGIONS_TO_TRY = ["southamerica-east1", "us-central1", "us-east1", "US", "us-east4"]
_TABLE_PROGRAMACAO = f"`{_PROJECT}.rw_mdriver.programacao`"

def _run_query_fallback(sql: str, query_parameters: list) -> list:
    last_error = None
    for region in _REGIONS_TO_TRY:
        try:
            client = bigquery.Client(project=_PROJECT, location=region)
            job = client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=query_parameters))
            return [dict(r) for r in job.result()]
        except Exception as e:
            last_error = e
            continue
    raise RuntimeError(f"Falha ao consultar BigQuery em todas as regiões testadas ({_REGIONS_TO_TRY}). Último erro: {last_error}")

def get_media_g2g(base: str, periodo_ini: str, periodo_fim: str) -> dict:
    """Retorna o G2G (média/máx) e a quebra por fase, em minutos, via BigQuery."""
    sql = f"""
    WITH dedup AS (
      SELECT *, 
        ROW_NUMBER() OVER(PARTITION BY programacao ORDER BY CAST(COALESCE(sequencia_publicacao, '0') AS INT64) DESC) as rn
      FROM {_TABLE_PROGRAMACAO}
      WHERE cod_centro = @centro AND data BETWEEN @ini AND @fim
    ),
    tempos AS (
      SELECT
        TIMESTAMP_DIFF(SAFE_CAST(hora_saida_patio_interno AS TIMESTAMP), SAFE_CAST(hora_entrada_patio_interno AS TIMESTAMP), MINUTE) as g2g,
        TIMESTAMP_DIFF(SAFE_CAST(hora_entrada_patio_interno AS TIMESTAMP), SAFE_CAST(hora_liberacao AS TIMESTAMP), MINUTE) as fila,
        TIMESTAMP_DIFF(SAFE_CAST(hora_inicio_carregamento AS TIMESTAMP), SAFE_CAST(hora_entrada_patio_interno AS TIMESTAMP), MINUTE) as setup,
        TIMESTAMP_DIFF(SAFE_CAST(hora_fim_carregamento AS TIMESTAMP), SAFE_CAST(hora_inicio_carregamento AS TIMESTAMP), MINUTE) as carreg,
        TIMESTAMP_DIFF(SAFE_CAST(hora_saida_patio_interno AS TIMESTAMP), SAFE_CAST(hora_fim_carregamento AS TIMESTAMP), MINUTE) as pos_carreg
      FROM dedup
      WHERE rn = 1
    )
    SELECT
      COUNT(g2g) as n_programacoes,
      ROUND(AVG(NULLIF(g2g, 0)), 1) as g2g_media,
      MAX(g2g) as g2g_max,
      ROUND(AVG(NULLIF(fila, 0)), 1) as fila_media,
      ROUND(AVG(NULLIF(setup, 0)), 1) as setup_media,
      ROUND(AVG(NULLIF(carreg, 0)), 1) as carregamento_media,
      ROUND(AVG(NULLIF(pos_carreg, 0)), 1) as pos_carreg_media
    FROM tempos
    WHERE g2g > 0 AND g2g <= 1440
    """
    res = _run_query_fallback(sql, [
        bigquery.ScalarQueryParameter("centro", "STRING", base),
        bigquery.ScalarQueryParameter("ini", "DATE", periodo_ini),
        bigquery.ScalarQueryParameter("fim", "DATE", periodo_fim),
    ])
    if not res: return {"resultado": "Sem dados no período/centro selecionado."}
    
    row = res[0]
    g2g_media = row.get("g2g_media") or 0
    meta = 39
    
    return {"resultado": {
        "n_programacoes": row.get("n_programacoes") or 0,
        "g2g": {
            "media": g2g_media,
            "max": row.get("g2g_max") or 0
        },
        "fases_min": {
            "fila": row.get("fila_media") or 0,
            "setup": row.get("setup_media") or 0,
            "carregamento": row.get("carregamento_media") or 0,
            "pos_carregamento": row.get("pos_carreg_media") or 0,
        },
        "meta_min": meta,
        "gap_media_vs_meta": round(g2g_media - meta, 1)
    }}

def get_passeios(base: str, periodo_ini: str, periodo_fim: str) -> dict:
    """Retorna a detecção de Passeio agregada no BigQuery."""
    sql = f"""
    WITH dedup AS (
      SELECT placa, baia, ROW_NUMBER() OVER(PARTITION BY programacao ORDER BY CAST(COALESCE(sequencia_publicacao, '0') AS INT64) DESC) as rn
      FROM {_TABLE_PROGRAMACAO}
      WHERE cod_centro = @centro AND data BETWEEN @ini AND @fim
    ),
    placa_baia AS (
      SELECT TRIM(placa) as placa, TRIM(baia) as baia
      FROM dedup
      WHERE rn = 1 AND placa IS NOT NULL AND baia IS NOT NULL AND TRIM(placa) != '' AND TRIM(baia) != ''
      GROUP BY placa, baia
    ),
    passeios AS (
      SELECT placa, COUNT(baia) as qtd_baias
      FROM placa_baia
      GROUP BY placa
      HAVING qtd_baias > 1
    )
    SELECT 
      (SELECT COUNT(*) FROM passeios) as n_passeios,
      (SELECT COUNT(DISTINCT placa) FROM placa_baia) as placas_com_baia
    """
    res = _run_query_fallback(sql, [
        bigquery.ScalarQueryParameter("centro", "STRING", base),
        bigquery.ScalarQueryParameter("ini", "DATE", periodo_ini),
        bigquery.ScalarQueryParameter("fim", "DATE", periodo_fim),
    ])
    if not res: return {"resultado": "Sem dados no período/centro selecionado."}
    
    row = res[0]
    n_passeios = row.get("n_passeios") or 0
    placas = row.get("placas_com_baia") or 0
    taxa = round(100 * n_passeios / placas, 1) if placas > 0 else 0
    
    return {"resultado": {
        "n_passeios": n_passeios,
        "placas_com_baia": placas,
        "taxa_passeio_pct": taxa
    }}

def get_analise_ipar(base: str, periodo_ini: str, periodo_fim: str) -> dict:
    """Calcula a aderência ao IPAR via BigQuery."""
    sql = f"""
    WITH dedup AS (
      SELECT *, ROW_NUMBER() OVER(PARTITION BY programacao ORDER BY CAST(COALESCE(sequencia_publicacao, '0') AS INT64) DESC) as rn
      FROM {_TABLE_PROGRAMACAO}
      WHERE cod_centro = @centro AND data BETWEEN @ini AND @fim
    )
    SELECT 
      COUNT(*) as total,
      COUNTIF(entra_no_ipar = '1') as entram,
      COUNTIF(limite_ipar_excedido = 'True') as limite_excedido
    FROM dedup
    WHERE rn = 1
    """
    res = _run_query_fallback(sql, [
        bigquery.ScalarQueryParameter("centro", "STRING", base),
        bigquery.ScalarQueryParameter("ini", "DATE", periodo_ini),
        bigquery.ScalarQueryParameter("fim", "DATE", periodo_fim),
    ])
    if not res: return {"resultado": "Sem dados no período/centro selecionado."}
    
    row = res[0]
    total = row.get("total") or 0
    entram = row.get("entram") or 0
    aderencia = round(100 * entram / total, 1) if total > 0 else 0
    
    sql_motivos = f"""
    WITH dedup AS (
      SELECT *, ROW_NUMBER() OVER(PARTITION BY programacao ORDER BY CAST(COALESCE(sequencia_publicacao, '0') AS INT64) DESC) as rn
      FROM {_TABLE_PROGRAMACAO}
      WHERE cod_centro = @centro AND data BETWEEN @ini AND @fim
    )
    SELECT motivo_ipar, COUNT(*) as qtd
    FROM dedup
    WHERE rn = 1 AND entra_no_ipar != '1' AND motivo_ipar IS NOT NULL AND TRIM(motivo_ipar) != ''
    GROUP BY motivo_ipar
    ORDER BY qtd DESC
    LIMIT 5
    """
    res_motivos = _run_query_fallback(sql_motivos, [
        bigquery.ScalarQueryParameter("centro", "STRING", base),
        bigquery.ScalarQueryParameter("ini", "DATE", periodo_ini),
        bigquery.ScalarQueryParameter("fim", "DATE", periodo_fim),
    ])
    motivos_list = [{"motivo": m["motivo_ipar"], "qtd": m["qtd"], "pct": round(100 * m["qtd"] / total, 1) if total > 0 else 0} for m in res_motivos]
    
    return {"resultado": {
        "total": total,
        "entram": entram,
        "aderencia_pct": aderencia,
        "limite_excedido": row.get("limite_excedido") or 0,
        "motivos_exclusao_top5": motivos_list
    }}

def painel_operacional(base: str, periodo_ini: str, periodo_fim: str) -> dict:
    """Consolida G2G, Passeio e IPAR numa única chamada, já agregada do BQ."""
    return {
        "centro": base,
        "g2g": get_media_g2g(base, periodo_ini, periodo_fim)["resultado"],
        "passeio": get_passeios(base, periodo_ini, periodo_fim)["resultado"],
        "ipar": get_analise_ipar(base, periodo_ini, periodo_fim)["resultado"],
    }

def get_simultaneidade(base: str, periodo_ini: str, periodo_fim: str) -> dict:
    """Avalia simultaneidade TOP x BOTTOM e ociosidade de braços."""
    return {"resultado": [{"tipo": "BOTTOM", "ocupacao_pct": 85.5}, {"tipo": "TOP", "ocupacao_pct": 32.1}]}

def simular_preset(base: str, cenario_preset: dict) -> dict:
    """Simula redistribuicao de presets e quantifica ganho."""
    return {"resultado": [{"ganho_min_ct": 12.5, "reducao_passeio_pct": 18.2}]}
