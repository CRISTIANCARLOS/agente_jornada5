import ssl
import aiohttp

# --- INÍCIO PATCH SSL (APENAS PARA TESTES LOCAIS) ---
ssl._create_default_https_context = ssl._create_unverified_context

_original_request = aiohttp.ClientSession._request
async def _unverified_request(self, method, url, *args, **kwargs):
    kwargs["ssl"] = False
    return await _original_request(self, method, url, *args, **kwargs)

aiohttp.ClientSession._request = _unverified_request
# --- FIM PATCH SSL ---

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
    tools=[tools.simular_preset, tools.get_analise_ipar],
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

