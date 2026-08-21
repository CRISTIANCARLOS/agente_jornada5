# Dicionário de Dados e Metodologias do Agente G2G

Este documento serve como referência de todas as métricas geradas pelas ferramentas (Tools) do Agente, descrevendo a origem de cada informação e a metodologia matemática (fórmulas SQL) utilizada para seu cálculo.

## Fonte de Dados Principal
- **Tabela/View:** `vibra-dtan-spoke-eso-dev.rw_mdriver.programacao`
- **Região:** `us-central1`
- **Filtros Base:** `cod_centro` (Base), `data` (entre Data Inicial e Final).
- **Desduplicação Canônica:** Sempre aplicamos particionamento por `programacao` pegando a maior `sequencia_publicacao` (`ROW_NUMBER() OVER(PARTITION BY programacao ORDER BY COALESCE(CAST(sequencia_publicacao AS INT64), 0) DESC) = 1`).

---

## 1. Métricas de Tempo (Gate-to-Gate e Fases)
**Ferramenta:** `get_media_g2g(base, periodo_ini, periodo_fim)`

Esta ferramenta calcula o tempo total em que o caminhão-tanque permaneceu na base e quebra esse tempo nas suas subfases lógicas. A métrica exclui valores atípicos absurdos (menores que 0 ou maiores que 24 horas/1440 minutos).

| Métrica | Como é calculada (SQL Pushdown) | Retorno no JSON |
| :--- | :--- | :--- |
| **G2G (Gate-to-Gate)** | `TIMESTAMP_DIFF(hora_saida_patio_interno, hora_entrada_patio_interno, MINUTE)` | `g2g.media`, `g2g.max` |
| **Tempo de Fila** | `TIMESTAMP_DIFF(hora_entrada_patio_interno, hora_liberacao, MINUTE)` | `fases_min.fila` |
| **Tempo de Setup** | `TIMESTAMP_DIFF(hora_inicio_carregamento, hora_entrada_patio_interno, MINUTE)` | `fases_min.setup` |
| **Tempo de Carregamento** | `TIMESTAMP_DIFF(hora_fim_carregamento, hora_inicio_carregamento, MINUTE)` | `fases_min.carregamento` |
| **Tempo Pós-Carregamento** | `TIMESTAMP_DIFF(hora_saida_patio_interno, hora_fim_carregamento, MINUTE)` | `fases_min.pos_carregamento` |
| **Gap da Meta** | `g2g_media - 39` (onde 39 é a meta fixa em minutos) | `gap_media_vs_meta` |
| **Volume Total** | Contagem bruta (`COUNT`) de programações válidas | `n_programacoes` |

---

## 2. Métricas de Passeio (Duplo Encoste)
**Ferramenta:** `get_passeios(base, periodo_ini, periodo_fim)`

O "passeio" ocorre quando um mesmo caminhão (placa) precisa carregar em mais de uma baia/ilha diferente no mesmo dia para concluir sua programação, aumentando o G2G devido ao tempo de manobra e novo setup.

**Mecanismo Híbrido:** As agregações quantitativas são feitas no BigQuery (SQL Pushdown), enquanto o enriquecimento qualitativo (descobrir o nome físico da Ilha baseada na baia) é feito **localmente no Python**, cruzando a resposta com a topologia do CSV tratado (`data/config_mdriver_tratado_clean.csv`). Isso evita sobrecarga no banco e excesso de tokens.

| Métrica | Como é calculada | Retorno no JSON |
| :--- | :--- | :--- |
| **Placas com Baia** | `COUNT(DISTINCT placa)` | `placas_com_baia` |
| **Quantidade de Passeios** | Agrupamento por placa onde `COUNT(baia) > 1` | `n_passeios` |
| **Taxa de Passeio (%)** | `(n_passeios / placas_com_baia) * 100` | `taxa_passeio_pct` |
| **Ranking Ofensores Enriquecido** | BQ traz Top 10 Baias. Python cruza a Baia com o Dicionário Local e insere a `Ilha` e o `tipo_ilha`. | `ranking_ofensoras_enriquecido` (Array de Objetos) |
| **Top 5 Placas (Rotas)** | BQ traz as piores placas e agrega `STRING_AGG(baia)`. Python formata para `Ilha 1 (Baia A) -> Ilha 2 (Baia B)`. | `top_5_placas_passeio` (Array de Objetos) |

---

## 3. Métricas de Aderência ao IPAR
**Ferramenta:** `get_analise_ipar(base, periodo_ini, periodo_fim)`

Analisa o volume de programações que entram no cálculo do Indicador de Performance de Atendimento Rápido (IPAR) e levanta os principais motivos sistêmicos ou operacionais que excluem um veículo dessa medição.

| Métrica | Como é calculada (SQL Pushdown) | Retorno no JSON |
| :--- | :--- | :--- |
| **Total de Viagens IPAR** | `COUNT(*)` após a desduplicação. | `total` |
| **Viagens Aderentes** | `COUNTIF(entra_no_ipar = '1')` | `entram` |
| **Aderência (%)** | `(entram / total) * 100` | `aderencia_pct` |
| **Limite Excedido** | `COUNTIF(limite_ipar_excedido = 'True')` | `limite_excedido` |
| **Top 5 Motivos de Exclusão** | `GROUP BY motivo_ipar` filtrando os que não entraram (`entra_no_ipar != '1'`), ranqueados por contagem descendente `ORDER BY qtd DESC LIMIT 5`. | `motivos_exclusao_top5` |

---

## 4. Orquestração e Outras Ferramentas
As ferramentas adicionais servem para simular ou envelopar as chamadas acima.

*   `painel_operacional(base, ini, fim)`: Dispara as funções de Tempo G2G, Passeio e IPAR simultaneamente e devolve um JSON único consolidado (ideal para o SA-5 Validador).
*   `get_simultaneidade`: (Atualmente implementada como um *stub* estático retornando `{tipo: BOTTOM, ocupacao_pct: 85.5}`) Avaliará no futuro a concorrência de braços.
*   `simular_preset`: (Atualmente um *stub* estático retornando `{ganho_min_ct: 12.5, reducao_passeio_pct: 18.2}`) Motor What-If que usará lógicas de otimização de pesquisa operacional para quantificar ganhos se os produtos mudassem de baia.

---

## 5. Performance por Tipo de Ilha (TOP vs BOTTOM)
**Ferramenta:** `get_simultaneidade(base, periodo_ini, periodo_fim)`

Avalia o impacto na fila e no tempo de carregamento de acordo com o design físico e o tipo de braço da ilha. Ilhas TOP possuem tempo de operação maior, enquanto BOTTOM carregam mais rápido mas sofrem com alta concorrência e ocupação (filas maiores).

**Tabelas utilizadas:**
*   Fato: `vibra-dtan-spoke-eso-dev.rw_mdriver.programacao` (p)
*   Dimensão: `vibra-dtan-spoke-eso-dev.rf_mdriver.dim_preset_ilha` (dim)
*   **JOIN:** `LEFT JOIN ... ON p.cod_centro = dim.cod_centro AND TRIM(p.baia) = TRIM(dim.baia)`

| Métrica | Como é calculada (SQL Pushdown) | Retorno no JSON |
| :--- | :--- | :--- |
| **Tipo de Ilha** | Trazido de `dim.tipo_ilha` (ex: `T`, `B`, `TB`). Fallback para `DESCONHECIDO` caso nulo. | `tipo_ilha` |
| **G2G Médio** | `AVG(g2g)` da query agrupado por `tipo_ilha` | `g2g_medio` |
| **Fila Média** | `AVG(hora_entrada_patio_interno - hora_liberacao)` agrupado por tipo | `fila_media` |
| **Carregamento Médio** | `AVG(hora_fim_carregamento - hora_inicio_carregamento)` agrupado por tipo | `carregamento_medio` |

---

## 6. Topologia e Oferta de Produtos (Mapeamento CSV)
**Ferramenta:** `get_topologia_ilhas(base)`

Retorna o layout físico da base e a alocação de produtos/presets por braço. Essencial para cruzar com a ferramenta de Passeio e descobrir por que os caminhões precisam dar voltas no pátio (falta de produto na mesma baia).

**Fonte de Dados:**
*   Arquivo local: `data/config_mdriver_tratado_clean.csv` (gerado pelo pipeline de limpeza)
*   Filtro principal: `NomeCentro == @base`

| Métrica/Dimensão | Coluna do CSV Tratado | Retorno no JSON |
| :--- | :--- | :--- |
| **Nome da Ilha** | `NomeIlha` | `ilha` |
| **Tipo da Ilha** | `TipoIlha` (T, B, C) | `tipo` |
| **Preset/Baia** | `Preset` | `preset` |
| **Produtos Oferecidos** | `Produto_agrupado` | `produtos` (Array) |
