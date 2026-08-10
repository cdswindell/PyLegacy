from types import SimpleNamespace

from src.pytrain.gui.accessories.station_gui import StationGui


def test_build_accessory_controls_clears_stale_button_references_before_remount() -> None:
    station = StationGui.__new__(StationGui)
    station._empty_label = "Depart"
    station._full_label = "Arrive"
    station._empty_image = "empty.png"
    station._full_image = "full.png"
    station.power_state = SimpleNamespace(tmcc_id=1)
    station.platform_state = SimpleNamespace(tmcc_id=2)
    stale_power = SimpleNamespace(name="stale power")
    stale_platform = SimpleNamespace(name="stale platform")
    station.power_button = stale_power
    station.platform_button = stale_platform
    station._cfg = SimpleNamespace(labels_for=lambda *_args: ("Power", "Platform"))

    state_updates: list[object] = []
    created: list[SimpleNamespace] = []

    def make_power_button(state, *_args, **_kwargs):
        button = SimpleNamespace(tmcc_id=state.tmcc_id)
        created.append(button)
        station.after_state_change(None, state)
        return button

    station.make_power_button = make_power_button
    station.is_active = lambda _state: False
    station.gate_widget_on_power = lambda _state, widget: state_updates.append(widget)
    station.set_button_active = lambda widget: state_updates.append(widget)
    station.set_button_inactive = lambda widget: state_updates.append(widget)

    station.build_accessory_controls(SimpleNamespace())

    assert stale_power not in state_updates
    assert stale_platform not in state_updates
    assert station.power_button is created[0]
    assert station.platform_button is created[1]
