"""Toolkit-independent presentation package for PyTrain.

The UI package depends on :mod:`pytrain`; core PyTrain code must not depend on
this package. Concrete GUI implementations live in subpackages such as
:mod:`pytrain_ui.qt`.
"""

from .contracts import CabCommandPort, CabStatePort, EngineViewState, StateListener

__all__ = ["CabCommandPort", "CabStatePort", "EngineViewState", "StateListener"]
