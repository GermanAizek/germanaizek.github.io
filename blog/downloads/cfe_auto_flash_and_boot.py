#!/usr/bin/env python3
import os
import sys
import time
import select
import termios
import threading
import subprocess
import glob

IMAGE_PATH = "openwrt_spi_fixed_v5_cfe.bin"
ROUTER_IP = "192.168.1.1"

def find_serial_port():
    ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
    if not ports:
        print("[-] No serial port found in /dev!")
        sys.exit(1)
    return sorted(ports)[-1]

def setup_serial(port):
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    attrs = termios.tcgetattr(fd)
    attrs[0] = termios.IGNBRK
    attrs[1] = 0
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attrs[3] = 0
    attrs[4] = termios.B115200
    attrs[5] = termios.B115200
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    return fd

def uploader_thread():
    time.sleep(1.5)
    print("\n[Uploader] Начинаю отправку прошивки через Web Recovery...")
    cmd = [
        "curl", "-s", "--http0.9",
        "-F", f"filename=@{IMAGE_PATH}",
        f"http://{ROUTER_IP}/upload.cgi"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(f"[Uploader] curl завершился (код {res.returncode})")
    if res.stdout:
        print(f"[Uploader] Ответ сервера:\n{res.stdout[:200]}")

def main():
    if not os.path.exists(IMAGE_PATH):
        print(f"[-] Ошибка: {IMAGE_PATH} не найден!")
        sys.exit(1)

    port = find_serial_port()
    fd = setup_serial(port)

    print("=" * 65)
    print(f"[*] CFE AUTO-FLASHER & BOOT MONITOR on {port} (115200 8N1)")
    print(f"[*] Образ: {IMAGE_PATH} ({os.path.getsize(IMAGE_PATH)} байт)")
    print("=" * 65)
    print("[+] UART готов. Ожидаю перезапуск роутера...")
    print("[!] ПОЖАЛУЙСТА, ВЫКЛЮЧИТЕ И ВКЛЮЧИТЕ ПИТАНИЕ РОУТЕРА ПРЯМО СЕЙЧАС!")
    print("-" * 65)
    sys.stdout.flush()

    in_cfe = False
    start_time = time.time()
    last_spam = 0
    upload_started = False
    flashed = False

    try:
        # Phase 1: Catch CFE
        while True:
            now = time.time()
            if not in_cfe and (now - last_spam >= 0.025):
                try:
                    os.write(fd, b" ")
                except Exception:
                    pass
                last_spam = now

            r, _, _ = select.select([fd], [], [], 0.005)
            if r:
                chunk = os.read(fd, 2048)
                if chunk:
                    text = chunk.decode('latin1', errors='replace')
                    sys.stdout.write(text)
                    sys.stdout.flush()

                    if not in_cfe and ("CFE>" in text or "cfe>" in text):
                        in_cfe = True
                        print("\n\n" + "=" * 65)
                        print("[+] УСПЕХ! МЫ В КОНСОЛИ CFE>!")
                        print("=" * 65)
                        break

        if not in_cfe:
            print("\n[-] Таймаут ожидания CFE.")
            return

        # Phase 2: Upload firmware (Web server is already waiting on socket 0)
        time.sleep(1.0)
        print("[+] CFE в режиме ожидания Web Recovery. Запускаю отправку прошивки...")

        # Start background uploader
        t = threading.Thread(target=uploader_thread, daemon=True)
        t.start()

        # Phase 3: Monitor flashing and next boot
        print("[*] Мониторю процесс прошивки и последующую загрузку OpenWrt...")
        phase3_start = time.time()
        while time.time() - phase3_start < 300:
            r, _, _ = select.select([fd], [], [], 0.05)
            if r:
                chunk = os.read(fd, 2048)
                if chunk:
                    text = chunk.decode('latin1', errors='replace')
                    sys.stdout.write(text)
                    sys.stdout.flush()

                    if any(k in text for k in ["Please press Enter to activate this console", "root@OpenWrt", "BusyBox v", "BACKFIRE"]):
                        print("\n\n" + "=" * 65)
                        print("[🎉🎉🎉] ПОБЕДА! OPENWRT УСПЕШНО ЗАГРУЗИЛСЯ!")
                        print("=" * 65)
                        print("[*] Жду 6 секунд завершения стартовых скриптов network и telnet...")
                        time.sleep(6)
                        os.write(fd, b"\r\n")
                        time.sleep(1)
                        print("\n[*] Запрашиваю статус системы (uname, free, ps, df, mtd, ifconfig)...")
                        for cmd in [b"uname -a\r\n", b"free\r\n", b"ps\r\n", b"cat /proc/mtd\r\n", b"mount\r\n", b"df -h\r\n", b"ifconfig\r\n"]:
                            os.write(fd, cmd)
                            time.sleep(1.5)
                        # Read diagnostic outputs for 6 more seconds
                        diag_start = time.time()
                        while time.time() - diag_start < 6:
                            r2, _, _ = select.select([fd], [], [], 0.1)
                            if r2:
                                ch = os.read(fd, 2048)
                                if ch:
                                    sys.stdout.write(ch.decode('latin1', errors='replace'))
                                    sys.stdout.flush()

                        # Now test LAN ping from host
                        print("\n" + "=" * 65)
                        print("[*] Тестирую ping до 192.168.1.1 с хоста (интерфейс eth1)...")
                        for attempt in range(1, 4):
                            ping_res = subprocess.run(["ping", "-c", "3", "-W", "2", "192.168.1.1"], capture_output=True, text=True)
                            if ping_res.returncode == 0:
                                print(ping_res.stdout)
                                print("[+] PING 192.168.1.1 УСПЕШЕН!")
                                break
                            else:
                                print(f"[-] Попытка {attempt}/3: ожидание ответа...")
                                time.sleep(2)

                        # Test Telnet port 23
                        print("\n[*] Тестирую подключение к Telnet (192.168.1.1:23)...")
                        try:
                            import socket
                            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            s.settimeout(3.0)
                            s.connect(("192.168.1.1", 23))
                            banner = s.recv(1024)
                            print(f"[+] TELNET PORT 23 OPEN! Banner: {repr(banner)}")
                            s.close()
                        except Exception as e:
                            print(f"[-] Ошибка подключения Telnet: {e}")
                        break

    finally:
        os.close(fd)

if __name__ == '__main__':
    main()
