# Tabelas de Dados e Funcionamento do Agente G2G

Este documento explica as tabelas (visões) do BigQuery utilizadas pelo agente para buscar informações determinísticas e como as consultas (`tools`) são estruturadas.

## 1. Visões do BigQuery

O Agente atua sobre visões preparadas (`views`), garantindo que o LLM não possua acesso livre a bases brutas ou não padronizadas.

### `g2g_kb.v_g2g_carregamento`
- **O que é:** A tabela principal contendo as medições e registros de Gate-to-Gate.
- **Por que usamos:** Fornece métricas prontas e diretas de tempos operacionais sem a necessidade de reconstruir os tempos de setup e passeio de forma isolada.
- **Campos Principais:**
  - `cod_centro`: Código identificador da base/centro.
  - `data` e `mes`: Referências temporais.
  - `programacao`: Identificador único do carregamento.
  - `g2g_min`: Tempo total do ciclo Gate-to-Gate (em minutos).
  - Outras flags operacionais (`is_claro`, `entra_no_ipar`, `f_elegivel`).

### `dim_topologia_ilha`
- **O que é:** Tabela de dimensão que mapeia a configuração física de cada baia/ilha.
- **Função:** Fornecer ao Agente o mapeamento (presets) dos produtos habilitados, braços disponíveis, distinguindo braços BOTTOM (carregamento inferior) de TOP (carregamento superior).

## 2. Funcionamento das Tools (Funções)

O módulo `microjornada5/tools.py` expõe métodos que o LLM (Agente) possui permissão para chamar. A lógica, agrupamento e matemáticas já estão consolidadas no SQL das ferramentas.

### Fluxo de Funcionamento:
1. **Intenção:** O usuário faz uma pergunta sobre o "tempo médio de G2G".
2. **Delegação:** O Orquestrador envia a tarefa ao `SA1_tempo_g2g`.
3. **Extração:** O Agente `SA1` extrai os parâmetros `base` (cod_centro), `periodo_ini`, e `periodo_fim` da conversa e invoca a ferramenta correspondente.
4. **Consulta Determinística:** A ferramenta (ex: `get_media_g2g`) executa uma query segura (usando *Query Parameters* `@base`, `@ini`, `@fim` para prevenir *SQL Injection*).
5. **Retorno:** O SQL retorna os agregados prontos (ex: total de programações e média G2G).
6. **Resposta:** O LLM recebe o JSON da ferramenta e o traduz para uma linguagem natural e amigável ao usuário.

### Exemplo do Cálculo de G2G (SQL em `get_media_g2g`):
A média do tempo é calculada agrupando as métricas da base solicitada:
```sql
SELECT
    COUNT(DISTINCT programacao) total_programacoes,
    ROUND(AVG(g2g_min), 2) media_g2g_min,
    MAX(g2g_min) max_g2g_min
FROM `vibra-dtan-spoke-eso-dev.g2g_kb.v_g2g_carregamento`
WHERE cod_centro=@base AND data BETWEEN @ini AND @fim
```
*A consulta avalia diretamente o tempo total apurado (g2g_min) e retorna sua média global para aquele período e local.*

## 3. Segurança e Guardrails
- As métricas são processadas unicamente pela engine do BigQuery através das queries parametrizadas. 
- O Agente (LLM) está instruído via *prompt* para atuar como tradutor; ele é proibido de deduzir ou calcular números por conta própria caso eles não retornem da ferramenta.
