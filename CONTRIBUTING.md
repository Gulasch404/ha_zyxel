# Contributing

## Project layout

| Path | Purpose |
| --- | --- |
| `custom_components/zyxel_router/api.py` | Async client for the Zyxel DAL web API (login, encryption, GET/PUT/POST/DELETE) |
| `custom_components/zyxel_router/models.py` | Parsing of raw DAL objects (no Home Assistant imports) |
| `custom_components/zyxel_router/coordinator.py` | Polling, throughput calculation, SMS events, auto-revert watchdog |
| `custom_components/zyxel_router/cellular.py` | Connectivity-relevant changes (always watchdog protected) |
| `tools/gen_translations.py` | Single source for `strings.json` and `translations/*.json` |
| `tools/probe.py` | Read-only dump of all known OIDs of a device |
| `tests/fixtures/` | Anonymised NR7101 data |

## API notes

The web GUI talks to `/cgi-bin/DAL?oid=<name>`. Over HTTP every request body and response is
encrypted:

- `GET /getRSAPublickKey` returns an RSA public key.
- `POST /UserLogin` carries an AES-256-CBC encrypted JSON payload. The random AES key (base64) is
  RSA-PKCS1v1.5 encrypted and sent as `key`; the password is base64 encoded inside the payload.
- All later POST/PUT/DELETE bodies are AES encrypted with the same key, and `sessionkey` is
  appended as a query parameter. The router returns a new `sessionkey` with every response.
- Responses containing `iv` and `content` are encrypted with the same key.
- Over HTTPS no payload encryption is used.

## Adding support for another model

1. Dump the device (read-only):

   ```bash
   ZYXEL_HOST=http://192.168.1.1 ZYXEL_USER=admin ZYXEL_PASS=... python tools/probe.py dumps/
   ```

2. Compare the dumps with `tests/fixtures/`. Feature detection lives in
   `ZyxelData.detect_features()`.
3. Never commit raw dumps. Anonymise IMEI, IMSI, ICCID, serial number, IP/MAC addresses, WiFi
   keys, GPS coordinates and cell/site IDs/TAC before adding fixtures.

## Translations

Edit `tools/gen_translations.py`, then regenerate:

```bash
python tools/gen_translations.py
```

CI fails if the generated files are out of date. All code, comments and documentation are in
English; only `translations/*.json` contain other languages.

## Tests

Home Assistant does not run natively on Windows. Use Linux, WSL or Docker:

```bash
pip install pytest-homeassistant-custom-component ruff
ruff check custom_components tests tools
pytest
```

Docker (PowerShell):

```powershell
# once: build an image with the test dependencies
docker run --name zyxel-test-build python:3.14-slim pip install -q pytest-homeassistant-custom-component
docker commit zyxel-test-build zyxel-ha-test:latest; docker rm zyxel-test-build

docker run --rm -v "${PWD}:/src:ro" zyxel-ha-test:latest bash -c `
  "mkdir /work && cd /src && tar --exclude=.venv -cf - . | tar -xf - -C /work && cd /work && pytest -q"
```

## Releases

1. Bump `version` in `custom_components/zyxel_router/manifest.json` and `pyproject.toml`.
2. Add a `## [X.Y.Z] - YYYY-MM-DD` section to `CHANGELOG.md` (Added / Changed / Fixed, written for
   users, one line per entry) and the compare link at the bottom.
3. Commit, then tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`.
4. The release workflow checks that the tag matches the manifest version and publishes a GitHub
   release with the changelog section as release notes. It fails if the section is missing.
