#!/usr/bin/env python3
import serial, struct, time, psutil, os, sys, subprocess
from PIL import Image, ImageDraw, ImageFont

PORT = "/dev/ttyACM0"
DISPLAY_BITMAP = 197
SET_ORIENTATION = 121
SET_BRIGHTNESS = 110
HELLO = 69

def send_command(ser, cmd, x=0, y=0, ex=0, ey=0):
    buf = bytearray(6)
    buf[0] = (x >> 2) & 0xFF
    buf[1] = ((x & 3) << 6) | ((y >> 4) & 0x3F)
    buf[2] = ((y & 15) << 4) | ((ex >> 6) & 0x0F)
    buf[3] = ((ex & 63) << 2) | ((ey >> 8) & 0x03)
    buf[4] = ey & 0xFF
    buf[5] = cmd & 0xFF
    ser.write(buf)

def image_to_rgb565(image):
    rgb = image.convert("RGB")
    w, h = rgb.size
    data = bytearray(w * h * 2)
    for y in range(h):
        for x in range(w):
            r, g, b = rgb.getpixel((x, y))
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            idx = (y * w + x) * 2
            struct.pack_into("<H", data, idx, rgb565)
    return bytes(data)

def display_image(ser, image, width, height):
    send_command(ser, DISPLAY_BITMAP, 0, 0, width - 1, height - 1)
    rgb565 = image_to_rgb565(image)
    chunk_size = width * 8
    for i in range(0, len(rgb565), chunk_size):
        ser.write(rgb565[i:i + chunk_size])

def draw_bar(draw, x, y, w, h, pct, color):
    draw.rectangle([x, y, x + w, y + h], fill=(40, 40, 60))
    filled = int(w * min(pct, 100) / 100)
    if filled > 0:
        draw.rectangle([x, y, x + filled, y + h], fill=color)

def get_color(pct):
    if pct < 60: return (0, 200, 80)
    if pct < 85: return (255, 200, 0)
    return (255, 60, 60)

def main():
    sys.stdout.reconfigure(line_buffering=True)
    print("Connecting to LCD...")
    ser = serial.Serial(PORT, 115200, timeout=1, rtscts=True)
    time.sleep(0.5)

    # Hello handshake
    print("Sending HELLO...")
    ser.write(bytearray([HELLO] * 6))
    response = ser.read(6)
    print(f"Response: {response.hex() if response else 'none'}")
    ser.reset_input_buffer()

    # Set orientation to reverse landscape (270 degrees)
    print("Setting orientation...")
    buf = bytearray(16)
    buf[5] = SET_ORIENTATION
    buf[6] = 102  # reverse_landscape (103 = 270 degrees)
    buf[7] = 0x01  # 480 >> 8
    buf[8] = 0xE0  # 480 & 255
    buf[9] = 0x01  # 320 >> 8
    buf[10] = 0x40  # 320 & 255
    ser.write(buf)
    time.sleep(0.3)

    # Set brightness to max
    send_command(ser, SET_BRIGHTNESS, 0, 0, 0, 0)
    time.sleep(0.1)

    W, H = 480, 320

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        sfont = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except:
        font = ImageFont.load_default()
        sfont = font

    prev_net = psutil.net_io_counters()
    prev_time = time.time()

    print("Starting render loop...")
    while True:
        try:
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()

            # ZFS pool usage via /proc (works inside container with --pid host)
            def zfs_usage(pool):
                try:
                    with open("/proc/spl/kstat/zfs/" + pool + "/objset-0x0", "r") as f:
                        pass  # just checking existence
                except:
                    pass
                # Read from host's zfs via nsenter (pid host)
                try:
                    r = subprocess.run(["nsenter", "-t", "1", "-m", "--", "zfs", "list", "-Hp", "-o", "used,avail", pool],
                                       capture_output=True, text=True, timeout=5)
                    if r.returncode == 0:
                        used, avail = r.stdout.strip().split()
                        used, avail = int(used), int(avail)
                        total = used + avail
                        return type('obj', (object,), {'used': used, 'total': total, 'percent': (used/total)*100 if total else 0})()
                except: pass
                return None
            # Auto-detect all ZFS pools (excluding boot-pool)
            pools = {}
            try:
                r = subprocess.run(["nsenter", "-t", "1", "-m", "--", "zfs", "list", "-Hp", "-o", "name,used,avail", "-d", "0"],
                                   capture_output=True, text=True, timeout=5)
                if r.returncode == 0:
                    for line in r.stdout.strip().split("\n"):
                        parts = line.split("\t")
                        if len(parts) == 3 and parts[0] != "boot-pool":
                            name, used, avail = parts[0], int(parts[1]), int(parts[2])
                            total = used + avail
                            pools[name] = type('obj', (object,), {'used': used, 'total': total, 'percent': (used/total)*100 if total else 0})()
            except: pass
            # Temperature: CPU + disk temps with proper labels
            cpu_temp = None
            disk_temps = {}
            try:
                for name, entries in psutil.sensors_temperatures().items():
                    if name == "coretemp":
                        for e in entries:
                            if "Package" in (e.label or ""):
                                cpu_temp = e.current
                    elif name == "drivetemp":
                        # Map by hwmon index to disk name
                        pass
                # Read disk temps with labels via sysfs
                import glob
                for hwmon in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
                    try:
                        n = open(hwmon + "/name").read().strip()
                        if n == "drivetemp":
                            temp = int(open(hwmon + "/temp1_input").read().strip()) / 1000
                            dev_path = os.path.realpath(hwmon + "/device")
                            blocks = os.listdir(dev_path + "/block") if os.path.isdir(dev_path + "/block") else []
                            blk = blocks[0] if blocks else "?"
                            label_map = {"sda": "Samsung", "sdb": "Seagate", "sdc": "SSD"}
                            disk_temps[label_map.get(blk, blk)] = temp
                    except: pass
                if cpu_temp is None:
                    for name, entries in psutil.sensors_temperatures().items():
                        if name == "coretemp":
                            for e in entries:
                                if e.current > 0:
                                    cpu_temp = e.current
                                    break
                            break
            except: pass
            net = psutil.net_io_counters()
            now = time.time()
            dt = now - prev_time
            if dt > 0:
                up_speed = (net.bytes_sent - prev_net.bytes_sent) / dt
                down_speed = (net.bytes_recv - prev_net.bytes_recv) / dt
            else:
                up_speed = down_speed = 0
            prev_net = net
            prev_time = now
            up = time.time() - psutil.boot_time()

            def fmt_speed(bps):
                if bps >= 1024*1024:
                    return f"{bps/(1024*1024):.1f} MB/s"
                elif bps >= 1024:
                    return f"{bps/1024:.0f} KB/s"
                return f"{bps:.0f} B/s"

            img = Image.new("RGB", (W, H), (15, 15, 25))
            d = ImageDraw.Draw(img)

            # Title
            d.text((15, 8), "TrueNAS Monitor", fill=(100, 180, 255), font=font)
            d.text((350, 10), f"UP {int(up//3600)}h{int((up%3600)//60)}m", fill=(120, 120, 140), font=sfont)

            # CPU
            y0 = 40
            d.text((15, y0), f"CPU  {cpu:.0f}%", fill=(255, 255, 255), font=sfont)
            draw_bar(d, 100, y0 + 2, 365, 16, cpu, get_color(cpu))

            # RAM
            y0 = 68
            d.text((15, y0), f"RAM  {mem.percent:.0f}%", fill=(255, 255, 255), font=sfont)
            draw_bar(d, 100, y0 + 2, 365, 16, mem.percent, get_color(mem.percent))
            d.text((100, y0 + 20), f"{mem.used//(1024**3)}GB / {mem.total//(1024**3)}GB", fill=(100, 100, 120), font=sfont)

            # Divider
            d.line([(15, 102), (465, 102)], fill=(50, 50, 70))

            # Storage pools (auto-detected)
            y0 = 110
            for pname, pdata in pools.items():
                short = pname.replace("Storage", "")
                d.text((15, y0), f"{short}  {pdata.percent:.0f}%", fill=(255, 255, 255), font=sfont)
                draw_bar(d, 140, y0 + 2, 325, 16, pdata.percent, (40, 120, 255))
                d.text((140, y0 + 20), f"{pdata.used//(1024**3)}GB / {pdata.total//(1024**3)}GB", fill=(100, 100, 120), font=sfont)
                y0 += 38

            # Divider
            d.line([(15, y0), (465, y0)], fill=(50, 50, 70))

            # Temperature
            y0 += 8
            d.text((15, y0), "TEMP", fill=(100, 180, 255), font=font)
            tx = 80
            if cpu_temp:
                tc = (0, 200, 80) if cpu_temp < 50 else ((255, 200, 0) if cpu_temp < 70 else (255, 60, 60))
                d.text((tx, y0), f"CPU:{cpu_temp:.0f}C", fill=tc, font=sfont)
                tx += 95
            for dname, dval in disk_temps.items():
                tc = (0, 200, 80) if dval < 45 else ((255, 200, 0) if dval < 55 else (255, 60, 60))
                d.text((tx, y0), f"{dname}:{dval:.0f}C", fill=tc, font=sfont)
                tx += 105

            # Divider
            y0 += 26
            d.line([(15, y0), (465, y0)], fill=(50, 50, 70))

            # Network - real-time speed
            y0 += 8
            up_color = (0, 200, 80) if up_speed < 10*1024*1024 else (255, 200, 0)
            dn_color = (0, 200, 80) if down_speed < 10*1024*1024 else (255, 200, 0)
            d.text((15, y0), "UP", fill=(100, 180, 255), font=sfont)
            d.text((45, y0), fmt_speed(up_speed), fill=up_color, font=sfont)
            d.text((200, y0), "DOWN", fill=(100, 180, 255), font=sfont)
            d.text((250, y0), fmt_speed(down_speed), fill=dn_color, font=sfont)

            # Total traffic
            y0 += 20
            d.text((15, y0), f"Total TX: {net.bytes_sent//(1024**2)}MB  RX: {net.bytes_recv//(1024**2)}MB", fill=(80, 80, 100), font=sfont)

            # Footer
            y0 = max(y0 + 24, 272)
            d.line([(15, y0), (465, y0)], fill=(50, 50, 70))
            d.text((15, y0 + 10), "172.30.1.79", fill=(80, 80, 100), font=sfont)
            d.text((200, y0 + 10), "TrueNAS 25.10", fill=(80, 80, 100), font=sfont)
            d.text((370, y0 + 10), "N100", fill=(80, 80, 100), font=sfont)

            display_image(ser, img, W, H)
            print(f"OK CPU:{cpu:.0f}% MEM:{mem.percent:.0f}%")
        except Exception as e:
            print(f"Error: {e}", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    main()
