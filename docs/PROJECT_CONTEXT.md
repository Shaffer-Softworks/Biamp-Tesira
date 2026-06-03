# Biamp Tesira — project context

Last updated: 2026-06-03

## Purpose

Greenfield **Home Assistant HACS** integration for **Biamp Tesira** DSPs using **Tesira Text Protocol (TTP)** over **SSH** (preferred) or **Telnet**.

- **Domain:** `biamp_tesira`
- **Target org repo:** [Shaffer-Softworks/biamp-tesira](https://github.com/Shaffer-Softworks/biamp-tesira) (manifest/issue_tracker URLs)
- **Current remote:** [sickkick/Biamp-Tesira](https://github.com/sickkick/Biamp-Tesira) (`origin`)
- **Sister template:** [Shaffer-Softworks/biamp-nexia](https://github.com/Shaffer-Softworks/biamp-nexia) (patterns only — Nexia is a different protocol/product)

## Hard constraints (do not violate)

1. **Original code only** — do not use or depend on [Darnel-K/tesira_ttp](https://github.com/Darnel-K/tesira_ttp) or `pytesira`.
2. **Not** the Trane/American Standard Nexia thermostat cloud integration.
3. **Git commits:** never add Cursor as co-author, contributor, or `Co-authored-by:` trailer.

## Architecture

| Layer | Module | Role |
|-------|--------|------|
| Transport | `tesira_client.py` | Async SSH (`asyncssh`) + Telnet; `SESSION set verbose true` / `detailedResponse false`; JSON `+OK` parsing; subscribe/unsubscribe; `SESSION get aliases` |
| Config | `config_flow.py`, `discovery.py` | Manual IP / UDP discovery port **12000**; credentials; optional control-point import; optional block entities |
| Runtime | `coordinator.py`, `__init__.py` | `DataUpdateCoordinator`; `biamp_tesira.send_command` service |
| Control points | `control_point.py`, `importer.py` | CSV/JSON → `number`, `switch`, `button`, `select` |
| Blocks | `block_registry.py` | `level`→`media_player`, `mute`/`logic_state`→`switch`, `source_selector`→`select`, `preset`→`button`, meters→`sensor`/`binary_sensor`, connectivity `binary_sensor` |

Subscription lines are drained after command responses (no separate background TTP reader).

## Key paths

```
custom_components/biamp_tesira/   # integration
tests/                            # unit tests (+ optional mock integration)
docker/tesira-mock/               # Telnet TTP mock
examples/control_points.csv
scripts/generate_brand_assets.py  # regen brand PNGs from _source_biamp_wordmark.png
docs/HACS_DEFAULT.md              # hacs/default PR steps
```

## Brand assets

Official Biamp wordmark source: `custom_components/biamp_tesira/brand/_source_biamp_wordmark.png` (from Biamp blog SVG). Regenerate with `python3 scripts/generate_brand_assets.py`.

## CI / GitHub

Workflow: `.github/workflows/validate.yaml` — **pytest**, **hassfest**, **hacs**.

- **pytest** needs `homeassistant` + `voluptuous` in CI (imports hit `__init__.py`).
- **hacs** requires repo **description** and topics (`homeassistant`, `hacs`, `hacs-integration`, `integration`) on GitHub.
- Latest run on `main` (after workflow fix): **success**.

Local tests: `python3 -m pytest tests/` → 9 passed, 1 skipped (mock integration skips if Docker mock not up).

## Open / optional next steps

1. Publish or mirror to **Shaffer-Softworks/biamp-tesira** and tag **v0.1.0**.
2. **hacs/default** PR per `docs/HACS_DEFAULT.md`.
3. Real-hardware validation (SSH/Telnet, TTP enabled on device).
4. Phase 3 blocks (logic family, paging, I/O, EQ, etc.) — only v1 block set implemented.
5. Consider `iot_class: local_push` when subscriptions drive updates.
6. HACS store icons may need default-repo listing (HA 2026.3+ brand path works locally).

## Environment

- `docker-compose.yml` — HA dev + `tesira-mock` (port 2323 Telnet).
- `.env.example` — copy to `.env` for local dev (not committed).

## License

Apache-2.0 — Shaffer-Softworks.
