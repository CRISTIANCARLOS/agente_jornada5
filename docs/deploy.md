# Como criar e fazer deploy do Agente da Microjornada 5 direto no GCP

**Stack recomendada:** **ADK (Agent Development Kit)** + **Vertex AI Agent Engine** + **BigQuery**.

## 1. Estrutura de pastas (padrão ADK)
```
agente_jornada_5/
├── microjornada5/
│   ├── __init__.py
│   ├── agent.py          # root_agent (orquestrador) + subagentes SA-1..SA-4
│   ├── prompts.py        # system prompts
│   └── tools.py          # functions BigQuery
├── deployment/
│   └── deploy.py         # script de deploy no Agent Engine
├── docs/                 # Documentação do sistema
├── requirements.txt
└── .env                  # variáveis de ambiente
```

## 2. Testar localmente

Instale as dependências:
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Execute a UI local para debugar as chamadas e roteamentos:
```bash
adk web
```

## 3. Deploy no Vertex AI Agent Engine

O deploy empacota o código, sobe pro GCS de staging e cria um recurso **ReasoningEngine** com sessão e escala gerenciadas.

```bash
python deployment/deploy.py
```

Ou usando o CLI do ADK:
```bash
adk deploy agent_engine \
  --project vibra-operacoes \
  --region us-east1 \
  --staging_bucket gs://vibra-agent-staging \
  microjornada5
```
