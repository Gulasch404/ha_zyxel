"""Async client for the Zyxel web configurator (DAL) API.

Used by Zyxel NR/FWA/VMG/EX series with the Vue based web GUI (e.g. NR7101).

Protocol (reverse engineered from the web GUI):
* ``GET /getRSAPublickKey`` returns the RSA public key used for login.
* ``POST /UserLogin`` with an AES-256-CBC encrypted JSON payload. The random AES
  key (base64 string) is RSA-PKCS1v1.5 encrypted and sent as ``key``.
* All further ``/cgi-bin/`` POST/PUT/DELETE bodies are AES encrypted with the
  same key (without ``key``), and ``sessionkey`` is appended as query parameter.
* Responses carrying ``iv`` + ``content`` are AES encrypted with the same key.
* When the GUI is reached via HTTPS, no payload encryption is used.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
import os
from typing import Any

import aiohttp
from cryptography.hazmat.primitives import padding, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30


class ZyxelError(Exception):
    """Generic Zyxel API error."""


class ZyxelConnectionError(ZyxelError):
    """Device not reachable."""


class ZyxelAuthError(ZyxelError):
    """Authentication failed."""


class ZyxelApiError(ZyxelError):
    """DAL returned an error result."""

    def __init__(self, message: str, result: str | None = None) -> None:
        super().__init__(message)
        self.result = result


def _aes_encrypt(plaintext: str, key_b64: str, iv_b64: str) -> str:
    key = base64.b64decode(key_b64)
    iv = base64.b64decode(iv_b64)[:16]
    padder = padding.PKCS7(128).padder()
    data = padder.update(plaintext.encode()) + padder.finalize()
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return base64.b64encode(enc.update(data) + enc.finalize()).decode()


def _aes_decrypt(content_b64: str, key_b64: str, iv_b64: str) -> str:
    key = base64.b64decode(key_b64)
    iv = base64.b64decode(iv_b64)[:16]
    dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    data = dec.update(base64.b64decode(content_b64)) + dec.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return (unpadder.update(data) + unpadder.finalize()).decode("utf-8", "replace")


def _random_b64(size: int = 32) -> str:
    return base64.b64encode(os.urandom(size)).decode()


def _unescape(text: str) -> str:
    return (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '\\"')
        .replace("&apos;", "'")
    )


class ZyxelClient:
    """Minimal async client for the Zyxel DAL API."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        *,
        ssl: bool = False,
        verify_ssl: bool = False,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        host = host.strip().rstrip("/")
        if host.startswith("https://"):
            ssl, host = True, host[8:]
        elif host.startswith("http://"):
            ssl, host = False, host[7:]
        self.host = host
        self._base = f"{'https' if ssl else 'http'}://{host}"
        self._use_https = ssl
        self._verify_ssl = verify_ssl
        self._username = username
        self._password = password
        self._session = session
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._aes_key: str | None = None
        self._session_key: str | None = None
        self._encrypt = not ssl
        self._lock = asyncio.Lock()
        self.logged_in = False

    # ------------------------------------------------------------------ http
    async def _raw(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        body: str | None = None,
        timeout: int | None = None,
    ) -> tuple[int, Any]:
        url = self._base + path
        try:
            async with self._session.request(
                method,
                url,
                params=params,
                data=body,
                headers={"If-Modified-Since": "Thu, 01 Jun 1970 00:00:00 GMT"},
                ssl=self._verify_ssl if self._use_https else None,
                timeout=aiohttp.ClientTimeout(total=timeout) if timeout else self._timeout,
            ) as resp:
                text = await resp.text(errors="replace")
                status = resp.status
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ZyxelConnectionError(f"{method} {path}: {err}") from err

        data: Any = None
        if text:
            try:
                data = json.loads(text)
            except ValueError:
                data = text
        if (
            isinstance(data, dict)
            and "iv" in data
            and "content" in data
            and self._aes_key
        ):
            data = json.loads(_aes_decrypt(data["content"], self._aes_key, data["iv"]))
        if isinstance(data, dict) and data.get("sessionkey"):
            self._session_key = str(data["sessionkey"])
        return status, data

    def _encrypt_body(self, payload: Any, rsa: RSAPublicKey | None = None) -> str:
        plain = payload if isinstance(payload, str) else json.dumps(payload)
        if not self._encrypt:
            return plain
        iv = _random_b64()
        if rsa is not None:
            self._aes_key = _random_b64()
        assert self._aes_key
        out = {"content": _aes_encrypt(plain, self._aes_key, iv), "key": "", "iv": iv}
        if rsa is not None:
            out["key"] = base64.b64encode(
                rsa.encrypt(self._aes_key.encode(), asym_padding.PKCS1v15())
            ).decode()
        return json.dumps(out)

    # ----------------------------------------------------------------- login
    async def login(self) -> dict[str, Any]:
        """Log in and return the login response."""
        async with self._lock:
            return await self._login()

    async def _login(self) -> dict[str, Any]:
        self.logged_in = False
        self._session_key = None
        rsa: RSAPublicKey | None = None
        if self._encrypt:
            _, key_resp = await self._raw("GET", "/getRSAPublickKey", timeout=15)
            pem = key_resp.get("RSAPublicKey") if isinstance(key_resp, dict) else None
            if not pem or pem == "None":
                self._encrypt = False
            else:
                loaded = serialization.load_pem_public_key(pem.encode())
                assert isinstance(loaded, RSAPublicKey)
                rsa = loaded
        payload = {
            "Input_Account": self._username,
            "Input_Passwd": base64.b64encode(self._password.encode()).decode(),
            "currLang": "en",
            "RememberPassword": 0,
            "SHA512_password": False,
        }
        status, data = await self._raw(
            "POST", "/UserLogin", body=self._encrypt_body(payload, rsa)
        )
        if status in (401, 403) or not isinstance(data, dict):
            raise ZyxelAuthError(f"Login failed (HTTP {status}): {data}")
        if data.get("result") not in (None, "ZCFG_SUCCESS"):
            raise ZyxelAuthError(f"Login failed: {data.get('result')}")
        self.logged_in = True
        return data

    async def logout(self) -> None:
        """Log out (best effort)."""
        if not self.logged_in:
            return
        with contextlib.suppress(ZyxelError):
            await self._request("POST", "/cgi-bin/UserLogout", relogin=False)
        self.logged_in = False

    # --------------------------------------------------------------- request
    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        payload: Any = None,
        relogin: bool = True,
        timeout: int | None = None,
    ) -> Any:
        params = dict(params or {})
        if method in ("POST", "PUT", "DELETE") and self._session_key:
            params["sessionkey"] = self._session_key
        body = self._encrypt_body(payload) if payload is not None else None
        status, data = await self._raw(
            method, path, params=params, body=body, timeout=timeout
        )
        if status in (401, 403) or (
            isinstance(data, dict) and data.get("result") == "Invalid Session"
        ):
            if not relogin:
                raise ZyxelAuthError(f"{path}: HTTP {status}")
            await self._login()
            return await self._request(
                method, path, params=params, payload=payload, relogin=False, timeout=timeout
            )
        if status >= 400:
            raise ZyxelApiError(f"{method} {path}: HTTP {status}: {data}")
        if isinstance(data, str):
            data = json.loads(_unescape(data)) if data.startswith(("{", "[")) else data
        return data

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Perform an authenticated request (logs in if required)."""
        async with self._lock:
            if not self.logged_in:
                await self._login()
            return await self._request(method, path, **kwargs)

    # ------------------------------------------------------------------- DAL
    @staticmethod
    def _check(oid: str, data: Any) -> Any:
        if isinstance(data, dict) and data.get("result", "ZCFG_SUCCESS") != "ZCFG_SUCCESS":
            raise ZyxelApiError(
                f"DAL {oid}: {data.get('result')} {data.get('ReplyMsg', '')}".strip(),
                data.get("result"),
            )
        return data

    async def dal_get(self, oid: str) -> list[dict[str, Any]]:
        """Return the ``Object`` list of a DAL oid."""
        data = self._check(oid, await self.request("GET", "/cgi-bin/DAL", params={"oid": oid}))
        if isinstance(data, dict):
            return data.get("Object") or []
        return []

    async def dal_get_one(self, oid: str) -> dict[str, Any]:
        """Return the first object of a DAL oid (or empty dict)."""
        objs = await self.dal_get(oid)
        return objs[0] if objs else {}

    async def dal_put(self, oid: str, payload: dict[str, Any], **params: str) -> Any:
        """Modify a DAL object."""
        return self._check(
            oid,
            await self.request("PUT", "/cgi-bin/DAL", params={"oid": oid, **params}, payload=payload),
        )

    async def dal_post(self, oid: str, payload: dict[str, Any], **params: str) -> Any:
        """Create/act on a DAL object."""
        return self._check(
            oid,
            await self.request("POST", "/cgi-bin/DAL", params={"oid": oid, **params}, payload=payload),
        )

    async def dal_delete(self, oid: str, **params: str) -> Any:
        """Delete a DAL object (index etc. via params)."""
        return self._check(
            oid, await self.request("DELETE", "/cgi-bin/DAL", params={"oid": oid, **params})
        )

    @property
    def base_url(self) -> str:
        """Base URL of the web GUI."""
        return self._base

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        await self._session.close()

    async def cgi_get(self, endpoint: str, **params: str) -> Any:
        """GET an arbitrary /cgi-bin endpoint."""
        return await self.request("GET", f"/cgi-bin/{endpoint}", params=params or None)

    async def reboot(self) -> Any:
        """Reboot the device. The device will be unreachable for a few minutes."""
        return await self.request("POST", "/cgi-bin/Reboot", payload={}, timeout=15)
