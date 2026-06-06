"use client";

import { useState, useEffect } from 'react';
import { Key, Eye, EyeOff, Save, CheckCircle, Settings, X } from 'lucide-react';
import { useWorkflowStore } from '@/store/useWorkflowStore';
import { api } from '@/lib/api-client';

export default function BYOKSettingsForm() {
  const { isKeyConfigured, setIsKeyConfigured, setCsrfToken, hasHydrated } = useWorkflowStore();
  
  // local state for editing
  const [kieKey, setKieKey] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  
  const [visibility, setVisibility] = useState({
    kieKey: false
  });
  
  const [isStored, setIsStored] = useState({
    kieKey: isKeyConfigured
  });
  
  const [saved, setSaved] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Sync with store and backend on mount (Hydration fix)
  useEffect(() => {
    setMounted(true);
    if (!hasHydrated) return;
    api.get('/auth/check-key')
      .then(res => {
        setIsKeyConfigured(res.configured);
        if (res.csrf_token) {
          setCsrfToken(res.csrf_token);
        }
        setIsStored({
          kieKey: res.configured
        });
        setKieKey("");
      })
      .catch(err => {
        console.error("Failed to check key configured", err);
      });
  }, [setIsKeyConfigured, setCsrfToken, hasHydrated]);

  if (!mounted) return null; // Prevent SSR Hydration Mismatch

  const handleSave = async () => {
    try {
      if (!isStored.kieKey && (!kieKey || kieKey.trim() === "")) {
        // Clear key
        await api.post('/auth/clear-key', {});
        setIsKeyConfigured(false);
        setCsrfToken(null);
        setIsStored({ kieKey: false });
        setKieKey("");
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
        return;
      }

      if (isStored.kieKey) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
        return;
      }

      // Save key to HttpOnly Cookie
      const res = await api.post('/auth/set-key', { kie_key: kieKey });
      if (res.csrf_token) {
        setCsrfToken(res.csrf_token);
      }
      setIsKeyConfigured(true);
      setIsStored({
        kieKey: true
      });
      setKieKey("");
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err: any) {
      alert(`키 설정에 실패했습니다: ${err.message}`);
    }
  };

  const toggleVisibility = (key: 'kieKey') => {
    if (isStored[key]) return;
    setVisibility(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleInputChange = (key: 'kieKey', value: string, setter: (val: string) => void) => {
    setter(value);
    if (isStored[key]) {
      setIsStored(prev => ({ ...prev, [key]: false }));
    }
  };

  const renderKeyInput = (label: string, value: string, key: 'kieKey', placeholder: string, setter: (val: string) => void, color: string) => {
    const maskedValue = isStored[key] ? "•".repeat(24) : value;
    
    return (
      <div key={key}>
        <label className="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
          {label}
        </label>
        <div className="relative">
          <input 
            type={visibility[key] || isStored[key] ? "text" : "password"} 
            value={maskedValue}
            onChange={(e) => handleInputChange(key, e.target.value, setter)}
            placeholder={placeholder}
            className={`w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-${color}-500/50 focus:border-transparent transition-all ${isStored[key] ? 'opacity-60 cursor-pointer' : ''}`}
            readOnly={isStored[key]}
            onClick={() => isStored[key] && handleInputChange(key, "", setter)}
          />
          <button 
            onClick={() => toggleVisibility(key)}
            disabled={isStored[key]}
            className={`absolute right-3 top-1/2 -translate-y-1/2 transition-colors ${isStored[key] ? 'text-gray-700' : 'text-gray-500 hover:text-white'}`}
            title={isStored[key] ? "저장된 키는 열람이 불가합니다. 수정하려면 클릭하여 새로 입력하세요." : "키 보기/숨기기"}
          >
            {visibility[key] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
      </div>
    );
  };


  return (
    <div className="relative z-[45] flex flex-col items-end">
      {/* Toggle Button */}
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2 px-5 py-3 rounded-full backdrop-blur-md border transition-all shadow-2xl ${
          isOpen 
            ? 'bg-red-500/10 border-red-500/30 text-red-400 hover:bg-red-500/20' 
            : 'bg-neutral-900/50 border-white/10 text-gray-300 hover:text-white hover:bg-neutral-800/80 hover:border-purple-500/50'
        }`}
      >
        {isOpen ? <X className="w-5 h-5" /> : <Settings className="w-5 h-5 text-purple-400" />}
        <span className="text-sm font-bold tracking-widest uppercase">
          {isOpen ? 'Close Settings' : 'Global Settings'}
        </span>
      </button>

      {/* Popover Form */}
      {isOpen && (
        <div className="absolute top-16 right-0 backdrop-blur-2xl bg-neutral-950/95 border border-white/10 rounded-2xl shadow-[0_0_40px_rgba(0,0,0,0.8)] w-[24rem] max-w-[90vw] flex flex-col max-h-[80vh] overflow-hidden animate-in slide-in-from-top-4 fade-in duration-300 origin-top-right z-[50]">
          <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-blue-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
          
          {/* 1. Modal Header (Fixed) */}
          <div className="px-6 py-5 border-b border-white/5 shrink-0 flex flex-col gap-4">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Settings className="w-5 h-5 text-purple-400" />
              Global Settings
            </h2>
            <button 
              onClick={handleSave}
              className={`w-full py-3 px-4 rounded-xl font-black text-sm uppercase tracking-widest flex items-center justify-center gap-2 transition-all duration-300 ${
                saved 
                  ? 'bg-green-500/20 text-green-400 border border-green-500/30' 
                  : 'bg-white text-black hover:bg-gray-200 shadow-xl'
              }`}
            >
              {saved ? (
                <><CheckCircle className="w-5 h-5" /> Saved</>
              ) : (
                <><Save className="w-5 h-5" /> Save Configuration</>
              )}
            </button>
          </div>

          <div className="px-6 py-6 overflow-y-auto grow space-y-5 custom-scrollbar">
            <div className="space-y-4">
              <div className="col-span-2">
                {renderKeyInput("🔑 KIE API Key", kieKey, "kieKey", "kie-...", setKieKey, "purple")}
              </div>
            </div>
            
            <div className="bg-blue-500/5 border border-blue-500/10 rounded-xl p-4 mt-4">
              <p className="text-[10px] text-blue-300 leading-relaxed italic">
                * KIE API Key 1개만 입력하면 모든 AI 렌더링 파이프라인(Claude 기획, DALL-E 이미지, Grok/Veo 비디오)이 자동 통합 매핑됩니다.
              </p>
            </div>
          </div>

          {/* 3. Modal Footer (Sticky) */}
          <div className="px-6 py-4 border-t border-white/5 bg-black/20 shrink-0">
            <p className="text-[9px] text-gray-500 text-center uppercase tracking-widest font-medium">
              V2.2 Unified KIE Engine Configuration
            </p>
          </div>

        </div>
      )}
    </div>
  );
}
