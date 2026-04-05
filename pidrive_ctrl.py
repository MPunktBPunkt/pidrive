#!/usr/bin/env python3
"""
ipod_ctrl.py - Tastatur-Steuerung via SSH
PiDrive Project - GPL-v3

Starten: python3 ipod_ctrl.py
"""

import sys
import tty
import termios

TRIGGER = "/tmp/pidrive_cmd"

def send(cmd):
    with open(TRIGGER, "w") as f:
        f.write(cmd)
    print(f"  >> {cmd}")

def main():
    print("=" * 42)
    print("  PiDrive Steuerung (SSH Terminal)")
    print("=" * 42)
    print("  Navigation:")
    print("    w / Pfeil hoch   = hoch")
    print("    s / Pfeil runter = runter")
    print("    d / Enter / →    = auswaehlen")
    print("    a / ESC / ←      = zurueck")
    print("  Kategorien:")
    print("    1 = Musik   2 = WiFi")
    print("    3 = BT      4 = System")
    print("  Audio:")
    print("    F1 = Klinke  F2 = HDMI")
    print("    F3 = BT      F4 = Alle")
    print("  Sonstiges:")
    print("    r = Neustart   p = Ausschalten")
    print("    q = Beenden")
    print("=" * 42)

    fd  = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch == 'q':
                break
            elif ch == 'w':   send("up")
            elif ch == 's':   send("down")
            elif ch == 'd':   send("enter")
            elif ch == 'a':   send("back")
            elif ch == '1':   send("cat:0")
            elif ch == '2':   send("cat:1")
            elif ch == '3':   send("cat:2")
            elif ch == '4':   send("cat:3")
            elif ch == 'r':   send("reboot")
            elif ch == 'p':   send("shutdown")
            elif ch == '\r':  send("enter")
            elif ch == '\x1b':
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    if ch3 == 'A':     send("up")
                    elif ch3 == 'B':   send("down")
                    elif ch3 == 'C':   send("enter")
                    elif ch3 == 'D':   send("back")
                    elif ch3 == '1':
                        ch4 = sys.stdin.read(2)
                        if   ch4 == '1~': send("audio_klinke")
                        elif ch4 == '2~': send("audio_hdmi")
                        elif ch4 == '3~': send("audio_bt")
                        elif ch4 == '4~': send("audio_all")
                else:
                    send("back")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        print("\nBeendet.")

if __name__ == "__main__":
    main()
