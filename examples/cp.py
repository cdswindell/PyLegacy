from signal import pause

from src.gpio.gpio_handler import GpioHandler
from src.protocol.command_req import CommandReq
from src.protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandDef, TMCC1EngineCommandDef
from src.protocol.tmcc2.tmcc2_constants import TMCC2RouteCommandDef, TMCC2EngineCommandDef

"""
    Simple examples of how to associate Lionel commands to Raspberry Pi buttons
"""
GpioHandler.when_button_held(26, TMCC2EngineCommandDef.BLOW_HORN_ONE)

GpioHandler.when_button_pressed(21, TMCC2RouteCommandDef.ROUTE, 10)

off = CommandReq(TMCC1AuxCommandDef.AUX2_OPTION_ONE, 9)
on = CommandReq(TMCC1AuxCommandDef.AUX1_OPTION_ONE, 9)
GpioHandler.when_toggle_switch(13, 19, off, on, led_pin=20)
# GpioHandler.when_toggle_button_pressed(19,  on, led_pin=20)

GpioHandler.when_pot(TMCC1EngineCommandDef.ABSOLUTE_SPEED, 1, server='192.168.3.35')

print("Buttons registered...")

pause()
