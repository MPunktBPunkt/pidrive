"""Zentraler Metadaten-Reset bei Quellwechsel."""

# Felder die bei Quellwechsel geloescht werden
_META_KEYS = (
    "track", "artist", "album",
    "dls", "dls_text", "dls_raw", "dls_ts",
    "metadata_unavailable", "_last_hist_track", "source_error",
    "dab_lock", "dab_sync", "dab_state",
)

_RADIO_KEYS = ("radio_name",)


def clear_playback_metadata(S: dict, *, keep_station: bool = False) -> None:
    """Entfernt Titel/DLS/Artist aus dem Core-State dict."""
    for k in _META_KEYS:
        S.pop(k, None)
    if not keep_station:
        for k in _RADIO_KEYS:
            S.pop(k, None)


def metadata_for_source(source: str, status: dict) -> dict:
    """Liefert angezeigte Titel/Artist/DLS passend zur aktiven Quelle."""
    src = (source or "idle").lower()
    st = status or {}

    if src in ("", "idle"):
        return {"title": "", "artist": "", "dls": "", "playing": False}

    if src == "scanner":
        return {
            "title": st.get("radio_name") or st.get("radio_station") or "Scanner",
            "artist": "",
            "dls": "",
            "playing": bool(st.get("radio")),
        }

    if src == "dab":
        return {
            "title": st.get("track") or st.get("radio_name") or "",
            "artist": st.get("artist") or "",
            "dls": st.get("dls_text") or st.get("dls") or "",
            "playing": True,
        }

    if src in ("webradio", "web"):
        return {
            "title": st.get("track") or st.get("radio_name") or "",
            "artist": st.get("artist") or "",
            "dls": "",
            "playing": bool(st.get("radio")),
        }

    if src == "fm":
        return {
            "title": st.get("radio_name") or st.get("track") or "",
            "artist": st.get("artist") or "",
            "dls": "",
            "playing": bool(st.get("radio")),
        }

    if src == "spotify":
        return {
            "title": st.get("track") or st.get("spotify_track") or "",
            "artist": st.get("artist") or st.get("spotify_artist") or "",
            "dls": "",
            "playing": bool(st.get("spotify")),
        }

    return {
        "title": st.get("track") or st.get("radio_name") or "",
        "artist": st.get("artist") or "",
        "dls": st.get("dls_text") or "",
        "playing": src not in ("idle",),
    }
