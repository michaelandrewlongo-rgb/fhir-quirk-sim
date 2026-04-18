"""FastAPI app factory for the Epic FHIR simulator."""
from fastapi import Depends, FastAPI
from fastapi.exceptions import HTTPException

from fhir_proxy.fhir_client.base import FhirClient
from epic_sim.auth.bearer import require_bearer
from epic_sim.auth.jwks import SimKeys
from epic_sim.auth.store import AccessTokenStore, AuthCodeStore, JtiStore
from epic_sim.auth import authorize as authorize_routes
from epic_sim.auth import token as token_routes
from epic_sim.auth import well_known as well_known_routes
from epic_sim.config import SimulatorConfig
from epic_sim.errors import fhir_http_exception_handler
from epic_sim.fixtures import load_default_client
from epic_sim.routes import fhir as fhir_routes
from epic_sim.routes import metadata as metadata_routes


def create_app(
    fhir_client: FhirClient | None = None,
    config: SimulatorConfig | None = None,
) -> FastAPI:
    app = FastAPI(
        title="epic-sim",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
    )
    app.state.fhir_client = fhir_client if fhir_client is not None else load_default_client()
    app.state.config = config if config is not None else SimulatorConfig.from_env()
    app.state.sim_keys = SimKeys()
    app.state.auth_code_store = AuthCodeStore(ttl_seconds=60)
    app.state.access_token_store = AccessTokenStore(ttl_seconds=3600)
    app.state.jti_store = JtiStore()

    app.add_exception_handler(HTTPException, fhir_http_exception_handler)

    # Order matters. oauth2 and metadata routes must come before the FHIR
    # catch-all routes (/{resource_type}) or they will be shadowed.
    app.include_router(well_known_routes.router, prefix="/fhir/R4")
    app.include_router(authorize_routes.router, prefix="/fhir/R4/oauth2")
    app.include_router(token_routes.router, prefix="/fhir/R4/oauth2")
    app.include_router(metadata_routes.router, prefix="/fhir/R4")
    app.include_router(
        fhir_routes.router,
        prefix="/fhir/R4",
        dependencies=[Depends(require_bearer)],
    )
    return app


app = create_app()
