"""
Simple examples of how to associate Lionel commands to Raspberry Pi buttons
"""

from src.pytrain import Controller

"""
Build a train controller component that uses an I2C-connected Keypad and LCD.
"""
Controller.build(
    keypad_address=0x20,
    speed_pins=[17, 27],
    halt_pin=10,
    reset_pin=11,
    horn_pin=5,
    bell_pin=9,
    start_up_pin=21,
    shutdown_pin=20,
    boost_pin=15,
    brake_pin=14,
    fwd_pin=16,
    rev_pin=12,
    rpm_up_pin=8,
    rpm_down_pin=7,
    front_coupler_pin=24,
    rear_coupler_pin=25,
    vol_up_pin=26,
    vol_down_pin=19,
    tower_dialog_pin=13,
    engr_dialog_pin=6,
    quilling_horn_chn=0,
    base_online_pin=23,
    base_offline_pin=4,
    lcd_address=0x27,
    lcd_rows=4,
    lcd_cols=20,
)
