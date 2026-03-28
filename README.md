# Solar

**Self-hosted solar energy management for Sungrow inverters on a Raspberry Pi.**

SolarFlow reads live data from your Sungrow inverters via Modbus TCP, stores everything in PostgreSQL, lets you define smart automation rules, and controls your home devices through MQTT — all running locally on your own hardware.

---

## Why SolarFlow?

Most solar monitoring solutions are cloud-based, closed-source, or limited to what the manufacturer's app provides. SolarFlow gives you:

- **Full ownership** of your energy data — no cloud, no subscriptions
- **Real-time automation** — turn devices on/off based on live solar production, battery state, or grid usage
- **Clean historical data** — query and analyze your energy flows over any time range
- **Local-first** — runs entirely on a Raspberry Pi 5 on your home network

---

## How It Works

```
Sungrow Inverter 1 (hybrid + battery)  ──┐
Sungrow Inverter 2 (string only)       ──┤── Modbus TCP ──▶ Poller
                                         │                    │
                                         │               ┌────┴────┐
                                         │               ▼         ▼
                                         │          PostgreSQL   Rules Engine
                                         │               │         │
                                         │               ▼         ▼
                                         │           REST API   MQTT Broker
                                         │                         │
                                         │                    Smart Home
                                         │                    Devices
```

Every 30 seconds, SolarFlow polls both inverters, stores the readings, evaluates your automation rules, and publishes MQTT messages when conditions are met.

---

## Features

### 📊 Data Collection
- Polls two Sungrow inverters via Modbus TCP (hybrid with battery + string-only)
- Tracks PV power, battery SOC, grid import/export, daily yields, and more
- Stores all readings with UTC timestamps in PostgreSQL

### ⚡ Rules Engine
- Define rules with conditions like *"battery SOC ≥ 95% AND PV power > 1000W"*
- Supports `AND` / `OR` logic
- Actions publish MQTT messages to control smart switches (Shelly, Tasmota, etc.)
- Auto-reverse actions when conditions clear — no stuck relays
- Configurable cooldowns to prevent rapid toggling
- Seed rules from a YAML file, manage via REST API

### 🌐 REST API
- `GET /api/health` — system status with last-seen per inverter
- `GET /api/readings/latest` — most recent reading per inverter
- `GET /api/readings` — historical query with filters (inverter, time range, limit)
- Full CRUD for rules + event history

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Sungrow inverter(s) reachable on your local network via Modbus TCP
- MQTT broker (e.g. Mosquitto) running on the host or network

### 1. Configure

Copy and edit the environment file:

```bash
cp .env.example .env
```

Set your inverter IPs, database credentials, and MQTT broker address in `.env`.

### 2. Run

```bash
docker compose up -d
```

This starts PostgreSQL and the FastAPI backend. Tables are created automatically on first launch.

### 3. Verify

```bash
curl http://localhost:8000/api/health
```

You should see the status of both inverters and their last-seen timestamps.

---

## Example Rule

Turn on the washing machine when the battery is nearly full and the sun is producing:

```yaml
rules:
  - name: "Battery full — turn on washer"
    condition_logic: AND
    conditions:
      - field: battery_soc_pct
        operator: gte
        value: 95
      - field: pv_power_w
        operator: gt
        value: 1000
    actions:
      - mqtt_topic: shellies/washer/relay/0/command
        mqtt_payload: "on"
    on_clear_action: reverse
    cooldown_seconds: 300
```

When conditions clear (battery drops below 95% or PV drops), the action is automatically reversed (`"off"`).

---

## Tech Stack

| Component | Technology |
|---|---|
| API Framework | FastAPI |
| Database | PostgreSQL 16 + async SQLAlchemy |
| Migrations | Alembic |
| Inverter Communication | pymodbus (Modbus TCP) |
| Device Control | paho-mqtt |
| Config | pydantic-settings |
| Runtime | Python 3.12, Docker |

---

## License

This project is for personal use. License TBD.
