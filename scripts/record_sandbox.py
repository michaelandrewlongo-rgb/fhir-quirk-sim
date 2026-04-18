"""
Record Epic sandbox responses into private/captures/<tag>/.

Usage:
    python scripts/record_sandbox.py \
        --acknowledge-private \
        --base-url https://<sandbox-fhir-base> \
        --token  $EPIC_BEARER \
        --patient <YOUR_SANDBOX_PATIENT_ID> \
        --tag epic-r4-sandbox-2026-04

Captures Observation + DocumentReference search + Binary dereferences for the
given sandbox patient into `private/captures/<tag>/`. `private/` is gitignored;
these bytes MUST NOT be committed and MUST NOT be copied into
`tests/compat/fixtures/`. Use `scripts/calibrate_fixtures.py --tag <tag>` to
produce a shape-only diff; rewrite synthetic fixtures in the public tree by
hand.

Sandbox patient IDs are documented by Epic at their developer portal; substitute
the placeholder above with a currently published sandbox patient ID.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
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


REPO = Path(__file__).resolve().parent.parent
TESTS_DIR = (REPO / "tests").resolve()


def _refuse_if_under_tests(root: Path) -> None:
    resolved = root.resolve()
    try:
        resolved.relative_to(TESTS_DIR)
    except ValueError:
        return
    print(
        f"record_sandbox: refusing to write under tests/ (resolved root: {resolved}). "
        "Sandbox captures must land in private/captures/, never in the public "
        "fixture tree. See tests/compat/fixtures/epic/README.md.",
        file=sys.stderr,
    )
    sys.exit(2)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", required=True)
    p.add_argument("--token", required=True)
    p.add_argument("--patient", required=True, help="Epic sandbox patient ID")
    p.add_argument("--tag", required=True, help="Capture subdirectory tag")
    p.add_argument(
        "--root",
        default="private/captures",
        help="Capture tree root (default: private/captures)",
    )
    p.add_argument(
        "--acknowledge-private",
        action="store_true",
        help=(
            "Required. Acknowledges that captured bytes are private and must not "
            "be committed to the public fixture tree."
        ),
    )
    args = p.parse_args()

    if not args.acknowledge_private:
        print(
            "record_sandbox: refusing to run without --acknowledge-private. "
            "Sandbox captures may contain Epic-authored Materials or real data; "
            "they must not be committed. Re-run with --acknowledge-private to "
            "confirm you will keep the output under private/ and rewrite "
            "synthetic fixtures by hand via scripts/calibrate_fixtures.py.",
            file=sys.stderr,
        )
        sys.exit(2)

    root = Path(args.root)
    _refuse_if_under_tests(root)

    asyncio.run(record(args.base_url, args.token, args.patient, args.tag, root))


if __name__ == "__main__":
    main()
