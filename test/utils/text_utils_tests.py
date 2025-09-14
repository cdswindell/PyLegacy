#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

# Python

from src.pytrain.utils.text_utils import title


def test_none_and_empty():
    assert title(None) is None  # type: ignore[arg-type]
    assert title("") == ""


def test_sd70ace_variants_compact_and_split():
    # Compact forms
    assert title("sd70ace") == "SD70ACe"
    assert title("SD70AC") == "SD70ACe"

    # Split forms
    assert title("sd-70 ace") == "SD70ACe"
    assert title("sd70 ace") == "SD70ACe"

    # Extra spaces should be normalized
    assert title("  sd70   ace  ") == "SD70ACe"


def test_sd80mac_variants_compact_and_split():
    # Compact forms
    assert title("sd80mac") == "SD80MAC"

    # Split forms
    assert title("sd-80 mac") == "SD80MAC"
    assert title("sd80 mac") == "SD80MAC"

    # Extra spaces should be normalized
    assert title("  sd80   mac  ") == "SD80MAC"


def test_preserve_series_codes_and_patterns():
    # Should remain uppercase as-is for these prefixes/patterns
    assert title("fa-2") == "FA-2"
    assert title("rs-11") == "RS-11"
    assert title("gp40") == "GP40"
    assert title("gp9") == "GP9"  # length <= 3 path (remains upper)
    assert title("u33c") == "U33C"  # matches [A-Z]\d{2}[A-Z]


def test_general_capitalization_and_short_words():
    # Words with length > 3 are capitalized (first letter upper, rest lower)
    assert title("hello WORLD") == "Hello World"

    # Selected short words are capitalized (not kept uppercase)
    assert title("and bee car dry ice man new old pad rio to") == "And Bee Car Dry Ice Man New Old Pad Rio To"

    # Mixed phrase showing both rules
    assert title("new york central") == "New York Central"


def test_multi_word_mixed_cases():
    # Ensure capitalization logic applies per-token and preserves intended exceptions
    assert title("rio grande western") == "Rio Grande Western"
    # Note: words not in the short-word list and <= 3 chars remain uppercase
    assert title("rio and western") == "Rio And Western"
