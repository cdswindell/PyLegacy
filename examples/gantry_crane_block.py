# noinspection PyUnresolvedReferences,PyPackageRequirements
from pytrain import PowerDistrict, GantryCrane, Switch

g = GantryCrane(
    address=87,
    cab_left_pin=20,
    cab_right_pin=21,
    ro_left_pin=12,
    ro_right_pin=16,
    bo_down_pin=8,
    bo_up_pin=7,
    mag_pin=23,
    led_pin=24,
    cab_rotary_encoder=True,
)

pd13 = PowerDistrict(
    13,
    on_pin=17,
    off_pin=27,
    on_led_pin=22,
)

pd14 = PowerDistrict(
    14,
    on_pin=10,
    off_pin=9,
    on_led_pin=11,
)

sw1 = Switch(
    1,
    thru_pin=5,
    out_pin=6,
    thru_led_pin=13,
    out_led_pin=19,
)
