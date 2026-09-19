export interface Theme {
  id: string;
  name: string;
  emoji: string;
  lightSquare: string;
  darkSquare: string;
  highlightColor: string;
  coordColor: string;
  preview: string;
}

export const THEMES: Theme[] = [
  {
    id: 'clasico',
    name: 'Clásico',
    emoji: '🟫',
    lightSquare: '#f0d9b5',
    darkSquare: '#b58863',
    highlightColor: '#cdd26a',
    coordColor: '#8b5a2b',
    preview: 'El tablero de madera tradicional'
  },
  {
    id: 'nocturno',
    name: 'Nocturno',
    emoji: '🌙',
    lightSquare: '#b8c4cc',
    darkSquare: '#5a6b78',
    highlightColor: '#ffc83c',
    coordColor: '#e0e8f0',
    preview: 'Grises azulados elegantes'
  },
  {
    id: 'bosque',
    name: 'Bosque',
    emoji: '🌲',
    lightSquare: '#e8e0c8',
    darkSquare: '#6b8e4e',
    highlightColor: '#ffd700',
    coordColor: '#2d4a1a',
    preview: 'Verdes naturales cálidos'
  },
  {
    id: 'oceano',
    name: 'Océano',
    emoji: '🌊',
    lightSquare: '#c8e0ec',
    darkSquare: '#4a7ba6',
    highlightColor: '#00d4ff',
    coordColor: '#0a2a42',
    preview: 'Azules profundos del mar'
  },
  {
    id: 'neon',
    name: 'Neón',
    emoji: '⚡',
    lightSquare: '#c8b0e8',
    darkSquare: '#7a5ab8',
    highlightColor: '#00ffff',
    coordColor: '#ffffff',
    preview: 'Violeta cyberpunk con cian'
  },
  {
    id: 'papel',
    name: 'Papel',
    emoji: '📜',
    lightSquare: '#f5f0e6',
    darkSquare: '#c9b99a',
    highlightColor: '#a8c66c',
    coordColor: '#7a6a4a',
    preview: 'Tonos suaves tipo periódico'
  }
];

export function getTheme(id: string): Theme {
  return THEMES.find(t => t.id === id) || THEMES[0];
}