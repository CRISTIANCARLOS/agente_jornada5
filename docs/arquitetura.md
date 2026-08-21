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
Os agentes utilizarão funções Python implementadas no GCP que acessam visões parametrizadas no BigQuery (`g2g_kb.v_g2g_carregamento` e outras tabelas acessórias).

- **Parâmetros Base da API:** `base` (cod_centro), `periodo_ini`, `periodo_fim`
- **Parâmetros Opcionais:** `produto`, `ilha`, `cenario_preset`
- **Contrato:** A função retorna um JSON estruturado com a métrica principal e sua decomposição. O LLM atua apenas como tradutor desse dado para o usuário.

## 5. Estrutura de Agentes

```mermaid
flowchart TD
    User((Usuário)) -->|Pergunta| Orquestrador[Agente Orquestrador]
    
    subgraph Subagentes [Agentes Especializados]
        SA1[SA-1: Tempo G2G]
        SA2[SA-2: Simultaneidade]
        SA3[SA-3: Ofensores]
        SA4[SA-4: Simulação]
        SA5[SA-5: Validador]
    end

    Orquestrador -->|Roteia intenção| SA1
    Orquestrador -->|Roteia intenção| SA2
    Orquestrador -->|Roteia intenção| SA3
    Orquestrador -->|Roteia intenção| SA4
    Orquestrador -->|Valida métricas| SA5
    
    subgraph Infraestrutura de Dados [Cálculo Fora do LLM]
        Tools[tools.py]
        EngineSQL{{Engine SQL / CTEs\nTIMESTAMP_DIFF, AVG, SUM}}
        BQ[(BigQuery\nrw_mdriver)]
        
        Tools -->|Query parametrizada| EngineSQL
        EngineSQL -->|Lê e Agrega| BQ
        BQ -->|Resultados Agregados| EngineSQL
    end
    
    SA1 <-->|Consulta via| Tools
    SA2 <-->|Consulta via| Tools
    SA3 <-->|Consulta via| Tools
    SA4 <-->|Consulta via| Tools
    SA5 <-->|Consulta via| Tools
    
    EngineSQL -.->|JSON Enxuto\n(Métricas Mastigadas)| SA1
    EngineSQL -.->|JSON Enxuto\n(Métricas Mastigadas)| SA2
    EngineSQL -.->|JSON Enxuto\n(Métricas Mastigadas)| SA3
    EngineSQL -.->|JSON Enxuto\n(Métricas Mastigadas)| SA4
    EngineSQL -.->|JSON Enxuto\n(Métricas Mastigadas)| SA5

    SA1 -.->|Resposta estruturada| Orquestrador
    SA2 -.->|Resposta estruturada| Orquestrador
    SA3 -.->|Resposta estruturada| Orquestrador
    SA4 -.->|Resposta estruturada| Orquestrador
    SA5 -.->|Validação Final| Orquestrador
    
    Orquestrador -.->|Resposta final| User

    %% Estilização de Cores
    classDef userNode fill:#e1bee7,stroke:#333,stroke-width:2px,color:#000;
    classDef orquestradorNode fill:#fff9c4,stroke:#333,stroke-width:2px,color:#000;
    classDef subAgenteNode fill:#bbdefb,stroke:#333,stroke-width:1px,color:#000;
    classDef dbNode fill:#c8e6c9,stroke:#333,stroke-width:2px,color:#000;
    classDef infraNode fill:#ffcc80,stroke:#333,stroke-width:1px,color:#000;

    class User userNode;
    class Orquestrador orquestradorNode;
    class SA1,SA2,SA3,SA4,SA5 subAgenteNode;
    class BQ dbNode;
    class Tools,EngineSQL infraNode;
```

### Agente Orquestrador
- **Responsabilidade:** Atuar como roteador (identifica o *role*, entende a intenção e delega para os Subagentes SA-1 a SA-4).
- **Regra de Ouro:** Não efetua cálculos matemáticos por conta própria e não infere dados não presentes na view. Se faltar informação, declara limitação de escopo.

### SA-1 — Tempo de G2G
- **Objetivo:** Calcular a média e estatísticas do tempo de G2G de um centro.
- **Cálculo Base:** 
  - `media_g2g_min` = Média do tempo Gate-to-Gate (em minutos) para o centro/período.
  - Análise do volume de programações.
- **Saída:** Média de tempo G2G, máximo de tempo G2G e total de programações.

### SA-2 — Simultaneidade TOP × BOTTOM
- **Objetivo:** Avaliar concorrência e ociosidade de braços para identificar gargalos de infraestrutura (ex: baia *bottom* cheia, baias *top* vazias).
- **Cálculo Base:** Ocupação simultânea, formação de filas, número de manobras e ociosidade de braços.
- **Saída:** Evidência de gargalo estrutural e oportunidades de conversão/dedicação.

### SA-3 — Ofensores de Passeio por Ilha e por Produto
- **Objetivo:** Ranquear e identificar os causadores do passeio (duplo encoste).
- **Cálculo Base:** Identificação de placas que carregaram em mais de uma baia no mesmo dia.
- **Saída:** Top ofensores e volume de Caminhões Tanque impactados pela taxa de passeio.

### SA-4 — Simulação de Presets & Reconfiguração
- **Objetivo:** Motor "What-If" para simular remanejamento de produtos e conversão de baias, quantificando o ganho financeiro e operacional.
- **Dinâmica:** Reaplica o motor de roteamento/passeio sobre um cenário hipotético (`cenario_preset`) e compara com o *baseline*. Também possui visão de aderência ao IPAR.
- **Saída:** Ganho estimado (minutos ganhos, % G2G) como subsídio para o **Capex Data Driven**.

### SA-5 — Validador de Resultados
- **Objetivo:** Auditar dados antes da entrega final ao usuário.
- **Responsabilidade:** Checar 18 itens obrigatórios, incluindo outliers, anticonfusão e as regras canônicas de G2G.

## 6. Regras Canônicas do Indicador G2G (ADR-030)
As regras do indicador G2G (Microjornada 5 · v3.2) são pilares fundamentais do sistema:
- **D1 (Cálculo Canônico):** A fonte única de dados brutos é `rw_mdriver.programacao`. O G2G é calculado exclusivamente como a diferença em minutos entre `hora_saida_patio_interno` e `hora_entrada_patio_interno`.
- **D3 (Claros):** O foco da análise recai em cargas claras.
- **D5 (Outliers):** Tratamento de valores discrepantes feito em Python limitando G2G em 1 a 1440 minutos.
- **D6 (Métrica Oficial):** O número oficial do G2G é sempre derivado da média/mediana exata do banco/código.
- **RB-ANTICONF:** O conceito de Gate-to-Gate (G2G) não se confunde com *g2g_green_to_green*.
- **RB-NAOLLM:** O LLM NUNCA calcula médias, medianas, ou somas de desempenho matemático por conta própria. Toda lógica matemática reside no arquivo `g2g_logic.py`.
