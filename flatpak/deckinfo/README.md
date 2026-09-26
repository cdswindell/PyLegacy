# Steam Deck Flatpak input probe

This is a local proof-of-concept Flatpak for `scripts/deckinfo.py`. It tests both
SDL/pygame controller events and PyTrain's direct `/dev/hidraw*` Steam Deck input
path from inside a Flatpak sandbox.

## Build on the Steam Deck

Run these commands from the root of the PyLegacy checkout:

```bash
flatpak install --user flathub org.freedesktop.Platform//25.08 org.freedesktop.Sdk//25.08
flatpak install --user flathub org.flatpak.Builder

flatpak run org.flatpak.Builder --user --install --force-clean \
  flatpak/deckinfo/build-dir flatpak/deckinfo/io.github.cdswindell.PyTrain.DeckInfo.yml
```

The prototype intentionally permits network access while building so pip can obtain
`pygame-ce`. This should be replaced with pinned offline sources before distribution.

## Run

```bash
flatpak run io.github.cdswindell.PyTrain.DeckInfo
```

Exercise the face buttons, D-pad, sticks, triggers, rear paddles, and both trackpads.
The important raw-HID success indicators are output similar to:

```text
Steam Deck controller hidraw nodes: /dev/hidrawN
HIDRAW /dev/hidrawN first report (64 bytes): ...
HIDRAW /dev/hidrawN BUTTON DOWN: ...
HIDRAW /dev/hidrawN LEFT pad ...
HIDRAW /dev/hidrawN RIGHT pad ...
```

If the controller is visible through SDL but the raw-HID lines report an open or
permission error, the Flatpak boundary is the part we need to adjust.

## Remove the probe

```bash
flatpak uninstall io.github.cdswindell.PyTrain.DeckInfo
```

This package deliberately uses `--device=all` because its purpose is to determine
whether the existing PyTrain direct-hardware implementation works inside Flatpak.
The eventual PyCab Flatpak can use the narrowest permissions proven to work here.
