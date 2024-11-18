"""
Simple examples of how to associate Lionel commands to Raspberry Pi buttons
"""

from src.gpio.gpio_handler import GpioHandler

# GpioHandler.when_button_held(26, TMCC2EngineCommandDef.BLOW_HORN_ONE)
# GpioHandler.when_button_pressed(21, TMCC2RouteCommandDef.FIRE, 10)

# rev = CommandReq(TMCC2EngineCommandDef.REVERSE_DIRECTION, 18)
# fwd = CommandReq(TMCC2EngineCommandDef.FORWARD_DIRECTION, 18)
# GpioHandler.when_toggle_switch(13, 19, rev, fwd, led_pin=20)
# GpioHandler.when_toggle_button_pressed(19,  on, led_pin=20)

# GpioHandler.when_pot(TMCC2EngineCommandDef.ABSOLUTE_SPEED, 18)

# GpioHandler.switch(10,
#                    thru_pin=26,
#                    out_pin=19,
#                    thru_led_pin=13,
#                    out_led_pin=6,
#                    cathode=False)

# GpioHandler.route(15, 21, 20)

# GpioHandler.accessory(10, 26, 19, 13, cathode=False)
# GpioHandler.power_district(15, 25, 21, 20)
# GpioHandler.culvert_loader(11, cycle_pin=5, cycle_led_pin=20)
# GpioHandler.smoke_fluid_loader(12, channel=0, dispense_pin=21, lights_on_pin=26, lights_off_pin=19)
GpioHandler.engine(67, speed_pin_1=19, speed_pin_2=26, fwd_pin=4)
# GpioHandler.gantry_crane(92, 20, 21, 0, 1, 16, 24)
# GpioHandler.base_watcher("192.168.3.124", 5, 6)

# GpioHandler.crane_car(91, 20, 21, 0, 16, bh_pin=25, bo_led_pin=23, bh_led_pin=24)
GpioHandler.controller(
    row_pins=[18, 23, 24, 25],
    column_pins=[12, 16, 20, 21],
    speed_pins=[19, 26],
    fwd_pin=4,
    lcd_address=0x27,
    num_rows=2,
    num_columns=16,
)

print("Buttons registered...")
