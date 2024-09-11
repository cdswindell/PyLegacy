from signal import pause

from src.gpio.gpio_handler import GpioHandler
from src.protocol.constants import TMCC2EngineCommandDef, TMCC2RouteCommandDef, TMCC1AuxCommandDef

"""
    Simple examples of how to associate Lionel commands to Raspberry Pi buttons
"""
GpioHandler.when_button_held(26, TMCC2EngineCommandDef.BLOW_HORN_ONE)

GpioHandler.when_button_pressed(21, TMCC2RouteCommandDef.ROUTE, 10)

GpioHandler.when_button_pressed(19, TMCC1AuxCommandDef.AUX1_OPTION_ONE, 9)
GpioHandler.when_button_pressed(13, TMCC1AuxCommandDef.AUX2_OPTION_ONE, 9)

pause()
