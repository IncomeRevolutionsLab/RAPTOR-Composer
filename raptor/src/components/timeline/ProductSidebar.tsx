"use client";

import { useProductStore } from '@/store/useProductStore';
import { useTimelineStore } from '@/store/useTimelineStore';
import { Plus, ShoppingBag } from 'lucide-react';

export default function ProductSidebar() {
  const { products } = useProductStore();
  const { addTag, currentTime } = useTimelineStore();

  return (
    <div className="backdrop-blur-md bg-white/5 border border-white/10 rounded-2xl p-6 shadow-2xl relative group">
      <div className="relative z-10">
        <h3 className="text-sm font-medium text-gray-300 uppercase tracking-wider mb-6 flex items-center gap-2">
          <ShoppingBag className="w-4 h-4 text-purple-400" />
          Product SKU Catalog
        </h3>
        
        <div className="space-y-3">
          {products.map((product) => (
            <div 
              key={product.id}
              className="group/item flex items-center gap-3 p-2 bg-black/40 border border-white/5 rounded-xl hover:border-purple-500/50 transition-all cursor-pointer"
              onClick={() => addTag(product.id, currentTime)}
            >
              <div className="w-12 h-12 rounded-lg overflow-hidden bg-gray-800 border border-white/10">
                <img src={product.imageUrl} alt={product.name} className="w-full h-full object-cover group-hover/item:scale-110 transition-transform duration-500" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">{product.name}</p>
                <p className="text-xs text-purple-400 font-mono">₩{product.price.toLocaleString()}</p>
              </div>
              <button className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center text-gray-400 group-hover/item:bg-purple-500 group-hover/item:text-white transition-all">
                <Plus className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
        
        <p className="mt-6 text-[10px] text-gray-500 leading-relaxed italic text-center">
          * Click product to tag at {currentTime.toFixed(1)}s
        </p>
      </div>
    </div>
  );
}
