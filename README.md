# SolarFlow

**Self-hosted solar energy management for Sungrow inverters on a Raspberry Pi.**

SolarFlow reads live data from your Sungrow inverters via Modbus TCP, stores everything in PostgreSQL, lets you define smart automation rules, and controls your home devices through MQTT or Tuya — all running locally on your own hardware with a full web UI.

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
Sungrow Inverter 2 (string only)       ──┤── Modbus TCP ──▶ Poller ──▶ PostgreSQL
                                                                │
Smart Meter (Tasmota)              ─────── HTTP ───────────────┤
                                                                │
                                                         Rules Engine
                                                                │
                                             ┌──────────────────┤
                                             ▼                  ▼
                                       MQTT Broker         Tuya Cloud
                                             │                  │
                                        Smart Home         Tuya Devices
                                        Devices (Shelly,
                                        Tasmota, etc.)
```

Every 30 seconds, SolarFlow polls all inverters and the smart meter, stores the readings, evaluates your automation rules, and publishes MQTT messages or sends Tuya commands when conditions are met. Live updates are pushed to the web UI via WebSocket.

---

## Features

### 📊 Data Collection
- Polls multiple Sungrow inverters via Modbus TCP (hybrid with battery + string-only)
- Tracks PV power, battery SOC & power, grid import/export, daily yields, inverter temperature, and more
- Optional smart meter support (Tasmota-based SmartMeterReader, e.g. bitShake MT631)
- Stores all readings with UTC timestamps in PostgreSQL

### ⚡ Rules Engine
- Define rules with conditions like *"battery SOC ≥ 95% AND PV power > 1000W"*
- Supports `AND` / `OR` logic with arbitrary conditions
- Actions can target managed devices directly or publish raw MQTT messages
- Auto-reverse actions when conditions clear — no stuck relays
- Configurable cooldowns to prevent rapid toggling
- Seed rules from a YAML file, manage via REST API or the web UI

### 📱 Web UI
- Real-time dashboard showing PV production, battery state, grid flow, and smart meter readings
- Devices page for managing and controlling connected smart home devices
- Rules editor for creating and editing automation rules
- History page with daily energy charts
- Settings page for timezone and smart meter configuration
- Responsive design — works on desktop and mobile

### 🔌 Device Management
- Discover and manage smart home devices via mDNS, MQTT, or Tuya
- Supports MQTT devices (Shelly, Tasmota, etc.) and Tuya devices
- Per-device capability control (toggle switches, dimmers, etc.)
- Device state tracked in real-time via WebSocket

### 🌐 REST API
- `GET /api/health` — system status with last-seen per inverter
- `GET /api/readings/latest` — most recent reading per inverter
- `GET /api/readings` — historical query with filters (inverter, time range, limit)
- `GET /api/stats/today` — cumulative today stats (yield, feed-in, grid buy, self-consumption)
- `GET /api/stats/daily` — historical daily stats (up to 365 days)
- `GET /api/meter/latest` — latest smart meter reading
- `GET /api/meter/readings` — smart meter history with `view=day|week|month|year`
- Full CRUD for rules + event history
- Full CRUD for devices + discovery endpoints

### 📡 Real-time Updates
- WebSocket at `/ws` broadcasts live inverter readings, meter readings, device state changes, and rule events to all connected clients

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Sungrow inverter(s) reachable on your local network via Modbus TCP
- MQTT broker (e.g. Mosquitto) running on the host or network (optional — required only for MQTT device control)

### 1. Configure inverters

Edit `inverters.yaml` to set the IP addresses and Modbus register map for each inverter:

```yaml
inverters:
  - id: inv1
    ip: 192.168.1.10
    port: 502
    unit_id: 1
    has_battery: true
    low_addr_as_holding: false
    registers:
      pv_yield_today: 13001
      grid_power:     13009
      battery_soc:    13022
      # ... see inverters.yaml for full reference
```

### 2. Configure environment

Copy and edit the environment file:

```bash
cp .env.example .env
```

Key variables in `.env`:

| Variable | Description |
|---|---|
| `DB_USER` / `DB_PASSWORD` / `DB_NAME` | PostgreSQL credentials |
| `MQTT_HOST` / `MQTT_PORT` | MQTT broker address |
| `SMART_METER_ENABLED` | Set `true` to enable smart meter |
| `SMART_METER_IP` | IP of the Tasmota SmartMeterReader |
| `TZ` | Timezone for the backend (e.g. `Europe/Berlin`) |

### 3. Run

```bash
docker compose up -d
```

This starts PostgreSQL, the FastAPI backend, and the Vue frontend. Database migrations run automatically on first launch.

### 4. Open the UI

```
http://localhost
```

Or verify the API directly:

```bash
curl http://localhost:8000/api/health
```

---

## Example Rule

Turn on the washing machine when the battery is nearly full and the sun is producing:

```yaml
rules:
  - name: "Battery full — turn on washer"
    enabled: true
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
| Database | PostgreSQL 16 + async SQLAlchemy 2 |
| Migrations | Alembic |
| Inverter Communication | pymodbus (Modbus TCP) |
| Smart Meter | HTTP polling (Tasmota) |
| Device Control | paho-mqtt, tinytuya |
| Device Discovery | mDNS (zeroconf), MQTT, Tuya |
| Real-time | WebSocket |
| Frontend | Vue 3 + TypeScript + Vite |
| UI Components | PrimeVue 4 + Tailwind CSS |
| State Management | Pinia |
| Charts | Chart.js + vue-chartjs |
| Config | pydantic-settings |
| Runtime | Python 3.12 + Node 22, Docker |

---

## License

This project is for personal use. License TBD.
