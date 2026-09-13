"""Toolkit-independent presentation package for PyTrain.

The UI package depends on :mod:`pytrain`; core PyTrain code must not depend on
this package. Concrete GUI implementations live in subpackages such as
:mod:`pytrain_ui.qt`.
"""

from .contracts import CabCommandPort, CabStatePort, EngineViewState, StateListener
from .profiles import EngineControlProfile, resolve_engine_control_profile

__all__ = [
    "CabCommandPort",
    "CabStatePort",
    "EngineControlProfile",
    "EngineViewState",
    "StateListener",
    "resolve_engine_control_profile",
]
