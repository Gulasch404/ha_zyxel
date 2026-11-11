"""Read-only probe: logs in and dumps DAL oids / cgi endpoints to JSON files.

Usage:
    ZYXEL_HOST=http://192.168.1.1 ZYXEL_USER=admin ZYXEL_PASS=... \
        python tools/probe.py OUTDIR [oid ...]

Only performs GET requests (plus login/logout).
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path

import aiohttp

_API = Path(__file__).resolve().parent.parent / "custom_components" / "zyxel_router" / "api.py"
_spec = importlib.util.spec_from_file_location("zyxel_api", _API)
api = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(api)  # type: ignore[union-attr]

DEFAULT_OIDS = [
    "status", "cardpage_status", "cellwan_status", "cellwan", "cellwan_sim", "cellwan_band",
    "cellwan_lock", "cellwan_nr_lock", "cellwan_mgmt", "cellwan_psru", "cellwan_plmn",
    "cellwan_mapn", "cellwan_sms", "cellwan_gnss", "cellwan_wait_state", "cellular",
    "lanhosts", "lan", "wan", "Traffic_Status", "wlan", "ethctl", "LanPortInfo", "sensor",
    "time", "mqtt_client", "mgmt_srv", "schedule_reboot", "logset", "snmp", "online_fw_info",
    "dns", "user_account", "login_privilege", "region", "email_ntfy", "ddns", "cellwan_esim",
]
CGI = ["WAN_LAN_LIST_Get", "LAN_PORT_LIST_Get", "MenuList", "CardInfo", "ARPTable_handle",
       "RoutingTable_handle"]


async def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    oids = sys.argv[2:] or DEFAULT_OIDS
    jar = aiohttp.CookieJar(unsafe=True)
    async with aiohttp.ClientSession(cookie_jar=jar) as session:
        client = api.ZyxelClient(
            os.environ["ZYXEL_HOST"], os.environ["ZYXEL_USER"], os.environ["ZYXEL_PASS"], session
        )
        login = await client.login()
        (out / "_login.json").write_text(json.dumps(login, indent=1))
        print("login ok:", {k: v for k, v in login.items() if k != "sessionkey"})
        for oid in oids:
            try:
                data = await client.request("GET", "/cgi-bin/DAL", params={"oid": oid})
                (out / f"dal_{oid}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
                res = data.get("result") if isinstance(data, dict) else type(data).__name__
                n = len(data.get("Object") or []) if isinstance(data, dict) else "?"
                print(f"DAL {oid:28} {res} objects={n}")
            except Exception as err:
                print(f"DAL {oid:28} ERROR {err}")
        if len(sys.argv) <= 2:
            for ep in CGI:
                try:
                    data = await client.cgi_get(ep)
                    (out / f"cgi_{ep}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
                    print(f"CGI {ep:28} ok")
                except Exception as err:
                    print(f"CGI {ep:28} ERROR {err}")
        await client.logout()


if __name__ == "__main__":
    asyncio.run(main())
