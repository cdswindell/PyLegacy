from unittest.mock import call, patch, sentinel

import pytest
from PIL import Image

from src.pytrain.utils import image_utils as mod


@pytest.mark.parametrize("size", [1, 18, 24])
def test_load_font_prefers_dejavu(size: int) -> None:
    with (
        patch.object(mod.ImageFont, "truetype", return_value=sentinel.font) as truetype,
        patch.object(mod.ImageFont, "load_default") as load_default,
    ):
        assert mod._load_font(size) is sentinel.font

    truetype.assert_called_once_with("DejaVuSans.ttf", size)
    load_default.assert_not_called()


@pytest.mark.parametrize("styled", [False, True])
@pytest.mark.parametrize("font_size", [4, 24])
def test_center_text_on_image_falls_back_when_dejavu_is_missing(styled: bool, font_size: int) -> None:
    source = Image.new("RGB", (320, 120), "white")
    real_truetype = mod.ImageFont.truetype

    def missing_dejavu(font, *args, **kwargs):
        if font == "DejaVuSans.ttf":
            raise OSError("cannot open resource")
        return real_truetype(font, *args, **kwargs)

    with (
        patch.object(mod.ImageFont, "truetype", side_effect=missing_dejavu),
        patch.object(mod.ImageFont, "load_default", wraps=mod.ImageFont.load_default) as load_default,
        patch.object(mod.ImageTk, "getimage", return_value=source) as getimage,
        patch.object(mod.ImageTk, "PhotoImage", return_value=sentinel.result) as photo_image,
    ):
        result = mod.center_text_on_image(sentinel.photo, "Steam Engine", font_size=font_size, styled=styled)

    assert result is sentinel.result
    getimage.assert_called_once_with(sentinel.photo)
    assert load_default.call_args_list == [call(size=font_size), call(size=max(font_size - 6, 1))]
    photo_image.assert_called_once()
    rendered = photo_image.call_args.args[0]
    assert rendered.size == source.size
    assert all(low < 221 and high == 255 for low, high in rendered.getextrema())
    assert source.getextrema() == ((255, 255),) * 3
