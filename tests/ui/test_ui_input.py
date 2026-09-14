from pytrain_ui.input import HoldGesture, RateThrottle, RepeatGate


def test_rate_throttle_is_center_return_and_cumulative() -> None:
    throttle = RateThrottle(dead_zone=0.25, min_step=1, max_step=5)

    assert throttle.delta(0.0) == 0
    assert throttle.delta(0.2) == 0
    assert throttle.delta(0.26) == 1
    assert throttle.delta(1.0) == 5
    assert throttle.delta(-1.0) == -5


def test_repeat_gate_resets_immediately() -> None:
    gate = RepeatGate(0.2)

    assert gate.ready(1.0) is True
    assert gate.ready(1.1) is False
    assert gate.ready(1.2) is True
    gate.reset()
    assert gate.ready(1.21) is True


def test_hold_gesture_distinguishes_short_and_long_press() -> None:
    gesture = HoldGesture(0.75)

    gesture.press(1.0)
    assert gesture.poll(1.5) is False
    assert gesture.release(1.5) is True

    gesture.press(2.0)
    assert gesture.poll(2.75) is True
    assert gesture.poll(2.8) is False
    assert gesture.release(2.9) is False
