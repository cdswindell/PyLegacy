from pytrain import GantryCrane, PowerDistrict, Switch

g = GantryCrane(
    address=87,
    cab_left_pin=20,
    cab_right_pin=21,
    ro_left_pin=12,
    ro_right_pin=16,
    bo_down_pin=7,
    bo_up_pin=8,
    mag_pin=25,
    led_pin=24,
    cab_rotary_encoder=True,
)

pd14 = PowerDistrict(
    14,
    on_pin=23,
    off_pin=27,
    on_led_pin=22,
)

pd13 = PowerDistrict(
    13,
    on_pin=14,
    off_pin=15,
    on_led_pin=18,
)

sw1 = Switch(
    1,
    thru_pin=5,
    out_pin=6,
    thru_led_pin=13,
    out_led_pin=19,
)
