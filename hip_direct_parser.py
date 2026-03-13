import socket
import struct
from datetime import datetime

DEVICE_IP = "192.168.100.166"
DEVICE_PORT = 5005
TIMEOUT = 5
PAGE_SIZE = 4096

VERIFY_MAP = {
    0: "Pwd",
    1: "Finger",
    2: "Card",
    3: "Face",
    4: "Finger/Pwd",
    5: "Card/Face"
}


# ---------------- NETWORK ---------------- #

def fetch_all_pages():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching all pages...")

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((DEVICE_IP, DEVICE_PORT))

    # HIP attendance pull command (example)
    cmd = b"\x01\x00\x00\x00"
    s.send(cmd)

    buffer = b""
    while True:
        chunk = s.recv(PAGE_SIZE)
        if not chunk:
            break
        buffer += chunk
        if len(chunk) < PAGE_SIZE:
            break

    s.close()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Buffer Size: {len(buffer)} bytes")
    return buffer


# ---------------- PARSER ---------------- #

def decode_time(raw):
    year = raw[0] + 2000
    month = raw[1]
    day = raw[2]
    hour = raw[3]
    minute = raw[4]
    second = raw[5]
    return datetime(year, month, day, hour, minute, second)


def parse(buffer):
    RECORD_SIZE = 16
    pos = 0
    records = []

    last_time = None
    seen = set()

    while pos + RECORD_SIZE <= len(buffer):
        block = buffer[pos:pos + RECORD_SIZE]
        pos += RECORD_SIZE

        try:
            uid = block[0]
            verify = block[1]

            raw_time = block[2:8]
            ts = decode_time(raw_time)

            # ---- ROLLOVER LOGIC ----
            if last_time and ts <= last_time:
                print(">>> Rollover detected. Stopping parse.")
                break

            last_time = ts

            key = (uid, ts)
            if key in seen:
                continue

            seen.add(key)

            records.append({
                "id": uid,
                "time": ts,
                "verify": VERIFY_MAP.get(verify, str(verify))
            })

        except Exception:
            continue

    return records


# ---------------- MAIN ---------------- #

def main():
    buf = fetch_all_pages()
    recs = parse(buf)

    print(f"\n=== FINAL RESULT: {len(recs)} RECORDS ===")
    print("ID | TIME                | VERIFY")
    print("-" * 45)

    for r in recs:
        print(f"{r['id']:<2} | {r['time']} | {r['verify']}")


if __name__ == "__main__":
    main()
