#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from threading import RLock
from typing import ClassVar
from urllib.parse import urlparse

import requests
from dotenv import find_dotenv, load_dotenv

from ..utils.path_utils import find_file

log = logging.getLogger(__name__)

# Load environment variables that drive behavior
load_dotenv(find_dotenv())
API_KEY = os.environ.get("LIONEL_API_KEY")
PROD_INFO_URL = os.environ.get("PROD_INFO_URL")
ENGINE_INFO_CACHE_DIR = os.environ.get("ENGINE_INFO_CACHE_DIR", "cache/engine_info")
ENGINE_IMAGES_CACHE_DIR = os.environ.get("ENGINE_IMAGES_CACHE_DIR", "cache/engine_images")
PROD_INFO_CONNECT_TIMEOUT = float(os.environ.get("PROD_INFO_CONNECT_TIMEOUT", "10.0"))
PROD_INFO_READ_TIMEOUT = float(os.environ.get("PROD_INFO_READ_TIMEOUT", "20.0"))


def _notify_cache_changed(cleared: bool = False) -> None:
    try:
        from .cache_sync import CacheSyncManager

        if cleared:
            CacheSyncManager.notify_cache_cleared()
        else:
            CacheSyncManager.notify_cache_changed()
    except Exception as e:
        log.warning("Cache sync notification failed: %s", e)


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
    pmid: str
    smoke: bool
    sound: bool
    front_coupler: bool
    rear_coupler: bool
    master_volume: bool
    custom_sound: bool

    image_url: str
    _image_file: str = field(init=False, default=None)
    _image_content: bytes = field(init=False, default=None)

    # class variables
    _bt_cache: ClassVar[dict[str, ProdInfo]] = {}
    _failed_bt_cache: ClassVar[set[str]] = set()
    _cache_lock: ClassVar = RLock()

    def __post_init__(self):
        self._image_content = None
        self._image = None
        with ProdInfo._cache_lock:
            ProdInfo._bt_cache[self.ble_hexid] = self
            ProdInfo._failed_bt_cache.discard(self.ble_hexid)
        try:
            self._image_file = PurePosixPath(urlparse(self.image_url).path).name
        except ValueError:
            pass

    def as_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if not k.startswith("_")}

    @property
    def image_content(self) -> bytes:
        if self._image_content is None:
            image_cache_path = None
            if ENGINE_IMAGES_CACHE_DIR and self._image_file:
                file_name = find_file(self._image_file, places=(Path.cwd(), ENGINE_IMAGES_CACHE_DIR))
                if file_name and Path(file_name).is_file():
                    try:
                        self._image_content = Path(file_name).read_bytes()
                        return self._image_content
                    except OSError as e:
                        log.warning("Failed to load product image from file %s: %s", file_name, e)
                image_cache_path = Path(ENGINE_IMAGES_CACHE_DIR) / self._image_file

            response = requests.get(self.image_url, timeout=30.0)
            if response.status_code == 200:
                self._image_content = response.content
                if image_cache_path:
                    try:
                        image_cache_path.parent.mkdir(parents=True, exist_ok=True)
                        image_cache_path.write_bytes(self._image_content)
                        _notify_cache_changed()
                    except OSError as e:
                        log.warning("Failed to cache product image to file %s: %s", image_cache_path, e)
            else:
                msg = f"Request for product image on {self.pid} failed with status code {response.status_code}"
                log.warning(msg)
                raise requests.RequestException(msg)
        return self._image_content

    @classmethod
    def clear_caches(cls, preserve_custom=True, verbose: bool = False) -> None:
        with cls._cache_lock:
            cls._bt_cache.clear()
            cls._failed_bt_cache.clear()

            for cache_dir in (ENGINE_INFO_CACHE_DIR, ENGINE_IMAGES_CACHE_DIR):
                if not cache_dir:
                    continue

                cache_path = Path(cache_dir)
                if not cache_path.is_dir():
                    continue

                for path in cache_path.iterdir():
                    if path.is_file() or path.is_symlink():
                        if preserve_custom and path.stem.isdigit() and path.name.endswith(".jpg"):
                            continue
                        if verbose:
                            log.info("Clearing cached file: %s", path)
                        path.unlink()
            _notify_cache_changed(cleared=True)

    @classmethod
    def by_btid(cls, bt_id: str) -> ProdInfo | None:
        """Attempts product info lookup; returns cached or None"""
        with cls._cache_lock:
            if bt_id in cls._bt_cache:
                return cls._bt_cache[bt_id]
        try:
            prod_json = cls.get_info(bt_id)
        except (requests.RequestException, ValueError) as e:
            with cls._cache_lock:
                cls._failed_bt_cache.add(bt_id)
            log.warning("Product info lookup failed for %s: %s", bt_id, e)
            return None
        if prod_json:
            prod_info = cls.from_dict(prod_json)
            with cls._cache_lock:
                cls._bt_cache[bt_id] = prod_info
            return prod_info
        else:
            with cls._cache_lock:
                cls._failed_bt_cache.add(bt_id)
            return None

    @classmethod
    def get_info(cls, bt_id: str) -> dict:
        key = bt_id + "_dict"
        with cls._cache_lock:
            if key in cls._bt_cache:
                return cls._bt_cache[key]
            if bt_id in cls._failed_bt_cache:
                return None
            # look in local file cache
            if ENGINE_INFO_CACHE_DIR:
                file_name = find_file(f"{bt_id}.json", places=(Path.cwd(), ENGINE_INFO_CACHE_DIR))
                if file_name and Path(file_name).is_file():
                    try:
                        with open(file_name, "r", encoding="utf-8") as f:
                            prod_dict = json.load(f)
                        cls._bt_cache[key] = prod_dict
                        return prod_dict
                    except Exception as e:
                        log.warning("Failed to load product info from file: %s", e)

        if PROD_INFO_URL is None or API_KEY is None:
            raise ValueError("Missing required environment variables")
        header = {"LionelApiKey": API_KEY}
        response = requests.get(
            PROD_INFO_URL.format(bt_id),
            headers=header,
            timeout=(PROD_INFO_CONNECT_TIMEOUT, PROD_INFO_READ_TIMEOUT),
        )
        if response.status_code == 200:
            prod_dict = response.json()

            # write json to file
            if ENGINE_INFO_CACHE_DIR:
                Path(ENGINE_INFO_CACHE_DIR).mkdir(parents=True, exist_ok=True)
                with open(f"{ENGINE_INFO_CACHE_DIR}/{bt_id}.json", "w", encoding="utf-8") as f:
                    json.dump(prod_dict, f, indent=2)
                _notify_cache_changed()
            with cls._cache_lock:
                cls._bt_cache[key] = prod_dict
            return prod_dict
        else:
            with cls._cache_lock:
                cls._failed_bt_cache.add(bt_id)
            msg = f"Request for product information on {bt_id} failed with status code {response.status_code}"
            raise requests.RequestException(msg)

    # noinspection PyTypeChecker
    @classmethod
    def from_dict(cls, data: dict) -> ProdInfo:
        if not data:
            return None

        return cls(
            pid=data.get("id", None),
            pmid=data.get("pmid", None),
            sku_number=int(data.get("skuNumber", 0)),
            ble_hexid=data.get("blE_HexId", None),
            product_family=data.get("productFamily", None),
            engine_class=data.get("engineClass", None),
            engine_type=data.get("engineType", None),
            description=data.get("description", None),
            road_name=data.get("roadName", None),
            road_number=data.get("roadNumber", None),
            gauge=data.get("gauge", None),
            smoke=bool(data.get("smoke", None)),
            sound=bool(data.get("sound", None)),
            front_coupler=bool(data.get("frontCoupler", None)),
            rear_coupler=bool(data.get("rearCoupler", None)),
            master_volume=bool(data.get("masterVolume", None)),
            custom_sound=bool(data.get("customSound", None)),
            image_url=data.get("imageUrl", None),
        )
