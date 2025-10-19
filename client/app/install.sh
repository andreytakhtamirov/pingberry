#!/bin/bash
BASEDIR="$(cd "$(dirname "$0")" && pwd)/../"

SKIP_ROTATION=0
# Parse args
for arg in "$@"; do
    if [ "$arg" = "--skip-rotation" ]; then
        SKIP_ROTATION=1
    fi
done

# --- Step 1: Use binaries bundled in environment ---
PYTHON_BIN="$BASEDIR/tools/python3/python3"
PYTHONHOME="$BASEDIR/"
PYTHONPATH="$BASEDIR/lib/python3.11"
LD_LIBRARY_PATH="$BASEDIR/lib:$LD_LIBRARY_PATH"

PROFILE="$HOME/.profile"
PINGBERRY_ENV_DIR="$BASEDIR/"

if [ "$SKIP_ROTATION" -eq 1 ]; then
    echo "Skipping key rotation and registration (client_data.json exists)."
else
    # --- Step 2: Prompt for email ---
    read -rp "Enter your email address: " EMAIL

    # --- Step 3: Parse PIN and generate UUID ---
    echo "Generating UUID from device details..."
    UUID=$($PYTHON_BIN "$PINGBERRY_ENV_DIR/app/get_uuid.py" "$EMAIL" --uuid-only)
    if [ -z "$UUID" ]; then
        echo "Failed to generate UUID"
        exit 1
    fi
    echo "UUID: $UUID"

    # --- Step 4: Generate keys and persist everything ---
    echo "Generating notification encryption keys..."
    $PYTHON_BIN <<EOF
import sys
import rsa
import json
import requests
from pathlib import Path
from uuid import UUID

PINGBERRY_URL = "https://scoreless-clinically-carol.ngrok-free.app/server/register"
basedir = "$PINGBERRY_ENV_DIR"
email = "$EMAIL"
uuid_str = "$UUID"
uuid_val = UUID(uuid_str)

# --- Generate keys ---
# 1. Notification encryption key pair (server ➜ client)
notif_public_key, notif_private_key = rsa.newkeys(2048)

# 2. Status signing key pair (client ➜ server)
status_public_key, status_private_key = rsa.newkeys(2048)

# --- Serialize keys ---
data = {
    "email": email,
    "uuid": str(uuid_val),

    "notification_private_key": notif_private_key.save_pkcs1().decode(),
    "notification_public_key": notif_public_key.save_pkcs1().decode(),

    "status_private_key": status_private_key.save_pkcs1().decode(),
    "status_public_key": status_public_key.save_pkcs1().decode()
}

file_path = Path(basedir) / "app" / "client_data.json"
file_path.write_text(json.dumps(data, indent=2))

# --- Send public keys to server ---
try:
    resp = requests.post(PINGBERRY_URL, json={
        "email": email,
        "uuid": str(uuid_val),
        "notification_public_key": data["notification_public_key"],
        "status_public_key": data["status_public_key"]
    })
except requests.RequestException as e:
    print(f"Registration failed: {e}")
    sys.exit(1) 

if resp.status_code == 201:
    print("Registration complete! Your device has been registered with the server.")
elif resp.status_code == 200:
    print("Existing registration found. Keys were rotated successfully.")
else:
    print("Registration failed.")
    print(f"Server responded with status {resp.status_code}:")
    print(resp.text)
EOF
fi

# Ensure the profile file exists
touch "$PROFILE"

# --- Step 5: Add to shell startup (only once, only for interactive non‑SSH shells) ---
# Only add block if it's not already present
if ! grep -Fq "$PINGBERRY_ENV_DIR/app/run.sh" "$PROFILE"; then
    cat >> "$PROFILE" <<EOF

# Start PingBerry Notification Client
if [ -t 0 ] && [ -z "\$SSH_CONNECTION" ]; then
    "$PINGBERRY_ENV_DIR/bin/bash" "$PINGBERRY_ENV_DIR/app/run.sh" > /dev/null 2>&1 &
    echo "Started PingBerry Notification Client"
fi
EOF

    echo "Added notification service to Term48 startup."
    echo "Setup complete. Restart Term48 to start the notification service."
else
    echo "Notification service already in Term48 startup."
fi

