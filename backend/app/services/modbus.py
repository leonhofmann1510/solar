import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from pymodbus.client import ModbusTcpClient

logger = logging.getLogger(__name__)

# Register offsets relative to base address 13000
REG_PV_YIELD_TODAY = 1   # 13001
REG_PV_POWER = 7         # 13007
REG_GRID_POWER = 9       # 13009
REG_PV_U1 = 10           # 13010
REG_PV_I1 = 11           # 13011
REG_PV_U2 = 12           # 13012
REG_PV_I2 = 13           # 13013
REG_HOUSE_LOAD = 16      # 13016
REG_BATTERY_POWER = 21   # 13021
REG_BATTERY_SOC = 22     # 13022

# Offsets relative to base address 13035
REG_GRID_BUY_TODAY = 0   # 13035
REG_FEED_IN_TODAY = 9    # 13044

# Temperature register
REG_INVERTER_TEMP = 3    # 5003 (from holding registers block at 5000)

BASE_REALTIME = 13000
REALTIME_COUNT = 30
BASE_COUNTER = 13035
COUNTER_COUNT = 15
BASE_DEVICE = 5000
DEVICE_COUNT = 8


def _signed(val: int) -> int:
    """Convert unsigned 16-bit to signed (for grid/battery power)."""
    return val if val < 32768 else val - 65536


@dataclass
class InverterData:
    inverter_id: str
    timestamp: datetime
    pv_power_w: float
    pv_string1_w: float
    pv_string2_w: float
    battery_soc_pct: float | None
    battery_power_w: float | None
    grid_power_w: float
    house_load_w: float
    pv_yield_today_kwh: float
    feed_in_today_kwh: float
    grid_buy_today_kwh: float
    inverter_temp_c: float
    grid_frequency_hz: float


class SungrowModbus:
    """Reads live data from a Sungrow inverter via Modbus TCP."""

    def __init__(self, ip: str, port: int, unit_id: int, inverter_id: str, *, has_battery: bool):
        self.ip = ip
        self.inverter_id = inverter_id
        self.has_battery = has_battery
        self._client = ModbusTcpClient(ip, port=port, timeout=3)
        self._unit_id = unit_id

    def connect(self) -> bool:
        return self._client.connect()

    def read(self) -> InverterData | None:
        """Read all registers and return a structured InverterData, or None on failure."""
        try:
            rt = self._client.read_input_registers(BASE_REALTIME, REALTIME_COUNT, slave=self._unit_id)
            ct = self._client.read_input_registers(BASE_COUNTER, COUNTER_COUNT, slave=self._unit_id)
            dev = self._client.read_input_registers(BASE_DEVICE, DEVICE_COUNT, slave=self._unit_id)

            if rt.isError() or ct.isError() or dev.isError():
                logger.error("Modbus read error on %s", self.inverter_id)
                return None

            r, z = rt.registers, ct.registers

            u_pv1 = r[REG_PV_U1] / 10.0
            i_pv1 = r[REG_PV_I1] / 10.0
            u_pv2 = r[REG_PV_U2] / 10.0
            i_pv2 = r[REG_PV_I2] / 10.0

            return InverterData(
                inverter_id=self.inverter_id,
                timestamp=datetime.now(UTC),
                pv_power_w=float(r[REG_PV_POWER]),
                pv_string1_w=round(u_pv1 * i_pv1, 1),
                pv_string2_w=round(u_pv2 * i_pv2, 1),
                battery_soc_pct=r[REG_BATTERY_SOC] / 10.0 if self.has_battery else None,
                battery_power_w=float(_signed(r[REG_BATTERY_POWER])) if self.has_battery else None,
                grid_power_w=float(_signed(r[REG_GRID_POWER])),
                house_load_w=float(r[REG_HOUSE_LOAD]),
                pv_yield_today_kwh=r[REG_PV_YIELD_TODAY] / 10.0,
                feed_in_today_kwh=z[REG_FEED_IN_TODAY] / 10.0,
                grid_buy_today_kwh=z[REG_GRID_BUY_TODAY] / 10.0,
                inverter_temp_c=dev[REG_INVERTER_TEMP] / 10.0,
                grid_frequency_hz=r[7 + 1] / 10.0 if len(r) > 8 else 50.0,
            )
        except Exception:
            logger.exception("Failed to read inverter %s", self.inverter_id)
            return None

    def close(self) -> None:
        self._client.close()
