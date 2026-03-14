"""Sungrow Modbus TCP reader with fully configurable register addresses.

Register addresses are absolute (e.g. 13007), exactly as shown in the
inverter's Modbus documentation — no base offsets, no manual arithmetic.

Detection of register type is automatic:
  address >= 10000  →  input   register  (read_input_registers)
  address <  10000  →  holding register  (read_holding_registers)

Reads are batched into the minimal contiguous blocks needed to cover all
configured addresses, keeping TCP round-trips low.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pymodbus.client import ModbusTcpClient

logger = logging.getLogger(__name__)
logging.getLogger("pymodbus").setLevel(logging.CRITICAL)


def _signed(val: int) -> int:
    """Convert unsigned 16-bit to signed (Sungrow two's complement)."""
    return val if val < 32768 else val - 65536


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class RegisterMap:
    """Absolute Modbus addresses for every data point of one inverter.
    Set any field to None if the inverter does not expose that register.
    """
    pv_yield_today: int | None
    pv_power: int | None
    pv_u1: int | None
    pv_i1: int | None
    pv_u2: int | None
    pv_i2: int | None
    inverter_temp: int | None
    house_load: int | None = None
    grid_power: int | None = None
    grid_buy_today: int | None = None
    feed_in_today: int | None = None
    battery_power: int | None = None
    battery_soc: int | None = None
    grid_frequency: int | None = None


@dataclass
class InverterConfig:
    id: str
    ip: str
    port: int
    unit_id: int
    has_battery: bool
    registers: RegisterMap
    low_addr_as_holding: bool = True  # if False, all addresses use FC4 (input registers)


@dataclass
class InverterData:
    inverter_id: str
    timestamp: datetime
    pv_power_w: float
    pv_string1_w: float
    pv_string2_w: float
    battery_soc_pct: float | None
    battery_power_w: float | None
    grid_power_w: float | None
    house_load_w: float | None
    pv_yield_today_kwh: float
    feed_in_today_kwh: float | None
    grid_buy_today_kwh: float | None
    inverter_temp_c: float
    grid_frequency_hz: float


# ── YAML loader ───────────────────────────────────────────────────────────────

def load_inverter_configs(path: str) -> list[InverterConfig]:
    """Load inverter configs from a YAML file. Returns an empty list on error."""
    p = Path(path)
    if not p.exists():
        logger.error("Inverters config not found: %s", p)
        return []

    with open(p) as f:
        raw = yaml.safe_load(f)

    configs: list[InverterConfig] = []
    for entry in raw.get("inverters", []):
        regs = entry["registers"]
        configs.append(InverterConfig(
            id=entry["id"],
            ip=entry["ip"],
            port=entry.get("port", 502),
            unit_id=entry.get("unit_id", 1),
            has_battery=entry.get("has_battery", False),
            low_addr_as_holding=entry.get("low_addr_as_holding", True),
            registers=RegisterMap(
                pv_yield_today=regs["pv_yield_today"],
                house_load=regs["house_load"],
                pv_power=regs["pv_power"],
                grid_power=regs["grid_power"],
                pv_u1=regs["pv_u1"],
                pv_i1=regs["pv_i1"],
                pv_u2=regs["pv_u2"],
                pv_i2=regs["pv_i2"],
                grid_buy_today=regs["grid_buy_today"],
                feed_in_today=regs["feed_in_today"],
                inverter_temp=regs["inverter_temp"],
                battery_power=regs.get("battery_power"),
                battery_soc=regs.get("battery_soc"),
                grid_frequency=regs.get("grid_frequency"),
            ),
        ))
        logger.info("Loaded inverter config: %s @ %s:%d", entry["id"], entry["ip"], entry.get("port", 502))

    return configs


# ── Modbus client ─────────────────────────────────────────────────────────────

class SungrowModbus:
    """Reads live data from a Sungrow inverter using absolute register addresses."""

    def __init__(self, cfg: InverterConfig) -> None:
        self.inverter_id = cfg.id
        self.ip = cfg.ip
        self._cfg = cfg
        self._regs = cfg.registers
        self._client = ModbusTcpClient(cfg.ip, port=cfg.port, timeout=3)
        self._unit = cfg.unit_id

    def connect(self) -> bool:
        return self._client.connect()

    def close(self) -> None:
        self._client.close()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _read_block(self, addresses: list[int], holding: bool) -> dict[int, int] | None:
        """Read a minimal contiguous block covering all given addresses.

        Returns a dict mapping absolute address → raw register value,
        or None if the read failed.
        """
        if not addresses:
            return {}

        min_addr = min(addresses)
        max_addr = max(addresses)
        count = max_addr - min_addr + 1

        if holding:
            resp = self._client.read_holding_registers(min_addr, count=count, slave=self._unit)
        else:
            resp = self._client.read_input_registers(min_addr, count=count, slave=self._unit)

        if resp.isError():
            logger.error(
                "Modbus %s read failed on %s (addr=%d count=%d fc=%s exc=%s)",
                "holding" if holding else "input",
                self.inverter_id,
                min_addr, count,
                getattr(resp, "function_code", None),
                getattr(resp, "exception_code", None),
            )
            return None

        return {min_addr + i: v for i, v in enumerate(resp.registers)}

    def _read_all(self) -> tuple[dict[int, int], dict[int, int]] | None:
        """Fetch input and holding registers in one call each.

        Returns (input_map, holding_map) or None on any failure.
        """
        r = self._regs

        all_addrs = [
            a for a in [
                r.pv_yield_today, r.house_load, r.pv_power, r.grid_power,
                r.pv_u1, r.pv_i1, r.pv_u2, r.pv_i2,
                r.battery_power, r.battery_soc,
                r.grid_buy_today, r.feed_in_today,
                r.grid_frequency, r.inverter_temp,
            ]
            if a is not None
        ]

        if self._cfg.low_addr_as_holding:
            input_addrs = [a for a in all_addrs if a >= 10000]
            holding_addrs = [a for a in all_addrs if a < 10000]
        else:
            input_addrs = all_addrs
            holding_addrs = []

        input_map = self._read_block(input_addrs, holding=False)
        if input_map is None:
            return None

        holding_map = self._read_block(holding_addrs, holding=True)
        if holding_map is None:
            return None

        return input_map, holding_map

    @staticmethod
    def _get(reg_map: dict[int, int], address: int | None, *, signed: bool = False) -> float | None:
        """Look up an address in a register map and return the scaled value."""
        if address is None:
            return None
        raw = reg_map.get(address)
        if raw is None:
            return None
        val = _signed(raw) if signed else raw
        return val / 10.0

    # ── Public read ───────────────────────────────────────────────────────────

    def read(self) -> InverterData | None:
        try:
            result = self._read_all()
            if result is None:
                return None

            inp, hld = result
            reg = {**inp, **hld}  # unified map — handles low_addr_as_holding=false where hld is empty
            r = self._regs

            u_pv1 = self._get(inp, r.pv_u1) or 0.0
            i_pv1 = self._get(inp, r.pv_i1) or 0.0
            u_pv2 = self._get(inp, r.pv_u2) or 0.0
            i_pv2 = self._get(inp, r.pv_i2) or 0.0

            data = InverterData(
                inverter_id=self.inverter_id,
                timestamp=datetime.now(UTC),
                pv_power_w=self._get(inp, r.pv_power) or 0.0,
                pv_string1_w=round(u_pv1 * i_pv1, 1),
                pv_string2_w=round(u_pv2 * i_pv2, 1),
                battery_soc_pct=self._get(inp, r.battery_soc),
                battery_power_w=self._get(inp, r.battery_power, signed=True),
                grid_power_w=self._get(inp, r.grid_power, signed=True),
                house_load_w=self._get(inp, r.house_load),
                pv_yield_today_kwh=self._get(inp, r.pv_yield_today) or 0.0,
                feed_in_today_kwh=self._get(inp, r.feed_in_today),
                grid_buy_today_kwh=self._get(inp, r.grid_buy_today),
                inverter_temp_c=self._get(reg, r.inverter_temp) or 0.0,
                grid_frequency_hz=self._get(inp, r.grid_frequency) or 0.0,
            )

            logger.info(
                "[%s] pv=%.0fW str1=%.0fW str2=%.0fW yield=%.2fkWh "
                "grid=%s house=%s bat_soc=%s bat_pwr=%s "
                "feed_in=%s grid_buy=%s temp=%.1f°C freq=%.2fHz",
                data.inverter_id,
                data.pv_power_w,
                data.pv_string1_w,
                data.pv_string2_w,
                data.pv_yield_today_kwh,
                f"{data.grid_power_w:.0f}W" if data.grid_power_w is not None else "n/a",
                f"{data.house_load_w:.0f}W" if data.house_load_w is not None else "n/a",
                f"{data.battery_soc_pct:.0f}%" if data.battery_soc_pct is not None else "n/a",
                f"{data.battery_power_w:.0f}W" if data.battery_power_w is not None else "n/a",
                f"{data.feed_in_today_kwh:.2f}kWh" if data.feed_in_today_kwh is not None else "n/a",
                f"{data.grid_buy_today_kwh:.2f}kWh" if data.grid_buy_today_kwh is not None else "n/a",
                data.inverter_temp_c,
                data.grid_frequency_hz,
            )

            return data

        except Exception:
            logger.exception("Failed to read inverter %s", self.inverter_id)
            return None
