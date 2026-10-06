#!/usr/bin/env python3
"""
Register the PingBerry BlackBerry client with the server.

If the email already has a device of either type, the server responds with
HTTP 202 and delivers a 6-digit verification code to the existing device. We
prompt for that code here and confirm it.

Usage: register.py <email> <uuid> <basedir>
"""

import sys
import json

import requests
from pathlib import Path

import rsa

PINGBERRY_REGISTER_URL = "https://api.pingberry.xyz/register"
PINGBERRY_CONFIRM_URL = "https://api.pingberry.xyz/register/confirm"


def main(argv):
    if len(argv) != 4:
        print("Usage: register.py <email> <uuid> <basedir>", file=sys.stderr)
        return 1

    email = argv[1]
    uuid_str = argv[2]
    basedir = argv[3]

    # Generate the two key pairs (notification encryption + status signing).
    notif_public_key, notif_private_key = rsa.newkeys(2048)
    status_public_key, status_private_key = rsa.newkeys(2048)

    data = {
        "email": email,
        "uuid": uuid_str,
        "notification_private_key": notif_private_key.save_pkcs1().decode(),
        "notification_public_key": notif_public_key.save_pkcs1().decode(),
        "status_private_key": status_private_key.save_pkcs1().decode(),
        "status_public_key": status_public_key.save_pkcs1().decode(),
    }

    client_data_path = Path(basedir) / "app" / "client_data.json"
    client_data_path.write_text(json.dumps(data, indent=2))

    try:
        resp = requests.post(PINGBERRY_REGISTER_URL, json={
            "email": email,
            "uuid": uuid_str,
            "notification_public_key": data["notification_public_key"],
            "status_public_key": data["status_public_key"],
        })
    except requests.RequestException as e:
        print(f"Registration failed: {e}")
        return 1

    if resp.status_code == 201:
        print("Registration complete! Your device has been registered with the server.")
        return 0

    if resp.status_code == 202:
        try:
            body = resp.json()
        except ValueError:
            print("Registration failed: unexpected response from server.")
            return 1

        pending_id = body.get("pending_id")
        if not pending_id:
            print("Registration failed: missing verification id.")
            return 1

        via = body.get("challenge_delivered_via", "")
        via_text = {
            "ios": "your iOS device",
            "blackberry": "your other BlackBerry device",
        }.get(via, "your existing device")

        print(f"A verification code was sent to {via_text}.")
        code = input("Enter the 6-digit verification code: ").strip()

        try:
            confirm = requests.post(
                PINGBERRY_CONFIRM_URL,
                json={"pending_id": pending_id, "code": code},
            )
        except requests.RequestException as e:
            print(f"Verification failed: {e}")
            return 1

        if confirm.status_code == 200:
            print("Registration complete! Your device has been registered with the server.")
            return 0

        print("Verification failed.")
        print(f"Server responded with status {confirm.status_code}:")
        print(confirm.text)
        return 1

    print("Registration failed.")
    print(f"Server responded with status {resp.status_code}:")
    print(resp.text)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
