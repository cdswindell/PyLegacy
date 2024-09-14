from signal import pause

from src.gpio.gpio_handler import GpioHandler
from src.protocol.command_req import CommandReq
from src.protocol.constants import TMCC2EngineCommandDef, TMCC2RouteCommandDef, TMCC1AuxCommandDef

"""
    Simple examples of how to associate Lionel commands to Raspberry Pi buttons
"""
GpioHandler.when_button_held(26, TMCC2EngineCommandDef.BLOW_HORN_ONE)

GpioHandler.when_button_pressed(21, TMCC2RouteCommandDef.ROUTE, 10)

off = CommandReq(TMCC1AuxCommandDef.AUX2_OPTION_ONE, 9)
on = CommandReq(TMCC1AuxCommandDef.AUX1_OPTION_ONE, 9)
GpioHandler.when_toggle_switch(13, 19, off, on, 20)


print("Buttons registered...")

pause()
