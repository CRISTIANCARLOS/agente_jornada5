import os
import ssl
import tempfile
import base64
import atexit
import vertexai
from vertexai import agent_engines

# --- INÍCIO PATCH GPRC SSL PARA REDE CORPORATIVA ---
# O gRPC no Python não lê os certificados do Windows automaticamente.
# Este script extrai os certificados do Windows (incluindo o do Proxy/Zscaler)
# e os entrega para o gRPC confiar neles.
def inject_windows_certs_for_grpc():
    try:
        pem_certs = []
        for store in ["CA", "ROOT"]:
            for cert, encoding, trust in ssl.enum_certificates(store):
                if encoding == "x509_asn":
                    if isinstance(cert, bytes):
                        # Formata o certificado de binário (DER) para texto (PEM)
                        b64 = base64.b64encode(cert).decode('ascii')
                        # Quebra em linhas de 64 caracteres
                        b64_lines = "\n".join(b64[i:i+64] for i in range(0, len(b64), 64))
                        pem = f"-----BEGIN CERTIFICATE-----\n{b64_lines}\n-----END CERTIFICATE-----\n"
                        pem_certs.append(pem)
        if pem_certs:
            fd, path = tempfile.mkstemp(suffix=".pem")
            with os.fdopen(fd, "w") as f:
                f.write("\n".join(pem_certs))
            os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = path
            # Garante que o arquivo seja deletado ao sair do script
            atexit.register(lambda: os.remove(path) if os.path.exists(path) else None)
    except Exception as e:
        print(f"Aviso: Falha ao exportar certificados locais: {e}")

inject_windows_certs_for_grpc()
# --- FIM PATCH GRPC ---

# Resolve o aviso "UserWarning: Your application has authenticated using end user credentials... without a quota project"
os.environ["GOOGLE_CLOUD_QUOTA_PROJECT"] = "vibra-dtan-spoke-eso-dev"

# Inicializa o projeto e define a região onde fizemos o deploy
vertexai.init(project="vibra-dtan-spoke-eso-dev", location="us-central1")

# Carrega o agente remoto recém-criado usando o Resource ID exato do GCP
print("Conectando ao Agente na nuvem...")
remote = agent_engines.get("projects/849977803015/locations/us-central1/reasoningEngines/5271720099802251264")

# Cria uma sessão (isso faz com que o agente lembre do contexto da conversa)
session = remote.create_session(user_id="usuario_teste")
print("\nSessão criada! O agente está pronto para conversar.")
print("Digite sua pergunta ou digite 'sair' para encerrar o script.\n")

while True:
    pergunta = input("Você: ")
    if pergunta.lower() in ["sair", "exit"]:
        break
        
    print("Agente: ", end="", flush=True)
    try:
        # Envia a requisição em modo streaming (a resposta aparece letra por letra, igual no ChatGPT)
        for chunk in remote.stream_query(
                user_id="usuario_teste",
                session_id=session["id"],
                message=pergunta):
            print(chunk, end="", flush=True)
        print("\n")
    except Exception as e:
        print(f"\n[Erro na chamada da API]: {e}\n")
