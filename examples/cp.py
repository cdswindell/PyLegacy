from signal import pause

from src.gpio.gpio_handler import GpioHandler
from src.protocol.constants import TMCC2EngineCommandDef, TMCC2RouteCommandDef

"""
    Simple examples of how to associate Lionel commands to Raspberry Pi buttons
"""
b = GpioHandler.when_button_held(26, TMCC2EngineCommandDef.BLOW_HORN_ONE)
print(b)

b = GpioHandler.when_button_pressed(21, TMCC2RouteCommandDef.ROUTE, 10)
print(b)

pause()
