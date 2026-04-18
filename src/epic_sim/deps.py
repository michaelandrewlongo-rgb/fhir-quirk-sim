"""FastAPI dependency providers for config and FHIR client."""
from fastapi import Request

from fhir_proxy.fhir_client.base import FhirClient
from epic_sim.config import SimulatorConfig


def get_config(request: Request) -> SimulatorConfig:
    return request.app.state.config


def get_client(request: Request) -> FhirClient:
    return request.app.state.fhir_client
