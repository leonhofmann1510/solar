#!/usr/bin/env python3
"""
Standalone Tuya device availability tester.

Usage (from project root or backend/):
    python scripts/test_tuya_devices.py

What it does:
  1. LAN scan  — tinytuya.deviceScan() to find all broadcasting Tuya devices
  2. DB lookup — loads known devices + decrypts their local keys
  3. Connect   — attempts d.status() on every found device
  4. Report    — prints a table of what worked and what didn't

Requirements: tinytuya, cryptography, psycopg2 (or asyncpg via sync wrapper),
              .env with DB_PASSWORD and ENCRYPTION_KEY in the usual places.
"""

import os
import sys
import socket
import time

# ---------------------------------------------------------------------------
# Load .env manually (avoid importing the full FastAPI app)
# ---------------------------------------------------------------------------
def _load_env():
    for candidate in (".env", "../.env", "backend/.env"):
        if os.path.isfile(candidate):
            with open(candidate) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
            print(f"[env] Loaded from {candidate}")
            return
    print("[env] No .env file found — relying on existing environment variables")

_load_env()

# ---------------------------------------------------------------------------
# Imports that depend on the environment
# ---------------------------------------------------------------------------
try:
    import tinytuya
except ImportError:
    sys.exit("ERROR: tinytuya not installed. Run: pip install tinytuya")

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    sys.exit("ERROR: cryptography not installed. Run: pip install cryptography")

try:
    import psycopg2
    import psycopg2.extras
    _HAS_PSYCOPG2 = True
except ImportError:
    _HAS_PSYCOPG2 = False

# ---------------------------------------------------------------------------
# Crypto helper (mirrors app/crypto.py without importing the app)
# ---------------------------------------------------------------------------
_ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "")

def decrypt_key(ciphertext: str) -> str | None:
    if not ciphertext or not _ENCRYPTION_KEY:
        return None
    try:
        f = Fernet(_ENCRYPTION_KEY.encode())
        return f.decrypt(ciphertext.encode()).decode()
    except (InvalidToken, Exception):
        return None

# ---------------------------------------------------------------------------
# DB: load known Tuya devices
# ---------------------------------------------------------------------------
def load_db_devices() -> list[dict]:
    """Return list of {name, raw_id, ip, local_key, version} from the DB."""
    if not _HAS_PSYCOPG2:
        print("[db] psycopg2 not installed — skipping DB lookup (no key matching)")
        return []

    dsn = {
        "host":     os.environ.get("DB_HOST", "localhost"),
        "port":     int(os.environ.get("DB_PORT", 5432)),
        "user":     os.environ.get("DB_USER", "solarflow"),
        "password": os.environ.get("DB_PASSWORD", ""),
        "dbname":   os.environ.get("DB_NAME", "solar"),
        "connect_timeout": 5,
    }
    try:
        conn = psycopg2.connect(**dsn)
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("""
            SELECT name, raw_id, ip_address, tuya_local_key, meta
            FROM devices
            WHERE protocol = 'tuya'
            ORDER BY name
        """)
        rows = cur.fetchall()
        conn.close()
    except Exception as e:
        print(f"[db] Connection failed: {e}")
        return []

    devices = []
    for row in rows:
        local_key = decrypt_key(row["tuya_local_key"] or "")
        meta = row["meta"] or {}
        devices.append({
            "name":      row["name"],
            "raw_id":    row["raw_id"],
            "ip":        row["ip_address"],
            "local_key": local_key,
            "version":   float(meta.get("tuya_version", 3.3)),
        })
    return devices

# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------
def is_reachable(ip: str, port: int = 6668, timeout: float = 2.0) -> bool:
    """TCP ping to the Tuya local port."""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False

def try_status(ip: str, raw_id: str, local_key: str, version: float) -> tuple[bool, str]:
    """Attempt tinytuya status() call. Returns (success, detail)."""
    try:
        d = tinytuya.OutletDevice(
            dev_id=raw_id,
            address=ip,
            local_key=local_key,
            version=version,
        )
        d.set_socketPersistent(False)
        result = d.status()
        if result and "dps" in result:
            return True, f"dps={result['dps']}"
        if result and result.get("Error"):
            return False, f"Tuya error: {result['Error']}"
        return False, f"Unexpected response: {result}"
    except Exception as e:
        return False, str(e)

# ---------------------------------------------------------------------------
# ANSI colours (graceful fallback on non-TTY)
# ---------------------------------------------------------------------------
_USE_COLOR = sys.stdout.isatty()
GREEN  = "\033[32m" if _USE_COLOR else ""
RED    = "\033[31m" if _USE_COLOR else ""
YELLOW = "\033[33m" if _USE_COLOR else ""
CYAN   = "\033[36m" if _USE_COLOR else ""
RESET  = "\033[0m"  if _USE_COLOR else ""
BOLD   = "\033[1m"  if _USE_COLOR else ""

def ok(s):    return f"{GREEN}{s}{RESET}"
def err(s):   return f"{RED}{s}{RESET}"
def warn(s):  return f"{YELLOW}{s}{RESET}"
def info(s):  return f"{CYAN}{s}{RESET}"

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print(f"\n{BOLD}=== Tuya Device Availability Test ==={RESET}\n")

    # 1. LAN scan
    print(f"{BOLD}[1/3] LAN scan (tinytuya.deviceScan) …{RESET}")
    t0 = time.time()
    try:
        scan_raw: dict = tinytuya.deviceScan(verbose=False)
    except Exception as e:
        print(err(f"  LAN scan failed: {e}"))
        scan_raw = {}
    elapsed = time.time() - t0

    # scan_raw: { ip: {gwId, version, productKey, ...} }
    scan: dict[str, dict] = {}
    for ip, info_dict in scan_raw.items():
        gw_id = info_dict.get("gwId") or info_dict.get("id", "")
        scan[gw_id] = {
            "ip":      ip,
            "version": float(info_dict.get("version", 3.3)),
            "raw":     info_dict,
        }

    print(f"  Found {len(scan)} device(s) on the LAN in {elapsed:.1f}s\n")
    if scan:
        print(f"  {'gwId':<30} {'IP':<18} {'Ver'}")
        print(f"  {'-'*30} {'-'*18} {'-'*5}")
        for gw_id, s in scan.items():
            print(f"  {gw_id:<30} {s['ip']:<18} {s['version']}")
    print()

    # 2. DB lookup
    print(f"{BOLD}[2/3] Loading known devices from DB …{RESET}")
    db_devices = load_db_devices()
    print(f"  Found {len(db_devices)} Tuya device(s) in DB\n")

    # 3. Attempt connection for each device
    print(f"{BOLD}[3/3] Connection tests{RESET}\n")

    results = []

    # --- devices known in DB ---
    for dev in db_devices:
        raw_id    = dev["raw_id"]
        db_ip     = dev["ip"]
        local_key = dev["local_key"]
        version   = dev["version"]

        # Prefer IP from LAN scan (may be fresher)
        scan_info = scan.get(raw_id, {})
        ip        = scan_info.get("ip") or db_ip
        in_scan   = bool(scan_info)
        if scan_info.get("version"):
            version = scan_info["version"]

        row = {
            "name":    dev["name"],
            "raw_id":  raw_id,
            "ip":      ip or "—",
            "version": version,
            "in_scan": in_scan,
            "has_key": bool(local_key),
            "tcp_ok":  False,
            "api_ok":  False,
            "detail":  "",
        }

        if not ip:
            row["detail"] = "No IP address"
            results.append(row)
            continue

        row["tcp_ok"] = is_reachable(ip)

        if not row["tcp_ok"]:
            row["detail"] = "TCP port 6668 unreachable"
            results.append(row)
            continue

        if not local_key:
            row["detail"] = "No local key (not yet paired or decrypt failed)"
            results.append(row)
            continue

        row["api_ok"], row["detail"] = try_status(ip, raw_id, local_key, version)
        results.append(row)

    # --- devices found on LAN but NOT in DB ---
    db_ids = {d["raw_id"] for d in db_devices}
    for gw_id, s in scan.items():
        if gw_id in db_ids:
            continue
        row = {
            "name":    "(unknown)",
            "raw_id":  gw_id,
            "ip":      s["ip"],
            "version": s["version"],
            "in_scan": True,
            "has_key": False,
            "tcp_ok":  is_reachable(s["ip"]),
            "api_ok":  False,
            "detail":  "Not in DB — add via QR login",
        }
        results.append(row)

    # --- Print summary table ---
    col_name    = max((len(r["name"])   for r in results), default=4) + 2
    col_id      = max((len(r["raw_id"]) for r in results), default=6) + 2

    header = (
        f"  {'Name':<{col_name}} {'ID':<{col_id}} {'IP':<18} "
        f"{'Ver':<5} {'LAN':>3} {'TCP':>3} {'API':>3}  Detail"
    )
    sep = "  " + "-" * (len(header) - 2)
    print(header)
    print(sep)

    for r in results:
        lan_sym = ok("YES") if r["in_scan"]  else warn("NO ")
        tcp_sym = ok("OK ") if r["tcp_ok"]   else err("FAIL")
        api_sym = ok("OK ") if r["api_ok"]   else err("FAIL")

        print(
            f"  {r['name']:<{col_name}} {r['raw_id']:<{col_id}} "
            f"{r['ip']:<18} {r['version']:<5} "
            f"{lan_sym}  {tcp_sym}  {api_sym}  {r['detail']}"
        )

    # --- Summary ---
    total   = len(results)
    api_ok  = sum(1 for r in results if r["api_ok"])
    tcp_ok  = sum(1 for r in results if r["tcp_ok"])
    in_scan = sum(1 for r in results if r["in_scan"])

    print(f"\n{BOLD}Summary:{RESET}  {in_scan}/{total} on LAN  |  "
          f"{tcp_ok}/{total} TCP reachable  |  {api_ok}/{total} API working\n")

    if api_ok < total:
        print(f"{BOLD}Possible causes for failures:{RESET}")
        print("  • Wrong IP stored in DB  → trigger a LAN re-scan via the UI")
        print("  • Device offline / rebooted and got new IP via DHCP")
        print("  • Local key changed      → re-run QR login to refresh the key")
        print("  • Wrong protocol version → version mismatch (3.3 vs 3.4/3.5)")
        print("  • Firewall / VLAN        → device not reachable from this host")
        print()

if __name__ == "__main__":
    main()
