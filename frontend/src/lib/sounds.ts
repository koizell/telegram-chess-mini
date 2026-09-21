/**
 * Gestor de sonidos de la Mini App.
 * - move/capture/select: archivos MP3 (Lichess)
 * - victory/defeat/draw: generados con Web Audio API (sin archivos)
 */
import { base } from '$app/paths';

class SoundManager {
  private sounds: Record<string, HTMLAudioElement> = {};
  private enabled: boolean = true;
  private volume: number = 0.5;
  private audioContext: AudioContext | null = null;

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

  private getAudioContext(): AudioContext {
    if (!this.audioContext) {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      this.audioContext = new AudioCtx();
    }
    return this.audioContext;
  }

  /**
   * Reproduce una melodía de notas con Web Audio API.
   * @param notes Array de { freq, duration, delay } en Hz y segundos.
   */
  private playMelody(notes: { freq: number; duration: number; delay: number }[]) {
    try {
      const ctx = this.getAudioContext();
      const now = ctx.currentTime;

      notes.forEach((note) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = 'sine';
        osc.frequency.value = note.freq;

        const startTime = now + note.delay;
        const endTime = startTime + note.duration;

        // Envolvente de volumen (ataque y caída suaves)
        gain.gain.setValueAtTime(0, startTime);
        gain.gain.linearRampToValueAtTime(this.volume, startTime + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.001, endTime);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start(startTime);
        osc.stop(endTime);
      });
    } catch (e) {
      console.debug('Error generando melodía:', e);
    }
  }

  play(name: 'move' | 'capture' | 'select' | 'victory' | 'defeat' | 'draw') {
    if (!this.enabled) return;

    // Sonidos de archivo
    if (name === 'move' || name === 'capture' || name === 'select') {
      const sound = this.sounds[name];
      if (!sound) return;
      try {
        sound.currentTime = 0;
        sound.play().catch((err) => console.debug('Audio bloqueado:', err.message));
      } catch (e) {
        console.debug('Error reproduciendo:', e);
      }
      return;
    }

    // Sonidos generados con Web Audio API
    if (name === 'victory') {
      // Fanfarria alegre: Do - Mi - Sol - Do (arriba)
      this.playMelody([
        { freq: 523.25, duration: 0.15, delay: 0 },     // C5
        { freq: 659.25, duration: 0.15, delay: 0.15 },  // E5
        { freq: 783.99, duration: 0.15, delay: 0.30 },  // G5
        { freq: 1046.50, duration: 0.4, delay: 0.45 }   // C6
      ]);
    } else if (name === 'defeat') {
      // Melodía triste descendente: Sol - Mi - Do - La (abajo)
      this.playMelody([
        { freq: 392.00, duration: 0.20, delay: 0 },     // G4
        { freq: 349.23, duration: 0.20, delay: 0.20 },  // F4
        { freq: 293.66, duration: 0.20, delay: 0.40 },  // D4
        { freq: 220.00, duration: 0.5, delay: 0.60 }    // A3
      ]);
    } else if (name === 'draw') {
      // Dos notas neutras iguales
      this.playMelody([
        { freq: 440.00, duration: 0.20, delay: 0 },     // A4
        { freq: 440.00, duration: 0.20, delay: 0.25 }   // A4
      ]);
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