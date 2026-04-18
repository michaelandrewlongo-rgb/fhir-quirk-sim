"""
Structural diff: private sandbox captures vs public synthetic fixtures.

Walks `private/captures/<tag>/` and `tests/compat/fixtures/epic/` and prints a
per-resource-type coverage summary: which resource types appear, which top-
level fields show up, and whether OperationOutcome issue codes are represented.

Intentionally shallow — only field names and structural shape are printed, so
engineers can rewrite synthetic fixtures by hand without ever pasting sandbox
bytes into the public tree.

Usage:
    python scripts/calibrate_fixtures.py --tag <capture-tag>
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parent.parent
PRIVATE_ROOT = REPO / "private" / "captures"
PUBLIC_ROOT = REPO / "tests" / "compat" / "fixtures" / "epic"


def iter_resources(root: Path) -> Iterable[dict[str, Any]]:
    if not root.exists():
        return
    for path in sorted(root.rglob("*.json")):
        if path.name.endswith(".provenance.json"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            if data.get("resourceType") == "Bundle":
                for entry in data.get("entry", []) or []:
                    resource = entry.get("resource") if isinstance(entry, dict) else None
                    if isinstance(resource, dict):
                        yield resource
            else:
                yield data


def summarize(root: Path) -> dict[str, Any]:
    fields: dict[str, set[str]] = defaultdict(set)
    outcome_codes: set[str] = set()
    for resource in iter_resources(root):
        rt = resource.get("resourceType")
        if not isinstance(rt, str):
            continue
        fields[rt].update(resource.keys())
        if rt == "OperationOutcome":
            for issue in resource.get("issue", []) or []:
                if isinstance(issue, dict) and issue.get("code"):
                    outcome_codes.add(issue["code"])
    return {
        "fields": {rt: sorted(v) for rt, v in sorted(fields.items())},
        "operation_outcome_codes": sorted(outcome_codes),
    }


def diff_summary(private: dict[str, Any], public: dict[str, Any]) -> None:
    priv_types = set(private["fields"].keys())
    pub_types = set(public["fields"].keys())
    print("== resource types ==")
    print(f"  only in private: {sorted(priv_types - pub_types)}")
    print(f"  only in public:  {sorted(pub_types - priv_types)}")
    print(f"  in both:         {sorted(priv_types & pub_types)}")
    print()
    print("== field coverage (per resource type) ==")
    for rt in sorted(priv_types | pub_types):
        priv_fields = set(private["fields"].get(rt, []))
        pub_fields = set(public["fields"].get(rt, []))
        missing_in_public = priv_fields - pub_fields
        if missing_in_public:
            print(f"  {rt}: public missing fields -> {sorted(missing_in_public)}")
    print()
    print("== OperationOutcome issue codes ==")
    print(f"  private: {private['operation_outcome_codes']}")
    print(f"  public:  {public['operation_outcome_codes']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True, help="Capture tag under private/captures/")
    args = parser.parse_args()

    private_root = PRIVATE_ROOT / args.tag
    if not private_root.exists():
        raise SystemExit(f"No captures at {private_root}")

    private = summarize(private_root)
    public = summarize(PUBLIC_ROOT)
    diff_summary(private, public)


if __name__ == "__main__":
    main()
