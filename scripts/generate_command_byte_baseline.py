"""Freeze command bytes from an explicitly selected, isolated Git revision."""

import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

ORIGINAL_REVISION = "677f25b4438f1765e0040b2b441913f21a022420"


def generate(output, revision):
    import pytrain
    from pytrain.pdi.pdi_req import TmccReq
    from pytrain.protocol.command_req import CommandReq
    from pytrain.protocol.constants import CommandScope
    from pytrain.protocol.multibyte.dcds_command_req import VariableCommandReq
    from pytrain.protocol.multibyte.multibyte_constants import (
        TMCC2DcdsCommandEnum,
        TMCC2EffectsControl,
        TMCC2LightingControl,
        TMCC2MaskingControl,
        TMCC2R4LCEnum,
        TMCC2VariableEnum,
    )
    from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
    from pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum

    exported = Path(os.environ["PYTRAIN_BASELINE_ROOT"]).resolve()
    assert Path(pytrain.__file__).resolve().is_relative_to(exported)
    four_digit_addresses = tuple(range(100, 128)) + (128, 550, 3233, 9999)
    legacy_addresses = (1, 37, 99) + four_digit_addresses
    selections = []
    for family in (TMCC1EngineCommandEnum, TMCC2EngineCommandEnum):
        for command in family:
            definition = command.value
            if not definition.is_addressable or definition.is_noop:
                continue
            if not definition.is_data:
                values = (0,)
            elif definition.data_map:
                values = tuple(sorted(definition.data_map))
            elif definition.data_max - definition.data_min <= 31:
                values = tuple(range(definition.data_min, definition.data_max + 1))
            else:
                values = tuple(
                    sorted({definition.data_min, (definition.data_min + definition.data_max) // 2, definition.data_max})
                )
            selections.extend((family, command, value) for value in values)
    for family, names in (
        (TMCC2MaskingControl, ("NC_NC", "ALWAYS_ALWAYS", "DEFAULT_DEFAULT")),
        (TMCC2EffectsControl, ("SMOKE_LOW", "SMOKE_HIGH")),
        (TMCC2LightingControl, ("CAB_ON", "CAB_OFF")),
    ):
        selections.extend((family, family[name], 0) for name in names)
    for name, values in (
        ("TRAIN_ADDRESS", (0, 37, 99)),
        ("TRAIN_UNIT", tuple(range(8))),
        ("MAX_SPEED", (32, 100, 200)),
    ):
        selections.extend((TMCC2R4LCEnum, TMCC2R4LCEnum[name], value) for value in values)
    for name, values in (
        ("MASTER_VOLUME", (0, 127, 255)),
        ("BLEND_VOLUME", (0, 127, 255)),
        ("HORN_DIRECT", (0, 7)),
        ("GET_INFO", (None,)),
        ("GET_STATUS", (None,)),
    ):
        selections.extend((TMCC2DcdsCommandEnum, TMCC2DcdsCommandEnum[name], value) for value in values)

    groups = []
    for family, command, data in selections:
        for scope in (CommandScope.ENGINE, CommandScope.TRAIN):
            addresses = (
                legacy_addresses
                if family is not TMCC1EngineCommandEnum
                else ((1, 37, 99) if scope is CommandScope.ENGINE else (1, 5, 9))
            )
            vectors = []
            for address in addresses:
                if isinstance(command, TMCC2VariableEnum):
                    request = VariableCommandReq.build(command, address, data, scope)
                else:
                    request = CommandReq.build(command, address, data, scope)
                vectors.append(
                    [address, request.as_bytes.hex(), [packet.hex() for packet in TmccReq.as_packets(request)]]
                )
            groups.append(
                {
                    "family": family.__name__,
                    "command": command.name,
                    "data": data,
                    "scope": scope.name,
                    "vectors": vectors,
                }
            )
    metadata = {
        "schema": 1,
        "revision": revision,
        "description": "Original encoder and PDI packet bytes from an isolated git archive; expected bytes are never computed from the current implementation.",
        "coverage": "All addressable, non-noop TMCC1/TMCC2 engine enums in ENGINE/TRAIN scope; full small data ranges, all mapped data, and min/mid/max of larger ranges; representative fixed and variable multibyte commands. All real four-digit IDs 100-127 plus upper boundaries. Prefix-valued variable payloads are excluded because their old checksum bug was intentionally corrected separately.",
        "vector_count": sum(len(group["vectors"]) for group in groups),
    }
    lines = [json.dumps(metadata, indent=2)[:-2] + ',\n  "groups": [']
    lines.extend(
        "    " + json.dumps(group, separators=(",", ":")) + ("," if i + 1 < len(groups) else "")
        for i, group in enumerate(groups)
    )
    lines.append("  ]\n}\n")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines))
    print(
        f"Frozen {metadata['vector_count']} vectors in {len(groups)} groups from {revision}; imported {pytrain.__file__}"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", default=ORIGINAL_REVISION)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        generate(args.output.resolve(), args.revision)
        return
    root = Path.cwd()
    archive = subprocess.check_output(["git", "archive", args.revision, "src/pytrain"], cwd=root)
    with tempfile.TemporaryDirectory(prefix="pytrain-byte-baseline-") as directory:
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            bundle.extractall(directory, filter="data")
        env = dict(
            os.environ,
            PYTHONPATH=str(Path(directory) / "src"),
            PYTHONDONTWRITEBYTECODE="1",
            PYTRAIN_BASELINE_ROOT=directory,
        )
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                "--revision",
                args.revision,
                "--output",
                str(args.output.resolve()),
            ],
            cwd=directory,
            env=env,
            check=True,
        )


if __name__ == "__main__":
    main()
