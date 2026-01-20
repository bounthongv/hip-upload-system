# HIP CMI F68S Proprietary Protocol Documentation

**Device**: HIP CMI F68S (ZKTeco OEM variant)
**Default Port**: 5005 (TCP)
**Protocol Type**: Proprietary binary protocol (Server-initiated PULL)

## Overview
The device does not use the standard ZKTeco ADMS (HTTP) or UDP-based SDK protocol. Instead, it uses a TCP-based proprietary handshake on port 5005. The communication is initiated by the Server (PC) connecting to the Device.

## Packet Structure
All packets seem to follow a 16-byte structure (for commands).
Responses may be 10 bytes (Ack) or larger (Data).

**Common Header**: `55 AA` (Magic Bytes)

## Conversation Flow

### 1. Connection
*   **Action**: Server connects to Device IP on port 5005.
*   **Result**: TCP Connection established. Device waits for data.

### 2. Handshake (Command 1)
*   **Server Sends** (16 bytes):
    ```
    55 aa 01 b0 00 00 00 00 00 00 00 00 00 00 00 00
    ```
    *   Command: `01 b0`
    *   Payload: All zeros
*   **Device Responds** (10 bytes):
    ```
    aa 55 01 01 00 00 00 00 00 00
    ```
    *   Ack Header: `aa 55` (Reverse of 55 AA)

### 3. Setup / Token Request (Command 2)
*   **Server Sends** (16 bytes):
    ```
    55 aa 01 b4 00 00 00 00 00 00 ff ff 00 00 18 00
    ```
    *   Command: `01 b4`
    *   Suffix: `ff ff 00 00 18 00` (Sequence 0x18?)
*   **Device Responds** (10 bytes):
    ```
    aa 55 01 00 TOKEN 00 00 00 18 00
    ```
    *   **TOKEN**: The 5th byte (Index 4) is a session token/ID.
    *   Example: `03` or `05`. This token MUST be used in the next command.

### 4. Request Attendance Data (Command 3)
*   **Server Sends** (16 bytes):
    ```
    55 aa 01 a4 00 00 00 TOKEN 20 00 00 00 00 TOKEN 19 00
    ```
    *   Command: `01 a4`
    *   **Token Injection**: The token received in Step 3 must be placed at:
        *   Offset 7 (Index 7)
        *   Offset 13 (Index 13)
    *   Constant: `20` at Offset 8 seems fixed.
    *   Suffix: `19 00` (Sequence 0x19?)

### 5. Data Transfer
*   **Device Responds**:
    *   **Header** (10 bytes): `aa 55 01 01 00 00 00 00 19 00`
    *   **Payload**: Binary data stream.
*   **Data Structure**:
    *   The payload starts effectively at **Offset 12** (skipping the 10-byte header + 2 bytes `55 aa` wrapper).
    *   **Record Size**: Fixed **20 bytes**.
    *   **Layout**:
        *   **Bytes 0-4**: User ID (Integer, Little Endian).
        *   **Bytes 4-7**: *Unknown* (Possibly reserved or high-word of UID).
        *   **Bytes 7-11**: Timestamp (Integer, Little Endian). *Note: Values appear to be Unix Timestamp-like but may have offsets or proprietary encoding.*
        *   **Bytes 11-15**: *Unknown* (Possibly sub-seconds).
        *   **Bytes 15-19**: Work Code (Integer, Little Endian).
        *   **Byte 19**: Verify Mode (0x40=Finger/Password, 0x10=Card/Face?).

## Implementation Notes
*   Timing is sensitive. Small delays (100ms) between commands improve reliability.
*   If the Token in Command 3 is incorrect, the device silently drops the packet (Timeout).
*   The "Full Download" command seems to return all data. "New Log" might require different flags in Command 3.

## Credits
Reverse engineering by analyzing Wireshark captures of "HIP Premium Time" software communication.
