"""
Usage:
    python3 get_uuid_from_pin_and_email.py user@example.com [path_to_device_file] [--uuid-only]

- Reads PIN from deviceproperties
- Combines PIN + email to generate UUIDv5
"""

import sys
import re
import uuid
from pathlib import Path

DEFAULT_PATH = "/pps/services/private/deviceproperties"
NAMESPACE_UUID = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # DNS namespace
PIN_RE = re.compile(r"\bdevicepin::0x([0-9A-Fa-f]+)\b")

def parse_pin_from_text(text):
    m = PIN_RE.search(text)
    if m:
        return m.group(1)
    alt = re.search(r"\bpin::0x([0-9A-Fa-f]+)\b", text)
    return alt.group(1) if alt else None

def generate_uuid(pin_hex: str, email: str, namespace=NAMESPACE_UUID) -> uuid.UUID:
    combined = f"{pin_hex.upper()}:{email.lower()}"
    return uuid.uuid5(namespace, combined)

def main(argv):
    if len(argv) < 2:
        print("Usage: python3 get_uuid_from_pin_and_email.py <email> [path] [--uuid-only]")
        return 1

    email = argv[1]
    path = Path(argv[2]) if len(argv) >= 3 and not argv[2].startswith("--") else Path(DEFAULT_PATH)
    uuid_only = "--uuid-only" in argv

    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 2

    try:
        text = path.read_text()
    except Exception as e:
        print(f"Error reading {path}: {e}", file=sys.stderr)
        return 3

    pin_hex = parse_pin_from_text(text)
    if not pin_hex:
        print("PIN not found in file.", file=sys.stderr)
        return 4

    pin_norm = pin_hex.upper().zfill(8)[-8:]
    try:
        uuid_val = generate_uuid(pin_norm, email)
    except Exception as e:
        print(f"UUID generation failed: {e}", file=sys.stderr)
        return 5

    if uuid_only:
        print(str(uuid_val))
    else:
        print("Email                :", email)
        print("PIN (hex, normalized):", pin_norm)
        print("UUID (v5)            :", uuid_val)

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
