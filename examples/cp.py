from src.gpio.gpio_handler import GpioHandler
from src.protocol.constants import TMCC2EngineCommandDef

GpioHandler.when_button_held(26, TMCC2EngineCommandDef.BLOW_HORN_ONE)
