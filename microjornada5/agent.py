from google.adk.agents import Agent
from . import tools, prompts

MODEL_PRO = "gemini-3.1-pro"
MODEL_FLASH = "gemini-3.5-flash"

# ---- Subagentes ----
sa1 = Agent(
    name="SA1_passeio_setup",
    model=MODEL_FLASH,
    description="Mede taxa de passeio e custo de setup por base/período.",
    instruction=prompts.SA1,
    tools=[tools.get_taxa_passeio],
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
    description="Ranqueia ofensores de passeio por ilha ou produto.",
    instruction=prompts.SA3,
    tools=[tools.get_ofensores],
)
sa4 = Agent(
    name="SA4_simulacao",
    model=MODEL_PRO,
    description="Simula presets/reconfiguração e quantifica ganho.",
    instruction=prompts.SA4,
    tools=[tools.simular_preset],
)

# ---- Orquestrador (root) ----
root_agent = Agent(
    name="agente_g2g",
    model=MODEL_PRO,
    description="Orquestrador da Taxa de Passeio -> G2G (Vibra).",
    instruction=prompts.ORQUESTRADOR,
    sub_agents=[sa1, sa2, sa3, sa4],
)
