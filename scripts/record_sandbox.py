"""
Record Epic sandbox responses into tests/compat/fixtures/epic/<tag>/.

Usage:
    python scripts/record_sandbox.py \
        --base-url https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4 \
        --token  $EPIC_BEARER \
        --patient eq081-VQEgP8drUUqCWzHfw3 \
        --tag epic-r4-sandbox-2026-04

Captures Observation + DocumentReference search + Binary dereferences for the
given sandbox patient. Intended to be run manually when you want fresh byte
samples; the resulting fixture tree becomes inputs to the local simulator.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from epic_sim.record.capture import RecordingFhirAdapter


SANDBOX_OBSERVATION_CODES = [
    "718-7",   # Hemoglobin
    "2951-2",  # Sodium
    "789-8",   # RBC
    "4548-4",  # Hemoglobin A1c
]


async def record(base_url: str, token: str, patient: str, tag: str, root: Path) -> None:
    adapter = RecordingFhirAdapter(
        base_url=base_url, capture_root=root, tag=tag, auth_token=token
    )
    try:
        await adapter.search("Patient", patient_id=patient)
        await adapter.search(
            "Observation",
            patient_id=patient,
            params={"code": ",".join(SANDBOX_OBSERVATION_CODES)},
        )
        doc_refs = await adapter.search(
            "DocumentReference",
            patient_id=patient,
            params={"category": "clinical-note"},
        )
        for doc_ref in doc_refs:
            for content in doc_ref.get("content", []):
                url = content.get("attachment", {}).get("url")
                if url:
                    try:
                        await adapter.read_binary(url)
                    except Exception as exc:
                        print(f"skip {url}: {exc}")
        await adapter.search("Condition", patient_id=patient)
        await adapter.search("MedicationRequest", patient_id=patient)
    finally:
        await adapter.close()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", required=True)
    p.add_argument("--token", required=True)
    p.add_argument("--patient", required=True, help="Epic sandbox patient ID")
    p.add_argument("--tag", required=True, help="Fixture subdirectory tag")
    p.add_argument(
        "--root",
        default="tests/compat/fixtures/epic",
        help="Fixture tree root (default: tests/compat/fixtures/epic)",
    )
    args = p.parse_args()
    asyncio.run(record(args.base_url, args.token, args.patient, args.tag, Path(args.root)))


if __name__ == "__main__":
    main()
