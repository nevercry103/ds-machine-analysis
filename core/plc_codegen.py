"""PLC code generator — YAML machine config -> SCL/ST file.

The "killer feature" per the roadmap: a customer's machine YAML is the
single source of truth, and the platform generates the matching PLC
code (Siemens SCL, Codesys ST, etc.) so the OT engineer doesn't hand-
write — and especially doesn't *desync* — both sides of the handshake.

Templates live in ``plc_templates/_codegen/<brand>/`` as Jinja2 files.
Adding a new brand = drop in a new ``.j2`` template; no Python change.

Architecture layer: CORE
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import jinja2

from core.data_model import MachineConfig
from utils.logger import log

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES_ROOT = _PROJECT_ROOT / "plc_templates" / "_codegen"

# Map (brand) -> default template filename.
DEFAULT_TEMPLATES: dict[str, str] = {
    "siemens_s7": "FB_CycleMaster.scl.j2",
    "codesys": "FB_CycleMaster.st.j2",
    "beckhoff": "FB_CycleMaster.st.j2",  # Beckhoff also accepts IEC ST
    "mitsubishi": "FB_CycleMaster.st.j2",
}

# Map (brand) -> output extension.
OUTPUT_EXTENSIONS: dict[str, str] = {
    "siemens_s7": ".scl",
    "codesys": ".st",
    "beckhoff": ".st",
    "mitsubishi": ".st",
}


class PlcCodegenError(Exception):
    """Raised when a template is missing or the config is unfit to render."""


def supported_brands() -> list[str]:
    """List brands that have a Jinja2 template available on disk."""
    if not _TEMPLATES_ROOT.exists():
        return []
    return sorted(
        b.name
        for b in _TEMPLATES_ROOT.iterdir()
        if b.is_dir() and (b / DEFAULT_TEMPLATES.get(b.name, "")).exists()
    )


def _build_environment() -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_ROOT)),
        autoescape=False,  # PLC code is not HTML — no escaping needed
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        undefined=jinja2.StrictUndefined,
    )


def _config_to_context(
    config: MachineConfig,
    *,
    source_yaml: str | Path | None = None,
) -> dict:
    """Translate a `MachineConfig` into the Jinja2 render context."""
    if config.total_steps != len(config.step_names):
        raise PlcCodegenError(
            f"Config '{config.machine_id}': total_steps={config.total_steps} but "
            f"step_names has {len(config.step_names)} entries"
        )

    steps = [
        {"index": i + 1, "name": name}
        for i, name in enumerate(config.step_names)
    ]

    return {
        "machine_id": config.machine_id,
        "machine_name": config.machine_name,
        "total_steps": config.total_steps,
        "steps": steps,
        "cycle_ready_tag": config.protocol.cycle_ready_tag,
        "cycle_reset_tag": config.protocol.cycle_reset_tag,
        "cycle_log_tag": config.protocol.cycle_log_tag,
        "source_yaml": str(source_yaml) if source_yaml else "(in-memory)",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def render(
    config: MachineConfig,
    brand: str,
    *,
    source_yaml: str | Path | None = None,
    template_filename: str | None = None,
) -> str:
    """Render the PLC code for one machine + one brand. Returns the file
    contents as a string. Caller decides where to write it.
    """
    brand_dir = _TEMPLATES_ROOT / brand
    if not brand_dir.exists():
        raise PlcCodegenError(
            f"No PLC template directory for brand '{brand}'. "
            f"Expected: {brand_dir}"
        )

    fname = template_filename or DEFAULT_TEMPLATES.get(brand)
    if fname is None:
        raise PlcCodegenError(
            f"No default template registered for brand '{brand}'. "
            f"Pass `template_filename=` explicitly."
        )

    env = _build_environment()
    template = env.get_template(f"{brand}/{fname}")
    rendered = template.render(_config_to_context(config, source_yaml=source_yaml))
    log.info(
        "Rendered PLC code",
        machine_id=config.machine_id,
        brand=brand,
        template=fname,
        lines=rendered.count("\n"),
    )
    return rendered


def render_to_file(
    config: MachineConfig,
    brand: str,
    output_dir: str | Path,
    *,
    source_yaml: str | Path | None = None,
    filename: str | None = None,
    template_filename: str | None = None,
) -> Path:
    """Render and write to ``<output_dir>/<machine_id>_FB_CycleMaster.<ext>``.

    Returns the absolute path of the written file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered = render(
        config,
        brand,
        source_yaml=source_yaml,
        template_filename=template_filename,
    )
    ext = OUTPUT_EXTENSIONS.get(brand, ".txt")
    out_name = filename or f"{config.machine_id}_FB_CycleMaster{ext}"
    out_path = output_dir / out_name
    out_path.write_text(rendered, encoding="utf-8")
    log.info(
        "Wrote PLC file",
        machine_id=config.machine_id,
        brand=brand,
        path=str(out_path),
    )
    return out_path


def render_for_brands(
    config: MachineConfig,
    brands: Iterable[str],
    output_dir: str | Path,
    *,
    source_yaml: str | Path | None = None,
) -> list[Path]:
    """Render the same machine for multiple brands at once."""
    output_dir = Path(output_dir)
    written: list[Path] = []
    for brand in brands:
        try:
            written.append(
                render_to_file(
                    config, brand, output_dir, source_yaml=source_yaml
                )
            )
        except PlcCodegenError as exc:
            log.warning(
                "Skipping brand (no template / bad config)",
                brand=brand,
                error=str(exc),
            )
    return written
