"""Epic-shaped OperationOutcome error responses for the FastAPI surface."""
from fastapi import Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse


def operation_outcome(severity: str, code: str, diagnostics: str) -> dict:
    return {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": severity,
                "code": code,
                "diagnostics": diagnostics,
            }
        ],
    }


class FhirHTTPError(HTTPException):
    """HTTPException carrying an OperationOutcome body."""

    def __init__(self, status_code: int, code: str, diagnostics: str, severity: str = "error"):
        super().__init__(
            status_code=status_code,
            detail=operation_outcome(severity, code, diagnostics),
        )


async def fhir_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    body = (
        exc.detail
        if isinstance(exc.detail, dict) and exc.detail.get("resourceType") == "OperationOutcome"
        else operation_outcome("error", "exception", str(exc.detail))
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=body,
        media_type="application/fhir+json",
    )
