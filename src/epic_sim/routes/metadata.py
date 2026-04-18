"""Minimal CapabilityStatement for the simulator."""
from fastapi import APIRouter, Response

router = APIRouter()


_CAPABILITY_STATEMENT = {
    "resourceType": "CapabilityStatement",
    "status": "active",
    "date": "2026-04-17",
    "kind": "instance",
    "software": {"name": "epic-sim", "version": "0.1.0"},
    "fhirVersion": "4.0.1",
    "format": ["application/fhir+json", "json"],
    "rest": [
        {
            "mode": "server",
            "resource": [
                {
                    "type": "Observation",
                    "interaction": [{"code": "search-type"}, {"code": "read"}],
                },
                {
                    "type": "DocumentReference",
                    "interaction": [{"code": "search-type"}, {"code": "read"}],
                },
                {
                    "type": "Binary",
                    "interaction": [{"code": "read"}],
                },
            ],
        }
    ],
}


@router.get("/metadata")
async def capability_statement() -> Response:
    import json
    return Response(
        content=json.dumps(_CAPABILITY_STATEMENT),
        media_type="application/fhir+json",
    )
