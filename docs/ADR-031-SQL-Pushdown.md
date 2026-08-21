# ADR-031: Pushdown de Agregação no BigQuery para Tools do Agente G2G

## Status
Aceito

## Contexto
O Agente G2G (Microjornada 5) precisa consultar e processar grandes volumes de dados da tabela `rw_mdriver.programacao`. A abordagem anterior consistia em fazer uma query do tipo `SELECT *` extraindo todos os registros filtrados para a memória local do contêiner/script e, então, usar lógicas em Python (no arquivo `g2g_logic.py`) para iterar nas linhas, desduplicar, calcular durações de fases e contabilizar métricas.

**Problemas identificados:**
1. **OOM (Out Of Memory):** Em dias de alto movimento ou grandes janelas de pesquisa, trazer centenas de milhares de linhas causaria estouro na memória RAM do host.
2. **Context Window Limits:** Caso o sistema tentasse colocar qualquer fração desses dados brutos no prompt do LLM ou em logs de depuração, ocorreria erro de *Token Limit Exceeded*.
3. **Latência Elevada:** O processo de desserializar JSONs maciços e processar loops aninhados em Python é ineficiente quando comparado às engines MPP (Massively Parallel Processing) de bancos de dados.

## Decisão
Implementamos a **Opção 1: Pushdown de Agregação no BigQuery**.
Toda a lógica matemática pesada que estava em `g2g_logic.py` foi migrada para queries SQL nativas dentro das ferramentas (`microjornada5/tools.py`). 

As `tools` agora solicitam ao BigQuery que realize:
1. **Desduplicação (Dedupe):** Através do uso de `ROW_NUMBER() OVER(PARTITION BY programacao ORDER BY sequencia_publicacao DESC)`.
2. **Cálculos de Tempos e G2G:** Substituímos o cálculo de Python por `TIMESTAMP_DIFF(hora_saida, hora_entrada, MINUTE)`.
3. **Agregação:** Realizamos os `AVG()`, `COUNTIF()` e `MAX()` em nível de banco de dados.

## Consequências
* **Positivas:** 
  * O Agente G2G agora recebe apenas um JSON minúsculo contendo as métricas sumarizadas.
  * Extrema escalabilidade: Mesmo se buscarmos dados de um ano inteiro, o Agente não estourará memória nem o contexto do LLM.
  * O BigQuery processará a query de forma otimizada.
* **Negativas:** 
  * A lógica em `g2g_logic.py` torna-se obsoleta para as tools do Agente, sendo mantida apenas por razões de compatibilidade com sistemas legados caso existam.
  * Modificar a lógica das métricas agora exige conhecimento em SQL (Standard SQL do BigQuery) e não mais apenas Python.

## Implementação
Arquivo modificado: `microjornada5/tools.py`.
Foi retirado o `SELECT *` e inseridas *Common Table Expressions* (CTEs) do BigQuery.
O retorno para o LLM foi padronizado em um `dict` com a chave `resultado`.
