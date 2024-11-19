from ..protocol.constants import CommandScope


class EngineController:
    def __init__(
        self,
        tmcc_id: int = 1,
        scope: CommandScope = CommandScope.ENGINE,
        is_legacy: bool = True,
        halt_pin: int | str = None,
        speed_pin_1: int | str = None,
        speed_pin_2: int | str = None,
        fwd_pin: int | str = None,
        rev_pin: int | str = None,
        toggle_pin: int | str = None,
        start_up_pin: int | str = None,
        shutdown_pin: int | str = None,
        reset_pin: int | str = None,
        boost_pin: int | str = None,
        brake_pin: int | str = None,
        bell_pin: int | str = None,
        horn_pin: int | str = None,
        rpm_up_pin: int | str = None,
        rpm_down_pin: int | str = None,
        momentum_up_pin: int | str = None,
        momentum_diwn_pin: int | str = None,
        vol_up_pin: int | str = None,
        vol_down_pin: int | str = None,
        smoke_up_pin: int | str = None,
        smoke_down_pin: int | str = None,
        train_brake_chn: int | str = None,
    ) -> None:
        pass
