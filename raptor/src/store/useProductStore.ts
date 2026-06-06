import { create } from 'zustand';

/**
 * Commerce State (상품 데이터)
 * - 상품의 고유 정보(이름, 가격, 이미지 URL)만 관리
 * - 타임라인 정보와는 독립적으로 존재하여 데이터 무결성 확보
 */

interface Product {
  id: string;
  name: string;
  price: number;
  imageUrl: string;
  link: string;
}

interface ProductState {
  products: Product[];
  setProducts: (products: Product[]) => void;
}

export const useProductStore = create<ProductState>((set) => ({
  products: [
    { 
      id: 'p1', 
      name: 'Oversized Hoodie', 
      price: 59000, 
      imageUrl: 'https://images.unsplash.com/photo-1556821840-3a63f95609a7?w=200&q=80',
      link: 'https://example.com/p1'
    },
    { 
      id: 'p2', 
      name: 'Tech Joggers', 
      price: 45000, 
      imageUrl: 'https://images.unsplash.com/photo-1552664110-ad30f082c1ff?w=200&q=80',
      link: 'https://example.com/p2'
    },
    { 
      id: 'p3', 
      name: 'Canvas Sneakers', 
      price: 89000, 
      imageUrl: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=200&q=80',
      link: 'https://example.com/p3'
    },
  ],
  setProducts: (products) => set({ products }),
}));
