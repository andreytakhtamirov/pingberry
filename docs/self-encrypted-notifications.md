# Sending Self-Encrypted Push Notifications

## Description
This guide explains how to send self-encrypted push notifications using a client’s public key. By encrypting the notification title and body before transmission, the PingBerry server and all intermediaries remain blind to the contents, ensuring true end-to-end privacy. Only the intended client can decrypt and read the message, guaranteeing confidentiality from sender to recipient.

Steps involved:
1. Retrieve a registered user's public key
2. Encrypt your title and message using RSA with PKCS#1 v1.5 padding
3. Send the encrypted payload to the server

⚠️ Note: The server does not perform any encryption or decryption—it simply forwards encrypted payloads. This design supports zero-knowledge push delivery.

## Encryption Method
All message contents must be encrypted using the following specifications to be correctly parsed by PingBerry clients:
- Asymmetric Algorithm: **RSA**
- Key Size: **2048 bits**
- Padding Scheme: **PKCS#1 v1.5**

### Python Example
```
import requests, base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

API_BASE_URL = "https://api.pingberry.xyz"
RECIPIENT_EMAIL = "user@email.com"
TITLE = "Hello PingBerry!"
MESSAGE = "This is a secret message."

def get_public_key(email: str) -> str:
    res = requests.post(f"{API_BASE_URL}/clients/public-key", json={"recipient_email": email})
    res.raise_for_status()
    return res.json()["notification_public_key"]

def encrypt_message(public_key_pem: str, message: str) -> str:
    pubkey = serialization.load_pem_public_key(public_key_pem.encode())
    encrypted = pubkey.encrypt(message.encode(), padding.PKCS1v15())
    return base64.b64encode(encrypted).decode()

def send_notification(email, encrypted_title, encrypted_body):
    payload = {
        "recipient_email": email,
        "encrypted_title": encrypted_title,
        "encrypted_body": encrypted_body,
        "queue_if_offline": False,
        "collapse_duplicates": False,
    }
    res = requests.post(f"{API_BASE_URL}/notify/encrypted", json=payload)
    res.raise_for_status()
    return res.json()

if __name__ == "__main__":
    try:
        print("🔑 Fetching public key...")
        pk = get_public_key(RECIPIENT_EMAIL)

        print("🔐 Encrypting...")
        title_enc = encrypt_message(pk, TITLE)
        msg_enc = encrypt_message(pk, MESSAGE)

        print("📤 Sending notification...")
        result = send_notification(RECIPIENT_EMAIL, title_enc, msg_enc)

        print("✅ Sent:", result)
    except Exception as e:
        print("❌ Error:", e)
```

### Node.js Example
```
import fetch from "node-fetch";
import forge from "node-forge";

const API_BASE_URL = "https://api.pingberry.xyz";
const RECIPIENT_EMAIL = "user@email.com";
const TITLE = "Hello PingBerry!";
const MESSAGE = "This is a secret message.";

async function getPublicKey(email) {
    const res = await fetch(`${API_BASE_URL}/clients/public-key`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ recipient_email: email }),
    });
    const data = await res.json();
    return data.notification_public_key;
}

function encryptMessage(publicKeyPem, message) {
    const pubKey = forge.pki.publicKeyFromPem(publicKeyPem);
    const encrypted = pubKey.encrypt(message, "RSAES-PKCS1-V1_5");
    return Buffer.from(encrypted, "binary").toString("base64");
}

async function sendNotification(email, titleEnc, bodyEnc) {
    const res = await fetch(`${API_BASE_URL}/notify/encrypted`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            recipient_email: email,
            encrypted_title: titleEnc,
            encrypted_body: bodyEnc,
            queue_if_offline: false,
            collapse_duplicates: false,
        }),
    });
    const data = await res.json();
    console.log("✅ Sent:", data);
}

(async () => {
    try {
        console.log("🔑 Fetching public key...");
        const pem = await getPublicKey(RECIPIENT_EMAIL);

        console.log("🔐 Encrypting...");
        const titleEnc = encryptMessage(pem, TITLE);
        const bodyEnc = encryptMessage(pem, MESSAGE);

        console.log("📤 Sending notification...");
        await sendNotification(RECIPIENT_EMAIL, titleEnc, bodyEnc);
    } catch (err) {
        console.error("❌ Error:", err);
    }
})();
```
