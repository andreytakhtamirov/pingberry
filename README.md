# 🔔 PingBerry
PingBerry is a background notification service for BlackBerry 10 devices, delivering **instant, native, push-style notifications** from connected apps and services directly to your device.

All notifications are **end-to-end encrypted**, ensuring that only your device can read the messages.

[Learn how to send truly end-to-end encrypted notifications (sender-encrypted)](docs/self-encrypted-notifications.md)


| Resource | Link |
|----------|------|
| Monitor server status and uptime | [PingBerry Status Monitor](https://status.pingberry.xyz) |
| Full API documentation | [PingBerry API Docs](docs/api-docs.md) |



## 📥 Installation Guide

> **⚠️ Must be installed in a Term48 or Term49 environment with _ALL PERMISSIONS ENABLED_ or else notifications won't appear!**

[Download Term49 BAR with all permissions enabled here](https://github.com/BerryFarm/Term49/releases/download/0.4.1.8/Term49-0.4.1.8.bar)

### 📱 Install PingBerry on your BlackBerry 10 device:
Navigate to: [download.pingberry.xyz](https://download.pingberry.xyz) to download the ZIP.

---

### Installation Instructions

1. **Using a web browser** on your BlackBerry 10 device, navigate to the link above and **save the ZIP file** inside the **Downloads** folder on your device.

2. **Open** Term48 or Term49.

3. Run the following commands one by one:

    ```sh
    cd /accounts/1000/shared/downloads

    unzip pingberry-env.zip
    ```

4. Once unzipping is complete, run:

    ```sh
    ./pingberry-env/install.sh
    ```

5. You will be prompted to **enter your email address**, which is used to identify your device and enable notifications from applications.

6. The device will take **approximately 3 minutes** to generate encryption keys and register with the server.

7. When complete, you should see the message:

    ```
    Setup complete. Restart Term48 to start the notification service.
    ```
### After Installation

- You can now **restart Term48/Term49** — the notification service will run automatically on launch.
- Upon first connection, you should see a welcome notification titled "Welcome to PingBerry!".
- **You must keep Term48/Term49 open in the background** to receive notifications.

---
  
## ⚡ Battery Life Impact

PingBerry is designed to run efficiently in the background on BlackBerry 10 devices. It uses a highly efficient Internet of Things (IoT) network protocol — **MQTT** — which keeps connections lightweight and minimizes battery and data usage while delivering notifications in near real-time.

In real-world usage tests:

- **Test scenario:** 18-hour day, receiving an average of 8 notifications per hour.
- **Result:** PingBerry consumed only **~2.4% of total battery** over the course of the day.

Most of the battery impact comes from decrypting each incoming notification, while maintaining the network connection has a negligible effect. This demonstrates that the service has a minimal impact on device battery life while keeping you connected and ready to receive notifications.


---

## 📱 iOS push notifications (APNs)

PingBerry can also deliver notifications to the [PingBerry iOS app](https://github.com/andreytakhtamirov/pingberry) (or any iOS app built against it) via Apple Push Notification service (APNs).

The iOS app registers its APNs device token against an email using **`POST /register/ios`**. When a notification is sent to that email via `POST /notify`, it is delivered to the iOS device through APNs in addition to any BlackBerry 10 (MQTT) clients.

To enable APNs delivery on the server:

1. Install the HTTP/2 dependency:
   ```sh
   pip install "httpx[http2]"
   ```
2. Add the APNs settings to `server/.env` (see `server/.env.example`):
   ```
   APNS_TEAM_ID=YOUR_APPLE_TEAM_ID
   APNS_KEY_ID=YOUR_APNS_KEY_ID
   APNS_PRIVATE_KEY_PATH=./certs/AuthKey_XXXXXXXXXX.p8
   APNS_TOPIC=com.pingberry.ios
   APNS_USE_SANDBOX=true
   ```
   - `APNS_TEAM_ID` — your Apple Developer Team ID.
   - `APNS_KEY_ID` — the Key ID of the APNs authentication key (`.p8`).
   - `APNS_PRIVATE_KEY_PATH` — path to that `.p8` key.
   - `APNS_TOPIC` — the app's bundle identifier.
   - `APNS_USE_SANDBOX` — `true` for development, `false` for production.

If the APNs settings are left empty, the server still runs normally and simply
skips APNs delivery (MQTT-only behavior is unchanged).
