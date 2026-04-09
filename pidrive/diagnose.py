#!/usr/bin/env python3
"""diagnose.py - PiDrive System-Diagnose v0.5.2"""
import os, subprocess, fcntl, sys, time

VT_ACTIVATE = 0x5606

def run(cmd):
    try: return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
    except: return ""

def S(t): print(f"\n{'='*50}\n  {t}\n{'='*50}")
def ok(m):   print(f"  ✓ {m}")
def warn(m): print(f"  ⚠ {m}")
def err(m):  print(f"  ✗ {m}")
def nfo(m):  print(f"    {m}")

def check_vt():
    S("VT STATUS")
    fg = run("fgconsole")
    ok(f"Aktives VT: {fg} (SDL verwendet diesen VT)")

    # Sessions explizit mit TTY prüfen
    raw = run("loginctl list-sessions 2>/dev/null")
    nfo("loginctl:"); [nfo(f"  {l}") for l in raw.splitlines()]

    tty3 = run("loginctl list-sessions 2>/dev/null | grep tty3")
    if tty3: ok(f"logind-Session auf tty3: {tty3.strip()}")
    else:
        nfo("Keine logind-Session auf tty3 (ohne PAMName normal — SDL erkennt VT selbst)")

    # Session-Details
    sid = run("loginctl list-sessions 2>/dev/null | grep tty3 | awk '{print $1}'")
    if sid:
        [nfo(f"  {l}") for l in run(f"loginctl session-status {sid} 2>/dev/null | head -8").splitlines()]

def check_service():
    S("PIDRIVE SERVICE")
    st = run("systemctl is-active pidrive")
    (ok if st=="active" else err)(f"pidrive.service: {st}")

    pid = run("systemctl show pidrive --property=MainPID --value")
    if not pid or pid == "0": warn("Kein PID"); return
    ok(f"Main PID: {pid}")

    # SDL Umgebungsvariablen des laufenden Prozesses
    S(f"SDL ENVIRONMENT (PID {pid})")
    try:
        env_raw = open(f"/proc/{pid}/environ","rb").read()
        env_vars = [e.decode("utf-8","replace") for e in env_raw.split(b"\x00") if b"SDL" in e]
        if env_vars:
            for v in env_vars:
                if "FBCON_KEEP_TTY=1" in v:
                    ok(f"{v}  ← KEEP_TTY aktiv")
                else:
                    ok(f"{v}")
            if not any("FBCON_KEEP_TTY" in v for v in env_vars):
                err("SDL_VIDEO_FBCON_KEEP_TTY fehlt! set_mode() wird haengen!")
        else:
            warn("Keine SDL_* Vars im Prozess — service env nicht gesetzt?")
    except Exception as e:
        warn(f"environ: {e}")

    # vtcon0 + vtcon1 Status
    S("VTCONSOLE STATUS — ueberlagert vtcon0 noch fb0?")
    for i in (0, 1):
        try:
            val  = open(f"/sys/class/vtconsole/vtcon{i}/bind").read().strip()
            name = open(f"/sys/class/vtconsole/vtcon{i}/name").read().strip()
            (ok if val=="0" else err)(f"vtcon{i}/bind={val}  {name}  {'← OK' if val=='0' else '← GEBUNDEN! Ueberschreibt fb0!'}")
        except Exception as e:
            nfo(f"vtcon{i}: {e}")

    # ── WICHTIGSTER CHECK: Ist der Prozess wirklich Python? ─────────────
    S(f"EXE-CHECK — laeuft wirklich Python? (PID {pid})")
    try:
        exe = os.readlink(f"/proc/{pid}/exe")
        if "python" in exe:
            ok(f"exe → {exe}  ← Python laeuft korrekt!")
        elif "systemd" in exe:
            err(f"exe → {exe}  ← KEIN Python! systemd-Helper haengt!")
            err("  PAMName=login + StandardInput=tty + User=root blockiert ExecStart")
            err("  Loesung: PAMName+TTYPath+StandardInput aus Service entfernen")
        else:
            warn(f"exe → {exe}  ← kein Python erkannt")
    except Exception as e:
        warn(f"exe nicht lesbar (sudo noetig?): {e}")

    # cmdline
    try:
        cmdline = open(f"/proc/{pid}/cmdline").read().replace('',' ').strip()
        if "launcher.py" in cmdline:
            ok(f"cmdline: {cmdline[:80]}")
        else:
            warn(f"cmdline: {cmdline[:80]}  ← launcher.py nicht sichtbar!")
    except Exception as e:
        warn(f"cmdline: {e}")

    # FDs des laufenden Prozesses — KERN-DIAGNOSE
    S(f"PROZESS FD-STATUS (PID {pid}) — welches TTY wirklich benutzt wird")
    for fd_n, fd_nm in [(0,"stdin"),(1,"stdout"),(2,"stderr")]:
        try:
            t = os.readlink(f"/proc/{pid}/fd/{fd_n}")
            if t == "/dev/null" and fd_n == 0:
                err(f"{fd_nm} (fd {fd_n}) → {t}  ← KEIN TTY! PAMName kann nicht greifen")
            elif "tty3" in t:
                ok(f"{fd_nm} (fd {fd_n}) → {t}  ← TTY korrekt gebunden")
            else:
                warn(f"{fd_nm} (fd {fd_n}) → {t}")
        except Exception as e:
            warn(f"{fd_nm} (fd {fd_n}): {e}")

    # Controlling terminal aus /proc/PID/stat
    try:
        stat = open(f"/proc/{pid}/stat").read().split()
        tty_nr = int(stat[6])
        if tty_nr == 0: warn("Kein controlling terminal (tty_nr=0) → SIGHUP-Risiko")
        else:
            minor = tty_nr & 0xff
            (ok if minor==3 else warn)(f"Controlling terminal: tty{minor} {'(korrekt)' if minor==3 else '(erwartet tty3)'}")
    except Exception as e: warn(f"stat parse: {e}")

    # ps
    nfo(run(f"ps -o pid,ppid,tty,stat,cmd -p {pid} 2>/dev/null | tail -1"))

    # Service-Konfiguration laut systemd (Laufzeitwerte, nicht nur Datei)
    S("SERVICE-KONFIGURATION (systemctl show — Laufzeitwerte)")
    show = run("systemctl show pidrive -p TTYPath -p StandardInput -p StandardOutput -p StandardError -p PAMName -p Type 2>/dev/null")
    for line in show.splitlines():
        k, _, v = line.partition("=")
        sym = "✓" if v and v not in ("","null") else "⚠"
        print(f"  {sym} {k} = {v if v else '(leer)'}")

    S("SERVICE-DATEI TTY-ZEILEN (/etc/systemd/system/pidrive.service)")
    cfg = run("grep -E 'TTYPath|StandardInput|StandardOutput|StandardError|PAMName' /etc/systemd/system/pidrive.service 2>/dev/null")
    for line in cfg.splitlines(): nfo(f"  {line}")

    for check, label in [("TTYPath=/dev/tty3",cfg), ("PAMName=login",cfg), ("StandardInput=tty",cfg)]:
        (ok if check in label else err)(f"{check} {'vorhanden' if check in label else 'FEHLT!'}")

def check_gettys():
    S("GETTY STATUS")
    for t in ("tty1","tty2","tty3"):
        st = run(f"systemctl is-active getty@{t}.service 2>/dev/null")
        en = run(f"systemctl is-enabled getty@{t}.service 2>/dev/null")
        if st == "active": warn(f"getty@{t}: active — kann VT blockieren")
        elif "masked" in en: ok(f"getty@{t}: masked")
        else: ok(f"getty@{t}: {st}/{en}")

def check_fbcp():
    S("FBCP")
    r = run("pgrep -a fbcp")
    (ok if r else err)(f"fbcp {'laeuft: '+r if r else 'laeuft NICHT — Display dunkel!'}")

def check_fb(path, name):
    S(f"FRAMEBUFFER {name} ({path})")
    if not os.path.exists(path): err(f"{path} fehlt"); return
    try:
        fb_num = path.replace("/dev/fb","")
        bpp_f  = f"/sys/class/graphics/fb{fb_num}/bits_per_pixel"
        bpp    = int(open(bpp_f).read().strip()) if os.path.exists(bpp_f) else 0
        if bpp:
            sym = "✓" if bpp in (16,32) else "⚠"
            print(f"  {sym} Farbtiefe: {bpp} bpp {'(RGB565)' if bpp==16 else '(BGRA32)'}")
            if bpp == 16:
                warn("pygame muss set_mode(..., 0, 16) verwenden — sonst Farb-Mismatch!")

        raw   = open(path,"rb").read()
        total = len(raw)
        nz    = sum(1 for b in raw if b != 0)
        pct   = nz*100//total if total else 0
        bpp_calc = total//(640*480) if total >= 640*480 else 0
        nfo(f"Groesse: {total} bytes = {bpp_calc} bytes/pixel = {bpp_calc*8} bpp")
        nfo(f"Non-zero: {nz} bytes ({pct}%)")
        nfo(f"Erste 16: {list(raw[:16])}")

        # Echter Schwarztest (bpp-bewusst)
        if bpp == 16:
            px_black = sum(1 for i in range(0,min(total,2000),2) if raw[i]==0 and raw[i+1]==0)
            pct_b = px_black*100//(min(total,2000)//2)
            (err if pct_b>90 else ok)(f"{'~'+str(pct_b)+'% schwarz (pygame zeichnet schwarz!)' if pct_b>90 else str(100-pct_b)+'% hat Farbe'}")
        elif bpp == 32:
            px_black = sum(1 for i in range(0,min(total,4000),4) if raw[i]==0 and raw[i+1]==0 and raw[i+2]==0)
            pct_b = px_black*100//(min(total,4000)//4)
            (err if pct_b>90 else ok)(f"{'~'+str(pct_b)+'% schwarz' if pct_b>90 else str(100-pct_b)+'% hat Farbe'}")
        else:
            (ok if pct>5 else err)(f"Inhalt: {pct}% non-zero")
    except Exception as e: err(f"Fehler: {e}")

def check_log():
    S("PIDRIVE LOG (letzte 5 Zeilen)")
    log = "/var/log/pidrive/pidrive.log"
    if not os.path.exists(log): err("Log-Datei fehlt"); return
    lines = open(log).readlines()
    for l in lines[-5:]: nfo(l.rstrip())
    last_ts = lines[-1][:19] if lines else "?"
    nfo(f"Letzter Eintrag: {last_ts}")
    pid = run("systemctl show pidrive --property=MainPID --value")
    if pid and pid != "0":
        svc_start = run(f"systemctl show pidrive --property=ExecMainStartTimestamp --value 2>/dev/null")
        nfo(f"Service gestartet: {svc_start}")
        if svc_start and last_ts < svc_start[:19].replace("T"," "):
            err("Log hat keine Eintraege vom aktuellen Service-Start!")
            nfo("→ launcher.py oder main.py haengt VOR dem ersten log.info()")

def test_vt():
    S("VT3 AKTIVIERUNGSTEST")
    try:
        fd = os.open("/dev/tty0", os.O_WRONLY | os.O_NOCTTY)
        fcntl.ioctl(fd, VT_ACTIVATE, 3)
        os.close(fd); time.sleep(0.5)
        fg = run("fgconsole")
        (ok if fg=="3" else err)(f"VT3 {'ist foreground' if fg=='3' else 'immer noch nicht foreground — logind blockiert!'}")
    except Exception as e: err(f"VT_ACTIVATE: {e}")

def test_sdl():
    S("SDL DISPLAY TEST")
    try:
        import pygame
        for k,v in [("SDL_VIDEODRIVER","fbcon"),("SDL_FBDEV","/dev/fb0"),("SDL_AUDIODRIVER","dummy")]:
            os.environ.setdefault(k,v)
        pygame.display.init()
        ok(f"pygame.display.init() OK — Treiber: {pygame.display.get_driver()}")
        pygame.display.quit()
    except Exception as e: err(f"pygame FEHLER: {e}")

def summary():
    S("ZUSAMMENFASSUNG")
    fg  = run("fgconsole")
    ses = run("loginctl list-sessions 2>/dev/null")
    svc = run("systemctl is-active pidrive")
    fcp = bool(run("pgrep fbcp"))
    cfg = run("grep -E '^TTYPath|^PAMName|^StandardInput' /etc/systemd/system/pidrive.service 2>/dev/null")
    pid = run("systemctl show pidrive --property=MainPID --value")
    stdin_t = ""
    if pid and pid != "0":
        try: stdin_t = os.readlink(f"/proc/{pid}/fd/0")
        except: pass

    checks = [
        (fg=="3",                    "VT3 foreground"),
        ("tty3" in ses,              "logind-Session auf tty3"),
        (svc=="active",              "pidrive.service laeuft"),
        (fcp,                        "fbcp laeuft"),
        ("TTYPath=/dev/tty3" in cfg, "TTYPath=/dev/tty3"),
        ("PAMName=login" in cfg,     "PAMName=login"),
        ("StandardInput=tty" in cfg, "StandardInput=tty"),
        # stdin ist /dev/null - kein Problem mehr (SDL liest Keyboard selbst)
    ]
    all_ok = True
    for r,l in checks:
        (ok if r else err)(l)
        if not r: all_ok = False
    print("\n  ✓✓✓ Alles korrekt!" if all_ok else "\n  ✗ Probleme vorhanden — siehe Details oben")

def main():
    print(f"\n{'='*50}\n  PiDrive Diagnose v0.5.7\n{'='*50}")
    print(f"  Datum:  {run('date')}\n  Kernel: {run('uname -r')}")
    check_vt(); check_service(); check_gettys()
    check_fbcp(); check_fb("/dev/fb0","fb0"); check_fb("/dev/fb1","fb1")
    check_log(); test_vt(); test_sdl(); summary()

if __name__ == "__main__":
    if os.getuid() != 0:
        print("sudo python3 diagnose.py"); sys.exit(1)
    main()
