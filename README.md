# Biamp Tesira — Home Assistant (HACS)

Custom integration for **Biamp Tesira** DSPs using the **Tesira Text Protocol (TTP)** over **SSH** (recommended) or **Telnet**.

> **Not** the Trane/American Standard “Nexia” thermostat cloud integration. This targets Biamp professional Tesira DSP hardware only.

> This is an original **Shaffer-Softworks** integration. It does not use or depend on community `tesira_ttp` packages.

## Features

- Async TTP client (SSH via `asyncssh`, Telnet with echo negotiation)
- `SESSION` setup, JSON `+OK` parsing, `subscribe` / `unsubscribe`
- Config flow: manual IP or UDP discovery (port 12000)
- **Control points**: import arbitrary TTP addresses from CSV/JSON
- **Block entities**: level (`media_player`), mute / logic (`switch`), source (`select`), presets (`button`), meters (`sensor` / `binary_sensor`)
- Service `biamp_tesira.send_command` for raw TTP
- Connection `binary_sensor`
- Local control (no cloud)

## Requirements

- Home Assistant 2024.1 or newer
- Tesira with **SSH** and/or **Telnet** enabled on the control port
- When system security is enabled: a Tesira user with **Controller** permission ([Biamp security](https://support.biamp.com/Tesira/Control/Tesira_security_best_practices))

## Brand icons

Official **Biamp** wordmark (from [biamp.com](https://blog.biamp.com/wp-content/themes/snap_child/logo.svg)), bundled under `custom_components/biamp_tesira/brand/` for Home Assistant 2026.3+ (`icon.png`, `logo.png`, dark / `@2x` variants).

Regenerate after updating `brand/_source_biamp_wordmark.png`:

```bash
python3 scripts/generate_brand_assets.py
```

## HACS installation

1. Add `https://github.com/Shaffer-Softworks/biamp-tesira` as a [custom repository](https://hacs.xyz/docs/faq/custom_repositories/) (category: **Integration**).
2. Install **Biamp Tesira** and restart Home Assistant.
3. **Settings → Devices & services → Add integration → Biamp Tesira**.

Or copy `custom_components/biamp_tesira` into `config/custom_components/`.

## Control points (CSV / JSON)

Export instance tags from Tesira software (DSP Properties / Object List), then build a file like [`examples/control_points.csv`](examples/control_points.csv).

| Column | Description |
|--------|-------------|
| `name` | Entity friendly name |
| `instance_tag` | Tesira instance tag (quote in CSV if it contains spaces) |
| `command` | Usually `get` (polling); `set` used when writing |
| `attribute` | TTP attribute (`level`, `mute`, `state`, …) |
| `index1`, `index2` | Optional channel indexes |
| `entity_type` | `number`, `switch`, `button`, `select` |
| `min`, `max`, `unit` | For `number` entities |
| `options` | For `select`: pipe-separated list |
| `preset` | For `button`: `DEVICE recallPreset` id |

## Block entities

During setup (or **Configure → Options → Add block entity**), map common blocks:

| Block type | HA platform |
|------------|-------------|
| `level` | `media_player` (volume / mute) |
| `mute` | `switch` |
| `logic_state` | `switch` |
| `source_selector` | `select` |
| `preset` | `button` (`DEVICE recallPreset`) |
| `signal_present_meter` | `binary_sensor` |
| `audio_meter` | `sensor` (dB) |

Enable **Live updates** to use TTP `subscribe` (polling interval applies when off).

## Service

```yaml
service: biamp_tesira.send_command
data:
  command: "Level1 get level 1"
  host: "192.168.1.50"  # required if multiple Tesiras
```

## Docker development

```bash
cp .env.example .env
docker compose up -d
```

Open [http://localhost:8123](http://localhost:8123), add **Biamp Tesira**.

### Mock Tesira (no hardware)

```bash
docker compose --profile mock up -d --build
```

| Service | Host from HA container | Port |
|---------|------------------------|------|
| `tesira-mock` | `tesira-mock` | 23 |
| `tesira-mock` (from host) | `localhost` | `2323` |

Use protocol **telnet**, paste [`examples/control_points.csv`](examples/control_points.csv), or add a **level** block on `Level1` channel 1.

## Development

```bash
python3 -m pytest tests/
```

## HACS default registry

See [docs/HACS_DEFAULT.md](docs/HACS_DEFAULT.md) for submitting to the official HACS default integration list.

## References

- [Tesira Text Protocol (PDF)](https://downloads.biamp.com/assets/docs/default-source/control/tesira_text_protocol_v4-2_jan22.pdf?sfvrsn=100c2497_46)
- [Tesira security best practices](https://support.biamp.com/Tesira/Control/Tesira_security_best_practices)
- [Biamp Nexia integration](https://github.com/Shaffer-Softworks/biamp-nexia) (sister project, NTP protocol)

## License

Apache-2.0
