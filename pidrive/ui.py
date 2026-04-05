"""
ui.py - Basisklassen fuer das PiDrive-Interface
PiDrive - Raspberry Pi Car Infotainment - GPL-v3
pygame 1.9 kompatibel
"""

import pygame
import sys
import time
import math
import os

# ── Konstanten ────────────────────────────────────────────────
W, H       = 320, 480   # Virtuelles Canvas (Hochformat)
FB_W, FB_H = 640, 480   # Echter Framebuffer

STATUS_H = 38
LEFT_W   = 90
RIGHT_W  = W - LEFT_W
CAT_IH   = (H - STATUS_H) // 4
SUB_IH   = 62

# ── Farben ────────────────────────────────────────────────────
C_BG      = (10,  11,  15 )
C_LEFT    = (16,  17,  22 )
C_RIGHT   = (13,  14,  18 )
C_HEADER  = (18,  19,  26 )
C_SEL     = (28,  32,  48 )
C_ACCENT  = (30,  90,  200)
C_DIVIDER = (35,  38,  55 )
C_WHITE   = (240, 242, 248)
C_GRAY    = (130, 135, 155)
C_DARK    = (40,  44,  60 )
C_BLUE    = (60,  140, 255)
C_GREEN   = (50,  210, 100)
C_RED     = (255, 70,  70 )
C_ORANGE  = (255, 160, 40 )
C_PURPLE  = (160, 80,  255)
C_BT_BLUE = (100, 160, 255)
C_DAB     = (0,   180, 180)
C_FM      = (255, 120, 0  )

# ── Fonts ─────────────────────────────────────────────────────
_font_cache = {}

def get_font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold
            else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]
        f = None
        for path in candidates:
            if os.path.exists(path):
                f = pygame.font.Font(path, size)
                break
        if f is None:
            f = pygame.font.SysFont("sans", size, bold=bold)
        _font_cache[key] = f
    return _font_cache[key]

# ── Draw Helpers ──────────────────────────────────────────────
def draw_rect(surf, color, rect):
    pygame.draw.rect(surf, color, pygame.Rect(rect))

def draw_wifi_icon(surf, x, y, connected, active, size=16):
    col = C_GREEN if connected else (C_GRAY if active else C_DARK)
    cx = x + size // 2
    cy = y + size - 2
    pygame.draw.circle(surf, col, (cx, cy), 2)
    if active:
        for r, w in [(5, 2), (9, 2), (13, 2)]:
            rect = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
            if r <= 5 or connected:
                try:
                    pygame.draw.arc(surf, col, rect,
                                    math.radians(30), math.radians(150), w)
                except Exception:
                    pass

def draw_bt_icon(surf, x, y, active, connected=False, size=16):
    col = C_GREEN if connected else (C_BT_BLUE if active else C_DARK)
    cx = x + size // 2
    cy = y + 2
    try:
        pts1 = [(cx-4, cy+12), (cx-4, cy), (cx+3, cy+4), (cx-4, cy+8)]
        pts2 = [(cx-4, cy), (cx+3, cy+4), (cx-4, cy+8), (cx+3, cy+12)]
        pygame.draw.lines(surf, col, False, pts1, 2)
        pygame.draw.lines(surf, col, False, pts2, 2)
    except Exception:
        pass

# ── Item & Category ───────────────────────────────────────────
class Item:
    def __init__(self, label, sub=None, action=None,
                 submenu=None, toggle=None, state=None):
        self.label   = label
        self.sub     = sub
        self.action  = action
        self.submenu = submenu
        self.toggle  = toggle
        self.state   = state

class Category:
    def __init__(self, label, color, items):
        self.label = label
        self.color = color
        self.items = items

# ── Statusbar ─────────────────────────────────────────────────
class StatusBar:
    def __init__(self, screen, status):
        self.screen = screen
        self.S      = status

    def draw(self, title="PiDrive", audio_out=""):
        S = self.S
        draw_rect(self.screen, C_HEADER, (0, 0, W, STATUS_H))
        pygame.draw.line(self.screen, C_ACCENT,
                         (0, STATUS_H - 1), (W, STATUS_H - 1), 2)

        t = get_font(14, bold=True).render(title, True, C_WHITE)
        self.screen.blit(t, (W//2 - t.get_width()//2,
                              STATUS_H//2 - t.get_height()//2))

        ts = get_font(13, bold=True).render(time.strftime("%H:%M"), True, C_WHITE)
        self.screen.blit(ts, (W - ts.get_width() - 8,
                               STATUS_H//2 - ts.get_height()//2))

        x = 6
        draw_wifi_icon(self.screen, x, STATUS_H//2 - 8,
                       S.get("conn", False), S.get("wifi", False))
        x += 22

        bt_audio = (audio_out == "Bluetooth" and bool(S.get("bt_sink", "")))
        draw_bt_icon(self.screen, x, STATUS_H//2 - 8,
                     S.get("bt", False), connected=bt_audio)
        x += 20

        if audio_out and audio_out != "auto":
            ao = get_font(11).render(audio_out[:6], True, C_ORANGE)
            self.screen.blit(ao, (x, STATUS_H//2 - ao.get_height()//2))
            x += ao.get_width() + 4

        if S.get("conn") and S.get("ssid") and x < W - 60:
            ssid = S["ssid"][:8] + ".." if len(S["ssid"]) > 8 else S["ssid"]
            st = get_font(11).render(ssid, True, C_GREEN)
            self.screen.blit(st, (x, STATUS_H//2 - st.get_height()//2))

# ── Split-Screen UI ───────────────────────────────────────────
class SplitUI:
    def __init__(self, screen, categories, status, settings):
        self.screen     = screen
        self.categories = categories
        self.S          = status
        self.settings   = settings
        self.cat_sel    = 0
        self.item_sel   = 0
        self.item_scroll= 0
        self.focus      = "right"
        self.stack      = []
        self.statusbar  = StatusBar(screen, status)

    def _items(self):
        if self.stack:
            return self.stack[-1][1]
        return self.categories[self.cat_sel].items

    def _max_items(self):
        back_h = 44 if self.stack else 0
        return (H - STATUS_H - back_h) // SUB_IH

    def draw(self):
        self.screen.fill(C_BG)
        self._draw_left()
        self._draw_right()
        title = self.stack[-1][0] if self.stack else "PiDrive"
        self.statusbar.draw(title, self.settings.get("audio_output", "auto"))
        # Kein pygame.display.flip() hier — wird in main.py gemacht

    def _draw_left(self):
        """Linke Spalte auf eigener Surface — kein Ueberlaufen in rechte Spalte."""
        surf = pygame.Surface((LEFT_W - 1, H - STATUS_H))
        surf.fill(C_LEFT)

        y = 0
        for i, cat in enumerate(self.categories):
            is_sel = (i == self.cat_sel)
            r = pygame.Rect(0, y, LEFT_W - 1, CAT_IH)
            if is_sel:
                surf.fill(cat.color, r)
                surf.fill(C_WHITE, pygame.Rect(LEFT_W - 4, y, 3, CAT_IH))
            else:
                surf.fill(C_LEFT, r)
            txt_col = C_WHITE if is_sel else C_GRAY
            lbl = get_font(12, bold=is_sel).render(cat.label, True, txt_col)
            lx = max(2, (LEFT_W - 1)//2 - lbl.get_width()//2)
            ly = y + CAT_IH//2 - lbl.get_height()//2
            surf.blit(lbl, (lx, ly))
            if not is_sel:
                pygame.draw.line(surf, C_DIVIDER,
                                 (6, y + CAT_IH - 1),
                                 (LEFT_W - 9, y + CAT_IH - 1), 1)
            y += CAT_IH

        self.screen.blit(surf, (0, STATUS_H))
        pygame.draw.line(self.screen, C_DIVIDER,
                         (LEFT_W - 1, STATUS_H), (LEFT_W - 1, H), 1)

    def _draw_right(self):
        rx, rw = LEFT_W, RIGHT_W
        draw_rect(self.screen, C_RIGHT, (rx, STATUS_H, rw, H - STATUS_H))
        items = self._items()
        max_v = self._max_items()
        visible = items[self.item_scroll: self.item_scroll + max_v]
        y = STATUS_H + 4

        for i, item in enumerate(visible):
            real_idx = self.item_scroll + i
            is_sel = (real_idx == self.item_sel)
            if is_sel:
                draw_rect(self.screen, C_SEL,
                          (rx + 4, y + 2, rw - 8, SUB_IH - 4))
                draw_rect(self.screen, self.categories[self.cat_sel].color,
                          (rx + 4, y + 2, 3, SUB_IH - 4))

            if item.state:
                active = item.state()
                col = C_GREEN if active else C_RED
                pygame.draw.circle(self.screen, col,
                                   (W - 14, y + SUB_IH//2), 7)
                st = get_font(12).render("Ein" if active else "Aus", True, col)
                self.screen.blit(st, (W - 14 - st.get_width() - 8,
                                      y + SUB_IH//2 - st.get_height()//2))
            elif item.submenu or item.action:
                arr = get_font(12).render(">", True,
                              C_DARK if not is_sel else C_WHITE)
                self.screen.blit(arr, (W - arr.get_width() - 10,
                                       y + SUB_IH//2 - arr.get_height()//2))

            lbl = get_font(18, bold=True).render(item.label, True,
                            C_WHITE if is_sel else (200, 202, 215))
            self.screen.blit(lbl, (rx + 14, y + 8))

            if item.sub:
                s = item.sub() if callable(item.sub) else item.sub
                sl = get_font(12).render(str(s)[:30], True,
                              C_GREEN if is_sel else C_GRAY)
                self.screen.blit(sl, (rx + 14, y + 34))

            if not is_sel:
                pygame.draw.line(self.screen, C_DIVIDER,
                                 (rx + 12, y + SUB_IH - 1),
                                 (W - 8, y + SUB_IH - 1), 1)
            y += SUB_IH

        # Scrollbar
        total = len(items)
        if total > max_v:
            track_h = H - STATUS_H - (44 if self.stack else 0)
            thumb_h = max(20, track_h * max_v // total)
            thumb_y = STATUS_H + (track_h - thumb_h) * \
                      self.item_scroll // max(1, total - max_v)
            draw_rect(self.screen, C_DIVIDER, (W - 4, STATUS_H, 3, track_h))
            draw_rect(self.screen, C_BLUE, (W - 4, thumb_y, 3, thumb_h))

        if self.stack:
            by = H - 44
            draw_rect(self.screen, C_HEADER, (rx, by, rw, 44))
            pygame.draw.line(self.screen, C_DIVIDER, (rx, by), (W, by), 1)
            bt = get_font(13, bold=True).render("< Zurueck", True, C_BLUE)
            self.screen.blit(bt, (rx + 12, by + 22 - bt.get_height()//2))

    # Navigation
    def key_up(self):
        if self.focus == "left":
            if self.cat_sel > 0:
                self.cat_sel -= 1
                self.item_sel = self.item_scroll = 0
        else:
            if self.item_sel > 0:
                self.item_sel -= 1
                if self.item_sel < self.item_scroll:
                    self.item_scroll = self.item_sel

    def key_down(self):
        if self.focus == "left":
            if self.cat_sel < len(self.categories) - 1:
                self.cat_sel += 1
                self.item_sel = self.item_scroll = 0
        else:
            items = self._items()
            if self.item_sel < len(items) - 1:
                self.item_sel += 1
                mv = self._max_items()
                if self.item_sel >= self.item_scroll + mv:
                    self.item_scroll = self.item_sel - mv + 1

    def key_right(self):
        self.focus = "right"

    def key_left(self):
        if self.stack: self._pop()
        elif self.focus == "right": self.focus = "left"

    def key_enter(self):
        if self.focus == "left":
            self.focus = "right"
            return
        items = self._items()
        if not items or self.item_sel >= len(items):
            return
        item = items[self.item_sel]
        if item.toggle:
            item.toggle()
        elif item.submenu:
            self._push(item.label, item.submenu)
        elif item.action:
            item.action()

    def key_back(self):
        if self.stack: self._pop()
        else: self.focus = "left"

    def _push(self, title, items):
        self.stack.append((title, items, self.item_sel, self.item_scroll))
        self.item_sel = self.item_scroll = 0

    def _pop(self):
        if self.stack:
            _, _, s, sc = self.stack.pop()
            self.item_sel, self.item_scroll = s, sc

    def touch(self, vx, vy):
        if self.stack and vy > H - 44:
            self._pop()
            return
        if 0 <= vx < LEFT_W:
            ci = (vy - STATUS_H) // CAT_IH
            if 0 <= ci < len(self.categories):
                self.cat_sel = ci
                self.item_sel = self.item_scroll = 0
                self.focus = "right"
                self.stack.clear()
        elif vx >= LEFT_W:
            ii = (vy - STATUS_H) // SUB_IH
            ri = self.item_scroll + ii
            items = self._items()
            if 0 <= ri < len(items):
                self.item_sel = ri
                self.focus = "right"
                self.key_enter()

# ── Hilfs-Dialoge ─────────────────────────────────────────────
def show_message(screen, title, text, color=C_BLUE):
    screen.fill(C_BG)
    draw_rect(screen, C_HEADER, (0, 0, W, STATUS_H))
    pygame.draw.line(screen, color, (0, STATUS_H - 1), (W, STATUS_H - 1), 2)
    t2 = get_font(14, bold=True).render("PiDrive", True, C_WHITE)
    screen.blit(t2, (W//2 - t2.get_width()//2,
                      STATUS_H//2 - t2.get_height()//2))
    draw_rect(screen, C_LEFT, (20, H//2 - 52, W - 40, 104))
    pygame.draw.rect(screen, color,
                     pygame.Rect(20, H//2 - 52, W - 40, 104), 1)
    t = get_font(16, bold=True).render(title[:22], True, C_WHITE)
    m = get_font(13).render(text[:36], True, C_GRAY)
    screen.blit(t, (W//2 - t.get_width()//2, H//2 - 28))
    screen.blit(m, (W//2 - m.get_width()//2, H//2 + 8))
    pygame.display.flip()

def pick_list(screen, title, items, color=C_BLUE):
    IH, BH = 52, 44
    mv = (H - STATUS_H - BH) // IH
    sc = sel = 0

    while True:
        screen.fill(C_BG)
        draw_rect(screen, C_HEADER, (0, 0, W, STATUS_H))
        pygame.draw.line(screen, color, (0, STATUS_H - 1), (W, STATUS_H - 1), 2)
        t = get_font(14, bold=True).render(title, True, C_WHITE)
        screen.blit(t, (W//2 - t.get_width()//2,
                         STATUS_H//2 - t.get_height()//2))

        y = STATUS_H + 4
        vis = items[sc: sc + mv]
        for i, item in enumerate(vis):
            is_sel = (sc + i == sel)
            if is_sel:
                draw_rect(screen, C_SEL, (4, y + 2, W - 8, IH - 4))
                draw_rect(screen, color, (4, y + 2, 3, IH - 4))
            lbl = get_font(18, bold=True).render(str(item)[:28], True,
                            C_WHITE if is_sel else (200, 202, 215))
            screen.blit(lbl, (14, y + IH//2 - lbl.get_height()//2))
            if not is_sel:
                pygame.draw.line(screen, C_DIVIDER,
                                 (12, y + IH - 1), (W - 8, y + IH - 1), 1)
            y += IH

        by = H - BH
        draw_rect(screen, C_HEADER, (0, by, W, BH))
        pygame.draw.line(screen, C_DIVIDER, (0, by), (W, by), 1)
        bt = get_font(13, bold=True).render("< Zurueck  [ESC]", True, color)
        screen.blit(bt, (12, by + BH//2 - bt.get_height()//2))
        pygame.display.flip()

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_UP and sel > 0:
                    sel -= 1
                    if sel < sc: sc = sel
                elif ev.key == pygame.K_DOWN and sel < len(items) - 1:
                    sel += 1
                    if sel >= sc + mv: sc = sel - mv + 1
                elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER,
                                pygame.K_RIGHT):
                    return items[sel]
                elif ev.key in (pygame.K_ESCAPE, pygame.K_LEFT):
                    return None
