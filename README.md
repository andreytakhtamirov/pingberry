# PingBerry
PingBerry is a background notification service for BlackBerry 10 devices.

**Monitor server status and uptime here**: [PingBerry Status Monitor](https://scoreless-clinically-carol.ngrok-free.app/monitor/)

## Installation Guide

> **⚠️ Must be installed in a Term48 or Term49 environment with _ALL PERMISSIONS ENABLED_.**

[Download Term49 BAR with all permissions enabled here](https://github.com/BerryFarm/Term49/releases/download/0.4.1.8/Term49-0.4.1.8.bar)

🔗 **[Download the installer ZIP here](LINK HERE)**  
*(Coming soon)*

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

---

### After Installation

- You can now **restart Term48/Term49** — the notification service will run automatically on launch.
- **Keep Term48/Term49 open in the background** to receive notifications.
