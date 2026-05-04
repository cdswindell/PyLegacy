#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#
#  SPDX-License-Identifier: LPGL
#

from src.pytrain.pdi.constants import PDI_EOP, PDI_SOP, IrdaAction, PdiCommand
from src.pytrain.pdi.irda_req import IrdaReq, IrdaSequence


def test_config_rx_as_bytes_contains_fields():
    """
    CONFIG with RX should serialize tmcc_id, debug, two zero bytes, sequence, loco_rl, loco_lr.
    """
    req = IrdaReq(
        25,
        PdiCommand.IRDA_RX,
        IrdaAction.CONFIG,
        sequence=IrdaSequence.RECORDING,
        debug=7,
        loco_rl=10,
        loco_lr=20,
    )

    # Human payload shape
    s = req.payload
    assert isinstance(s, str)
    # Be lenient about exact formatting; check key tokens
    assert "Sequence:" in s and "Debug:" in s
    assert "When Engine ID (R -> L):" in s and "When Engine ID (L -> R):" in s

    bs = req.as_bytes
    assert isinstance(bs, (bytes, bytearray))
    assert bs[0] == PDI_SOP
    assert bs[-1] == PDI_EOP

    # Core markers
    assert PdiCommand.IRDA_RX.as_bytes in bs
    assert IrdaAction.CONFIG.as_bytes in bs

    # The CONFIG payload for RX should include:
    #   tmcc_id, debug, 0x00, 0x00, sequence_id, loco_rl, loco_lr
    expected_tail = bytes([req.tmcc_id, 7, 0x00, 0x00, req.sequence_id, 10, 20])
    assert expected_tail in bs


def test_sequence_set_includes_sequence_byte():
    """
    SEQUENCE with SET should serialize the sequence byte.
    """
    req = IrdaReq(10, PdiCommand.IRDA_SET, IrdaAction.SEQUENCE, sequence=IrdaSequence.BELL_NONE)

    s = req.payload
    assert isinstance(s, str)
    assert "Sequence:" in s  # minimal check

    bs = req.as_bytes
    assert bs[0] == PDI_SOP and bs[-1] == PDI_EOP
    assert PdiCommand.IRDA_SET.as_bytes in bs
    assert IrdaAction.SEQUENCE.as_bytes in bs
    # Sequence byte must appear in the packet
    assert IrdaSequence.BELL_NONE.value.to_bytes(1, "big") in bs


def test_identify_set_includes_ident_byte():
    """
    IDENTIFY with SET should serialize the ident byte.
    """
    req = IrdaReq(9, PdiCommand.IRDA_SET, IrdaAction.IDENTIFY, ident=0x55)
    bs = req.as_bytes
    assert bs[0] == PDI_SOP and bs[-1] == PDI_EOP
    assert PdiCommand.IRDA_SET.as_bytes in bs
    assert IrdaAction.IDENTIFY.as_bytes in bs
    assert (0x55).to_bytes(1, "big") in bs


def test_get_requests_have_minimal_payload_for_config():
    """
    GET requests should not include the additional CONFIG body bytes.
    """
    req = IrdaReq(
        19,
        PdiCommand.IRDA_GET,
        IrdaAction.CONFIG,
        sequence=IrdaSequence.CROSSING_GATE_NONE,
        debug=2,
        loco_rl=1,
        loco_lr=2,
    )
    bs = req.as_bytes
    assert bs[0] == PDI_SOP and bs[-1] == PDI_EOP
    assert PdiCommand.IRDA_GET.as_bytes in bs
    assert IrdaAction.CONFIG.as_bytes in bs

    # Ensure the characteristic CONFIG body pattern is absent for GET
    unexpected_tail = bytes([req.tmcc_id, 2, 0x00, 0x00, IrdaSequence.CROSSING_GATE_NONE.value, 1, 2])
    assert unexpected_tail not in bs
