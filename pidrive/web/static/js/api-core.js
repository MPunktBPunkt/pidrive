// api-core.js — PiDrive API-Wrapper (Core-Polling, Commands)
// Wird von allen Seiten gemeinsam genutzt.

const PiDriveAPI = {
  async fetchCore() {
    const r = await fetch('/api/core');
    return r.json();
  },
  async sendCmd(cmd) {
    const r = await fetch('/api/cmd', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cmd })
    });
    return r.json();
  },
  async fetchStatus() {
    const r = await fetch('/api/state');
    return r.json();
  },
  async fetchAudio() {
    const r = await fetch('/api/audio');
    return r.json();
  },
  async fetchBtKnown() {
    const r = await fetch('/api/bt/known');
    return r.json();
  },
  async fetchDabStatus() {
    const r = await fetch('/api/dab/status');
    return r.json();
  },
  async fetchSystemResources() {
    const r = await fetch('/api/system/resources');
    return r.json();
  }
};
