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
    grid_power: int | None = None
    grid_buy_today: int | None = None
    feed_in_today: int | None = None
    battery_power: int | None = None
    battery_voltage: int | None = None
    battery_current: int | None = None
    battery_soc: int | None = None
    battery_running_state: int | None = None  # 0=standby, 1=charging, 2=discharging
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
    battery_running_state: int | None
    grid_power_w: float | None
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
                battery_voltage=regs.get("battery_voltage"),
                battery_current=regs.get("battery_current"),
                battery_soc=regs.get("battery_soc"),
                battery_running_state=regs.get("battery_running_state"),
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

    _MAX_BLOCK_GAP = 50  # max register gap before splitting into a new read block

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

    def _read_grouped(self, addresses: list[int], holding: bool) -> dict[int, int] | None:
        """Read addresses in contiguous groups (splits on large gaps), return merged map.

        Addresses far apart (> _MAX_BLOCK_GAP) are read as separate Modbus requests,
        avoiding oversized blocks that span thousands of unused registers.
        """
        if not addresses:
            return {}

        result: dict[int, int] = {}
        group: list[int] = [sorted(addresses)[0]]

        for addr in sorted(addresses)[1:]:
            if addr - group[-1] <= self._MAX_BLOCK_GAP:
                group.append(addr)
            else:
                block = self._read_block(group, holding)
                if block is None:
                    return None
                result.update(block)
                group = [addr]

        block = self._read_block(group, holding)
        if block is None:
            return None
        result.update(block)
        return result

    def _read_all(self) -> tuple[dict[int, int], dict[int, int]] | None:
        """Fetch input and holding registers, splitting non-contiguous address ranges.

        Returns (input_map, holding_map) or None on any failure.
        """
        r = self._regs

        all_addrs = [
            a for a in [
                r.pv_yield_today, r.pv_power, r.grid_power,
                r.pv_u1, r.pv_i1, r.pv_u2, r.pv_i2,
                r.battery_power, r.battery_voltage, r.battery_current,
                r.battery_soc, r.battery_running_state,
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

        input_map = self._read_grouped(input_addrs, holding=False)
        if input_map is None:
            return None

        holding_map = self._read_grouped(holding_addrs, holding=True)
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

    @staticmethod
    def _battery_power(reg_map: dict[int, int], r: RegisterMap) -> float | None:
        """Return signed battery power in W.

        Priority:
        1. voltage × current (×0.1 each) — most accurate when V and I registers exist
        2. single power register with raw × 10 scaling
        3. fallback: signed 0.1 W unit register

        Direction comes from battery_running_state: 1=charging (positive),
        2=discharging (negative), 0=standby (0).
        """
        # Compute magnitude
        if r.battery_voltage is not None and r.battery_current is not None:
            raw_v = reg_map.get(r.battery_voltage)
            raw_i = reg_map.get(r.battery_current)
            if raw_v is None or raw_i is None:
                return None
            watts = round((raw_v / 10.0) * (raw_i / 10.0), 1)
        elif r.battery_power is not None:
            raw = reg_map.get(r.battery_power)
            if raw is None:
                return None
            watts = float(raw * 10)
        else:
            return None

        # Apply direction
        if r.battery_running_state is not None:
            state = reg_map.get(r.battery_running_state, 0) or 0
            if state == 1:    # charging → positive
                return watts
            elif state == 2:  # discharging → negative
                return -watts
            else:             # standby
                return 0.0

        return watts

    # ── Public read ───────────────────────────────────────────────────────────

    def read(self) -> InverterData | None:
        try:
            result = self._read_all()
            if result is None:
                logger.info("[%s] Read failed — reconnecting and retrying", self.inverter_id)
                self._client.close()
                self._client.connect()
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

            pv_string1_w = round(u_pv1 * i_pv1, 1)
            pv_string2_w = round(u_pv2 * i_pv2, 1)

            data = InverterData(
                inverter_id=self.inverter_id,
                timestamp=datetime.now(UTC),
                pv_power_w=round(pv_string1_w + pv_string2_w, 1),
                pv_string1_w=pv_string1_w,
                pv_string2_w=pv_string2_w,
                battery_soc_pct=self._get(reg, r.battery_soc),
                battery_power_w=self._battery_power(reg, r),
                battery_running_state=reg.get(r.battery_running_state) if r.battery_running_state is not None else None,
                grid_power_w=self._get(inp, r.grid_power, signed=True),
                pv_yield_today_kwh=self._get(inp, r.pv_yield_today) or 0.0,
                feed_in_today_kwh=self._get(inp, r.feed_in_today),
                grid_buy_today_kwh=self._get(inp, r.grid_buy_today),
                inverter_temp_c=self._get(reg, r.inverter_temp) or 0.0,
                grid_frequency_hz=self._get(inp, r.grid_frequency) or 0.0,
            )

            logger.info(
                "[%s] pv=%.0fW str1=%.0fW str2=%.0fW yield=%.2fkWh "
                "grid=%s bat_soc=%s bat_pwr=%s "
                "feed_in=%s grid_buy=%s temp=%.1f°C freq=%.2fHz",
                data.inverter_id,
                data.pv_power_w,
                data.pv_string1_w,
                data.pv_string2_w,
                data.pv_yield_today_kwh,
                f"{data.grid_power_w:.0f}W" if data.grid_power_w is not None else "n/a",
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
