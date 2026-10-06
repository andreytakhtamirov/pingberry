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

    # --- Step 4: Generate keys and register with the server ---
    echo "Generating encryption keys and registering with the server..."
    "$PYTHON_BIN" "$PINGBERRY_ENV_DIR/app/register.py" "$EMAIL" "$UUID" "$PINGBERRY_ENV_DIR" || {
        echo "Registration failed."
        exit 1
    }
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

