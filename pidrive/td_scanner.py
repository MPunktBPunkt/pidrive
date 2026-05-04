#!/usr/bin/env python3
"""td_scanner.py — Scanner-Steuerung  v0.10.18"""
import os, sys, time as _time_mod, threading
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
import log, ipc
from settings import save_settings
from modules import source_state
from modules import (
    musik, wifi, bluetooth, audio, system as sys_mod,
    webradio, dab, fm, library, scanner, update, favorites
)


def handle(cmd, menu_state, store, S, settings, bg):
    # ── Scanner ─────────────────────────────────────────────────────────────
    if cmd.startswith("scan_up:"):
        band = cmd.split(":", 1)[1]
        def _scan_up(b=band):
            source_state.begin_transition(f"scan_up:{b}", "scanner")
            try:
                scanner.channel_up(b, S)
            finally:
                source_state.end_transition()
        bg(_scan_up)

    elif cmd.startswith("scan_down:"):
        band = cmd.split(":", 1)[1]
        def _scan_down(b=band):
            source_state.begin_transition(f"scan_down:{b}", "scanner")
            try:
                scanner.channel_down(b, S)
            finally:
                source_state.end_transition()
        bg(_scan_down)

    elif cmd.startswith("scan_next:"):
        band = cmd.split(":", 1)[1]
        def _scan_next(b=band):
            if source_state.begin_transition(f"scan_next:{b}", "scanner"):
                try:
                    scanner.scan_next(b, S, settings)
                finally:
                    source_state.end_transition()
        bg(_scan_next)

    elif cmd.startswith("scan_prev:"):
        band = cmd.split(":", 1)[1]
        def _scan_prev(b=band):
            if source_state.begin_transition(f"scan_prev:{b}", "scanner"):
                try:
                    scanner.scan_prev(b, S, settings)
                finally:
                    source_state.end_transition()
        bg(_scan_prev)

    elif cmd.startswith("scan_jump:"):
        parts = cmd.split(":")
        if len(parts) >= 3:
            band = parts[1]
            try:
                delta = int(parts[2])
            except Exception:
                delta = 0
            if delta:
                # v0.10.18: settings durchreichen + begin_transition wrapper
                def _scan_jump_fn(b=band, d=delta):
                    if source_state.begin_transition(f"scan_jump:{b}", "scanner"):
                        try:
                            scanner.channel_jump(b, d, S, settings)
                        finally:
                            source_state.end_transition()
                bg(_scan_jump_fn)

    elif cmd.startswith("scan_step:"):
        parts = cmd.split(":")
        if len(parts) >= 3:
            band = parts[1]
            try:
                delta = float(parts[2])
            except Exception:
                delta = 0.0
            if delta:
                # v0.10.18: begin_transition wrapper
                def _scan_step_fn(b=band, d=delta):
                    if source_state.begin_transition(f"scan_step:{b}", "scanner"):
                        try:
                            scanner.freq_step(b, d, S, settings)
                        finally:
                            source_state.end_transition()
                bg(_scan_step_fn)

    elif cmd.startswith("scan_setfreq:"):
        parts = cmd.split(":")
        if len(parts) >= 3:
            band = parts[1]
            try:
                freq = float(parts[2])
            except Exception:
                freq = 0.0
            if freq:
                # v0.10.18: begin_transition wrapper
                def _scan_setfreq_fn(b=band, f=freq):
                    if source_state.begin_transition(f"scan_setfreq:{b}", "scanner"):
                        try:
                            scanner.set_freq(b, f, S, settings)
                        finally:
                            source_state.end_transition()
                bg(_scan_setfreq_fn)

    elif cmd.startswith("scan_inputfreq:"):
        parts = cmd.split(":")
        if len(parts) >= 2:
            band = parts[1]
            # v0.10.18: begin_transition wrapper
            def _input_and_set(b=band):
                freq = scanner.freq_input_screen(b, settings)
                if freq is not None:
                    if source_state.begin_transition(f"scan_inputfreq:{b}", "scanner"):
                        try:
                            scanner.set_freq(b, freq, S, settings)
                        finally:
                            source_state.end_transition()
            bg(_input_and_set)

    else:
        return False
    return True
