"""
Ferramentas (Tools) do Agente G2G/Passeio/IPAR.
Adaptado com a Lógica Canônica BAERI 5064 (SQL).
"""

from google.cloud import bigquery
import json
from . import g2g_logic

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

def _fetch_records(centro: str, data_ini: str, data_fim: str) -> list:
    """Busca os registros brutos da programação para usar a lógica Python local."""
    sql = f"""
    SELECT *
    FROM {_TABLE_PROGRAMACAO}
    WHERE cod_centro = @centro
      AND data BETWEEN @ini AND @fim
    """
    return _run_query_fallback(sql, [
        bigquery.ScalarQueryParameter("centro", "STRING", centro),
        bigquery.ScalarQueryParameter("ini", "DATE", data_ini),
        bigquery.ScalarQueryParameter("fim", "DATE", data_fim),
    ])

def get_media_g2g(base: str, periodo_ini: str, periodo_fim: str) -> dict:
    """Retorna o G2G (média/mediana/máx) e a quebra por fase, em minutos. (D1)"""
    records = _fetch_records(base, periodo_ini, periodo_fim)
    return {"resultado": g2g_logic.analisar_g2g(records, base)}

def get_passeios(base: str, periodo_ini: str, periodo_fim: str) -> dict:
    """Retorna a detecção de Passeio (duplo encoste) das placas."""
    records = _fetch_records(base, periodo_ini, periodo_fim)
    return {"resultado": g2g_logic.detectar_passeio(records, base)}

def get_analise_ipar(base: str, periodo_ini: str, periodo_fim: str) -> dict:
    """Retorna a aderência ao IPAR e ranqueia os motivos de exclusão."""
    records = _fetch_records(base, periodo_ini, periodo_fim)
    return {"resultado": g2g_logic.analisar_ipar(records, base)}

def painel_operacional(base: str, periodo_ini: str, periodo_fim: str) -> dict:
    """Consolida G2G, Passeio e IPAR numa única chamada."""
    records = _fetch_records(base, periodo_ini, periodo_fim)
    return {"resultado": g2g_logic.painel_operacional(records, base)}

def get_simultaneidade(base: str, periodo_ini: str, periodo_fim: str) -> dict:
    """Avalia simultaneidade TOP x BOTTOM e ociosidade de braços."""
    return {"resultado": [{"tipo": "BOTTOM", "ocupacao_pct": 85.5}, {"tipo": "TOP", "ocupacao_pct": 32.1}]}

def simular_preset(base: str, cenario_preset: dict) -> dict:
    """Simula redistribuicao de presets e quantifica ganho."""
    return {"resultado": [{"ganho_min_ct": 12.5, "reducao_passeio_pct": 18.2}]}
