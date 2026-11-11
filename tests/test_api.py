"""Test the API client against a simulated Zyxel web server."""

from __future__ import annotations

import base64
import json

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.asymmetric import rsa

from custom_components.zyxel_router.api import (
    ZyxelApiError,
    ZyxelAuthError,
    ZyxelClient,
    _aes_decrypt,
    _aes_encrypt,
)

TEST_PASSWORD = "Test%Pass!?"  # special chars on purpose


def test_aes_roundtrip() -> None:
    key = base64.b64encode(b"k" * 32).decode()
    iv = base64.b64encode(b"i" * 32).decode()
    enc = _aes_encrypt('{"a": "ä"}', key, iv)
    assert _aes_decrypt(enc, key, iv) == '{"a": "ä"}'


class SimRouter:
    """Mimics the Zyxel httpd encryption behaviour."""

    def __init__(self) -> None:
        self.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.aes_key: str | None = None
        self.session_key = "4711"
        self.logged_in = False
        self.puts: list[dict] = []
        self.expire_once = False

    def pem(self) -> str:
        return (
            self.private.public_key()
            .public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )
            .decode()
        )

    def encrypt(self, obj: dict) -> web.Response:
        iv = base64.b64encode(b"v" * 32).decode()
        return web.json_response(
            {"content": _aes_encrypt(json.dumps(obj), self.aes_key, iv), "iv": iv}
        )

    async def rsa_key(self, request: web.Request) -> web.Response:
        return web.json_response({"RSAPublicKey": self.pem()})

    async def login(self, request: web.Request) -> web.Response:
        body = await request.json()
        self.aes_key = self.private.decrypt(
            base64.b64decode(body["key"]), asym_padding.PKCS1v15()
        ).decode()
        payload = json.loads(_aes_decrypt(body["content"], self.aes_key, body["iv"]))
        password = base64.b64decode(payload["Input_Passwd"]).decode()
        if payload["Input_Account"] != "admin" or password != TEST_PASSWORD:
            return web.json_response({"result": "Invalid"}, status=401)
        self.logged_in = True
        return self.encrypt({"result": "ZCFG_SUCCESS", "sessionkey": self.session_key})

    async def dal(self, request: web.Request) -> web.Response:
        if self.expire_once:
            self.expire_once = False
            self.logged_in = False
        if not self.logged_in:
            return web.json_response({"result": "Invalid Session"}, status=401)
        oid = request.query["oid"]
        if request.method == "GET":
            if oid == "broken":
                return self.encrypt({"result": "ZCFG_NO_SUCH_OBJECT", "ReplyMsg": "x"})
            return self.encrypt({"result": "ZCFG_SUCCESS", "Object": [{"oid": oid}]})
        assert request.query["sessionkey"] == self.session_key
        body = await request.json()
        assert body["key"] == ""
        self.puts.append(json.loads(_aes_decrypt(body["content"], self.aes_key, body["iv"])))
        return self.encrypt({"result": "ZCFG_SUCCESS"})


@pytest.fixture
async def sim(socket_enabled):
    router = SimRouter()
    app = web.Application()
    app.router.add_get("/getRSAPublickKey", router.rsa_key)
    app.router.add_post("/UserLogin", router.login)
    app.router.add_route("*", "/cgi-bin/DAL", router.dal)
    server = TestServer(app, host="127.0.0.1")
    await server.start_server()
    yield router, server
    await server.close()


def _client(server: TestServer, password: str = TEST_PASSWORD) -> ZyxelClient:
    session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))
    host = f"http://{server.host}:{server.port}"
    return ZyxelClient(host, "admin", password, session)


async def test_login_get_put(sim) -> None:
    router, test_client = sim
    client = _client(test_client)
    try:
        await client.login()
        assert client.logged_in
        assert await client.dal_get("cellwan_status") == [{"oid": "cellwan_status"}]
        await client.dal_put("wlan", {"Index": 1, "wlEnable": False})
        assert router.puts == [{"Index": 1, "wlEnable": False}]
        with pytest.raises(ZyxelApiError):
            await client.dal_get("broken")
    finally:
        await client.close()


async def test_relogin_on_expired_session(sim) -> None:
    router, test_client = sim
    client = _client(test_client)
    try:
        await client.login()
        router.expire_once = True
        assert await client.dal_get("status") == [{"oid": "status"}]
    finally:
        await client.close()


async def test_invalid_auth(sim) -> None:
    _, test_client = sim
    client = _client(test_client, password="wrong")
    try:
        with pytest.raises(ZyxelAuthError):
            await client.login()
    finally:
        await client.close()
