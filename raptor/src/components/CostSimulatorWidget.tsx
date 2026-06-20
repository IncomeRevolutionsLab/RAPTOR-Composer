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
    <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 shadow-lg animate-in fade-in slide-in-from-bottom-4 duration-500 my-8">
      <div className="flex items-center gap-2 mb-6">
        <Calculator className="w-5 h-5 text-indigo-400" />
        <h3 className="text-lg font-bold text-white">비용 추정 시뮬레이터</h3>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-400">씬 개수 (Scenes)</label>
          <input 
            type="number" 
            value={scenes} 
            onChange={(e) => setScenes(Number(e.target.value))} 
            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
            min={1}
            max={20}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-400">영상 길이 (초)</label>
          <input 
            type="number" 
            value={duration} 
            onChange={(e) => setDuration(Number(e.target.value))} 
            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
            min={1}
            max={60}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-400">텍스트 엔진</label>
          <select 
            value={textEngine} 
            onChange={(e) => setTextEngine(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
          >
            {Object.keys(pricingData.text).map(key => (
              <option key={key} value={key}>{key}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-400">이미지 엔진</label>
          <select 
            value={imageEngine} 
            onChange={(e) => setImageEngine(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
          >
            {Object.keys(pricingData.image).map(key => (
              <option key={key} value={key}>{key}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-400">비디오 엔진</label>
          <select 
            value={videoEngine} 
            onChange={(e) => setVideoEngine(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
          >
            {Object.keys(pricingData.video).map(key => (
              <option key={key} value={key}>{key}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="bg-slate-950 rounded-lg p-5 flex flex-col items-center justify-center border border-slate-800">
        <div className="text-sm text-slate-400 mb-1">총 예상 비용</div>
        <div className="text-4xl font-black text-indigo-400">
          ${totalCost.toFixed(3)}
        </div>
      </div>

      <div className="mt-4 p-3 bg-slate-800/50 rounded-lg border border-slate-700/50">
        <p className="text-sm text-gray-400 leading-relaxed text-center">
          ※ 안내: 위 금액은 사전 예상 추정치입니다. 실제 청구 비용은 KIE AI의 실시간 요금 정책 변동, 텍스트 프롬프트 길이, 그리고 서버 렌더링 환경 및 조건에 따라 달라질 수 있습니다.
        </p>
      </div>
    </div>
  );
}
