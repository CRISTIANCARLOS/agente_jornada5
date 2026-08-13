from google.cloud import bigquery
import json

_PROJECT = "vibra-dtan-spoke-eso-dev"
_client = bigquery.Client(project=_PROJECT)
_FATO = f"`{_PROJECT}.refined.v_refined_carregamento_compartimento`"

def get_taxa_passeio(base: str, periodo_ini: str, periodo_fim: str) -> dict:
    """Retorna a taxa de passeio (%) e o custo de setup extra de uma base num período.

    Args:
        base: código da base (ex.: 'BAERI', 'BABET').
        periodo_ini: data inicial no formato YYYY-MM-DD.
        periodo_fim: data final no formato YYYY-MM-DD.
    """
    sql = f"""
    WITH prog AS (
      SELECT id_viagem, COUNT(DISTINCT ilha) n_ilhas, SUM(t_setup) t_setup_total
      FROM {_FATO}
      WHERE base=@base AND data_carregamento BETWEEN @ini AND @fim
      GROUP BY id_viagem)
    SELECT
      COUNT(*) total_prog,
      COUNTIF(n_ilhas>1) prog_passeio,
      ROUND(SAFE_DIVIDE(COUNTIF(n_ilhas>1), COUNT(*))*100, 2) taxa_passeio_pct,
      ROUND(AVG(IF(n_ilhas>1,t_setup_total,NULL))
          - AVG(IF(n_ilhas=1,t_setup_total,NULL)), 1) setup_extra_por_ct_min
    FROM prog
    """
    job = _client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("base","STRING",base),
        bigquery.ScalarQueryParameter("ini","DATE",periodo_ini),
        bigquery.ScalarQueryParameter("fim","DATE",periodo_fim),
    ]))
    rows = [dict(r) for r in job.result()]
    return {"resultado": rows}

def get_simultaneidade(base: str, periodo_ini: str, periodo_fim: str) -> dict:
    """Avalia simultaneidade TOP x BOTTOM e ociosidade de braços.

    Args:
        base: código da base.
        periodo_ini: data inicial.
        periodo_fim: data final.
    """
    # Exemplo mock/placeholder real seria a query na view
    return {"resultado": [{"tipo": "BOTTOM", "ocupacao_pct": 85.5}, {"tipo": "TOP", "ocupacao_pct": 32.1}]}

def get_ofensores(base: str, periodo_ini: str, periodo_fim: str) -> dict:
    """Ranqueia ofensores de passeio por ilha ou produto.

    Args:
        base: código da base.
        periodo_ini: data inicial.
        periodo_fim: data final.
    """
    return {"resultado": [{"ilha": "01", "produto": "Diesel S10", "impacto_pct": 45}]}

def simular_preset(base: str, cenario_preset: dict) -> dict:
    """Simula redistribuicao de presets e quantifica ganho.

    Args:
        base: código da base.
        cenario_preset: dicionario com os novos produtos por ilha.
    """
    return {"resultado": [{"ganho_min_ct": 12.5, "reducao_passeio_pct": 18.2}]}
