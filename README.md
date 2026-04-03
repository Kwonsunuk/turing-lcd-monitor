# Turing Smart Screen - TrueNAS System Monitor

**[한국어 문서 (Korean)](README.ko.md)**

A Python script that displays real-time system stats on a **3.5" USB LCD monitor** (Turing Smart Screen / USB35INCHIPSV2) connected to a TrueNAS server.

![demo](screenshot.png)

## Supported Hardware

- **3.5" IPS USB LCD Monitor** (commonly sold on AliExpress)
- Vendor ID: `1a86` (QinHeng Electronics)
- Product ID: `5722`
- Device Name: `UsbMonitor`
- Serial: `USB35INCHIPSV2`
- Resolution: 480x320
- Interface: USB CDC-ACM (`/dev/ttyACM0`)
- Known compatible software: TURMO, UsbMonitor.exe

## What it shows

- CPU usage (with color-coded bar)
- RAM usage
- Disk usage per pool (Samsung / Seagate)
- Temperature sensors
- Real-time network upload/download speed
- Total network traffic
- System uptime
- IP address

## Protocol Details

This device uses the **Turing Smart Screen Revision A** protocol:

1. **Handshake**: Send `[0x45] * 6`, receive `[0x01] * 6` (3.5" device)
2. **Set Orientation**: 16-byte command with orientation code at byte 6
   - `100` = Portrait, `101` = Landscape, `102` = Reverse Portrait, `103` = Reverse Landscape
3. **Display Bitmap**: 6-byte coordinate-packed command (cmd=197), followed by RGB565 little-endian pixel data in chunks of `width * 8` bytes
4. **Serial**: 115200 baud, RTS/CTS flow control

### Command Format (6 bytes)

```
Byte 0: x >> 2
Byte 1: ((x & 3) << 6) | (y >> 4)
Byte 2: ((y & 15) << 4) | (ex >> 6)
Byte 3: ((ex & 63) << 2) | (ey >> 8)
Byte 4: ey & 255
Byte 5: command_id
```

### Key Command IDs

| Command | ID | Description |
|---------|-----|-------------|
| HELLO | 69 | Handshake |
| CLEAR | 102 | Clear screen |
| SCREEN_OFF | 108 | Backlight off |
| SCREEN_ON | 109 | Backlight on |
| SET_BRIGHTNESS | 110 | Set brightness (0=max, 255=off) |
| SET_ORIENTATION | 121 | Set display orientation |
| DISPLAY_BITMAP | 197 | Send image data |

## Quick Start

### Docker (Recommended)

```bash
# Build
docker build -t usb-lcd .

# Run
docker run -d \
  --name usb-lcd \
  --restart unless-stopped \
  --privileged \
  --pid host \
  --network host \
  -v /dev/ttyACM0:/dev/ttyACM0 \
  -v /mnt:/mnt:ro \
  usb-lcd
```

### Manual

```bash
pip install pyserial psutil Pillow
python3 monitor.py
```

## Configuration

Edit `monitor.py` to customize:

- `PORT` - Serial port (default: `/dev/ttyACM0`)
- `buf[6]` in orientation setup - Display rotation (`100`-`103`)
- Disk paths - Change `/mnt/StorageSamsung` and `/mnt/StorageSeagate` to your pool paths
- Colors, layout, fonts - Modify the render section

## TrueNAS Setup

1. Connect the USB LCD to your TrueNAS mini PC
2. Verify it appears as `/dev/ttyACM0`:
   ```bash
   dmesg | grep ttyACM
   ```
3. Run with Docker (see above)

## Troubleshooting

- **Screen shows garbage/noise**: Wrong protocol. Make sure your device responds `010101010101` to the HELLO command.
- **No display**: Check `/dev/ttyACM0` exists. Try `ls /dev/ttyACM*`.
- **Colors wrong**: The protocol uses RGB565 little-endian. If colors are swapped, check byte order.
- **Screen upside down**: Change orientation code (100-103) in the script.

## Credits

- Protocol reverse-engineered from the TURMO Windows application
- Reference: [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) for Revision A protocol documentation

## License

MIT
