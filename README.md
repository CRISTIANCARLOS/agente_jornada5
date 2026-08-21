# Agente G2G - Microjornada 5 (Vibra)

Este repositório contém o código-fonte e a documentação do Sistema Multiagente de Otimização do Tempo de G2G (Gate-to-Gate), desenvolvido utilizando o Google ADK (Agent Development Kit) e o Vertex AI Agent Engine.

## Objetivo do Projeto
Fornecer inteligência acionável e determinística para Analistas de Eficiência Operacional e Gestores de Base, através de um orquestrador conversacional. O Agente identifica ofensores, calcula gargalos de infraestrutura (braços top x bottom ociosos) e avalia cenários "What-if" para embasar decisões de CAPEX.

## Estrutura do Repositório

*   **`/microjornada5`**: Pacote principal contendo o código do agente.
    *   `agent.py`: Definição do Agente Orquestrador e subagentes (SA1 a SA5).
    *   `tools.py`: Ferramentas de consulta que integram os dados raw do BigQuery.
    *   `g2g_logic.py`: Lógica canônica Python (ADR-030) para cálculo de G2G, Passeio (duplo encoste) e IPAR.
    *   `prompts.py`: System prompts e instruções contextuais de cada agente, incorporando as regras de negócio de G2G.
*   **`/deployment`**: Scripts e configurações para o deploy na infraestrutura Serverless do Vertex AI.
*   **`/docs`**: Manuais, guias arquiteturais e tutoriais.
    *   `arquitetura.md`: PRD, requisitos, matemática, métricas canônicas e *guardrails* do sistema.
    *   `deploy.md`: Como testar localmente e realizar deploy para produção GCP.
    *   `execucao_terminal.md`: Como rodar o bot diretamente do CLI (Repl e Script via Cloud).
*   **`.env`**: Configuração de variáveis de ambiente.
*   **`requirements.txt`**: Dependências da stack.

## Como começar

1.  **Clone / Acesse o repositório:**
    ```bash
    cd agente_jornada_5
    ```

2.  **Crie seu ambiente virtual:**
    ```bash
    python -m venv .venv
    .\.venv\Scripts\activate
    ```

3.  **Instale os pacotes requeridos:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Autentique seu usuário no Google Cloud SDK:**
    ```bash
    gcloud auth application-default login
    ```

5.  **Teste o agente localmente (UI):**
    ```bash
    adk web
    ```

Para mais detalhes sobre deploy e integração, consulte a pasta `/docs`.

#O número (ID) desta nossa conversa é: 26dc2ba6-052c-4cff-95e3-8454f4285523

Perguntas: Cara preciso o orquestrados chame todos os subagents para me passar uma analise completa G2G, passeio, disponibilidade de │ ilhas produto e capex. 5064 01/01/2025 á 31/12/2025

