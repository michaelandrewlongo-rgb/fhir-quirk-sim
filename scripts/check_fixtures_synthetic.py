"""
CI guardrail: verify the public tree ships only synthetic, redistributable
content.

Rules (first violation aborts):

1. No `*.epic.com` host may appear under `tests/compat/fixtures/` or
   `src/epic_sim/`. `docs/EPIC_QUIRKS.md` is allowlisted for citation context.
2. No `urn:oid:1.2.840.114350.*` value may appear inside any fixture JSON
   unless it is on the documented-synthetic allowlist.
3. Every `*.json` in `tests/compat/fixtures/epic/` (except `*.provenance.json`)
   must have a sibling `<name>.provenance.json` whose top-level `source`
   field is `"synthetic"`.
4. Nothing under `private/` may be tracked by git.

Exit 0 on pass; non-zero with a path/line on first violation.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = REPO / "tests" / "compat" / "fixtures"
SRC_ROOT = REPO / "src" / "epic_sim"
DOCS_QUIRKS = REPO / "docs" / "EPIC_QUIRKS.md"

SYNTHETIC_OID_ALLOWLIST = {
    "urn:oid:1.2.840.114350.1.13.999.234",
}

EPIC_HOST_RE = re.compile(r"[A-Za-z0-9_.\-]*\.epic\.com")
EPIC_OID_RE = re.compile(r"urn:oid:1\.2\.840\.114350(?:\.[0-9]+)+")


def fail(msg: str) -> None:
    print(f"check_fixtures_synthetic: FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def iter_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and p.suffix in suffixes]


def check_no_epic_hosts() -> None:
    roots = [FIXTURE_ROOT, SRC_ROOT]
    suffixes = (".json", ".py", ".yaml", ".yml", ".md")
    for root in roots:
        if not root.exists():
            continue
        for path in iter_files(root, suffixes):
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                for match in EPIC_HOST_RE.finditer(line):
                    host = match.group(0)
                    if host.endswith(".example.com"):
                        continue
                    # Allow publicly documented Epic FHIR extension/profile URIs.
                    # These are HL7-style canonical identifiers, not live API endpoints.
                    span_end = match.end()
                    tail = line[span_end : span_end + 40]
                    if host == "open.epic.com" and tail.startswith("/FHIR/StructureDefinition/"):
                        continue
                    fail(f"{path}:{lineno}: forbidden Epic host reference: {host!r}")


def check_fixture_oids() -> None:
    for path in iter_files(FIXTURE_ROOT, (".json",)):
        if path.name.endswith(".provenance.json"):
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            for match in EPIC_OID_RE.finditer(line):
                oid = match.group(0)
                if oid not in SYNTHETIC_OID_ALLOWLIST:
                    fail(
                        f"{path}:{lineno}: non-allowlisted Epic OID in fixture: {oid!r}. "
                        f"Allowlist: {sorted(SYNTHETIC_OID_ALLOWLIST)}"
                    )


def check_provenance_sidecars() -> None:
    epic_dir = FIXTURE_ROOT / "epic"
    if not epic_dir.exists():
        return
    for path in sorted(epic_dir.glob("*.json")):
        if path.name.endswith(".provenance.json"):
            continue
        sidecar = path.with_name(path.stem + ".provenance.json")
        if not sidecar.exists():
            fail(f"{path}: missing sidecar {sidecar.name}")
        try:
            meta = json.loads(sidecar.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(f"{sidecar}: invalid JSON: {exc}")
        if meta.get("source") != "synthetic":
            fail(f"{sidecar}: source must be 'synthetic', got {meta.get('source')!r}")


def check_no_private_tracked() -> None:
    try:
        result = subprocess.run(
            ["git", "ls-files", "private/"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return
    tracked = result.stdout.strip()
    if tracked:
        fail(f"paths under private/ are tracked by git:\n{tracked}")


def main() -> None:
    check_no_epic_hosts()
    check_fixture_oids()
    check_provenance_sidecars()
    check_no_private_tracked()
    print("check_fixtures_synthetic: OK")


if __name__ == "__main__":
    main()
