"""Pack discovery endpoints — list and inspect Machine Packs.

Read-only. Packs are platform extensions (CNC / bottle filler / robot
cell / customer-specific). The platform exposes their metadata so the
PWA / engineer dashboard can show "Available Packs" and offer to
populate a fresh machine config from a pack template.

The platform deliberately never executes pack code from this router —
serving manifests is safe; running code is not.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.pack_loader import PackLoader, PackManifest

router = APIRouter(prefix="/api/packs", tags=["packs"])

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_PACKS_DIR = _PROJECT_ROOT / "packs"


class PackResponse(BaseModel):
    """Wire shape — manifest + a few computed fields."""

    pack_id: str
    version: str
    machine_class: str
    description: str
    supported_plc_brands: list[str]
    default_steps: int
    tier_required: str
    author: str
    license: str
    has_machine_config_sample: bool
    has_plc_template: bool

    @classmethod
    def from_pack(cls, pack) -> "PackResponse":  # noqa: ANN001
        m: PackManifest = pack.manifest
        return cls(
            pack_id=m.pack_id,
            version=m.version,
            machine_class=m.machine_class,
            description=m.description,
            supported_plc_brands=list(m.supported_plc_brands),
            default_steps=m.default_steps,
            tier_required=m.tier_required,
            author=m.author,
            license=m.license,
            has_machine_config_sample=pack.has_machine_config_sample,
            has_plc_template=pack.has_plc_template,
        )


def _loader() -> PackLoader:
    return PackLoader(roots=[_DEFAULT_PACKS_DIR])


@router.get("", response_model=list[PackResponse])
async def list_packs() -> list[PackResponse]:
    return [PackResponse.from_pack(p) for p in _loader().discover()]


@router.get("/{pack_id}", response_model=PackResponse)
async def get_pack(pack_id: str) -> PackResponse:
    pack = _loader().get(pack_id)
    if pack is None:
        raise HTTPException(status_code=404, detail=f"Pack {pack_id!r} not found")
    return PackResponse.from_pack(pack)


@router.get("/{pack_id}/machine_config")
async def get_pack_sample_config(pack_id: str) -> dict:
    """Return the pack's `machine_config.yaml.sample` as raw text.

    The PWA / engineer wizard uses this to pre-fill the new-machine
    form when an engineer picks a pack.
    """
    pack = _loader().get(pack_id)
    if pack is None:
        raise HTTPException(status_code=404, detail=f"Pack {pack_id!r} not found")
    sample = pack.path / "machine_config.yaml.sample"
    if not sample.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Pack {pack_id!r} has no machine_config.yaml.sample",
        )
    return {"pack_id": pack_id, "yaml": sample.read_text(encoding="utf-8")}
