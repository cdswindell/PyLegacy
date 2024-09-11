from signal import pause

from src.gpio.gpio_handler import GpioHandler
from src.protocol.constants import TMCC2EngineCommandDef, TMCC2RouteCommandDef

GpioHandler.when_button_held(26, TMCC2EngineCommandDef.BLOW_HORN_ONE)

GpioHandler.when_button_pressed(21, TMCC2RouteCommandDef.ROUTE, 10)

pause()
