"""Fixtures for Zyxel Router tests."""

from __future__ import annotations

import copy
import json
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.zyxel_router.const import DOMAIN

FIXTURES = Path(__file__).parent / "fixtures"


def load_oid(oid: str) -> list[dict[str, Any]]:
    """Load the Object list of a fixture."""
    path = FIXTURES / f"{oid}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("Object") or []


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations."""


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="S000Z00000000",
        title="NR7101",
        data={
            CONF_HOST: "http://192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
        },
    )


class FakeRouter:
    """In-memory DAL backend used to mock ZyxelClient."""

    def __init__(self) -> None:
        self.objects: dict[str, list[dict[str, Any]]] = {}
        self.writes: list[tuple[str, str, Any]] = []
        self.connected = True

    def get(self, oid: str) -> list[dict[str, Any]]:
        if oid not in self.objects:
            self.objects[oid] = load_oid(oid)
        objs = copy.deepcopy(self.objects[oid])
        if oid == "cellwan_status" and objs and not self.connected:
            objs[0]["INTF_Status"] = "Down"
        return objs

    async def dal_get(self, oid: str) -> list[dict[str, Any]]:
        return self.get(oid)

    async def dal_get_one(self, oid: str) -> dict[str, Any]:
        objs = self.get(oid)
        return objs[0] if objs else {}

    async def dal_put(self, oid: str, payload: dict[str, Any], **params: str) -> dict:
        self.writes.append(("PUT", oid, copy.deepcopy(payload)))
        objs = self.get(oid)
        if objs:
            objs[0].update(payload)
            self.objects[oid] = objs
        return {"result": "ZCFG_SUCCESS"}

    async def dal_post(self, oid: str, payload: dict[str, Any], **params: str) -> dict:
        self.writes.append(("POST", oid, copy.deepcopy(payload)))
        return {"result": "ZCFG_SUCCESS"}

    async def dal_delete(self, oid: str, **params: str) -> dict:
        self.writes.append(("DELETE", oid, params))
        return {"result": "ZCFG_SUCCESS"}


@pytest.fixture
def router() -> FakeRouter:
    """Fake router."""
    return FakeRouter()


@pytest.fixture
def mock_client(router: FakeRouter) -> Generator[AsyncMock]:
    """Patch ZyxelClient everywhere."""
    with (
        patch("custom_components.zyxel_router.ZyxelClient", autospec=True) as cls,
        patch("custom_components.zyxel_router.config_flow._validate") as validate,
    ):
        client = cls.return_value
        client.host = "192.168.1.1"
        client.base_url = "http://192.168.1.1"
        client.login = AsyncMock(return_value={"result": "ZCFG_SUCCESS"})
        client.logout = AsyncMock()
        client.reboot = AsyncMock()
        client.dal_get.side_effect = router.dal_get
        client.dal_get_one.side_effect = router.dal_get_one
        client.dal_put.side_effect = router.dal_put
        client.dal_post.side_effect = router.dal_post
        client.dal_delete.side_effect = router.dal_delete
        validate.return_value = {"SerialNumber": "S000Z00000000", "ModelName": "NR7101"}
        client.validate = validate
        yield client
