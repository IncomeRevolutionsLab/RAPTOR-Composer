import React, { useState, useEffect } from 'react';
import pricingData from '../config/kie_pricing.json';
import { Calculator } from 'lucide-react';

interface CostSimulatorWidgetProps {
  initialScenes?: number;
  initialDuration?: number;
  initialTextEngine?: string;
  initialImageEngine?: string;
  initialVideoEngine?: string;
}

export default function CostSimulatorWidget({
  initialScenes = 5,
  initialDuration = 15,
  initialTextEngine = 'claude-sonnet-4-6',
  initialImageEngine = 'gpt-image-2',
  initialVideoEngine = 'veo_lite'
}: CostSimulatorWidgetProps) {
  const [scenes, setScenes] = useState(initialScenes);
  const [duration, setDuration] = useState(initialDuration);
  const [textEngine, setTextEngine] = useState(initialTextEngine);
  const [imageEngine, setImageEngine] = useState(initialImageEngine);
  const [videoEngine, setVideoEngine] = useState(initialVideoEngine);
  const [totalCost, setTotalCost] = useState(0);

  useEffect(() => {
    // 텍스트 단가는 씬 당 대략 프롬프트가 300자라고 가정할 수도 있고, 그냥 호출당 단가로 칠 수도 있음
    // 여기서는 단순화하여 (텍스트 1회 호출 + 씬 개수 * 이미지 1장 + 씬 개수 * 비디오 1초당 단가 * 초) 등으로 계산하거나
    // 주어진 단순 계산 로직: 텍스트 단가 + (씬 개수 * 이미지 단가) + (씬 개수 * (영상길이/씬개수) * 비디오 단가) -> 텍스트 + 씬*이미지 + 영상길이*비디오 단가
    const txtPrice = (pricingData.text as any)[textEngine] || pricingData.text['claude-sonnet-4-6'];
    const imgPrice = (pricingData.image as any)[imageEngine] || pricingData.image['gpt-image-2'];
    const vidPrice = (pricingData.video as any)[videoEngine] || pricingData.video['veo_lite'];

    // 예상 로직:
    // 기획/스크립트 텍스트 호출 (단가 * 1)
    // 씬 개수만큼 이미지 생성 (씬 개수 * 이미지 단가)
    // 영상 생성: 비디오 단가는 초당 단가로 가정 (영상 길이 * 비디오 단가)
    const textCost = txtPrice * 1;
    const imageCost = scenes * imgPrice;
    const videoCost = duration * vidPrice;

    setTotalCost(textCost + imageCost + videoCost);
  }, [scenes, duration, textEngine, imageEngine, videoEngine]);

  return (
    <div className="bg-neutral-950/40 border border-white/5 rounded-2xl p-8 flex flex-col h-full animate-in fade-in duration-500">
      <div className="flex items-center gap-3 mb-8 pb-4 border-b border-white/5">
        <Calculator className="w-6 h-6 text-indigo-400" />
        <div>
          <h3 className="text-lg font-black text-white">비용 추정 시뮬레이터</h3>
          <p className="text-xs text-gray-500 mt-1">사용량 기반 예상 비용 사전 시뮬레이션</p>
        </div>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-8 flex-1">
        <div className="flex flex-col gap-2">
          <label className="text-xs font-bold text-slate-400 uppercase tracking-widest">씬 개수 (Scenes)</label>
          <input 
            type="number" 
            value={scenes} 
            onChange={(e) => setScenes(Number(e.target.value))} 
            className="bg-black/60 border border-white/10 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-indigo-500 transition-all"
            min={1} max={20}
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-xs font-bold text-slate-400 uppercase tracking-widest">영상 길이 (초)</label>
          <input 
            type="number" 
            value={duration} 
            onChange={(e) => setDuration(Number(e.target.value))} 
            className="bg-black/60 border border-white/10 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-indigo-500 transition-all"
            min={1} max={60}
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-xs font-bold text-slate-400 uppercase tracking-widest">텍스트 엔진</label>
          <select 
            value={textEngine} 
            onChange={(e) => setTextEngine(e.target.value)}
            className="bg-black/60 border border-white/10 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-indigo-500 transition-all cursor-pointer"
          >
            {Object.keys(pricingData.text).map(key => <option key={key} value={key}>{key}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-xs font-bold text-slate-400 uppercase tracking-widest">이미지 엔진</label>
          <select 
            value={imageEngine} 
            onChange={(e) => setImageEngine(e.target.value)}
            className="bg-black/60 border border-white/10 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-indigo-500 transition-all cursor-pointer"
          >
            {Object.keys(pricingData.image).map(key => <option key={key} value={key}>{key}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-xs font-bold text-slate-400 uppercase tracking-widest">비디오 엔진</label>
          <select 
            value={videoEngine} 
            onChange={(e) => setVideoEngine(e.target.value)}
            className="bg-black/60 border border-white/10 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-indigo-500 transition-all cursor-pointer"
          >
            {Object.keys(pricingData.video).map(key => <option key={key} value={key}>{key}</option>)}
          </select>
        </div>
      </div>

      <div className="bg-slate-900/50 rounded-2xl p-6 flex flex-col items-center justify-center border border-indigo-500/20 mb-4 shadow-inner">
        <div className="text-sm text-slate-400 mb-2 uppercase tracking-widest font-bold">총 예상 비용</div>
        <div className="text-5xl font-black text-indigo-400 drop-shadow-md">
          ${totalCost.toFixed(3)}
        </div>
      </div>

      <div className="text-[10px] text-gray-500 text-center bg-black/30 p-3 rounded-lg border border-white/5">
        ※ 안내: 위 금액은 사전 예상 추정치입니다. 실제 청구 비용은 KIE AI의 실시간 요금 정책 변동, 텍스트 프롬프트 길이, 그리고 서버 렌더링 환경 및 조건에 따라 달라질 수 있습니다.
      </div>
    </div>
  );
}
