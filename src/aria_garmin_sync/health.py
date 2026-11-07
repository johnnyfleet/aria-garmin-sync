"""Minimal Google Health API v4 client."""

from collections.abc import Iterator

from google.auth.transport.requests import AuthorizedSession

from . import config
from .google_auth import load_credentials


class HealthApiError(RuntimeError):
    pass


class HealthClient:
    def __init__(self) -> None:
        self.session = AuthorizedSession(load_credentials())

    def _get(self, path: str, params: dict | None = None) -> dict:
        resp = self.session.get(f"{config.HEALTH_API_BASE}{path}", params=params, timeout=30)
        if not resp.ok:
            raise HealthApiError(f"GET {path} -> HTTP {resp.status_code}: {resp.text}")
        return resp.json()

    def identity(self) -> dict:
        return self._get("/users/me/identity")

    def data_points(self, data_type: str, filter: str | None = None, page_size: int = 500) -> Iterator[dict]:
        params: dict = {"pageSize": page_size}
        if filter:
            params["filter"] = filter
        while True:
            page = self._get(f"/users/me/dataTypes/{data_type}/dataPoints", params)
            yield from page.get("dataPoints", [])
            token = page.get("nextPageToken")
            if not token:
                return
            params["pageToken"] = token


def since_filter(data_type: str, start_rfc3339: str) -> str:
    """Filter for sample-type data (weight, body-fat) recorded at or after start.

    Field prefix is the data type in snake_case, e.g. weight.sample_time.physical_time.
    """
    field = data_type.replace("-", "_")
    return f'{field}.sample_time.physical_time >= "{start_rfc3339}"'
