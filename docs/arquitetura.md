# Arquitetura do Sistema de Agentes: Otimização de Passeio e G2G (Vibra)

## 1. Visão Geral
Sistema baseado em Agentic AI (Gemini Enterprise / Vertex AI) desenhado para otimizar operações em bases de carregamento, reduzindo manobras de Caminhões Tanque (taxa de "passeio") e o tempo total Gate-to-Gate (G2G). O sistema servirá de apoio analítico e ferramenta de simulação (What-If) para justificar investimentos (Capex Data Driven).

## 2. Perfis de Usuário (Roles)
- **Analista de Eficiência Operacional (Foco da Fase 1):** Busca detalhamento profundo, números, ranking de ofensores, simulações em séries de dados. Interage de forma conversacional e com tabelas.
- **Gestor da Base (Fase 2):** Busca uma síntese visual ("bater o olho"), focada em ganhos de G2G e impacto em CAPEX/payback. Respostas curtas via cards.

## 3. Diretrizes de Dados e Arquitetura
- **Grão de Análise:** A leitura de dados ocorre obrigatoriamente a nível de **compartimento** (não por programação geral), garantindo aderência exata ao *preset* e mix habilitado da ilha.
- **Restrição de Tokens:** É proibido injetar histórico anual bruto no *prompt* do LLM. O agente lida apenas com agregações (JSON) retornadas pelas APIs.
- **Determinismo:** Taxas de passeio e tempos de *setup* devem ser aferidos usando a topologia/mediologia da época exata do carregamento, não a régua atual.
- **Guardrails:** 
  - Proibido ler tabelas `raw`.
  - Proibido gerar SQL dinâmico não homologado (livre).
  - Obrigatório referenciar o período e a base nas respostas.

## 4. Integrações Técnicas (Tools / Function Calling)
Os agentes utilizarão funções Python implementadas no GCP que acessam visões parametrizadas no BigQuery (`v_refined_carregamento_compartimento` cruzada com `dim_topologia_ilha` e `v_g2g_*`).

- **Parâmetros Base da API:** `base`, `periodo_ini`, `periodo_fim`
- **Parâmetros Opcionais:** `produto`, `ilha`, `cenario_preset`
- **Contrato:** A função retorna um JSON estruturado com a métrica principal e sua decomposição. O LLM atua apenas como tradutor desse dado para o usuário.

## 5. Estrutura de Agentes

### Agente Orquestrador
- **Responsabilidade:** Atuar como roteador (identifica o *role*, entende a intenção e delega para os Subagentes SA-1 a SA-4).
- **Regra de Ouro:** Não efetua cálculos matemáticos por conta própria e não infere dados não presentes na view. Se faltar informação, declara limitação de escopo.

### SA-1 — Taxa de Passeio & Setup
- **Objetivo:** Medir a taxa de CTs que carregam em >1 ilha e estimar o custo temporal (setup).
- **Cálculo Base:** 
  - `taxa_passeio` = (programações em >1 ilha) / (total de programações)
  - `custo_setup_extra` = (`t_setup_multi_ilha` - `t_setup_ilha_unica`) × (CTs em passeio)
- **Saída:** % de passeio, minutos extras, impacto no G2G.

### SA-2 — Simultaneidade TOP × BOTTOM
- **Objetivo:** Avaliar concorrência e ociosidade de braços para identificar gargalos de infraestrutura (ex: baia *bottom* cheia, baias *top* vazias).
- **Cálculo Base:** Ocupação simultânea, formação de filas, número de manobras e ociosidade de braços.
- **Saída:** Evidência de gargalo estrutural e oportunidades de conversão/dedicação.

### SA-3 — Ofensores por Ilha e por Produto
- **Objetivo:** Ranquear e identificar os causadores do passeio.
- **Cálculo Base:** Decomposição do passeio cruzando a matriz de `dim_topologia_ilha` (mix) contra a demanda efetiva carregada.
- **Saída:** Top ofensores e volume de Caminhões Tanque impactados.

### SA-4 — Simulação de Presets & Reconfiguração
- **Objetivo:** Motor "What-If" para simular remanejamento de produtos e conversão de baias, quantificando o ganho financeiro e operacional.
- **Dinâmica:** Reaplica o motor de roteamento/passeio sobre um cenário hipotético (`cenario_preset`) e compara com o *baseline*.
- **Saída:** Ganho estimado (minutos ganhos, % G2G) como subsídio para o **Capex Data Driven**.
