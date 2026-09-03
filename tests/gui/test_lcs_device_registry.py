"""
The LCS device registry: its shape, its lookups, and the conventions it names modes by.

No mode's wording is written down here. A mode's name, its qualifier, its note and both
of its labels are read off the registry and asserted as *compositions* -- a label is the
mode's own name and the registry's one spelling of the block it claims, in that order --
so renaming a mode or rewording a note needs no edit in this file, while a mode that
breaks a naming rule fails wherever it is added.

Two pieces of vocabulary are written down, both deliberately and both in one place each:

* TestModeNames.CAB_KEYS -- ACC, SW and TR, which are printed on the Cab remote rather
  than chosen by this project.
* "TMCC ID" / "TMCC IDs", asserted by the rule tests in TestTmccIdText and
  TestModeLabels: the registry's docstring insists that what is counted is always a
  TMCC ID, never bare "IDs" and never "ports", and a convention is worth nothing if no
  test knows what it says.
"""

from __future__ import annotations

import re

import pytest

import src.pytrain.gui.controller.lcs_device_registry as reg
from src.pytrain.gui.controller.engine_gui_conf import SENSOR_TRACK_OPTS
from src.pytrain.pdi.irda_req import IrdaSequence
from src.pytrain.pdi.pdi_device import PdiDevice
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum, TMCC1EngineCommandEnum


class TestRegistryShape:
    def test_the_registry_knows_five_modules(self):
        assert tuple(d.key for d in reg.LCS_DEVICES) == ("asc2", "bpc2", "stm2", "sensor_track", "amc2")

    def test_four_of_them_can_be_programmed(self):
        assert tuple(d.key for d in reg.configurable_devices()) == ("asc2", "bpc2", "sensor_track", "stm2")

    def test_they_are_offered_in_name_order(self):
        # The device page opens on the first of them, so the order has to be predictable.
        labels = [d.label for d in reg.configurable_devices()]
        assert labels == sorted(labels, key=str.upper)
        # Named by identity rather than by label, so a module renamed on the page is not a
        # test to fix -- what matters is which module the panel opens on.
        assert reg.configurable_devices()[0] is reg.ASC2

    def test_the_recognition_order_is_left_alone(self):
        # LCS_DEVICES is walked to identify a module from its state flags. A module this
        # pass cannot program must not be recognized ahead of one it can, so it stays last
        # however the presentation order is sorted.
        assert reg.LCS_DEVICES[-1] is reg.AMC2

    def test_every_mode_is_complete(self):
        for device in reg.configurable_devices():
            assert device.modes
            for mode in device.modes:
                assert isinstance(mode.scope, CommandScope)
                assert mode.ports >= 1
                assert mode.presses, f"{device.key}/{mode.key} declares no presses"

    def test_asc2_has_four_modes(self):
        assert len(reg.ASC2.modes) == 4
        assert [m.ports for m in reg.ASC2.modes] == [8, 1, 4, 4]
        assert [m.pdi_mode for m in reg.ASC2.modes] == [0, 1, 2, 3]
        assert [m.scope for m in reg.ASC2.modes] == [
            CommandScope.ACC,
            CommandScope.ACC,
            CommandScope.SWITCH,
            CommandScope.SWITCH,
        ]

    def test_bpc2_one_id_modes_are_reserved(self):
        reserved = [reg.BPC2.mode(key) for key in ("tr_1", "acc_1")]
        for mode in reserved:
            assert mode.enabled is False
            # Each says why it is not on offer -- the panel prints those words in its
            # "Not available" line -- and both say the same thing, since it is the same
            # reason. The sentence itself is the registry's to change.
            assert mode.note
        assert len({mode.note for mode in reserved}) == 1
        assert [m.key for m in reg.enabled_modes(reg.BPC2)] == ["tr_8", "acc_8"]
        assert reg.BPC2.mode("tr_8").scope == CommandScope.TRAIN
        assert reg.BPC2.mode("acc_8").scope == CommandScope.ACC

    def test_stm2_modes(self):
        assert reg.STM2.mode("single_wire").ports == 16
        assert reg.STM2.mode("two_wire").ports == 8
        assert all(m.scope == CommandScope.SWITCH for m in reg.STM2.modes)

    def test_pdi_devices(self):
        assert reg.ASC2.pdi_device == PdiDevice.ASC2
        assert reg.BPC2.pdi_device == PdiDevice.BPC2
        assert reg.STM2.pdi_device == PdiDevice.STM2
        assert reg.SENSOR_TRACK.pdi_device == PdiDevice.IRDA


class TestSensorTrack:
    def test_single_acc_mode(self):
        assert len(reg.SENSOR_TRACK.modes) == 1
        mode = reg.SENSOR_TRACK.modes[0]
        assert mode.scope == CommandScope.ACC
        assert mode.ports == 1
        assert mode.pdi_mode is None

    def test_action_choices_track_sensor_track_opts(self):
        option = reg.SENSOR_TRACK.option("action")
        assert option.required is True
        assert option.kind == reg.OptionKind.RADIO
        assert len(option.choices) == 10
        assert [label for label, _ in option.choices] == [label for label, _ in SENSOR_TRACK_OPTS]
        assert [value.value for _, value in option.choices] == list(range(10))
        assert all(isinstance(value, IrdaSequence) for _, value in option.choices)

    def test_default_action_is_no_action(self):
        assert reg.SENSOR_TRACK.option("action").default == IrdaSequence.NONE


class TestMaxBase:
    @pytest.mark.parametrize(
        "device, mode_key, expected",
        [
            (reg.ASC2, "acc_8", 91),
            (reg.ASC2, "acc_1", 98),
            (reg.ASC2, "sw_momentary", 95),
            (reg.ASC2, "sw_latching", 95),
            (reg.STM2, "single_wire", 83),
            (reg.STM2, "two_wire", 91),
            (reg.SENSOR_TRACK, "acc", 98),
        ],
    )
    def test_max_base(self, device, mode_key, expected):
        mode = device.mode(mode_key)
        assert reg.max_base(mode) == expected
        assert mode.max_base == expected

    def test_never_above_98(self):
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                assert 1 <= reg.max_base(mode) <= 98


class TestAmc2:
    """
    Recognized so that the panel can name it and count the TMCC IDs it holds, but not
    programmable until its modes and presses are written.
    """

    def test_it_is_in_the_registry(self):
        assert reg.AMC2 in reg.LCS_DEVICES
        # Named, because the panel reports it in the Currently Assigned box; which name is
        # the registry's business.
        assert reg.AMC2.label
        assert reg.AMC2.pdi_device == PdiDevice.AMC2

    def test_it_is_not_offered_as_a_choice(self):
        assert reg.AMC2.configurable is False
        assert reg.AMC2 not in reg.configurable_devices()

    def test_it_declares_no_modes_yet(self):
        assert reg.AMC2.modes == ()
        # Asking for a mode it does not have says why rather than raising IndexError.
        with pytest.raises(ValueError, match="no modes"):
            _ = reg.AMC2.default_mode

    def test_it_is_recognized_from_its_own_state_flag(self):
        class _Amc2:
            is_asc2 = False
            is_bpc2 = False
            is_stm2 = False
            is_sensor_track = False
            is_amc2 = True

        assert reg.device_for_state(_Amc2()) is reg.AMC2

    def test_every_other_module_is_still_programmable(self):
        assert all(device.configurable for device in reg.LCS_DEVICES if device is not reg.AMC2)


class TestLookups:
    def test_device_for_key(self):
        assert reg.device_for_key("bpc2") is reg.BPC2
        # Recognized modules are found by key too; only an unknown key raises.
        assert reg.device_for_key("amc2") is reg.AMC2
        with pytest.raises(ValueError):
            reg.device_for_key("asc3")

    def test_device_for_state(self):
        class _State:
            is_asc2 = False
            is_bpc2 = True
            is_stm2 = False
            is_sensor_track = False

        assert reg.device_for_state(_State()) is reg.BPC2
        assert reg.device_for_state(None) is None
        assert reg.device_for_state(object()) is None

    def test_devices_for_state_names_every_module_a_shared_record_identifies(self):
        # A component state is keyed by scope and address alone, so an AMC2 and a BPC2 both
        # answering to ACC 1 leave one record carrying both flags.
        class _Shared:
            is_asc2 = False
            is_bpc2 = True
            is_stm2 = False
            is_sensor_track = False
            is_amc2 = True

        assert reg.devices_for_state(_Shared()) == (reg.BPC2, reg.AMC2)
        assert reg.devices_for_state(None) == ()
        assert reg.devices_for_state(object()) == ()

    def test_device_for_pdi_device(self):
        assert reg.device_for_pdi_device(PdiDevice.IRDA) is reg.SENSOR_TRACK
        assert reg.device_for_pdi_device(PdiDevice.AMC2) is reg.AMC2
        assert reg.device_for_pdi_device(PdiDevice.BASE) is None

    def test_mode_for_pdi_mode(self):
        assert reg.ASC2.mode_for_pdi_mode(3).key == "sw_latching"
        assert reg.ASC2.mode_for_pdi_mode(7) is None

    def test_default_mode_skips_disabled(self):
        assert reg.BPC2.default_mode.key == "tr_8"

    def test_unknown_option_raises(self):
        with pytest.raises(ValueError):
            reg.ASC2.option("restore")


class TestAuxNumber:
    def test_acc_scope(self):
        assert reg.aux_number(0, CommandScope.ACC) == TMCC1AuxCommandEnum.AUX_NUMBER_0
        assert reg.aux_number(9, CommandScope.ACC) == TMCC1AuxCommandEnum.AUX_NUMBER_9

    def test_train_scope(self):
        assert reg.aux_number(0, CommandScope.TRAIN) == TMCC1EngineCommandEnum.AUX_NUMBER_0

    def test_invalid(self):
        with pytest.raises(ValueError):
            reg.aux_number(10, CommandScope.ACC)
        with pytest.raises(ValueError):
            reg.aux_number(1, CommandScope.SWITCH)


class TestTmccIdText:
    """
    The one spelling of a block of addresses, read by both label forms and by the panel's
    Currently Assigned and Overlaps rows.

    Asserted by its rules rather than by repeating the phrases it builds: a block names
    both of its ends, one address is never spoken of as several, and what is counted is
    always a TMCC ID. Reword the phrase and these still hold; break one of the rules and
    they do not.
    """

    def test_a_block_is_named_by_its_two_ends(self):
        assert re.findall(r"\d+", reg.tmcc_id_text(12, 19)) == ["12", "19"]

    def test_a_single_address_is_named_once(self):
        # Given as a block of one, or with no end at all: both are one address, and an
        # operator is not shown the two ends of a block of one.
        assert reg.tmcc_id_text(12, 12) == reg.tmcc_id_text(12)
        assert re.findall(r"\d+", reg.tmcc_id_text(12)) == ["12"]

    def test_an_end_below_the_base_is_a_single_address(self):
        # Nothing builds one, but a block cannot run backwards, and the alternative is a
        # row that counts down.
        assert reg.tmcc_id_text(12, 9) == reg.tmcc_id_text(12)

    def test_a_count_is_a_digit(self):
        assert re.findall(r"\d+", reg.tmcc_id_count(8)) == ["8"]

    def test_one_address_is_never_plural(self):
        for text in (reg.tmcc_id_text(12), reg.tmcc_id_text(12, 12), reg.tmcc_id_count(1)):
            assert not re.search(r"\bIDs\b", text), text

    def test_more_than_one_address_always_is(self):
        for text in (reg.tmcc_id_text(12, 19), reg.tmcc_id_count(8)):
            assert re.search(r"\bIDs\b", text), text

    def test_what_is_counted_is_always_a_tmcc_id(self):
        # The convention the registry's docstring sets out: never bare "IDs", never
        # "ports", either of which is ambiguous beside a PDI address or a port number.
        # One of the two places in this file where a term is written down at all.
        for text in (reg.tmcc_id_text(12), reg.tmcc_id_text(12, 19), reg.tmcc_id_count(1), reg.tmcc_id_count(8)):
            assert not re.findall(r"(?<!TMCC )\bIDs?\b", text), text


class TestModeNames:
    """
    The naming conventions the module docstring sets out: a mode opens with the Cab key
    that begins its programming sequence, parenthesizes whatever tells it from the
    module's other modes on that key, and says nothing about how many addresses it takes.

    The names are read off the registry and the conventions asserted over them, so a mode
    renamed or a note reworded is not a test to fix -- and a mode added in breach of a
    rule fails here rather than on the Pi.
    """

    # The three keys on the Cab remote. The one piece of vocabulary the registry does not
    # own -- they are printed on the handset -- and so the one written down here. The
    # panel's SCOPE_LABEL has to spell them the same way, which the panel's own tests check
    # by joining the legend above the Mode radios to the rows below it.
    CAB_KEYS = {CommandScope.ACC: "ACC", CommandScope.SWITCH: "SW", CommandScope.TRAIN: "TR"}

    def test_every_offered_mode_is_named(self):
        for device in reg.configurable_devices():
            for mode in reg.enabled_modes(device):
                assert mode.name.strip(), f"{device.key}/{mode.key} goes unnamed"

    def test_no_two_modes_a_module_offers_are_named_alike(self):
        # Two radio rows reading the same thing are a choice the operator cannot make,
        # which is the whole reason a qualifier exists. Read over the modes the panel
        # offers: the BPC2's reserved single-ID modes do repeat the name of the eight-ID
        # mode on their key, and that is harmless because they are never on screen.
        for device in reg.configurable_devices():
            names = [mode.name for mode in reg.enabled_modes(device)]
            assert len(set(names)) == len(names), f"{device.key}: {names}"

    def test_a_name_opens_with_its_cab_key(self):
        # The key that begins the programming sequence, spelled the way the remote spells
        # it and standing alone at the head of the row, which is also how the legend above
        # the radios names it.
        for device in reg.configurable_devices():
            for mode in device.modes:
                assert mode.name.split()[0] == self.CAB_KEYS[mode.scope], f"{device.key}/{mode.key}: {mode.name}"

    def test_a_key_is_spelled_one_way_throughout(self):
        # However the keys come to be spelled, every mode addressed in a scope opens with
        # the same word for it: one module's rows are read down the Mode box, and the
        # Currently Assigned rows below them name the same keys over again.
        spellings: dict[CommandScope, set[str]] = {}
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                spellings.setdefault(mode.scope, set()).add(mode.name.split()[0])
        assert all(len(words) == 1 for words in spellings.values()), spellings

    def test_a_name_is_a_key_and_at_most_one_qualifier(self):
        # Whatever tells this mode from the module's others on its key follows the key in
        # parentheses, reads as the aside it is rather than as a second word of the key,
        # and is what `qualifier` reads back -- which is how the panel looks the mode's
        # note up under the very word the row it explains carries.
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                key = mode.name.split()[0]
                expected = key if mode.qualifier is None else f"{key} ({mode.qualifier})"
                assert mode.name == expected, f"{device.key}/{mode.key}: {mode.name}"

    def test_a_mode_is_qualified_exactly_when_its_key_offers_a_choice(self):
        # A qualifier earns its room on the row by telling two modes on one key apart, so
        # a module offering one mode per key -- the BPC2, the Sensor Track -- has nothing
        # to tell apart and says nothing. Read over the modes the panel offers, for the
        # reason given above: a reserved mode is never beside anything.
        for device in reg.configurable_devices():
            offered = list(reg.enabled_modes(device))
            for mode in offered:
                shares_key = len([other for other in offered if other.scope is mode.scope]) > 1
                assert (mode.qualifier is not None) is shares_key, f"{device.key}/{mode.key}: {mode.name}"

    def test_a_qualifier_is_one_word(self):
        # A radio row is as wide as its label, so the qualifier can say which mode this is
        # and little else; what the mode is good for is the note's business.
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                if mode.qualifier is None:
                    continue
                assert " " not in mode.qualifier, f"{device.key}/{mode.key}: {mode.name}"

    def test_the_asc2_accessory_modes_are_told_apart_by_what_they_are_for(self):
        # Neither purpose can be read off the block the mode claims, and the two modes are
        # on the same key: one address driving all eight outputs for uncoupling tracks,
        # against eight addresses for whatever is wired to them. So each is qualified by
        # what it is for, the count is left to the row's tail, and the rest is said by the
        # note the panel prints under the radios -- all three of them the registry's own
        # words, which is why what is asserted here is that each mode has them.
        mixed, uncouple = reg.ASC2.mode("acc_8"), reg.ASC2.mode("acc_1")

        assert mixed.scope is uncouple.scope, "the pair is on one key or there is nothing to tell apart"
        assert (mixed.ports, uncouple.ports) == (8, 1)
        assert (mixed.pdi_mode, uncouple.pdi_mode) == (0, 1)
        assert mixed.qualifier and uncouple.qualifier
        assert mixed.qualifier != uncouple.qualifier
        for mode in (mixed, uncouple):
            assert mode.note, f"{mode.key} says nothing about what it is for"

    def test_a_name_counts_nothing(self):
        # The count is the label's business, and a name that carried one would say it
        # twice beside the block ids_label names.
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                assert not re.search(r"\d", mode.name), f"{device.key}/{mode.key}: {mode.name}"
                assert not re.search(r"\bIDs?\b", mode.name), f"{device.key}/{mode.key}: {mode.name}"

    def test_the_asc2_switch_modes_key_keeps_a_word_the_operator_never_reads(self):
        # The key keeps the word asc2_req.py and the flowchart use for mode 2, so the code
        # and the manual agree; what the operator reads is what the switch motor is
        # actually given. The word is taken off the key rather than written here, so a
        # rewording cannot leave this test quoting the old one.
        mode = reg.ASC2.mode("sw_momentary")
        key_word = mode.key.split("_")[-1]

        assert mode.qualifier
        for label in (mode.name, mode.ports_label, mode.ids_label(1)):
            assert key_word not in label.lower(), label
        # And the press that tells this mode from its latching sibling is the very thing
        # the qualifier names, so the row and the review page say one word between them.
        assert [press.note for press in mode.presses] == [None, mode.qualifier]

    def test_a_name_says_nothing_a_mode_does_besides_claiming_addresses(self):
        # A radio row is as wide as its label, and the panel is a portrait pane. The Sensor
        # Track's Action Command is set in the same gesture as its ID, and naming both asks
        # 751 px of the 714 px the pane gives a row at the Pi's 1.5x font scale -- even with
        # the key abbreviated -- losing 18 px off each end. It is the whole of the options
        # page that follows instead, so no mode's name says what its module's own options
        # say.
        for device in reg.configurable_devices():
            for mode in device.modes:
                assert len(mode.name.split()) <= 2, f"{device.key}/{mode.key}: {mode.name}"
                for option in device.options:
                    for word in option.label.split():
                        assert word.lower() not in mode.name.lower(), f"{device.key}/{mode.key}: {mode.name}"


class TestModeLabels:
    """
    The two labels built from a mode's name: the block it would claim from an entered
    address, and -- where there is no address to name it from -- the count alone.

    Asserted as compositions rather than as sentences repeated here: a label is the mode's
    own name and the registry's one spelling of what it claims, in that order. That stays
    true however either part comes to be worded, which is the whole point of building both
    labels in the registry instead of in the panel.
    """

    def test_every_mode_names_the_block_it_would_claim(self):
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                for base_id in (1, 12, mode.max_base):
                    last_id = base_id + mode.ports - 1
                    expected = f"{mode.name} {reg.tmcc_id_text(base_id, last_id)}"
                    assert mode.ids_label(base_id) == expected, f"{device.key}/{mode.key}"

    def test_every_mode_names_the_count_it_claims(self):
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                assert mode.ports_label == f"{mode.name}, {reg.tmcc_id_count(mode.ports)}", f"{device.key}/{mode.key}"

    def test_a_block_follows_the_address_it_is_based_at(self):
        # The arithmetic, spelled out at both ends of an 8-ID mode's range.
        mode = reg.ASC2.mode("acc_8")
        assert mode.ids_label(12) == f"{mode.name} {reg.tmcc_id_text(12, 19)}"
        assert mode.ids_label(91) == f"{mode.name} {reg.tmcc_id_text(91, 98)}"

    def test_a_mode_is_offered_at_the_highest_base_it_fits(self):
        # The Mode radios are labeled from the ID on the page, which a narrower mode can
        # have carried above this one's ceiling: the 4-ID modes reach 95, and an 8-ID mode
        # based there would run off the end. The label names where choosing it lands, which
        # is what the panel clamps the ID to.
        acc_8, single_wire = reg.ASC2.mode("acc_8"), reg.STM2.mode("single_wire")
        assert acc_8.ids_label(95) == acc_8.ids_label(acc_8.max_base)
        assert re.findall(r"\d+", acc_8.ids_label(95)) == ["91", "98"]
        assert single_wire.ids_label(98) == single_wire.ids_label(single_wire.max_base)
        assert re.findall(r"\d+", single_wire.ids_label(98)) == ["83", "98"]
        # And nothing is named below the first address, whatever it is handed.
        acc_1 = reg.ASC2.mode("acc_1")
        assert acc_1.ids_label(0) == acc_1.ids_label(1)

    def test_an_id_is_always_a_tmcc_id(self):
        # A bare "ID" is ambiguous beside a PDI address or a port number.
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                for label in (mode.ports_label, mode.ids_label(1)):
                    assert not re.findall(r"(?<!TMCC )\bIDs?\b", label), f"{device.key}/{mode.key}: {label}"

    NUMBER_WORDS = ("one", "single", "two", "three", "four", "five", "six", "seven", "eight", "sixteen")

    def test_a_count_is_a_digit(self):
        # "Eight ID" was the old spelling; a digit is read at a glance.
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                for word in re.findall(r"(\w+)\s+TMCC IDs?\b", mode.ports_label):
                    assert word.lower() not in self.NUMBER_WORDS, f"{device.key}/{mode.key}: {mode.ports_label}"

    def test_a_counted_label_agrees_with_the_mode(self):
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                counted = re.search(r"(\d+) TMCC IDs?\b", mode.ports_label)
                assert counted, f"{device.key}/{mode.key}: {mode.ports_label}"
                assert int(counted.group(1)) == mode.ports, f"{device.key}/{mode.key}: {mode.ports_label}"

    def test_the_longest_row_is_the_stm2s_widest_block(self):
        # A radio row is as wide as its label and the panel is a portrait pane, so the
        # widest row any module can ask for is worth pinning: 33 characters as the modes
        # are worded today, which is 671 px of the 714 px the pane gives it at the Pi's
        # 1.5x font scale. The ceiling is what matters, so a shorter wording costs nothing
        # and a longer one has to be measured before it is adopted.
        widest = reg.STM2.mode("single_wire")
        longest = max(
            (mode.ids_label(mode.max_base) for device in reg.configurable_devices() for mode in device.modes),
            key=len,
        )
        assert longest == widest.ids_label(widest.max_base)
        assert len(longest) <= 33

    def test_a_block_covers_exactly_the_ids_the_mode_claims(self):
        # However the mode reads, the two ends of the block are the addresses that go with
        # its port count: an operator reserving them has to be told the truth. Read as the
        # numbers in the label rather than by matching the phrase around them -- a name
        # counts nothing, so every digit in a block label is one of the block's ends.
        for device in reg.configurable_devices():
            for mode in device.modes:
                label = mode.ids_label(1)
                ends = [int(number) for number in re.findall(r"\d+", label)]
                assert ends[-1] - ends[0] + 1 == mode.ports, f"{device.key}/{mode.key}: {label}"

    def test_every_switch_mode_names_the_ids_it_consumes(self):
        # A switch mode reserves a block just as an accessory mode does, and an operator
        # laying out switch IDs has to know which of them go with the choice.
        for device in reg.configurable_devices():
            for mode in device.modes:
                if mode.scope != CommandScope.SWITCH:
                    continue
                assert re.search(rf"\b{mode.ports} TMCC IDs?\b", mode.ports_label), f"{device.key}/{mode.key}"
                assert "TMCC ID" in mode.ids_label(1), f"{device.key}/{mode.key}"
