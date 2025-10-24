# PingBerry API Docs

**Base URL: https://api.pingberry.xyz**

## Table of Contents

- [POST /notify](#post-notify)
- [POST /notify/encrypted](#post-notifyencrypted)
- [POST /clients/public-key](#post-clientspublic-key)

# Notifications

## POST /notify

Send a notification to a registered client device. The message is encrypted on the server before delivery.

### Description

This endpoint sends a message from one client or service to another via MQTT.  

Fields `message_title` and `message_body` are validated to be at most **245 bytes** (UTF-8) each due to limits imposed by the encryption keys.

If the target device is offline:

- If `queue_if_offline` is `true`, the message will be queued (HTTP 202) and received when the client comes online.
- Otherwise, delivery fails immediately (HTTP 409).


#### Request Body

```json
{
  "recipient_email": "user@example.com",
  "message_title": "Twitter - New Like",
  "message_body": "Alice liked your post.",
  "method": "mqtt",
  "queue_if_offline": false,
  "collapse_duplicates": true
}
```

#### Schema

| Field                 | Type           | Required | Default  | Description                                                                         |
| --------------------- | -------------- | -------- | -------- | ----------------------------------------------------------------------------------- |
| `recipient_email`     | string (email) | Yes      | —        | The email address of the recipient (must be registered).                            |
| `message_title`       | string         | Yes      | —        | The title of the notification (displayed prominently on the device).                |
| `message_body`        | string         | Yes      | —        | The main content or body of the message.                                            |
| `method`              | string         | No       | `"mqtt"` | Delivery method. Currently only `"mqtt"` is supported.                              |
| `queue_if_offline`    | boolean        | No       | `false`  | If `true`, queue the message until the recipient comes online.                      |
| `collapse_duplicates` | boolean        | No       | `true`   | If `true`, replaces previous notifications with the same title to avoid duplicates. |


#### Responses

| Status                        | Meaning                  | Description                                                                         |
| ----------------------------- | ------------------------ | ----------------------------------------------------------------------------------- |
| **200 OK**                    | Success                  | Message delivered immediately via MQTT.                                             |
| **202 Accepted**              | Queued                   | Device is offline; message accepted and queued for delivery when device reconnects. |
| **404 Not Found**             | Invalid Recipient        | The recipient email is not registered.                                              |
| **400 Bad Request**           | Validation Error         | Input failed validation (e.g., field too long, invalid email).                      |
| **409 Conflict**              | Offline / Queue Disabled | Device offline and `queue_if_offline` is `false`.                                   |
| **500 Internal Server Error** | Server Error             | Unexpected error while processing the request.                                      |

#### Example Success
```
{
  "message": "Notification sent via mqtt",
  "details": {
    "method": "mqtt",
    "status": "success",
    "code": 200
  }
}
```
---


## POST /notify/encrypted

Send a pre-encrypted notification to a registered client device.

### Description

External clients can send messages that are already encrypted using the recipient’s public key.
The server does not decrypt the message; it simply delivers it via MQTT.

If the recipient device is offline:
- If `queue_if_offline` is `true`, the message will be queued (HTTP 202) and received when the client comes online.
- Otherwise, delivery fails immediately (HTTP 409).

#### Request Body
```
{
  "recipient_email": "user@example.com",
  "encrypted_title": "BASE64_ENCRYPTED_TITLE",
  "encrypted_body": "BASE64_ENCRYPTED_BODY",
  "queue_if_offline": false,
  "collapse_duplicates": true
}
```

#### Schema

| Field                 | Type           | Required | Default | Description                                                                             |
| --------------------- | -------------- | -------- | ------- | --------------------------------------------------------------------------------------- |
| `recipient_email`     | string (email) | Yes      | —       | The email address of the recipient (must be registered).                                |
| `encrypted_title`     | string         | Yes      | —       | Pre-encrypted notification title (opaque to server).                                    |
| `encrypted_body`      | string         | Yes      | —       | Pre-encrypted notification body (opaque to server).                                     |
| `queue_if_offline`    | boolean        | No       | `false` | If `true`, queue the message until the recipient comes online.                          |
| `collapse_duplicates` | boolean        | No       | `true`  | If `true`, only the latest message with the same title appears on the recipient device. |

#### Responses

| Status                        | Meaning                  | Description                                                                         |
| ----------------------------- | ------------------------ | ----------------------------------------------------------------------------------- |
| **200 OK**                    | Success                  | Message delivered immediately via MQTT.                                             |
| **202 Accepted**              | Queued                   | Device is offline; message accepted and queued for delivery when device reconnects. |
| **404 Not Found**             | Invalid Recipient        | The recipient email is not registered.                                              |
| **400 Bad Request**           | Validation Error         | Input failed validation (e.g., field too long, invalid email).                      |
| **409 Conflict**              | Offline / Queue Disabled | Device offline and `queue_if_offline` is `false`.                                   |
| **500 Internal Server Error** | Server Error             | Unexpected error while processing the request.                                      |

#### Example Success
```
{
  "message": "Notification sent via mqtt",
  "details": {
    "method": "mqtt",
    "status": "success",
    "code": 200
  }
}
```

---


## POST /clients/public-key

Retrieve the public key for a registered client. This allows external applications to encrypt messages before sending.

### Description

This endpoint returns the **notification public key** of a recipient given their email.  


#### Request Body

```json
{
  "recipient_email": "user@example.com"
}
```
#### Schema
| Field             | Type           | Required | Description                                    |
| ----------------- | -------------- | -------- | ---------------------------------------------- |
| `recipient_email` | string (email) | Yes      | The email address of the registered recipient. |

#### Response

##### 200 OK
```
{
  "notification_public_key": "-----BEGIN PUBLIC KEY-----\nMIIBIjANB...\n-----END PUBLIC KEY-----"
}
```

---
