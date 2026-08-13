# Tutorial de Execução do Agente via Terminal

Este guia detalha como você pode interagir com o agente da Microjornada 5 (Otimização G2G) diretamente pelo seu terminal, sem depender de uma interface gráfica web.

## Pré-requisitos
Antes de executar qualquer comando, certifique-se de que seu ambiente virtual Python está ativado na raiz do projeto:

```powershell
cd C:\Users\ce9x\agente_jornada_5
.\.venv\Scripts\activate
```

---

## 1. Executando Localmente (Interface ADK no Terminal)

A forma mais rápida de debugar as *tools* (SQL do BigQuery) e ver os LLMs em ação na sua máquina é usar a ferramenta de CLI do Google ADK.

Para iniciar uma sessão interativa pelo terminal (modo "repl"):
```bash
adk run microjornada5
```

O terminal exibirá um prompt `User:`. Você pode começar a conversar diretamente:
> **User:** "Qual a taxa de passeio da BAERI em julho de 2026?"

Você verá no log o Orquestrador roteando para o `SA1_passeio_setup` e acionando as funções do BigQuery antes de devolver a resposta.

---

## 2. Consumindo o Agente já em Produção (Agent Engine) via Python

Se você já executou o `deployment/deploy.py` e o agente está vivo no GCP, você não precisará rodá-lo na sua máquina local; você poderá simplesmente fazer perguntas diretamente à nuvem usando um script Python no terminal.

Crie um arquivo chamado `ask_agent.py` e cole o código abaixo (lembre-se de trocar o `RESOURCE_ID` pelo nome impresso após o deploy):

```python
import vertexai
from vertexai import agent_engines

# Inicializa o projeto
vertexai.init(project="vibra-dtan-spoke-eso-dev", location="us-east1")

# Carrega o agente remoto (troque pelo SEU RESOURCE_ID real retornado no deploy)
remote = agent_engines.get("projects/123456789/locations/us-east1/reasoningEngines/SEU_ID_AQUI")

# Cria uma sessão (memoriza histórico do chat)
session = remote.create_session(user_id="terminal_user")
print("Sessão criada. Digite sua pergunta (ou 'sair' para encerrar):")

while True:
    pergunta = input("\nVocê: ")
    if pergunta.lower() in ["sair", "exit"]:
        break
        
    print("\nAgente (pensando...): ")
    # Envia a requisição em modo streaming para a nuvem
    for chunk in remote.stream_query(
            user_id="terminal_user",
            session_id=session["id"],
            message=pergunta):
        print(chunk, end="", flush=True)
    print("\n")
```

Para usá-lo via terminal, basta rodar:
```bash
python ask_agent.py
```

---

## Resumo de Comandos Úteis (CLI)

| Comando | O que faz |
|---|---|
| `adk web` | Sobe uma UI web no navegador para testes locais. |
| `adk run microjornada5` | Roda o chat do agente direto no próprio terminal (local). |
| `python deployment/deploy.py` | Empacota e sobe o agente local para o ambiente Serverless da Vertex AI. |
| `python ask_agent.py` | Envia perguntas via API para o agente que já está na nuvem. |
