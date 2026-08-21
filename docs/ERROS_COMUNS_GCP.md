# Guia de Resolução de Erros - Google Cloud / Vertex AI

Este documento lista os erros mais comuns enfrentados ao desenvolver, fazer deploy e consultar agentes no Google Cloud (Vertex AI) e como resolvê-los.

---

## 1. Erro: 403 PERMISSION_DENIED

**Mensagem típica:**
`403 PERMISSION_DENIED. {'error': {'code': 403, 'message': "Permission 'aiplatform.endpoints.predict' denied on resource...`

**Causa:**
O seu usuário logado no terminal (ou a conta de serviço) não tem a permissão necessária para utilizar os modelos do Vertex AI. É necessário ter a *role* (papel) de **Vertex AI User** (`roles/aiplatform.user`).

**Como resolver:**
*   **Se você for Administrador do Projeto (Owner/IAM Admin):**
    Abra o terminal e rode o comando abaixo, substituindo pelo seu e-mail:
    ```bash
    gcloud projects add-iam-policy-binding vibra-dtan-spoke-eso-dev \
        --member="user:SEU_EMAIL@vibraenergia.com.br" \
        --role="roles/aiplatform.user"
    ```
*   **Se você tiver apenas perfil Editor/Viewer:**
    Você não tem permissão para rodar o comando acima. Peça para a equipe de Infraestrutura/Cloud (Administradores do GCP) rodarem o comando para você ou adicionarem a permissão de "Vertex AI User" ao seu e-mail no console do Google Cloud.

---

## 2. Erro: 404 NOT_FOUND

**Mensagem típica:**
`404 NOT_FOUND. {'error': {'code': 404, 'message': 'Publisher model `.../models/gemini-3.1-pro` was not found or your project does not have access to it.`

**Causa:**
O modelo solicitado no código (ex: `gemini-3.1-pro`) não existe na região especificada (`us-central1`), não está mais disponível, ou o projeto não tem acesso a essa versão específica (muito comum com modelos recém-lançados ou descontinuados).

**Como resolver:**
1. Altere o nome do modelo no seu código (ex: arquivo `microjornada5/agent.py`) para uma versão estável e garantida na sua região, como `gemini-2.5-flash` ou `gemini-1.5-pro`.
   ```python
   MODEL_PRO = "gemini-2.5-flash"
   MODEL_FLASH = "gemini-2.5-flash"
   ```
2. Após alterar o código local, **faça o deploy novamente** para atualizar a versão do agente na nuvem:
   ```bash
   python deployment/deploy.py
   ```
3. Atualize o seu script de teste (`ask_agent.py`) com o novo `Resource name` gerado pelo script de deploy.

---

## 3. Aviso (Warning): InsecureRequestWarning / Certificados

**Mensagem típica:**
`InsecureRequestWarning: Unverified HTTPS request is being made to host 'oauth2.googleapis.com'. Adding certificate verification is strongly advised.`

**Causa:**
Esse é um aviso comum em redes corporativas (como VPNs, Zscaler, Netskope) que interceptam e inspecionam o tráfego HTTPS. O Python avisa que o certificado não é o raiz padrão, mas a conexão foi bem-sucedida.

**Como resolver:**
Você pode ignorar esses avisos, eles não impedem o funcionamento do código. Seu script de autenticação (`gcloud auth application-default login`) e a comunicação com a nuvem funcionarão normalmente.

---

## 4. Como garantir que estou usando a conta certa no Terminal

Se os erros de permissão persistirem, garanta que seu terminal está usando o e-mail correto com o comando:
```bash
gcloud auth application-default login
```
Isso abrirá uma janela do navegador para você confirmar sua conta corporativa. Para checar qual conta está ativa no momento, use:
```bash
gcloud config get-value account
```

---

## 5. Erro no BigQuery: No matching signature for function COALESCE

**Mensagem típica:**
`400 No matching signature for function COALESCE. Argument types: INT64, STRING. Unable to find common supertype for templated argument <T1>.`

**Causa:**
A função `COALESCE` no BigQuery requer que todos os seus argumentos sejam do mesmo tipo de dado (ex: todos `INT64` ou todos `STRING`). O erro acontece quando tentamos misturar tipos. Exemplo incorreto: `COALESCE(sequencia_publicacao, '0')`, onde a coluna original era `INT64` e o fallback `'0'` era `STRING`.

**Como resolver:**
Converta explicitamente (com `CAST`) um dos valores para que ambos tenham a mesma tipagem.
*   **Forma Correta:** `COALESCE(CAST(sequencia_publicacao AS INT64), 0)`
*   Neste projeto, as queries foram refatoradas em `microjornada5/tools.py`.

---

## 6. Erro Oculto (Masking): Dataset/Table Not Found in Location (Falha de Fallback)

**Mensagem típica:**
`Falha ao consultar BigQuery em todas as regiões testadas. Último erro: 404 Not found: Dataset vibra-dtan-spoke-eso-dev:rw_mdriver was not found in location us-east4`

**Causa:**
Este erro é gerado por uma lógica de *fallback* falha no código de integração com o BigQuery. O código tentava rodar a query na região correta (ex: `us-central1`), mas encontrava um erro real (como um erro de sintaxe SQL ou permissão). O script então silenciava esse erro real e tentava nas próximas regiões da lista. Quando chegava na última (ex: `us-east4`), gerava o erro `404 Not found` pois de fato a tabela não existe lá, **escondendo o verdadeiro erro da região original**.

**Como resolver:**
Evite lógicas de fallback cegas para consultas de banco de dados. 
1. Fixe a região onde a tabela sabidamente reside (ex: `client = bigquery.Client(location="us-central1")`).
2. Remova o laço de repetição (`try/except` que mascara erros).
3. Leia o log de erro real que será devolvido na primeira tentativa.

---

## 7. Erro no BigQuery: Unparseable query parameter in type TYPE_DATE

**Mensagem típica:**
`400 Unparseable query parameter 'ini' in type 'TYPE_DATE', Invalid date: '01/01/2026' value: '01/01/2026'`

**Causa:**
O BigQuery utiliza estritamente o formato ISO-8601 (`YYYY-MM-DD`) para parâmetros do tipo Data. Quando o LLM recebe a data no formato brasileiro pelo prompt (ex: `01/01/2026`) e a passa diretamente como argumento (`ScalarQueryParameter`) sem tratamento, o banco rejeita a query. Além disso, falhas similares ocorrem se strings vazias forem passadas no lugar de datas.

**Como resolver:**
Não confie no LLM para enviar a data formatada corretamente para o banco. Adicione um **Parser Intermediário** na camada Python (Tools) antes de enviar a consulta.
1. Crie uma função que detecta se a string possui barras (`/`).
2. Inverta a ordem (`DD/MM/YYYY` -> `YYYY-MM-DD`).
3. Crie valores de "fallback" de segurança caso o parâmetro seja vazio (ex: `2020-01-01` a `2030-12-31`).
*   Neste projeto, a função `_parse_date_to_iso()` foi implementada em `microjornada5/tools.py`.
