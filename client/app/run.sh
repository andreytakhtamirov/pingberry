# Directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PYTHON_BIN="$SCRIPT_DIR/../tools/python3/python3"
PYTHONHOME="$SCRIPT_DIR/../"
export SSL_CERT_FILE="$SCRIPT_DIR/../lib/python3.11/site-packages/certifi/cacert.pem"

CLIENT_DATA="$SCRIPT_DIR/client_data.json"
MQTT_CREDS="$SCRIPT_DIR/mqtt_credentials.json"

# --- Check client is registered ---
if [ ! -f "$CLIENT_DATA" ]; then
    echo "Client is not registered. Run setup first."
    exit 1
fi

if [ ! -f "$MQTT_CREDS" ]; then
    echo "MQTT credentials not found."
    exit 1
fi

# --- Run the subscriber in background ---
$PYTHON_BIN "$SCRIPT_DIR/subscriber.py" --client-data "$CLIENT_DATA" --mqtt-credentials "$MQTT_CREDS"
