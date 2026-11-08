"""Policy for in-place PyTrain updates managed by external packaging."""

import os


def self_update_disabled() -> bool:
    """True when the distributor, rather than PyTrain, owns application updates."""
    return os.environ.get("PYTRAIN_DISABLE_SELF_UPDATE", "").lower() in {"1", "true", "yes", "on"}
