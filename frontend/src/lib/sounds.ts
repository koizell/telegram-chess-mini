/**
 * Gestor de sonidos de la Mini App.
 * Precarga los audios para reproducción instantánea.
 */
import { base } from '$app/paths';

class SoundManager {
  private sounds: Record<string, HTMLAudioElement> = {};
  private enabled: boolean = true;
  private volume: number = 0.5;

  constructor() {
    if (typeof window !== 'undefined') {
      this.preload();
      this.loadSettings();
    }
  }

  private preload() {
    this.sounds = {
      move: new Audio(`${base}/sounds/move.mp3`),
      capture: new Audio(`${base}/sounds/capture.mp3`),
      select: new Audio(`${base}/sounds/select.mp3`)
    };

    // Establecer volumen
    Object.values(this.sounds).forEach((audio) => {
      audio.volume = this.volume;
      audio.preload = 'auto';
    });
  }

  private loadSettings() {
    if (typeof localStorage !== 'undefined') {
      const saved = localStorage.getItem('chess_sound_enabled');
      if (saved !== null) this.enabled = saved === 'true';

      const savedVol = localStorage.getItem('chess_sound_volume');
      if (savedVol) this.setVolume(parseFloat(savedVol));
    }
  }

  play(name: 'move' | 'capture' | 'select') {
    if (!this.enabled) return;

    const sound = this.sounds[name];
    if (!sound) return;

    // Reiniciar el audio si ya está sonando (para movimientos rápidos)
    try {
      sound.currentTime = 0;
      sound.play().catch((err) => {
        // Los navegadores pueden bloquear el audio hasta la primera interacción
        console.debug('Audio bloqueado o error:', err.message);
      });
    } catch (e) {
      console.debug('Error reproduciendo sonido:', e);
    }
  }

  setEnabled(value: boolean) {
    this.enabled = value;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('chess_sound_enabled', String(value));
    }
  }

  isEnabled() {
    return this.enabled;
  }

  setVolume(value: number) {
    this.volume = Math.max(0, Math.min(1, value));
    Object.values(this.sounds).forEach((audio) => {
      audio.volume = this.volume;
    });
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('chess_sound_volume', String(this.volume));
    }
  }

  getVolume() {
    return this.volume;
  }
}

export const sounds = new SoundManager();