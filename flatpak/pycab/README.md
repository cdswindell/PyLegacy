# PyCab Flatpak prototype

This packages the existing SteamDeckGui as a Flatpak using the hardware access
already proven by the DeckInfo Flatpak.

It currently targets Freedesktop 26.08, builds Tcl/Tk 8.6.18 with Xft support,
and builds Python 3.14.8 inside /app so tkinter is independent of SteamOS.
Top-level Python dependencies are exactly pinned in requirements-pinned.txt;
zeroconf is pinned to 0.151.5.

## Build and install on Steam Deck

From the PyLegacy repository root:

```bash
git fetch
git switch flatpak-pycab
git pull

flatpak run org.flatpak.Builder \
    --user \
    --install \
    --force-clean \
    flatpak/pycab/build-dir \
    flatpak/pycab/io.github.cdswindell.PyCab.yml
```

The Freedesktop 26.08 Platform/SDK and Flatpak Builder may remain system
installations; PyCab itself is installed per-user.

## Run from Desktop Mode / SSH

```bash
flatpak run io.github.cdswindell.PyCab
```

The launcher starts PyTrain in client mode with cache synchronization enabled
and the 1280x800 SteamDeckGui. It uses the bundled default controller profile.

## Prototype notes

The DeckInfo proof established that --device=all exposes the Steam Deck's raw
hidraw input path as well as SDL/pygame. Keep that broad permission until PyCab
itself has been validated.

The dependency versions are pinned, but this prototype still permits network
access during the Python dependency build. After the full GUI, discovery, cache
sync, and train control are proven, generate offline Flatpak Python sources with
hashes for a reproducible distributable build.
