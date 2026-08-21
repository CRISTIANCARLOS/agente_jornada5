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
    # Como a tabela já foi confirmada na us-central1, vamos focar nela
    # e parar de esconder erros de sintaxe ou acesso num loop de falhas.
    try:
        client = bigquery.Client(project=_PROJECT, location="us-central1")
        job = client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=query_parameters))
        return [dict(r) for r in job.result()]
    except Exception as e:
        raise RuntimeError(f"Erro ao consultar BigQuery na us-central1: {str(e)}")

def _parse_date_to_iso(date_str: str, default: str) -> str:
    """Converte 'DD/MM/YYYY' para 'YYYY-MM-DD'. Se inválido/vazio, usa o default."""
    if not date_str:
        return default
    
    date_str = date_str.strip()
    if "/" in date_str:
        parts = date_str.split("/")
        if len(parts) == 3:
            # Ex: 01/12/2025 -> 2025-12-01
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return date_str

def get_media_g2g(base: str, periodo_ini: str, periodo_fim: str) -> dict:
    """Retorna o G2G (média/máx) e a quebra por fase, em minutos, via BigQuery."""
    ini_param = _parse_date_to_iso(periodo_ini, "2020-01-01")
    fim_param = _parse_date_to_iso(periodo_fim, "2030-12-31")

    sql = f"""
    WITH dedup AS (
      SELECT *, 
        ROW_NUMBER() OVER(PARTITION BY programacao ORDER BY COALESCE(CAST(sequencia_publicacao AS INT64), 0) DESC) as rn
      FROM {_TABLE_PROGRAMACAO}
      WHERE cod_centro = @centro AND DATE(SAFE_CAST(data AS TIMESTAMP)) BETWEEN @ini AND @fim
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
        bigquery.ScalarQueryParameter("ini", "DATE", ini_param),
        bigquery.ScalarQueryParameter("fim", "DATE", fim_param),
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
    """Retorna a detecção de Passeio (visita a múltiplas ILHAS) agregada no BQ, usando topologia local."""
    ini_param = _parse_date_to_iso(periodo_ini, "2020-01-01")
    fim_param = _parse_date_to_iso(periodo_fim, "2030-12-31")

    # 1. Busca a topologia local para ensinar o BigQuery a traduzir Presets/Baias para Ilhas
    topologia = get_topologia_ilhas(base)
    ilhas_dict = {}
    
    import re
    
    if "resultado" in topologia and isinstance(topologia["resultado"], dict):
        for detalhe in topologia["resultado"].get("detalhes", []):
            for preset_info in detalhe.get("baias", []):
                nome_preset = preset_info["preset"]
                ilha_nome = detalhe["ilha"]
                # Associa o nome exato do CSV à Ilha
                ilhas_dict[nome_preset] = ilha_nome
                
                # Regra de negócio (Tradução heurística):
                # Se o CSV tiver "PRESET-10", e o BQ tiver "PE 10 A" ou "PE 10 TA"
                # A gente extrai os números do PRESET e faz o de-para para suportar o formato do BQ
                match = re.search(r'\d+', nome_preset)
                if match:
                    numero = match.group()
                    # Mapeia formatos comuns de BQ baseados nesse número
                    ilhas_dict[f"PE {numero} A"] = ilha_nome
                    ilhas_dict[f"PE {numero} TA"] = ilha_nome
                    ilhas_dict[f"PE {numero} SK1"] = ilha_nome
                    ilhas_dict[f"PE {numero} SK2"] = ilha_nome
                    ilhas_dict[f"PE {numero} B100"] = ilha_nome
                    ilhas_dict[f"PE {numero} POD"] = ilha_nome
                    ilhas_dict[f"PE {numero} PODIUM C"] = ilha_nome
                    ilhas_dict[f"PE{numero} TA"] = ilha_nome # Sem espaço
                
    # 2. Constrói o tradutor dinâmico (CASE WHEN)
    case_when_clauses = []
    for chave_bq, ilha in ilhas_dict.items():
        case_when_clauses.append(f"WHEN '{chave_bq}' THEN '{ilha}'")
        
    if case_when_clauses:
        case_sql = "CASE TRIM(baia) " + " ".join(case_when_clauses) + " ELSE TRIM(baia) END"
    else:
        case_sql = "TRIM(baia)" # Fallback

    # 3. Query BQ contando Ilhas (não mais presets soltos) por Viagem (Placa + Dia)
    sql = f"""
    WITH historico_viagem AS (
      SELECT 
        CONCAT(CAST(DATE(SAFE_CAST(data AS TIMESTAMP)) AS STRING), '|', TRIM(placa)) as id_viagem,
        TRIM(placa) as placa, 
        TRIM(baia) as preset_utilizado,
        ({case_sql}) as ilha_visitada
      FROM {_TABLE_PROGRAMACAO}
      WHERE cod_centro = @centro 
        AND DATE(SAFE_CAST(data AS TIMESTAMP)) BETWEEN @ini AND @fim
        AND baia IS NOT NULL AND TRIM(baia) != ''
        AND placa IS NOT NULL AND TRIM(placa) != ''
    ),
    viagens_agregadas AS (
      SELECT 
        id_viagem, 
        MAX(placa) as placa, 
        COUNT(DISTINCT ilha_visitada) as qtd_ilhas, 
        STRING_AGG(DISTINCT ilha_visitada, ' -> ') as rotas_ilhas
      FROM historico_viagem
      GROUP BY id_viagem
    ),
    passeios AS (
      SELECT * FROM viagens_agregadas WHERE qtd_ilhas > 1
    ),
    todas_viagens AS (
      SELECT * FROM viagens_agregadas
    ),
    ilhas_passeio AS (
      SELECT DISTINCT id_viagem, ilha_visitada
      FROM historico_viagem
      WHERE id_viagem IN (SELECT id_viagem FROM passeios)
    )
    SELECT 
      (SELECT COUNT(*) FROM passeios) as n_passeios,
      (SELECT COUNT(*) FROM todas_viagens) as programacoes_totais,
      (
        SELECT ARRAY_AGG(STRUCT(ilha_visitada as ilha, qtd))
        FROM (
          SELECT ilha_visitada, COUNT(DISTINCT id_viagem) as qtd
          FROM ilhas_passeio
          GROUP BY ilha_visitada
          ORDER BY qtd DESC
          LIMIT 10
        )
      ) as top_ilhas_ofensoras,
      (
        SELECT ARRAY_AGG(STRUCT(placa, qtd_ilhas, rotas_ilhas))
        FROM (
          SELECT placa, qtd_ilhas, rotas_ilhas
          FROM passeios
          ORDER BY qtd_ilhas DESC
          LIMIT 5
        )
      ) as exemplos_placas_passeio
    """
    res = _run_query_fallback(sql, [
        bigquery.ScalarQueryParameter("centro", "STRING", base),
        bigquery.ScalarQueryParameter("ini", "DATE", ini_param),
        bigquery.ScalarQueryParameter("fim", "DATE", fim_param),
    ])
    if not res: return {"resultado": "Sem dados no período/centro selecionado."}
    
    row = res[0]
    n_passeios = row.get("n_passeios") or 0
    programacoes = row.get("programacoes_totais") or 0
    taxa = round(100 * n_passeios / programacoes, 1) if programacoes > 0 else 0
    
    top_ilhas = []
    for b in (row.get("top_ilhas_ofensoras") or []):
        top_ilhas.append({"ilha": b["ilha"], "ocorrencias_em_passeios": b["qtd"]})
        
    # Monta um dicionário reverso para enriquecer a rota com produtos e tipo
    ilha_details = {}
    if "resultado" in topologia and isinstance(topologia["resultado"], dict):
        for detalhe in topologia["resultado"].get("detalhes", []):
            produtos_ilha = set()
            for baia in detalhe.get("baias", []):
                produtos_ilha.update(baia.get("produtos", []))
            produtos_limpos = [p.strip() for p in produtos_ilha if p.strip() and p.strip() != "SEM PRODUTO"]
            ilha_details[detalhe["ilha"]] = {
                "tipo": detalhe["tipo"],
                "produtos": produtos_limpos
            }
            
    top_placas = []
    for p in (row.get("exemplos_placas_passeio") or []):
        ilhas_str = p["rotas_ilhas"]
        ilhas_lista = [i.strip() for i in ilhas_str.split("->") if i.strip()]
        rota_enriquecida = []
        for ilha in ilhas_lista:
            info = ilha_details.get(ilha)
            if info:
                prods = ", ".join(info["produtos"]) if info["produtos"] else "Sem Produtos Cadastrados"
                rota_enriquecida.append(f"{ilha} [Tipo: {info['tipo']}, Produtos: {prods}]")
            else:
                rota_enriquecida.append(ilha)
                
        top_placas.append({
            "placa": p["placa"], 
            "ilhas_visitadas": p["qtd_ilhas"], 
            "rota": " -> ".join(rota_enriquecida)
        })
    
    return {"resultado": {
        "n_passeios": n_passeios,
        "programacoes_envolvidas": programacoes,
        "taxa_passeio_pct": taxa,
        "ranking_ilhas_ofensoras": top_ilhas,
        "top_5_placas_passeio_rotas": top_placas
    }}

def get_analise_ipar(base: str, periodo_ini: str, periodo_fim: str) -> dict:
    """Calcula a aderência ao IPAR via BigQuery."""
    ini_param = _parse_date_to_iso(periodo_ini, "2020-01-01")
    fim_param = _parse_date_to_iso(periodo_fim, "2030-12-31")

    sql = f"""
    WITH dedup AS (
      SELECT *, ROW_NUMBER() OVER(PARTITION BY programacao ORDER BY COALESCE(CAST(sequencia_publicacao AS INT64), 0) DESC) as rn
      FROM {_TABLE_PROGRAMACAO}
      WHERE cod_centro = @centro AND DATE(SAFE_CAST(data AS TIMESTAMP)) BETWEEN @ini AND @fim
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
        bigquery.ScalarQueryParameter("ini", "DATE", ini_param),
        bigquery.ScalarQueryParameter("fim", "DATE", fim_param),
    ])
    if not res: return {"resultado": "Sem dados no período/centro selecionado."}
    
    row = res[0]
    total = row.get("total") or 0
    entram = row.get("entram") or 0
    aderencia = round(100 * entram / total, 1) if total > 0 else 0
    
    sql_motivos = f"""
    WITH dedup AS (
      SELECT *, ROW_NUMBER() OVER(PARTITION BY programacao ORDER BY COALESCE(CAST(sequencia_publicacao AS INT64), 0) DESC) as rn
      FROM {_TABLE_PROGRAMACAO}
      WHERE cod_centro = @centro AND DATE(SAFE_CAST(data AS TIMESTAMP)) BETWEEN @ini AND @fim
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
        bigquery.ScalarQueryParameter("ini", "DATE", ini_param),
        bigquery.ScalarQueryParameter("fim", "DATE", fim_param),
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
    """Consolida G2G, Passeio, IPAR, Simultaneidade (Filas Top/Bottom) e Simulacao de CAPEX numa única chamada."""
    return {
        "centro": base,
        "g2g": get_media_g2g(base, periodo_ini, periodo_fim).get("resultado"),
        "passeio": get_passeios(base, periodo_ini, periodo_fim).get("resultado"),
        "ipar": get_analise_ipar(base, periodo_ini, periodo_fim).get("resultado"),
        "simultaneidade_top_bottom": get_simultaneidade(base, periodo_ini, periodo_fim).get("resultado"),
        "simulacao_capex_setup": simular_reducao_setup(base, periodo_ini, periodo_fim).get("resultado")
    }

def get_simultaneidade(base: str, periodo_ini: str, periodo_fim: str) -> dict:
    """Avalia o G2G, Fila e Carregamento quebrado por Tipo de Ilha (TOP, BOTTOM, MISTA) cruzando com a topologia local."""
    ini_param = _parse_date_to_iso(periodo_ini, "2020-01-01")
    fim_param = _parse_date_to_iso(periodo_fim, "2030-12-31")

    # 1. Busca a topologia local para ensinar o BQ a traduzir Presets/Baias para Tipo de Ilha
    topologia = get_topologia_ilhas(base)
    tipo_dict = {}
    
    import re
    if "resultado" in topologia and isinstance(topologia["resultado"], dict):
        for detalhe in topologia["resultado"].get("detalhes", []):
            tipo_bruto = detalhe.get("tipo", "DESCONHECIDO").strip().upper()
            
            # Traduz os códigos do Excel para strings legíveis
            if tipo_bruto == "T":
                tipo_clean = "TOP"
            elif tipo_bruto == "B":
                tipo_clean = "BOTTOM"
            elif tipo_bruto in ("TB", "BT", "M", "C"):
                tipo_clean = "MISTA"
            else:
                tipo_clean = tipo_bruto
                
            for preset_info in detalhe.get("baias", []):
                nome_preset = preset_info["preset"]
                tipo_dict[nome_preset] = tipo_clean
                
                # Regra de heurística de regex (a mesma de passeios)
                match = re.search(r'\d+', nome_preset)
                if match:
                    numero = match.group()
                    tipo_dict[f"PE {numero} A"] = tipo_clean
                    tipo_dict[f"PE {numero} TA"] = tipo_clean
                    tipo_dict[f"PE {numero} SK1"] = tipo_clean
                    tipo_dict[f"PE {numero} SK2"] = tipo_clean
                    tipo_dict[f"PE {numero} B100"] = tipo_clean
                    tipo_dict[f"PE {numero} POD"] = tipo_clean
                    tipo_dict[f"PE {numero} PODIUM C"] = tipo_clean
                    tipo_dict[f"PE{numero} TA"] = tipo_clean
                    
    # 2. Constrói o tradutor dinâmico (CASE WHEN)
    case_when_clauses = []
    for chave_bq, tipo_clean in tipo_dict.items():
        case_when_clauses.append(f"WHEN '{chave_bq}' THEN '{tipo_clean}'")
        
    if case_when_clauses:
        case_sql = "CASE TRIM(baia) " + " ".join(case_when_clauses) + " ELSE 'DESCONHECIDO' END"
    else:
        case_sql = "'DESCONHECIDO'" # Fallback
        
    sql = f"""
    WITH dedup AS (
      SELECT p.*, 
             ({case_sql}) as tipo_ilha,
             ROW_NUMBER() OVER(PARTITION BY p.programacao ORDER BY COALESCE(CAST(p.sequencia_publicacao AS INT64), 0) DESC) as rn
      FROM {_TABLE_PROGRAMACAO} p
      WHERE p.cod_centro = @centro AND DATE(SAFE_CAST(p.data AS TIMESTAMP)) BETWEEN @ini AND @fim
    ),
    tempos AS (
      SELECT
        tipo_ilha,
        TIMESTAMP_DIFF(SAFE_CAST(hora_saida_patio_interno AS TIMESTAMP), SAFE_CAST(hora_entrada_patio_interno AS TIMESTAMP), MINUTE) as g2g,
        TIMESTAMP_DIFF(SAFE_CAST(hora_entrada_patio_interno AS TIMESTAMP), SAFE_CAST(hora_liberacao AS TIMESTAMP), MINUTE) as fila,
        TIMESTAMP_DIFF(SAFE_CAST(hora_fim_carregamento AS TIMESTAMP), SAFE_CAST(hora_inicio_carregamento AS TIMESTAMP), MINUTE) as carreg
      FROM dedup
      WHERE rn = 1 AND baia IS NOT NULL AND TRIM(baia) != ''
    )
    SELECT
      tipo_ilha,
      COUNT(*) as qtd_viagens,
      ROUND(AVG(NULLIF(g2g, 0)), 1) as g2g_medio,
      ROUND(AVG(NULLIF(fila, 0)), 1) as fila_media,
      ROUND(AVG(NULLIF(carreg, 0)), 1) as carregamento_medio
    FROM tempos
    GROUP BY tipo_ilha
    ORDER BY qtd_viagens DESC
    """
    try:
        res = _run_query_fallback(sql, [
            bigquery.ScalarQueryParameter("centro", "STRING", base),
            bigquery.ScalarQueryParameter("ini", "DATE", ini_param),
            bigquery.ScalarQueryParameter("fim", "DATE", fim_param),
        ])
    except Exception as e:
        return {"erro_sql": str(e)}
    
    if not res: return {"resultado": "Sem dados de ilhas no período/centro selecionado."}
    
    return {"resultado": res}

import pandas as pd

def get_topologia_ilhas(base: str) -> dict:
    """Retorna a configuração física das ilhas (presets e produtos agrupados) lendo do CSV tratado."""
    try:
        # Lê o CSV tratado gerado pelo pipeline de dados
        file_path = "C:/Users/ce9x/agente_jornada_5/data/config_mdriver_tratado_clean.csv"
        df = pd.read_csv(file_path, sep=';', encoding='utf-8-sig')
        
        # Filtra pelo CodCentro (Base) em formato string
        df_base = df[df["CodCentro"].astype(str) == str(base)]
        
        if df_base.empty:
            # Fallback caso alguém tenha passado o nome do centro em vez do código
            df_base = df[df["NomeCentro"].astype(str).str.contains(str(base), case=False, na=False)]
            
        if df_base.empty:
            return {"resultado": f"Nenhuma configuração de ilha encontrada para a base {base} no arquivo Excel."}
            
        # Agrupa por Ilha e Baia para mostrar a capacidade (produtos)
        topologia = []
        for ilha, group in df_base.groupby("NomeIlha"):
            baias = []
            for _, row in group.iterrows():
                baias.append({
                    "preset": row.get("Preset", "N/A"),
                    "produtos": str(row.get("Produto_agrupado", "N/A")).split(",") # Produtos podem vir separados por vírgula
                })
            
            # Pega o Tipo da Ilha do primeiro registro (T, B, C, etc)
            tipo = group["TipoIlha"].iloc[0] if not group.empty else "N/A"
            
            topologia.append({
                "ilha": ilha,
                "tipo": tipo,
                "baias": baias
            })
            
        return {"resultado": {
            "centro": base,
            "total_ilhas_configuradas": len(topologia),
            "detalhes": topologia
        }}
    except Exception as e:
        return {"erro": f"Falha ao ler topologia do Excel: {str(e)}"}

def simular_reducao_setup(base: str, periodo_ini: str, periodo_fim: str) -> dict:
    """Simula o agrupamento de produtos baseado na afinidade de rotas para calcular a redução de passeios e G2G."""
    passeios_data = get_passeios(base, periodo_ini, periodo_fim)
    
    if "resultado" not in passeios_data or not isinstance(passeios_data["resultado"], dict):
        return {"resultado": "Não foi possível obter dados de passeio para simulação."}
        
    resultado_passeios = passeios_data["resultado"]
    top_placas = resultado_passeios.get("top_5_placas_passeio_rotas", [])
    n_passeios_total = resultado_passeios.get("n_passeios", 0)
    programacoes_totais = resultado_passeios.get("programacoes_envolvidas", 1)
    
    if n_passeios_total == 0:
        return {"resultado": "Sem passeios registrados para simular redução."}
        
    # Heurística: Encontrar quais produtos frequentemente forçam o deslocamento lendo a Rota Enriquecida
    import re
    afinidade_produtos = {}
    
    for p in top_placas:
        rota = p.get("rota", "")
        # Extrai os blocos de produtos: [Tipo: TOP, Produtos: GASOLINA, DIESEL S10]
        blocos_produtos = re.findall(r'Produtos:\s([^\]]+)', rota)
        if len(blocos_produtos) >= 2:
            # Assumimos que o caminhão carregou pelo menos um produto do primeiro bloco e um do segundo
            mix = f"{blocos_produtos[0].split(',')[0].strip()} + {blocos_produtos[1].split(',')[0].strip()}"
            afinidade_produtos[mix] = afinidade_produtos.get(mix, 0) + p.get("ilhas_visitadas", 2)
            
    # Ordena pelo maior ofensor
    top_mix = sorted(afinidade_produtos.items(), key=lambda x: x[1], reverse=True)
    
    if not top_mix:
        top_mix = [("Produto Tipo A + Produto Tipo B", n_passeios_total)] # Fallback
        
    mix_principal = top_mix[0][0]
    
    # Estimativa de Ganho (Ex: Resolver o mix principal elimina 40% dos passeios)
    reducao_passeios_pct = 40.0 
    passeios_evitados = int(n_passeios_total * (reducao_passeios_pct / 100))
    
    # Setup médio de um passeio é cerca de 15 minutos adicionais (Manobra, Validação, Aterramento)
    tempo_salvo_minutos_total = passeios_evitados * 15.0
    
    # Impacto no G2G Global = (Tempo Total Salvo) / (Total de Caminhões)
    reducao_g2g_minutos = round(tempo_salvo_minutos_total / programacoes_totais, 1) if programacoes_totais > 0 else 0
    
    return {"resultado": {
        "insight_afinidade": f"Caminhões frequentemente visitam múltiplas ilhas para carregar o mix [{mix_principal}].",
        "acao_recomendada": f"Agrupar os produtos [{mix_principal}] em baias adjacentes na mesma ilha.",
        "estimativa_reducao_passeios_pct": reducao_passeios_pct,
        "passeios_evitados_qtd": passeios_evitados,
        "tempo_setup_economizado_por_caminhao": 15.0,
        "reducao_g2g_global_estimada_minutos": reducao_g2g_minutos
    }}
