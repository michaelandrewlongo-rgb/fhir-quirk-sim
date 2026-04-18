"""
Error / status-code quirks.

- vip_patient_ids → any request scoped to this patient returns 403 with an
  Epic-shaped OperationOutcome.
- btg_403_rate → probabilistic break-the-glass 403 (not used yet — stub for
  future route that exercises it).
"""
from __future__ import annotations

from epic_sim.config import SimulatorConfig
from epic_sim.errors import FhirHTTPError


def maybe_block_vip(patient_id: str, config: SimulatorConfig) -> None:
    if patient_id in set(config.vip_patient_ids):
        raise FhirHTTPError(
            403,
            "forbidden",
            f"Patient/{patient_id} is VIP-restricted; break-the-glass required",
        )
