#!/usr/bin/env python
"""generate_plc_template — CLI for the YAML -> SCL/ST PLC code generator.

The "killer feature" call site. Run on the engineer's laptop after editing
a machine YAML; copy the resulting file into TIA Portal / Codesys /
TwinCAT and the PLC and Python sides stay in lockstep.

Examples:

    # Render Siemens SCL into ./build/plc/
    python scripts/generate_plc_template.py \\
        --config config/machines/machine_001.yaml \\
        --brand siemens_s7

    # Render every brand we have a template for
    python scripts/generate_plc_template.py \\
        --config config/machines/machine_001.yaml \\
        --all-brands

    # Pipe the generated SCL straight to stdout
    python scripts/generate_plc_template.py \\
        --config config/machines/machine_001.yaml \\
        --brand siemens_s7 --stdout

Exit codes (mirrors commissioning/ convention):
    0 = pass, 1 = bad arguments / config, 2 = template error
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root so `from core import ...` works when run as a script.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.config_model import MachineConfigSchema  # noqa: E402
from core.plc_codegen import (  # noqa: E402
    PlcCodegenError,
    render,
    render_for_brands,
    render_to_file,
    supported_brands,
)
from utils.logger import log  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="generate_plc_template",
        description="Render PLC code (SCL/ST) from a machine YAML config.",
    )
    p.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to a machine YAML config (e.g. config/machines/machine_001.yaml)",
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--brand",
        choices=["siemens_s7", "codesys", "beckhoff", "mitsubishi"],
        help="Single PLC brand to render.",
    )
    g.add_argument(
        "--all-brands",
        action="store_true",
        help="Render for every brand that has a template.",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("build/plc"),
        help="Directory to write rendered files into (default: build/plc).",
    )
    p.add_argument(
        "--stdout",
        action="store_true",
        help="Write rendered code to stdout instead of a file (single brand only).",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    if not args.config.exists():
        print(f"ERROR: config not found: {args.config}", file=sys.stderr)
        return 1

    try:
        schema = MachineConfigSchema.from_yaml(args.config)
        machine = schema.to_machine_config()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: failed to load config: {exc}", file=sys.stderr)
        return 1

    if args.stdout and args.all_brands:
        print("ERROR: --stdout requires a single --brand", file=sys.stderr)
        return 1

    available = supported_brands()
    if not available:
        print(
            "ERROR: no PLC templates found in plc_templates/_codegen/",
            file=sys.stderr,
        )
        return 2

    try:
        if args.all_brands:
            written = render_for_brands(
                machine,
                brands=available,
                output_dir=args.output_dir,
                source_yaml=args.config,
            )
            print(f"Wrote {len(written)} file(s):")
            for path in written:
                print(f"  - {path}")
            return 0

        # Single brand path.
        if args.brand not in available:
            print(
                f"ERROR: brand '{args.brand}' has no template "
                f"(available: {', '.join(available)})",
                file=sys.stderr,
            )
            return 2

        if args.stdout:
            sys.stdout.write(
                render(machine, args.brand, source_yaml=args.config)
            )
            return 0

        path = render_to_file(
            machine,
            args.brand,
            args.output_dir,
            source_yaml=args.config,
        )
        print(f"Wrote: {path}")
        return 0

    except PlcCodegenError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        log.exception("Codegen failed", error=str(exc))
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
