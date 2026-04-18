"""FHIR REST endpoints backed by a FhirClient (FixtureFhirClient by default)."""
import base64
import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from fhir_proxy.fhir_client.base import FhirClient
from epic_sim.config import SimulatorConfig
from epic_sim.errors import FhirHTTPError
from epic_sim import quirks


router = APIRouter()


def get_client(request: Request) -> FhirClient:
    """Dependency returning the FhirClient bound to app state."""
    return request.app.state.fhir_client


def get_config(request: Request) -> SimulatorConfig:
    return request.app.state.config


def _fhir_json(payload: dict, status_code: int = 200) -> Response:
    return Response(
        content=json.dumps(payload),
        media_type="application/fhir+json",
        status_code=status_code,
    )


def _build_bundle(
    resources: list[dict],
    resource_type: str,
    request: Request,
) -> dict:
    base_fhir_url = f"{str(request.base_url).rstrip('/')}/fhir/R4"
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(resources),
        "link": [{"relation": "self", "url": str(request.url)}],
        "entry": [
            {
                "fullUrl": f"{base_fhir_url}/{resource_type}/{r.get('id', 'unknown')}",
                "resource": r,
            }
            for r in resources
        ],
    }


@router.get("/Binary/{binary_id}")
async def read_binary(
    binary_id: str,
    client: FhirClient = Depends(get_client),
    config: SimulatorConfig = Depends(get_config),
) -> Response:
    quirks.check_binary_access(binary_id, config)
    try:
        result = await client.read_binary(f"Binary/{binary_id}")
    except RuntimeError as exc:
        raise FhirHTTPError(403, "forbidden", str(exc)) from exc
    if result is None:
        raise FhirHTTPError(404, "not-found", f"Binary/{binary_id} not found")
    text, content_type = result
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    payload = {
        "resourceType": "Binary",
        "id": binary_id,
        "contentType": content_type,
        "data": encoded,
    }
    return _fhir_json(payload)


@router.get("/{resource_type}/{resource_id}")
async def read_resource(
    resource_type: str,
    resource_id: str,
    client: FhirClient = Depends(get_client),
    config: SimulatorConfig = Depends(get_config),
) -> Response:
    resource = await client.read(resource_type, resource_id)
    if resource is None:
        raise FhirHTTPError(404, "not-found", f"{resource_type}/{resource_id} not found")
    resource = quirks.apply_read_quirks(resource_type, resource, config)
    return _fhir_json(resource)


@router.get("/{resource_type}")
async def search_resource(
    resource_type: str,
    request: Request,
    client: FhirClient = Depends(get_client),
    config: SimulatorConfig = Depends(get_config),
) -> Response:
    params = dict(request.query_params)
    patient_id = params.pop("patient", None) or params.pop("subject", None)
    if patient_id is None:
        raise FhirHTTPError(
            400, "required", "patient (or subject) query parameter is required"
        )
    quirks.check_patient_access(patient_id, config)
    try:
        resources = await client.search(resource_type, patient_id, params or None)
    except RuntimeError as exc:
        raise FhirHTTPError(400, "not-supported", str(exc)) from exc
    resources = quirks.apply_search_quirks(resource_type, resources, params, config)
    bundle = _build_bundle(resources, resource_type, request)
    return _fhir_json(bundle)
