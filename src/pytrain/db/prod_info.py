#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import ClassVar

import requests
from dotenv import find_dotenv, load_dotenv

# Load environment variables that drive behavior
load_dotenv(find_dotenv())
API_KEY = os.environ.get("LIONEL_API_KEY")
PROD_INFO_URL = os.environ.get("PROD_INFO_URL")


# noinspection PyTypeChecker
@dataclass
class ProdInfo:
    pid: int
    sku_number: int
    ble_hexid: str
    product_family: int
    engine_class: int
    engine_type: str
    description: str
    road_name: str
    road_number: str
    gauge: str
    image_url: str
    _image_content: bytes = field(init=False, default=None)

    # class variables
    _bt_cache: ClassVar[dict[str, ProdInfo]] = {}

    def __post_init__(self):
        self._image_content = None
        self._image = None
        ProdInfo._bt_cache[self.ble_hexid] = self

    @property
    def image_content(self) -> bytes:
        if self._image_content is None:
            response = requests.get(self.image_url)
            if response.status_code == 200:
                self._image_content = response.content
            else:
                msg = f"Request for product image on {self.pid} failed with status code {response.status_code}"
                raise requests.RequestException(msg)
        return self._image_content

    @classmethod
    def by_btid(cls, bt_id: str) -> ProdInfo | None:
        if bt_id in cls._bt_cache:
            return cls._bt_cache[bt_id]
        prod_json = cls.get_info(bt_id)
        if prod_json:
            return cls.from_dict(prod_json)
        else:
            return None

    @classmethod
    def get_info(cls, bt_id: str) -> dict:
        if PROD_INFO_URL is None or API_KEY is None:
            raise ValueError("Missing required environment variables")
        header = {"LionelApiKey": API_KEY}
        response = requests.get(PROD_INFO_URL.format(bt_id), headers=header)
        if response.status_code == 200:
            return response.json()
        else:
            msg = f"Request for product information on {bt_id} failed with status code {response.status_code}"
            raise requests.RequestException(msg)

    # noinspection PyTypeChecker
    @classmethod
    def from_dict(cls, data: dict) -> ProdInfo:
        # Handle potential missing keys or type conversions
        pid = data.get("id", None)
        sku_number = int(data.get("skuNumber", 0))  # Convert to int
        image_url = data.get("imageUrl", None)
        ble_hexid = data.get("blE_HexId", None)
        engine_type = data.get("engineType", None)
        product_family = data.get("productFamily", None)
        engine_class = data.get("engineClass", None)
        description = data.get("description", None)
        road_name = data.get("roadName", None)
        road_number = data.get("roadNumber", None)
        gauge = data.get("gauge", None)

        return cls(
            pid=pid,
            sku_number=sku_number,
            ble_hexid=ble_hexid,
            product_family=product_family,
            engine_class=engine_class,
            engine_type=engine_type,
            description=description,
            road_name=road_name,
            road_number=road_number,
            gauge=gauge,
            image_url=image_url,
        )
