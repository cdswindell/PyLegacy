import requests
from requests import RequestException

from ..utils.singleton import singleton

API_KEY = "LionChief-Android-ED2E9A6F5F08"
PROD_INFO_URL = "https://proddb.lionel.com/api/engine/getenginebyhexid/{}"


@singleton
class ProdInfo:
    def __init__(self) -> None:
        if hasattr(self, "_initialized") and self._initialized:
            return
        else:
            self._initialized = True

    @classmethod
    def get_info(cls, bt_id: str) -> dict:
        header = {"LionelApiKey": API_KEY}
        response = requests.get(PROD_INFO_URL.format(bt_id), headers=header)
        if response.status_code == 200:
            return response.json()
        else:
            msg = f"Request for product information on {bt_id} failed with status code {response.status_code}"
            raise RequestException(msg)
