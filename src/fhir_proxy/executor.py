import asyncio
import logging
from fhir_proxy.deid.freetext import FreetextDeidentifier
from fhir_proxy.deid.html_stripper import strip_to_text
from fhir_proxy.deid.structured import StructuredDeidentifier
from fhir_proxy.deid.token_store import TokenStore
from fhir_proxy.fhir_client.base import FhirClient
from fhir_proxy.models.fetch_plan import FetchPlan, FetchPlanItem
from fhir_proxy.models.sanitized_bundle import SanitizedBundle, SanitizedResource

logger = logging.getLogger(__name__)


class FetchPlanExecutor:
    def __init__(
        self,
        fhir_client: FhirClient,
        token_store: TokenStore,
        freetext_deid: FreetextDeidentifier | None = None,
    ):
        self.fhir_client = fhir_client
        self.token_store = token_store
        self.deid = StructuredDeidentifier(token_store)
        self.freetext_deid = freetext_deid
        self._binary_errors: list[str] = []

    async def execute(self, plan: FetchPlan) -> SanitizedBundle:
        self._binary_errors = []
        tasks = [self._execute_item(plan.patient_id, item) for item in plan.items]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        resources = []
        errors = list(self._binary_errors)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                item = plan.items[i]
                errors.append(f"Failed to fetch {item.resource_type}: {str(result)}")
            else:
                resources.extend(result)
        return SanitizedBundle(session_id=plan.session_id, resources=resources, errors=errors)

    async def _execute_item(self, patient_id: str, item: FetchPlanItem) -> list[SanitizedResource]:
        params = {}
        if item.codes:
            params["code"] = ",".join(item.codes)
        if item.category:
            params["category"] = item.category
        if item.time_window_hours:
            from datetime import datetime, timedelta, timezone
            cutoff = datetime.now(timezone.utc) - timedelta(hours=item.time_window_hours)
            params["date"] = f"ge{cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        raw_resources = await self.fhir_client.search(
            resource_type=item.resource_type, patient_id=patient_id,
            params=params if params else None)
        sanitized = []
        for raw in raw_resources:
            deidentified = self.deid.deidentify(raw)
            content_text = None
            if item.resource_type == "DocumentReference":
                try:
                    content_text = await self._fetch_note_content(raw)
                except Exception as exc:
                    err = f"Binary fetch failed for DocumentReference/{raw.get('id', 'unknown')}: {exc}"
                    logger.warning(err)
                    self._binary_errors.append(err)
            sanitized.append(SanitizedResource(
                resource_type=item.resource_type,
                data=deidentified,
                source_ref=f"{item.resource_type}/{raw.get('id', 'unknown')}",
                content_text=content_text,
            ))
        return sanitized

    async def _fetch_note_content(self, raw: dict) -> str | None:
        """
        Follow content[].attachment URL or decode inline data from a DocumentReference.

        Tries each attachment in order, returns the first successfully decoded text.
        Applies freetext de-identification if FreetextDeidentifier is available.
        Raises on fetch failure (caller catches per-resource and records in bundle.errors).
        """
        for content_item in raw.get("content", []):
            attachment = content_item.get("attachment", {})
            content_type = attachment.get("contentType", "text/plain")
            url = attachment.get("url")
            inline_data = attachment.get("data")

            if url:
                result = await self.fhir_client.read_binary(url)
                if result is None:
                    continue
                raw_text, content_type = result
            elif inline_data:
                import base64
                raw_bytes = base64.b64decode(inline_data)
                raw_text = raw_bytes.decode("utf-8", errors="replace")
            else:
                continue

            plain = strip_to_text(raw_text, content_type)
            if plain is None:
                logger.warning("Unsupported note content type: %s, skipping", content_type)
                continue
            if not plain:
                continue

            if self.freetext_deid:
                plain = self.freetext_deid.deidentify(plain)

            return plain

        return None
