// page-index.js — PiDrive Alltagsseite (index.html)
// Übernimmt Favoriten-Laden und Source-Update via PiDriveAPI

document.addEventListener('DOMContentLoaded', function() {

  // Favoriten laden
  async function loadFavorites() {
    try {
      const j = await PiDriveAPI.fetchJson('/api/favorites');
      const favs = j.favorites || j || [];
      const grid = document.getElementById('favGrid');
      if (!grid) return;
      if (!favs.length) {
        grid.innerHTML = '<div style="color:var(--muted);font-size:12px">Keine Favoriten</div>';
        return;
      }
      grid.innerHTML = favs.slice(0, 8).map((f, i) =>
        `<button class="fav-btn" onclick="PiDriveAPI.sendCmd('favorites_play:${i+1}');showToast('${f.name||'?'}')">
          <span class="fb-src">${(f.source||'').toUpperCase()}</span>
          <span class="fb-name">${f.name||'?'}</span>
        </button>`).join('');
    } catch(e) { console.log('page-index: Favoriten-Fehler', e); }
  }

  // onBaseRefresh-Hook — wird von base.html aufgerufen
  window.onBaseRefresh = function(j, st, ss) {
    const e = (id) => document.getElementById(id);
    const src = ss.source_current || '';
    const srcMap = {dab:'📻 DAB+', fm:'📡 FM', webradio:'📶 Web', spotify:'🎵 Spotify', idle:'–', '':'–'};
    if(e('nowSource')) e('nowSource').textContent = srcMap[src] || src.toUpperCase();
    const nowTxt = st.track || (st.radio_playing ? st.radio_name : '') || '–';
    if(e('nowTrack')) e('nowTrack').textContent = nowTxt;
    const metaParts = [st.artist, st.radio_type].filter(Boolean);
    if(st.radio_name && st.radio_name !== nowTxt) metaParts.push(st.radio_name);
    if(e('nowMeta')) e('nowMeta').textContent = metaParts.join(' · ') || '–';
    const dls = st.dls_text || st.dls_raw || '';
    if(e('nowDls')) { e('nowDls').textContent = dls; e('nowDls').style.display = dls ? '' : 'none'; }
    const msEl = e('metaStatus');
    if(msEl) {
      const ps = st.dab_playback_state || '';
      let msg = '';
      if(st.metadata_unavailable) msg = '(Metadaten nicht verfügbar)';
      else if(ps === 'no_lock') msg = '⚠ DAB: kein Lock';
      else if(ps === 'partial_sync') msg = '📡 DAB: partieller Sync';
      else if(ps === 'starting') msg = '⏳ DAB: suche Signal…';
      msEl.textContent = msg; msEl.style.display = msg ? 'block' : 'none';
    }
    document.querySelectorAll('.source-tile').forEach(t => t.classList.remove('playing'));
    const tileMap = {dab:'tileDAB', fm:'tileFM', webradio:'tileWeb', spotify:'tileSpot'};
    if(tileMap[src]) { const a = e(tileMap[src]); if(a) a.classList.add('playing'); }
    if(e('btCardVal')) {
      e('btCardVal').textContent = st.bt ? '● Verbunden' : '○ Getrennt';
      e('btCardVal').style.color = st.bt ? 'var(--green)' : 'var(--muted)';
    }
    if(e('btCardDev')) e('btCardDev').textContent = st.bt_device || '';
    if(e('volCardVal')) e('volCardVal').textContent = (st.volume ?? '–') + '%';
    if(e('volCardAudio')) e('volCardAudio').textContent = st.audio_effective || '–';
    if(e('navAudioSub')) e('navAudioSub').textContent = st.audio_effective || 'klinke';
  };

  loadFavorites();
  console.log('PiDrive page-index.js geladen');
});
