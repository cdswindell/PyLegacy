"""
    Lionel PDI Command Protocol Constants
"""
# General constants
PDI_SOP: int = 0xd1
PDI_STF: int = 0xde
PDI_EOP: int = 0xdf

# Keep-alive message
KEEP_ALIVE: bytes = bytes([0xD1, 0x29, 0xD7, 0xDF])
KEEP_ALIVE_STR: str = KEEP_ALIVE.hex()


# Command Definitions
TMCC_TX: int = 0x27
TMCC_RX: int = 0x28
