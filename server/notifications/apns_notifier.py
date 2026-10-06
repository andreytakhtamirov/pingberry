"""
Apple Push Notification service (APNs) delivery for iOS devices.

Sends HTTP/2 requests to APNs, authenticated with a short-lived provider token
(JWT) signed using the APNs authentication key (.p8, ES256). See Apple's
"Establishing a token-based connection to APNs" documentation.

The `httpx` dependency is optional: if it is not installed, the server still
runs and APNs delivery is simply skipped (see `send`).
"""

import base64
import json
import time

from Crypto.Hash import SHA256
from Crypto.PublicKey import ECC
from Crypto.Signature import DSS

try:
    import httpx
except ImportError:  # APNs is optional; keep the server importable without it.
    httpx = None


class APNSNotification:
    def __init__(self, team_id=None, key_id=None, private_key_path=None,
                 topic=None, use_sandbox=True):
        self.team_id = (team_id or "").strip()
        self.key_id = (key_id or "").strip()
        self.private_key_path = private_key_path
        self.topic = (topic or "").strip()
        self.use_sandbox = use_sandbox

        self._signing_key = None
        self.enabled = bool(self.team_id and self.key_id and self.private_key_path and self.topic)

        if self.enabled:
            try:
                with open(self.private_key_path, "rb") as f:
                    self._signing_key = ECC.import_key(f.read())
            except Exception as e:
                print(f"[WARN] Could not load APNs private key: {e}")
                self.enabled = False

    def _base64url(self, data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    def _provider_token(self) -> str:
        """Build and sign a short-lived APNs provider token (ES256 JWT)."""
        header = {"alg": "ES256", "kid": self.key_id}
        claims = {"iss": self.team_id, "iat": int(time.time())}
        signing_input = (
            self._base64url(json.dumps(header, separators=(",", ":")).encode())
            + "."
            + self._base64url(json.dumps(claims, separators=(",", ":")).encode())
        )
        signer = DSS.new(self._signing_key, "fips-186-3", encoding="binary")
        signature = signer.sign(SHA256.new(signing_input.encode()))
        return signing_input + "." + self._base64url(signature)

    def _endpoint(self, device_token: str) -> str:
        host = "api.sandbox.push.apple.com" if self.use_sandbox else "api.push.apple.com"
        return f"https://{host}/3/device/{device_token}"

    async def send(self, title: str, body: str, device_token: str) -> bool:
        """Send an alert notification to a single APNs device token."""
        if not self.enabled:
            print("[WARN] APNs is not configured; skipping iOS delivery.")
            return False
        if httpx is None:
            print("[WARN] httpx is not installed; skipping iOS delivery (pip install 'httpx[http2]').")
            return False

        payload = {
            "aps": {
                "alert": {"title": title, "body": body},
                "sound": "default",
            }
        }
        headers = {
            "authorization": f"bearer {self._provider_token()}",
            "apns-topic": self.topic,
            "apns-push-type": "alert",
            "apns-priority": "10",
        }

        try:
            async with httpx.AsyncClient(http2=True, timeout=10.0) as client:
                response = await client.post(
                    self._endpoint(device_token), json=payload, headers=headers
                )
        except Exception as e:
            print(f"[ERROR] APNs send exception: {e}")
            return False

        if response.status_code == 200:
            print(f"[INFO] APNs push delivered to {device_token[:8]}...")
            return True

        print(f"[ERROR] APNs push failed: HTTP {response.status_code} - {response.text}")
        return False
