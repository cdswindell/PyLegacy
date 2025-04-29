#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#
#  SPDX-License-Identifier: LPGL
#
#
import pytest
from src.pytrain.gpio.utils.text_buffer import TextBuffer


class TestTextBuffer:
    def test_initialization(self):
        buffer = TextBuffer(rows=5, cols=10, auto_update=False)
        assert buffer.rows == 5
        assert buffer.cols == 10
        assert not buffer.auto_update
        assert len(buffer) == 0
        assert buffer.cursor_pos == (0, 0)

    def test_repr_empty(self):
        buffer = TextBuffer(rows=3)
        assert repr(buffer) == ""

    def test_set_and_get_item(self):
        buffer = TextBuffer(rows=3)
        buffer[0] = "Hello"
        buffer[1] = "World"
        assert buffer[0] == "Hello"
        assert buffer[1] == "World"

    def test_set_item_out_of_bounds(self):
        buffer = TextBuffer(rows=3)
        with pytest.raises(IndexError):
            buffer[5] = "Out of bounds"

    def test_delete_item(self):
        buffer = TextBuffer(rows=3)
        buffer[0] = "Row 1"
        buffer[1] = "Row 2"
        del buffer[0]
        assert len(buffer) == 1
        assert buffer[0] == "Row 2"

    def test_insert_item(self):
        buffer = TextBuffer(rows=3)
        buffer[0] = "Row 1"
        buffer.insert(0, "Inserted Row")
        assert len(buffer) == 2
        assert buffer[0] == "Inserted Row"
        assert buffer[1] == "Row 1"

    def test_insert_out_of_bounds(self):
        buffer = TextBuffer(rows=3)
        with pytest.raises(IndexError):
            buffer.insert(5, "Out of bounds")

    def test_reverse_buffer(self):
        buffer = TextBuffer(rows=3)
        buffer[0] = "Row 1"
        buffer[1] = "Row 2"
        buffer.reverse()
        assert buffer[0] == "Row 2"
        assert buffer[1] == "Row 1"

    def test_add_row(self):
        buffer = TextBuffer(rows=3)
        assert buffer.add("New Row")
        assert len(buffer) == 1
        assert buffer[0] == "New Row"

    def test_add_row_exceeds_limit(self):
        buffer = TextBuffer(rows=1)
        buffer.add("Row 1")
        assert not buffer.add("Row 2")

    def test_contains(self):
        buffer = TextBuffer(rows=3)
        buffer[0] = "Hello"
        assert "Hello" in buffer
        assert "World" not in buffer

    def test_count(self):
        buffer = TextBuffer(rows=3)
        buffer[0] = "Hello"
        buffer[1] = "Hello"
        assert buffer.count("Hello") == 2
        assert buffer.count("World") == 0

    def test_clear_buffer(self):
        buffer = TextBuffer(rows=3)
        buffer[0] = "Row 1"
        buffer[1] = "Row 2"
        buffer.clear()
        assert len(buffer) == 0
        assert buffer.cursor_pos == (0, 0)

    def test_auto_update_property(self):
        buffer = TextBuffer(auto_update=True)
        assert buffer.auto_update
        buffer.auto_update = False
        assert not buffer.auto_update

    def test_cursor_pos_setting(self):
        buffer = TextBuffer(rows=3, cols=5)
        buffer.cursor_pos = (1, 4)
        assert buffer.cursor_pos == (1, 4)

    def test_cursor_pos_invalid(self):
        buffer = TextBuffer(rows=3, cols=5)
        with pytest.raises(AttributeError):
            buffer.cursor_pos = (5, 4)

    def test_changed_rows(self):
        buffer = TextBuffer(rows=3)
        buffer[0] = "Row 1"
        buffer[1] = "Row 2"
        assert buffer.changed_rows == [0, 1]
        assert buffer.changed_rows == []

    def test_write_char(self):
        buffer = TextBuffer(rows=3, cols=5)
        buffer.write_chr(65, (0, 0))
        assert buffer[0] == "A"

    def test_write_string(self):
        buffer = TextBuffer(rows=3, cols=10)
        buffer.write("Hello", (1, 0))
        assert buffer[1] == "Hello"

    def test_write_out_of_bounds(self):
        buffer = TextBuffer(rows=3, cols=10)
        with pytest.raises(AttributeError):
            buffer.write("Overflow", (5, 0))
