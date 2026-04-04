from pymodbus.client import ModbusTcpClient
from pymodbus.constants import Endian
import time

inverters = [
    {"name": "SH10RT (Hybrid)", "ip": "192.168.178.24", "unit_id": 1},
    {"name": "SG12RT", "ip": "192.168.178.26", "unit_id": 1}
]

def read_sungrow_v3(inv):
    client = ModbusTcpClient(inv["ip"], port=502)
    if not client.connect():
        print(f"❌ Keine Verbindung zu {inv['ip']}")
        return

    print(f"\n--- {inv['name']} ({inv['ip']}) ---")

    try:
        # Block 1: PV & Leistung (Start bei 5007, da 5000-5006 oft Fehler werfen)
        res = client.read_input_registers(address=5007, count=10, slave=inv["unit_id"])
        
        if not res.isError():
            # Wir nutzen die neue v3.x Methode. 
            # wordorder=Endian.LITTLE korrigiert die Millionen-Watt-Anzeige
            p_total = client.convert_from_registers(res.registers[0:2], data_type=client.DATATYPE.INT32, word_order=Endian.LITTLE)
            
            # MPPTs (16-bit, kein Word-Order Problem da nur 1 Register)
            v1 = res.registers[3] * 0.1
            a1 = res.registers[4] * 0.1
            v2 = res.registers[5] * 0.1
            a2 = res.registers[6] * 0.1
            v3 = res.registers[7] * 0.1
            a3 = res.registers[8] * 0.1

            print(f"Leistung (Gesamt): {p_total} W")
            print(f"MPPT 1: {round(v1*a1,1):>7} W ({round(v1,1)}V | {round(a1,2)}A)")
            print(f"MPPT 2: {round(v2*a2,1):>7} W ({round(v2,1)}V | {round(a2,2)}A)")
            if v3 > 10: # Nur zeigen wenn Spannung anliegt
                print(f"MPPT 3: {round(v3*a3,1):>7} W ({round(v3,1)}V | {round(a3,2)}A)")

        # Block 2: Hybrid Spezifisch (Batterie / Haus)
        if "SH10RT" in inv["name"]:
            # Wir lesen gezielt kleinere Blöcke um 132-Fehler zu vermeiden
            res_p = client.read_input_registers(address=13007, count=4, slave=inv["unit_id"])
            res_soc = client.read_input_registers(address=13021, count=1, slave=inv["unit_id"])

            if not res_p.isError():
                load_p = client.convert_from_registers(res_p.registers[0:2], data_type=client.DATATYPE.INT32, word_order=Endian.LITTLE)
                export_p = client.convert_from_registers(res_p.registers[2:4], data_type=client.DATATYPE.INT32, word_order=Endian.LITTLE)

                # Bei Sungrow ist Export negativ = Netzbezug
                print(f"Hausverbrauch:    {abs(load_p)} W")
                if export_p >= 0:
                    print(f"Netz-Einspeisung: {export_p} W")
                else:
                    print(f"Netz-Bezug:       {abs(export_p)} W")

            if not res_soc.isError():
                print(f"Batterie SOC:     {res_soc.registers[0] * 0.1} %")

            # Batterie-Register Dump: findet State + Power Register
            print("\n--- Batterie Register Dump (13000-13040) ---")
            print(f"  {'Addr':>6}  {'raw':>6}  {'×0.1':>8}  {'×10W':>7}  {'signed':>7}  note")
            res_bat = client.read_input_registers(address=13000, count=40, slave=inv["unit_id"])
            if not res_bat.isError():
                for i, val in enumerate(res_bat.registers):
                    addr = 13000 + i
                    signed = val if val < 32768 else val - 65536
                    note = ""
                    if val <= 5:
                        note = "<-- state candidate?"
                    elif 200 <= val <= 500:
                        note = "<-- power? (×0.1W)"
                    print(f"  [{addr}]  {val:>6}  {val*0.1:>8.1f}  {val*10:>7}W  {signed:>7}  {note}")

    except Exception as e:
        print(f"Fehler: {e}")
    finally:
        client.close()

for inv in inverters:
    read_sungrow_v3(inv)
    time.sleep(0.5)