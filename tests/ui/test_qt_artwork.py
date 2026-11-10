"""Engine artwork trimming preserves originals and meaningful image content."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")
# PySide6 is supplied by the optional qt-gui extra and guarded by importorskip.
# noinspection PyPackageRequirements
from PySide6.QtGui import QColor, QImage, QPainter

from pytrain_ui.qt.artwork import cached_artwork


def write_artwork(path: Path, background: str = "white", top: int = 10, bottom: int = 30) -> bytes:
    image = QImage(60, 40, QImage.Format.Format_ARGB32)
    image.fill(QColor(background))
    painter = QPainter(image)
    painter.fillRect(15, top, 30, bottom - top, QColor("black"))
    painter.end()
    assert image.save(str(path))
    return path.read_bytes()


def test_trims_vertical_white_borders_without_changing_width_or_original(tmp_path: Path) -> None:
    source = tmp_path / "engine.png"
    original = write_artwork(source)
    prepared = cached_artwork(source, directory=tmp_path / "display")
    assert prepared is not None
    result = Path(prepared)
    assert result != source
    trimmed = QImage(str(result))
    assert (trimmed.width(), trimmed.height()) == (60, 24)
    assert trimmed.pixelColor(15, 2) == QColor("black")
    assert source.read_bytes() == original
    modified = result.stat().st_mtime_ns
    assert cached_artwork(source, directory=tmp_path / "display") == str(result)
    assert result.stat().st_mtime_ns == modified


@pytest.mark.parametrize("background", ["#173775", "#d0d0d0"])
def test_preserves_nonwhite_backgrounds(tmp_path: Path, background: str) -> None:
    source = tmp_path / "engine.png"
    write_artwork(source, background)
    assert cached_artwork(source, directory=tmp_path / "display") == str(source)


def test_trims_transparent_borders_and_retains_faint_details(tmp_path: Path) -> None:
    source = tmp_path / "transparent.png"
    write_artwork(source, "transparent")
    image = QImage(str(source))
    image.setPixelColor(30, 4, QColor("#eeeeee"))
    assert image.save(str(source))
    prepared = cached_artwork(source, directory=tmp_path / "display")
    assert prepared is not None
    result = QImage(prepared)
    assert result.height() == 30
    assert result.pixelColor(30, 2) == QColor("#eeeeee")
    assert result.pixelColor(15, 8) == QColor("black")


def test_all_white_artwork_is_left_intact(tmp_path: Path) -> None:
    source = tmp_path / "blank.png"
    image = QImage(60, 40, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    assert image.save(str(source))
    assert cached_artwork(source, directory=tmp_path / "display") == str(source)


def test_source_changes_generate_a_fresh_display_copy(tmp_path: Path) -> None:
    source = tmp_path / "engine.png"
    write_artwork(source)
    stamp = source.stat().st_mtime_ns
    first = cached_artwork(source, directory=tmp_path / "display")
    write_artwork(source, top=5, bottom=35)
    os.utime(source, ns=(stamp + 1_000_000, stamp + 1_000_000))
    second = cached_artwork(source, directory=tmp_path / "display")
    assert second is not None
    assert first != second
    assert QImage(second).height() == 34


def test_cache_write_failure_falls_back_to_original(tmp_path: Path) -> None:
    source = tmp_path / "engine.png"
    original = write_artwork(source)
    with patch("pytrain_ui.qt.artwork.NamedTemporaryFile", side_effect=OSError("Read-only cache")):
        assert cached_artwork(source, directory=tmp_path / "display") == str(source)
    assert source.read_bytes() == original


def test_missing_and_corrupt_artwork_do_not_prevent_display(tmp_path: Path) -> None:
    source = tmp_path / "missing.png"
    assert cached_artwork(source, directory=tmp_path / "display") == str(source)
    source.write_text("Invalid image", encoding="utf-8")
    assert cached_artwork(source, directory=tmp_path / "display") == str(source)
    assert cached_artwork(None, directory=tmp_path / "display") is None


def test_deleted_display_copy_is_rebuilt(tmp_path: Path) -> None:
    source = tmp_path / "engine.png"
    write_artwork(source)
    prepared = cached_artwork(source, directory=tmp_path / "display")
    assert prepared is not None
    result = Path(prepared)
    assert result != source
    result.unlink()
    assert cached_artwork(source, directory=tmp_path / "display") == str(result)
    assert QImage(str(result)).height() == 24


def test_artwork_worker_keeps_preparation_and_shutdown_off_the_gui_path(tmp_path: Path) -> None:
    import subprocess
    import sys

    source = tmp_path / "worker.png"
    write_artwork(source)
    child = r"""
import sys
import threading
import time
from unittest.mock import patch
from PySide6.QtCore import QCoreApplication
from pytrain_ui.qt.artwork import ArtworkLoader, cached_artwork

app = QCoreApplication([])
owner = threading.get_ident()
started, release = threading.Event(), threading.Event()
calls, completions = [], []


def prepare(path):
    assert threading.get_ident() != owner, "Image preparation ran on the GUI thread"
    calls.append(path)
    started.set()
    assert release.wait(5)
    return cached_artwork(path, directory=sys.argv[2])


with patch("pytrain_ui.qt.artwork.cached_artwork", side_effect=prepare):
    loader = ArtworkLoader()
    loader.artworkReady.connect(lambda path: completions.append((path, threading.get_ident())))
    assert loader.request(sys.argv[1]) == sys.argv[1]
    assert started.wait(2)
    assert not release.is_set(), "The GUI request must return before the trim finishes"
    assert loader.request(sys.argv[1]) == sys.argv[1]
    release.set()
    deadline = time.monotonic() + 3
    while not completions and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    assert completions == [(sys.argv[1], owner)], "Completion must return to the GUI owner thread"
    assert len(calls) == 1, "Repeated requests must share pending image work"
    assert loader.request(sys.argv[1]) != sys.argv[1]
    loader.close()
    started.clear()
    release.clear()
    closing_loader = ArtworkLoader()
    closing_loader.request(sys.argv[1])
    assert started.wait(2)
    closing_loader.close()
    assert not release.is_set(), "Shutdown must not wait for the image worker"
    release.set()
print("ARTWORK_WORKER_OK")
"""
    result = subprocess.run(
        [sys.executable, "-c", child, str(source), str(tmp_path / "display")],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ARTWORK_WORKER_OK" in result.stdout
