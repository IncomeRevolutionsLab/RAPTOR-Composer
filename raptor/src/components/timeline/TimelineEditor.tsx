"use client";

import { useState, useRef, useEffect } from 'react';
import { Play, Pause, Maximize2, Tag, Wand2, Trash2 } from 'lucide-react';
import { useTimelineStore } from '@/store/useTimelineStore';
import { useProductStore } from '@/store/useProductStore';

export default function TimelineEditor() {
  const { currentTime, setCurrentTime, duration, tags, updateTagPosition, removeTag } = useTimelineStore();
  const { products } = useProductStore();
  const [isPlaying, setIsPlaying] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Playback simulation
  useEffect(() => {
    let interval: any;
    if (isPlaying) {
      interval = setInterval(() => {
        setCurrentTime(Math.min(currentTime + 0.1, duration));
        if (currentTime >= duration) setIsPlaying(false);
      }, 100);
    }
    return () => clearInterval(interval);
  }, [isPlaying, currentTime, duration]);

  const handleTimelineClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const nextTime = (x / rect.width) * duration;
    setCurrentTime(Math.min(Math.max(nextTime, 0), duration));
  };

  const activeTags = tags.filter(t => Math.abs(t.timestamp - currentTime) < 0.5);

  const [automationResult, setAutomationResult] = useState<any>(null);

  return (
    <div className="flex flex-col gap-6 w-full max-w-4xl">
      {/* Preview Player */}
      <div 
        ref={containerRef}
        className="relative aspect-video bg-black rounded-2xl overflow-hidden border border-white/10 shadow-2xl group select-none"
      >
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900">
          {/* 실제 Grok 영상이 생성되었다고 가정한 시각적 처리 */}
          <div className="text-center">
            <Wand2 className="w-12 h-12 text-purple-500 mx-auto mb-4 animate-pulse" />
            <span className="text-gray-400 font-medium tracking-widest text-sm uppercase">GEM V2.1 AI GENERATED VIDEO</span>
          </div>
        </div>

        {/* AI 자동 자막 (Burn-in Simulation) */}
        {automationResult && (
          <div className="absolute bottom-16 inset-x-0 flex justify-center z-40 px-10">
            <div className="bg-black/80 text-white px-4 py-1.5 rounded-lg text-lg font-bold border border-white/20 text-center animate-bounce">
              {automationResult.scenes.find((s: any) => 
                currentTime >= (automationResult.scenes.indexOf(s) * 4) && 
                currentTime < ((automationResult.scenes.indexOf(s) + 1) * 4)
              )?.caption || ""}
            </div>
          </div>
        )}
        
        {/* Dynamic Tag Overlay */}
        {/* ... (기존 태그 로직 유지) ... */}

        {/* Player Controls */}
        <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/80 to-transparent p-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center justify-between z-30">
          <button onClick={() => setIsPlaying(!isPlaying)} className="text-white">
            {isPlaying ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6" />}
          </button>
          <div className="flex items-center gap-4">
             <span className="text-xs font-mono text-white/50">{currentTime.toFixed(1)}s</span>
             <button className="flex items-center gap-2 bg-green-500/80 text-white text-[10px] font-bold px-3 py-1.5 rounded-lg">
              <Maximize2 className="w-3 h-3" /> Export 720p
            </button>
          </div>
        </div>
      </div>

      {/* GEM V2.1 자동화 패널 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Timeline & Controls */}
        <div className="backdrop-blur-xl bg-gray-900/50 border border-white/10 rounded-2xl p-6 shadow-xl">
           <div className="flex items-center justify-between mb-6">
            <h3 className="text-white font-medium flex items-center gap-2">
              <Wand2 className="w-4 h-4 text-purple-400" />
              GEM V2.1 AI Auto-Pilot
            </h3>
            {automationResult && <span className="text-[10px] bg-purple-500/20 text-purple-300 px-2 py-1 rounded border border-purple-500/30 font-bold">{automationResult.pattern} 적용됨</span>}
          </div>

          <button 
            onClick={async () => {
              const { api } = await import('@/lib/api-client');
              try {
                const res = await api.post('/generate-full-automation', {
                  product_name: 'Premium Hoodie',
                  image_url: 'https://images.unsplash.com/photo-1556821840-3a63f95609a7?w=200&q=80'
                });
                setAutomationResult(res);
              } catch (e) {
                alert('Automation Error: ' + e);
              }
            }}
            className="w-full bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white py-4 rounded-xl font-bold flex items-center justify-center gap-3 shadow-xl shadow-purple-500/20 mb-6 transition-all transform active:scale-95"
          >
            <Wand2 className="w-5 h-5 animate-spin" /> START GEM V2.1 FULL AUTOMATION
          </button>

          {/* 스크립트 프리뷰 */}
          {automationResult && (
            <div className="space-y-3">
              <p className="text-xs font-bold text-gray-500 uppercase tracking-widest">AI Script Preview</p>
              {automationResult.scenes.map((s: any) => (
                <div key={s.id} className="p-3 bg-black/30 rounded-lg border border-white/5 text-xs text-gray-300">
                   <span className="text-purple-400 font-bold mr-2">[{s.id}]</span> {s.script}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Upload Package (유튜브 전용) */}
        <div className="backdrop-blur-xl bg-blue-900/10 border border-blue-500/20 rounded-2xl p-6 shadow-xl">
          <h3 className="text-white font-medium flex items-center gap-2 mb-6">
            <Maximize2 className="w-4 h-4 text-blue-400" />
            Upload Package (YT/TikTok)
          </h3>
          
          {automationResult ? (
            <div className="space-y-4">
              <div>
                <p className="text-[10px] text-blue-300 uppercase mb-2 font-bold">Recommended Titles</p>
                {automationResult.upload_package.titles.map((t: string, i: number) => (
                  <div key={i} className="text-xs bg-black/40 p-2 rounded border border-white/5 mb-1 text-gray-200">{t}</div>
                ))}
              </div>
              <div>
                <p className="text-[10px] text-blue-300 uppercase mb-2 font-bold">Description & CTA</p>
                <div className="text-[10px] bg-black/40 p-3 rounded border border-white/5 text-gray-400 leading-relaxed whitespace-pre-wrap">
                  {automationResult.upload_package.description}
                  {"\n\n" + automationResult.upload_package.cta}
                  {"\n\n" + automationResult.upload_package.hashtags.map((h: string) => `#${h}`).join(" ")}
                </div>
              </div>
            </div>
          ) : (
             <div className="h-48 flex items-center justify-center text-gray-600 text-xs text-center">
              자동 생성이 완료되면 여기에 <br/> 제목, 설명, 해시태그가 나타납니다.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
