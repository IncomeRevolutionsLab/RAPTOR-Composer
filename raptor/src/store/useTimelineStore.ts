import { create } from 'zustand';

/**
 * Composition State (편집 데이터)
 * - 영상 내 상품이 노출되는 시간(timestamp)과 좌표(x, y)만 관리
 * - 상품의 실제 가격, 이름 등 메타데이터는 ProductStore와 분리
 */

interface Tag {
  id: string;
  productId: string; // ProductStore의 ID를 참조하는 외래키 역할
  timestamp: number;
  x: number;
  y: number;
}

interface TimelineState {
  currentTime: number;
  duration: number;
  tags: Tag[];
  setCurrentTime: (time: number) => void;
  addTag: (productId: string, timestamp: number) => void;
  updateTagPosition: (id: string, x: number, y: number) => void;
  removeTag: (id: string) => void;
}

export const useTimelineStore = create<TimelineState>((set) => ({
  currentTime: 0,
  duration: 15,
  tags: [
    { id: 't1', productId: 'p1', timestamp: 2.5, x: 25, y: 40 },
    { id: 't2', productId: 'p2', timestamp: 7.2, x: 60, y: 70 }
  ],
  setCurrentTime: (time) => set({ currentTime: time }),
  addTag: (productId, timestamp) => set((state) => ({
    tags: [...state.tags, { 
      id: `tag-${Date.now()}`, 
      productId, 
      timestamp, 
      x: 50, 
      y: 50 
    }]
  })),
  updateTagPosition: (id, x, y) => set((state) => ({
    tags: state.tags.map(t => t.id === id ? { ...t, x, y } : t)
  })),
  removeTag: (id) => set((state) => ({
    tags: state.tags.filter(t => t.id !== id)
  })),
}));
