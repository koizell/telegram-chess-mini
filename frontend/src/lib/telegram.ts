/**
 * Integración con Telegram WebApp SDK.
 */
import { writable } from 'svelte/store';

export interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  language_code?: string;
  photo_url?: string;
}

export const tgUser = writable<TelegramUser | null>(null);
export const isTelegram = writable<boolean>(false);

/**
 * Inicializa el SDK de Telegram. Se llama una sola vez desde +layout.svelte.
 */
export function initTelegram() {
  if (typeof window === 'undefined') return;

  const tg = (window as any).Telegram?.WebApp;
  if (!tg) {
    console.log('⚠️ No estamos dentro de Telegram (modo desarrollo).');
    return;
  }

  tg.ready();
  tg.expand();

  const user = tg.initDataUnsafe?.user;
  if (user) {
    tgUser.set(user);
    isTelegram.set(true);
    console.log('✅ Usuario de Telegram detectado:', user.first_name);
  }
}