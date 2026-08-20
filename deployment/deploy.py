import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import vertexai
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp
from microjornada5.agent import root_agent

vertexai.init(
    project="vibra-dtan-spoke-eso-dev",
    location="us-central1",
    staging_bucket="gs://vibra-staging-cristiancarlos-agente5",
)

app = AdkApp(agent=root_agent, enable_tracing=True)

remote = agent_engines.create(
    app,
    display_name="Agente G2G - Microjornada 5",
    requirements=[
        "google-cloud-aiplatform[agent_engines,adk]",
        "google-cloud-bigquery",
    ],
    extra_packages=["./microjornada5"],
)
print("Resource name:", remote.resource_name)
