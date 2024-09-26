from src.gpio.gpio_handler import GpioHandler
from src.protocol.command_req import CommandReq
from src.protocol.tmcc2.tmcc2_constants import TMCC2RouteCommandDef
from src.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandDef

"""
    Simple examples of how to associate Lionel commands to Raspberry Pi buttons
"""
GpioHandler.when_button_held(20, TMCC2EngineCommandDef.BLOW_HORN_ONE)

GpioHandler.when_button_pressed(21, TMCC2RouteCommandDef.FIRE, 10)

rev = CommandReq(TMCC2EngineCommandDef.REVERSE_DIRECTION, 65)
fwd = CommandReq(TMCC2EngineCommandDef.FORWARD_DIRECTION, 65)
GpioHandler.when_toggle_switch(26, 16, rev, fwd, led_pin=19)
# GpioHandler.when_toggle_button_pressed(19,  on, led_pin=20)

GpioHandler.when_pot(TMCC2EngineCommandDef.ABSOLUTE_SPEED, 65)

print("Buttons registered...")
