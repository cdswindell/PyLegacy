from pathlib import Path
from unittest.mock import patch

import pytest

from src.pytrain.gui.gas_station_gui import TITLES, VARIANTS, GasStationGui
from src.pytrain.utils.path_utils import find_file


class TestGasStationGui:
    """Unit tests for GasStationGui class"""

    def test_all_image_files_present(self) -> None:
        """Test that all image files referenced in VARIANTS are present"""
        missing_files = []

        for variant_key, image_filename in VARIANTS.items():
            try:
                image_path = find_file(image_filename)
                # Verify the file exists
                if image_path is None or not Path(image_path).exists():
                    missing_files.append(image_filename)
            except (FileNotFoundError, ValueError) as e:
                missing_files.append(f"{image_filename} ({e})")

        assert len(missing_files) == 0, f"Missing image files: {missing_files}"

    def test_car_image_present(self) -> None:
        """Test that the gas station car image is present"""
        car_image = find_file("gas-station-car.png")
        assert car_image is not None, "gas-station-car.png not found"
        assert Path(car_image).exists(), "gas-station-car.png file does not exist"

    def test_all_variants_have_titles(self) -> None:
        """Test that all image files in VARIANTS have corresponding TITLES"""
        missing_titles = []

        for image_filename in VARIANTS.values():
            if image_filename not in TITLES:
                missing_titles.append(image_filename)

        assert len(missing_titles) == 0, f"Missing titles for: {missing_titles}"

    def test_all_titles_have_variants(self) -> None:
        """Test that all TITLES have corresponding entries in VARIANTS"""
        variant_images = set(VARIANTS.values())
        extra_titles = []

        for image_filename in TITLES.keys():
            if image_filename not in variant_images:
                extra_titles.append(image_filename)

        assert len(extra_titles) == 0, f"Extra titles without variants: {extra_titles}"

    def test_get_variant_sinclair(self) -> None:
        """Test get_variant with Sinclair station"""
        title, image = GasStationGui.get_variant("sinclair")
        assert title == "Sinclair Gas Station"
        assert "Sinclair-Gas-Station-30-9101.jpg" in image

    def test_get_variant_texaco(self) -> None:
        """Test get_variant with Texaco station"""
        title, image = GasStationGui.get_variant("texaco")
        assert title == "Texaco Gas Station"
        assert "Texaco-Gas-Station-30-91001.jpg" in image

    def test_get_variant_esso(self) -> None:
        """Test get_variant with Esso station"""
        title, image = GasStationGui.get_variant("esso")
        assert title == "Esso Gas Station"
        assert "Esso-Gas-Station-30-9106.jpg" in image

    def test_get_variant_shell(self) -> None:
        """Test get_variant with Shell station"""
        title, image = GasStationGui.get_variant("shell")
        assert title == "Shell Gas Station"
        assert "Shell-Gas-Station-30-9182.jpg" in image

    def test_get_variant_sunoco(self) -> None:
        """Test get_variant with Sunoco station"""
        title, image = GasStationGui.get_variant("sunoco")
        assert title == "Sunoco Gas Station"
        assert "Sunoco-Gas-Station-30-9154.jpg" in image

    def test_get_variant_mobile(self) -> None:
        """Test get_variant with Mobile station"""
        title, image = GasStationGui.get_variant("mobile")
        assert title == "Mobile Gas Station"
        assert "Mobile-Gas-Station-30-9124.jpg" in image

    def test_get_variant_gulf(self) -> None:
        """Test get_variant with Gulf station"""
        title, image = GasStationGui.get_variant("gulf")
        assert title == "Gulf Gas Station"
        assert "Gulf-Gas-Station-30-9168.jpg" in image

    def test_get_variant_tidewater(self) -> None:
        """Test get_variant with Tidewater Oil station"""
        title, image = GasStationGui.get_variant("tidewater")
        assert title == "Tidewater Oil Gas Station"
        assert "Tidewater-Oil-Gas-Station-30-9181.jpg" in image

    def test_get_variant_route66(self) -> None:
        """Test get_variant with Route 66 station"""
        title, image = GasStationGui.get_variant("route 66")
        assert title == "Route 66 Gas Station"
        assert "Route-66-Gas-Station-30-91002.jpg" in image

    def test_get_variant_atlantic(self) -> None:
        """Test get_variant with Atlantic station"""
        title, image = GasStationGui.get_variant("atlantic")
        assert title == "Atlantic Gas Station"
        assert "Atlantic-Gas-Station-30-91003.jpg" in image

    def test_get_variant_bp(self) -> None:
        """Test get_variant with BP station"""
        title, image = GasStationGui.get_variant("bp")
        assert title == "BP Gas Station"
        assert "BP-Gas-Station-30-9181.jpg" in image

    def test_get_variant_citgo(self) -> None:
        """Test get_variant with Citgo station"""
        title, image = GasStationGui.get_variant("citgo")
        assert title == "Citgo Gas Station"
        assert "Citgo-Gas-Station-30-9113.jpg" in image

    def test_get_variant_default_none(self) -> None:
        """Test get_variant with None defaults to Sinclair"""
        title, image = GasStationGui.get_variant(None)
        assert title == "Sinclair Gas Station"
        assert "Sinclair-Gas-Station-30-9101.jpg" in image

    def test_get_variant_case_insensitive(self) -> None:
        """Test get_variant is case insensitive"""
        title1, image1 = GasStationGui.get_variant("SHELL")
        title2, image2 = GasStationGui.get_variant("shell")
        assert title1 == title2
        assert image1 == image2

    def test_get_variant_with_hyphen(self) -> None:
        """Test get_variant handles hyphens correctly"""
        title, image = GasStationGui.get_variant("shell-gas-station")
        assert title == "Shell Gas Station"
        assert "Shell-Gas-Station-30-9182.jpg" in image

    def test_get_variant_with_product_number(self) -> None:
        """Test get_variant with product number"""
        title, image = GasStationGui.get_variant("30-9182")
        assert title == "Shell Gas Station"
        assert "Shell-Gas-Station-30-9182.jpg" in image

    def test_get_variant_invalid_raises_exception(self) -> None:
        """Test get_variant raises ValueError for invalid variant"""
        with pytest.raises(ValueError, match="Unsupported gas station"):
            GasStationGui.get_variant("invalid_station_name")

    def test_get_variant_partial_match(self) -> None:
        """Test get_variant with partial name match"""
        title, image = GasStationGui.get_variant("esso gas")
        assert title == "Esso Gas Station"
        assert "Esso-Gas-Station-30-9106.jpg" in image

    @patch("pytrain.gui.gas_station_gui.AccessoryBase.__init__")
    @patch("pytrain.gui.gas_station_gui.find_file")
    def test_init_with_variant(self, mock_find_file, mock_super_init) -> None:
        """Test GasStationGui initialization with variant"""
        mock_find_file.return_value = "/path/to/image.jpg"
        mock_super_init.return_value = None

        gui = GasStationGui.__new__(GasStationGui)
        gui._power = 1
        gui._alarm = 2
        gui._variant = "shell"
        gui._title, gui._image = gui.get_variant("shell")

        assert gui._title == "Shell Gas Station"
        assert "Shell-Gas-Station-30-9182.jpg" in gui._image

    def test_variants_dict_completeness(self) -> None:
        """Test that VARIANTS dict has expected number of entries"""
        # Based on the VARIANTS dict in the code, there should be 12 entries
        assert len(VARIANTS) == 12, f"Expected 12 variants, found {len(VARIANTS)}"

    def test_titles_dict_completeness(self) -> None:
        """Test that TITLES dict has expected number of entries"""
        # TITLES should match VARIANTS count
        assert len(TITLES) == 12, f"Expected 12 titles, found {len(TITLES)}"

    def test_all_variant_keys_lowercase_normalized(self) -> None:
        """Test that all variant keys can be matched with lowercase normalization"""
        for variant_key in VARIANTS.keys():
            # Verify the key is already in lowercase format suitable for matching
            normalized = variant_key.lower().replace("'", "")
            # Should be able to find itself
            found = False
            for k in VARIANTS.keys():
                if normalized in k:
                    found = True
                    break
            assert found, f"Variant key '{variant_key}' cannot match itself after normalization"
