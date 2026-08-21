import ssl
import aiohttp

# --- INÍCIO PATCH SSL E FALLBACK DE REGIÃO ---
ssl._create_default_https_context = ssl._create_unverified_context

import re
_original_request = aiohttp.ClientSession._request

REGIOES_FALLBACK = ["us-central1", "us-east1", "us-east4", "us-west1", "us-west4", "europe-west4"]

async def _custom_request(self, method, url, *args, **kwargs):
    kwargs["ssl"] = False
    url_str = str(url)
    
    if "aiplatform.googleapis.com" in url_str:
        for regiao in REGIOES_FALLBACK:
            nova_url = re.sub(r'https://[a-zA-Z0-9-]+-aiplatform', f'https://{regiao}-aiplatform', url_str)
            nova_url = re.sub(r'/locations/[a-zA-Z0-9-]+/', f'/locations/{regiao}/', nova_url)
            
            response = await _original_request(self, method, nova_url, *args, **kwargs)
            
            # Se for sucesso ou um erro diferente de permissão/não encontrado, retorna
            if response.status not in (403, 404):
                return response
            
            # Libera a resposta para evitar vazamento de memória e tenta a próxima
            response.release()
            
        # Se esgotar as tentativas, retorna a chamada na URL original
        return await _original_request(self, method, url_str, *args, **kwargs)
        
    return await _original_request(self, method, url, *args, **kwargs)

aiohttp.ClientSession._request = _custom_request
# --- FIM PATCH SSL E FALLBACK DE REGIÃO ---

from google.adk.agents import Agent
from . import tools, prompts

MODEL_PRO = "gemini-2.5-flash"
MODEL_FLASH = "gemini-2.5-flash"

# ---- Subagentes ----
sa1 = Agent(
    name="SA1_tempo_g2g",
    model=MODEL_FLASH,
    description="Mede a média do tempo de G2G por base/período.",
    instruction=prompts.SA1,
    tools=[tools.get_media_g2g],
)
sa2 = Agent(
    name="SA2_simultaneidade",
    model=MODEL_FLASH,
    description="Avalia simultaneidade TOP x BOTTOM e ociosidade de braços.",
    instruction=prompts.SA2,
    tools=[tools.get_simultaneidade],
)
sa3 = Agent(
    name="SA3_ofensores",
    model=MODEL_FLASH,
    description="Ranqueia ofensores de passeio e detecta duplo encoste.",
    instruction=prompts.SA3,
    tools=[tools.get_passeios],
)
sa4 = Agent(
    name="SA4_simulacao",
    model=MODEL_PRO,
    description="Simula presets/reconfiguração e quantifica ganho.",
    instruction=prompts.SA4,
    tools=[tools.simular_reducao_setup, tools.get_analise_ipar],
)
sa5 = Agent(
    name="SA5_validador",
    model=MODEL_PRO,
    description="Valida os dados antes da entrega (18 itens obrigatórios, outliers, anticonfusão).",
    instruction=prompts.SA5,
    tools=[tools.painel_operacional],
)

# ---- Orquestrador (root) ----
root_agent = Agent(
    name="agente_g2g",
    model=MODEL_PRO,
    description="Orquestrador do Tempo de G2G (Vibra).",
    instruction=prompts.ORQUESTRADOR,
    sub_agents=[sa1, sa2, sa3, sa4, sa5],
    tools=[tools.painel_operacional]
)
