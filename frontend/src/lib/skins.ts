export interface Skin {
  id: string;
  name: string;
  emoji: string;
  description: string;
}

export const SKINS: Skin[] = [
  {
    id: 'cburnett',
    name: 'Clásica',
    emoji: '♟️',
    description: 'Estilo tradicional de Wikipedia'
  },
  {
    id: 'merida',
    name: 'Mérida',
    emoji: '♜',
    description: 'Clásico español detallado'
  },
  {
    id: 'alpha',
    name: 'Alpha',
    emoji: '◆',
    description: 'Moderno y minimalista'
  },
  {
    id: 'kiwen-suwi',
    name: 'Kiwen Suwi',
    emoji: '🌸',
    description: 'Adorable y suave'
  }
];

export function getSkin(id: string): Skin {
  return SKINS.find(s => s.id === id) || SKINS[0];
}