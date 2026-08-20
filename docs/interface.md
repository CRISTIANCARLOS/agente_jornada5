# Interface de Usuário (UI) do Agente G2G

Este documento descreve como a interface de usuário do Agente G2G funciona, como foi construída e como realizar sua implantação (deploy) no Google Cloud Platform.

## 1. Arquitetura da Interface

A interface do agente foi desenvolvida utilizando **Streamlit**, um framework Python voltado para a criação rápida de aplicações web para dados e IA.

### Características Principais:
- **Chat Interativo:** A aplicação provê uma interface de conversação no formato de chat, semelhante às interfaces populares de LLMs.
- **Integração Nativa:** Conecta-se diretamente ao serviço *Reasoning Engine* da Vertex AI usando a biblioteca `google-cloud-aiplatform`.
- **Manutenção de Sessão:** A aplicação gerencia o estado da sessão (`st.session_state`), mantendo o histórico de mensagens ativo durante a navegação do usuário e enviando o `session_id` para o Vertex AI para preservação do contexto pelo agente.
- **Respostas em Streaming:** Utiliza o método `stream_query` para exibir as respostas em tempo real, melhorando a experiência do usuário ("efeito de digitação").

## 2. Estrutura de Arquivos da UI

A aplicação está contida no diretório `/ui_app` e é composta pelos seguintes arquivos:

- `app.py`: O código principal do Streamlit que implementa o chat e a conexão com o GCP.
- `requirements.txt`: Lista de dependências (Streamlit, Vertex AI SDK, etc).
- `Dockerfile`: Configuração de imagem de contêiner para empacotamento da aplicação.

## 3. Como Executar Localmente

Para rodar a interface em sua máquina local para testes e desenvolvimento:

```bash
cd ui_app
# Ative seu ambiente virtual (se aplicável) e instale as dependências
pip install -r requirements.txt
# Inicie o servidor Streamlit
streamlit run app.py
```
A aplicação abrirá no seu navegador, normalmente em `http://localhost:8501`.

## 4. Implantação no Cloud Run (GCP)

A forma recomendada de servir esta aplicação publicamente no Google Cloud é utilizando o **Cloud Run**. O Cloud Run cria e escala o contêiner Docker a partir do código-fonte automaticamente.

Para realizar a implantação, execute o comando abaixo na pasta `ui_app`:

```bash
gcloud run deploy agente-ui \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

Ao término, o comando fornecerá a URL pública de acesso à aplicação.

## 5. Permissões de Segurança
Para que a interface funcione no Cloud Run acessando o Vertex AI:
- A conta de serviço padrão (Service Account) associada ao Cloud Run deve possuir as permissões necessárias para acessar o serviço *Vertex AI Reasoning Engine* (ex: papel `Vertex AI User`).
