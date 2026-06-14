"use client";

import { useState, useEffect } from 'react';
import { Link as LinkIcon, Sparkles, CheckCircle, Download, Wand2, Trash2, Plus, Play, Loader2, Image as ImageIcon, Languages, Monitor, Smartphone, Square, RotateCcw, AlertCircle, Upload, Film } from 'lucide-react';
import { useWorkflowStore } from '@/store/useWorkflowStore';
import { api } from '@/lib/api-client';
import { supabase } from '@/lib/supabaseClient';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

// --- Client-Side Image Compression (Resizing to 1024px) ---
const compressImage = (base64: string): Promise<string> => {
  return new Promise((resolve) => {
    const img = new Image();
    img.src = base64;
    img.onload = () => {
      const canvas = document.createElement("canvas");
      const MAX_SIZE = 1024;
      let width = img.width;
      let height = img.height;

      if (width > height) {
        if (width > MAX_SIZE) {
          height *= MAX_SIZE / width;
          width = MAX_SIZE;
        }
      } else {
        if (height > MAX_SIZE) {
          width *= MAX_SIZE / height;
          height = MAX_SIZE;
        }
      }

      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      ctx?.drawImage(img, 0, 0, width, height);
      resolve(canvas.toDataURL("image/jpeg", 0.7)); // Quality 0.7 for compression
    };
    img.onerror = () => resolve(base64); // Fallback
  });
};

export default function RaptorWorkflow() {
  const [mounted, setMounted] = useState(false);

  // Zustand Store Hooks
  const {
    step, setStep,
    loading, statusMessage, setLoading,
    inputMode, setInputMode,
    aspectRatio, setAspectRatio,
    voiceType, setVoiceType,
    subtitlePosition, setSubtitlePosition, // Added
    renderDuration, setRenderDuration,
    productData, setProductData,
    analysis, setAnalysis,
    recommendedPatterns, setRecommendedPatterns,
    selectedType, setSelectedType,
    finalAssets, setFinalAssets,
    manualAdditions, setManualAdditions,
    isRendering, renderProgress, renderedVideoUrl, setRenderStatus,
    tempInput, setTempInput,
    errorMessage, setErrorMessage,
    resetWorkflow,
    watermarkEnabled, watermarkLogo, watermarkPosition, setWatermarkSettings,
    imageEngine, textEngine, claudeModel, setEngineSettings,
    projectId, setProjectId
  } = useWorkflowStore();
  
  const [videoEngine, setVideoEngine] = useState<'grok' | 'veo_lite' | 'veo_fast'>('grok');
  const [isUploading, setIsUploading] = useState(false);
  const [sceneFeedbacks, setSceneFeedbacks] = useState<Record<number, string>>({});
  const [abortController, setAbortController] = useState<AbortController | null>(null);

  // [FIX] P0: Step 4, 5 버튼 스코프 버그 수정을 위한 컴포넌트 최상위 호이스팅
  const script = finalAssets?.script || [];
  const totalScenes = script.length || 0;
  const completedImages = script.filter((s: any) => s.image_url).length;
  const completedVideos = script.filter((s: any) => s.video_url || s.use_image_only).length;
  const allVideosReady = completedVideos === totalScenes && totalScenes > 0;


  // [NEW] 렌더링 큐 상태 폴링
  const [renderQueueCount, setRenderQueueCount] = useState(0);

  useEffect(() => {
    const fetchRenderStatus = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/status/render`);
        if (res.ok) {
          const data = await res.json();
          setRenderQueueCount(data.active_renders || 0);
        }
      } catch (err) {
        console.error("Render status poll failed", err);
      }
    };
    
    if (mounted) {
      fetchRenderStatus();
      const interval = setInterval(fetchRenderStatus, 5000);
      return () => clearInterval(interval);
    }
  }, [mounted]);

  const getTrafficLight = () => {
    if (renderQueueCount === 0) return { color: "bg-green-500", text: "원활" };
    if (renderQueueCount === 1) return { color: "bg-orange-500", text: "보통" };
    return { color: "bg-red-500", text: "포화 대기" };
  };
  const trafficLight = getTrafficLight();

  const handleCancelRender = () => {
    if (abortController) {
      abortController.abort();
      setAbortController(null);
      setRenderStatus(false, 0);
      setErrorMessage("사용자에 의해 렌더링이 취소되었습니다.");
    }
  };

  const allImagesReady = !!(finalAssets?.script && finalAssets.script.length > 0 && finalAssets.script.every((s: any) => 
    ((s.image_url && s.image_url.trim() !== "") || 
     (s.user_video_id && s.user_video_id.trim() !== "") || 
     (s.video_url && s.video_url.trim() !== "")) &&
    s.status !== 'rendering' && 
    s.status !== 'error'
  ));

  useEffect(() => {
    setMounted(true);
    setErrorMessage(null);
    // 새로고침 시 렌더링 진행 상태 깔끔하게 초기화
    useWorkflowStore.getState().setRenderStatus(false, 0);
  }, [setErrorMessage]);

  if (!mounted) return null; // Prevent Hydration Mismatch

  const addHILItem = (type: 'pain_points' | 'strengths') => {
    const val = type === 'pain_points' ? tempInput.pain : tempInput.strength;
    if (!val.trim()) return;
    setManualAdditions(prev => ({ ...prev, [type]: [...prev[type], val.trim()] }));
    setTempInput({ [type === 'pain_points' ? 'pain' : 'strength']: '' });
  };

  const removeHILItem = (type: 'pain_points' | 'strengths', index: number) => {
    setManualAdditions(prev => ({ ...prev, [type]: prev[type].filter((_, i) => i !== index) }));
  };

  const handleImageInput = async (e: any) => {
    e.preventDefault();
    let files = [] as File[];
    if (e.clipboardData) files = Array.from(e.clipboardData.files);
    else if (e.dataTransfer) files = Array.from(e.dataTransfer.files);
    
    const validFiles = files.filter(file => {
      if (!file.type.startsWith('image/')) return false;
      if (file.size > 10 * 1024 * 1024) {
        alert("10MB 이하의 이미지만 업로드 가능합니다.");
        return false;
      }
      if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
        alert("JPG, PNG, WEBP 파일만 업로드 가능합니다.");
        return false;
      }
      return true;
    });

    if (validFiles.length > 0) {
      setIsUploading(true);
      for (const file of validFiles) {
        const promise = new Promise<void>((resolve) => {
          const reader = new FileReader();
          reader.onload = async (event) => {
            const rawBase64 = event.target?.result as string;
            const compressed = await compressImage(rawBase64);
            setProductData(prev => ({ ...prev, images: [...prev.images, compressed].slice(-20) }));
            resolve();
          };
          reader.readAsDataURL(file);
        });
        await promise;
      }
      setIsUploading(false);
    }
  };

  const handleLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
      alert("PNG, JPG, JPEG, WEBP 파일만 업로드 가능합니다.");
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      alert("파일 크기는 2MB 이하여야 합니다.");
      return;
    }
    const reader = new FileReader();
    reader.onload = (ev) => {
      setWatermarkSettings({ watermarkLogo: ev.target?.result as string });
    };
    reader.readAsDataURL(file);
  };

  const handleScrape = async () => {
    // Apify scraper disabled per user instructions
    setErrorMessage("현재 스크래핑 기능은 점검 중입니다. 수동 입력을 이용해 주세요.");
  };

  const handleAnalyze = async () => {
    const store = useWorkflowStore.getState();
    if (process.env.NODE_ENV === 'production') {
      const userEmail = store.user?.email || '';
      const isMock = userEmail.endsWith('@example.com') || 
                     userEmail.endsWith('@mock.com') || 
                     userEmail.includes('mock') || 
                     userEmail.includes('test');
      if (isMock) {
        setErrorMessage("프로덕션 환경에서는 Mock/테스트 계정으로 서비스를 이용할 수 없습니다.");
        return;
      }
    }

    setLoading(true, '상품 분석 중입니다');
    setErrorMessage(null);

    setAnalysis(null);
    setFinalAssets(null);

    try {
      const projRes = await api.post('/projects', {
        product_name: productData.name,
        user_id: store.userId
      });
      if (projRes && projRes.project_id) {
        setProjectId(projRes.project_id);
      }

      // 1. Generate Plan (Claude) - Only get product analysis without generating images
      const planRes = await api.post('/generate-plan', {
        ...productData,
        target_audience: productData.targetAudience,
        video_length: productData.duration,
        selected_pattern: "", // Do not send pattern yet
        mode: inputMode || 'auto',
        target_language: productData.targetLanguage,
        manual_additions: inputMode === 'manual' ? manualAdditions : undefined
      });

      if (!planRes || !planRes.product_analysis) {
        throw new Error("Claude 분석 데이터가 유효하지 않습니다.");
      }

      setAnalysis(planRes.product_analysis);
      setRecommendedPatterns(planRes.recommended_patterns || null);
      if (planRes.recommended_patterns && planRes.recommended_patterns.length > 0) {
        setSelectedType(planRes.recommended_patterns[0].pattern_name);
      }
      setStep(2); // Analysis view (Pattern Choice)

    } catch (e: any) {
      console.error('Pipeline Error:', e);
      setErrorMessage(`기획/분석 오류: ${e.message}`);
    }
    finally {
      setLoading(false);
    }
  };

  const handleGenerateAssets = async (type: string) => {
    setSelectedType(type);
    setLoading(true, '선택한 패턴으로 스크립트 작성 중입니다...');
    setErrorMessage(null);

    try {
      // 1. Generate Script with selected pattern
      const planRes = await api.post('/generate-plan', {
        ...productData,
        target_audience: productData.targetAudience,
        video_length: productData.duration,
        selected_pattern: type,
        mode: inputMode || 'auto',
        target_language: productData.targetLanguage,
        manual_additions: inputMode === 'manual' ? manualAdditions : undefined
      });

      if (!planRes || !planRes.scenes) {
        throw new Error("시나리오 데이터가 유효하지 않습니다.");
      }

      const initialScenes = (planRes.scenes || []).map((s: any) => ({
        ...s,
        image_url: null,
        image_prompt: s.image_prompt,
        image_source: null,
        status: 'waiting'
      }));

      setFinalAssets({
        ...planRes,
        script: initialScenes
      });
      setStep(3); // 상태 업데이트 완료 후 부드럽게 전환 (프로세스는 여기서 정지)

    } catch (e: any) {
      console.error('Asset Generation Error:', e);
      setErrorMessage(`시나리오 생성 오류: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateImages = async () => {
    if (!finalAssets || !finalAssets.script) return;
    setLoading(true, '스크립트에 맞는 AI 이미지 생성 중...');
    setErrorMessage(null);

    const script = [...finalAssets.script];
    
    try {
      const promises = script.map(async (scene: any, index: number) => {
        // 이미 이미지가 있거나(수동 등록 포함) 스킵 조건에 맞는 경우 (토큰 방어 및 오버라이트 방지)
        if (scene.image_url || scene.image_source === 'manual') {
          console.log(`[SKIP] Scene ${index+1} already has an image or is marked as manual upload.`);
          return;
        }

        // 상태를 'rendering' (생성 중)으로 갱신
        setFinalAssets((prev: any) => {
          if (!prev || !prev.script) return prev;
          const ns = [...prev.script];
          ns[index] = { ...ns[index], status: 'rendering', error: null, isRegenerating: false };
          return { ...prev, script: ns };
        });

        try {
          const res = await api.post('/generate-images', {
            product_name: productData.name,
            scenes: [scene],
            aspect_ratio: aspectRatio,
            model: imageEngine || "gpt-image-2",
            n: 1,
            size: "1024x1536",
            quality: "medium"
          });

          const item = res?.data?.[0];
          const extractedUrl = item?.url || (item?.b64_json ? `data:image/png;base64,${item.b64_json}` : null);

          if (extractedUrl) {
            setFinalAssets((prev: any) => {
              if (!prev || !prev.script) return prev;
              const newScript = [...prev.script];
              if (newScript[index]) {
                newScript[index] = {
                  ...newScript[index],
                  image_url: extractedUrl,
                  image_source: 'ai',
                  status: 'ready',
                  error: null
                };
              }
              return { ...prev, script: newScript };
            });
          } else {
            throw new Error("이미지 URL을 추출할 수 없습니다.");
          }
        } catch (error: any) {
          let displayError = error.message;
          if (error.message.includes('401') || error.message.includes('403') || error.message.includes('Tier') || error.message.includes('model_not_found') || error.message.includes('not exist')) {
            displayError = `${error.message}`; // 에러 마스킹 해제 (실제 에러 원문 노출)
          }

          setFinalAssets((prev: any) => {
            if (!prev || !prev.script) return prev;
            const newScript = [...prev.script];
            if (newScript[index]) {
              newScript[index] = { 
                ...newScript[index], 
                status: 'error', 
                error: displayError, 
                badge: '[❌ 생성 실패]' 
              };
            }
            return { ...prev, script: newScript };
          });
        }
      });

      await Promise.all(promises);
    } catch (e: any) {
      setErrorMessage(`이미지 일괄 생성 실패: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const updateSceneScript = (index: number, field: string, value: any) => {
    setFinalAssets((prev: any) => {
      if (!prev || !prev.script) return prev;
      const newScript = [...prev.script];
      newScript[index] = { 
        ...newScript[index], 
        [field]: value,
        video_url: field === 'dialogue' ? null : newScript[index].video_url 
      };
      return { ...prev, script: newScript };
    });
  };

  const handleFallbackToImage = (index: number) => {
    setFinalAssets((prev: any) => {
      if (!prev || !prev.script) return prev;
      const newScript = [...prev.script];
      newScript[index] = {
        ...newScript[index],
        use_image_only: true,
        status: 'fallback',
        error: null,
        video_url: null
      };
      return { ...prev, script: newScript };
    });
    setErrorMessage(null);
  };

  const handleVideoEngineChange = (engine: 'grok' | 'veo_lite' | 'veo_fast') => {
    setVideoEngine(engine);
    setErrorMessage(null);
    if (finalAssets?.script) {
      const resetScript = finalAssets.script.map((scene: any) => {
        if (scene.status === 'error') {
          return { ...scene, status: 'waiting', error: null };
        }
        return scene;
      });
      setFinalAssets({ ...finalAssets, script: resetScript });
    }
  };

  const handleRegenerateScene = async (index: number, feedback: string = "") => {
    if (!finalAssets?.script) return;
    const scene = finalAssets.script[index];

    // 즉시 해당 씬 번호의 isRegenerating 상태를 true로 설정 및 video_url 캐시 제거
    setFinalAssets((prev: any) => {
      if (!prev || !prev.script) return prev;
      const newScript = [...prev.script];
      newScript[index] = { ...newScript[index], isRegenerating: true, video_url: null };
      return { ...prev, script: newScript };
    });

    setLoading(true, '이미지 생성 중입니다');
    setErrorMessage(null);
    try {
      let extractedUrl = null;
      let newPrompt = scene.image_prompt;

      const actualFeedback = feedback || "수정된 대사(dialogue)와 지문(visual_description)을 바탕으로 기존 프롬프트를 무시하고 새로운 프롬프트로 완벽히 재작성해주세요.";

      const refineRes = await api.post('/refine-prompt', {
        product_name: productData.name,
        current_scene: scene, // 최신 상태의 scene 데이터 (수정된 대사 포함)
        user_feedback: actualFeedback,
        aspect_ratio: aspectRatio,
        model: imageEngine || "gpt-image-2"
      });

      extractedUrl = refineRes?.image_url;
      if (refineRes?.image_prompt) newPrompt = refineRes.image_prompt;

      if (!extractedUrl) throw new Error("이미지 데이터가 없습니다. 다시 시도해주세요.");

      setFinalAssets((prev: any) => {
        if (!prev || !prev.script) return prev;
        const newScript = [...prev.script];
        newScript[index] = { 
          ...newScript[index], 
          image_url: extractedUrl, 
          image_prompt: newPrompt, 
          status: 'ready', 
          error: null,
          isRegenerating: false 
        };
        return { ...prev, script: newScript };
      });
    } catch (e: any) {
      console.error('Regeneration Error:', e);
      
      // catch 블록에서 즉시 isRegenerating 상태를 false로 해제
      setFinalAssets((prev: any) => {
        if (!prev || !prev.script) return prev;
        const newScript = [...prev.script];
        newScript[index] = { ...newScript[index], isRegenerating: false };
        return { ...prev, script: newScript };
      });

      setErrorMessage(`이미지 재생성 오류: ${e.message}`);
    }
    finally { 
      setLoading(false); 
    }
  };

  const handleRegenerateMissingImages = async () => {
    if (!finalAssets?.script) return;
    setLoading(true, '이미지 생성 중입니다');
    setErrorMessage(null);
    try {
      const script = finalAssets.script;
      for (let i = 0; i < script.length; i++) {
        if (!script[i].image_url || script[i].status === 'error') {
          await handleRegenerateScene(i);
        }
      }
    } catch (e: any) {
      console.error('Image Regeneration Error:', e);
      setErrorMessage(`이미지 재생성 오류: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateClips = async (overrideScript?: any[]) => {
    if (!finalAssets?.script) return;
    const store = useWorkflowStore.getState();
    if (!store.user) {
      alert("계정 로그인이 필요합니다. 상단의 로그인 패널에서 이메일 인증을 진행해주세요.");
      return;
    }
    
    setLoading(true, '장면별 비디오 클립 생성 중입니다...');
    setErrorMessage(null);
    const cleanedScript = finalAssets.script.map((scene: any) => {
      if (scene.status === 'error') {
        return { ...scene, status: 'waiting', error: null };
      }
      return scene;
    });
    setFinalAssets({ ...finalAssets, script: cleanedScript });
    let timeoutId: any = null;
    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        'Connection': 'keep-alive',
      };
      if (store.kieKey) headers['X-BYOK-KIE'] = store.kieKey;

      let activeCsrfToken = store.csrfToken;
      if (!activeCsrfToken) {
        try {
          const res = await fetch(`${BACKEND_URL}/api/auth/csrf-token`, { method: 'GET', credentials: 'include' });
          if (res.ok) {
            const data = await res.json();
            if (data.csrf_token) {
              store.setCsrfToken(data.csrf_token);
              activeCsrfToken = data.csrf_token;
            }
          }
        } catch (err) {}
      }
      if (activeCsrfToken) headers['X-CSRF-Token'] = activeCsrfToken;

      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) headers['Authorization'] = `Bearer ${session.access_token}`;

      const requestBody = {
        product_name: productData.name,
        scenes: overrideScript || finalAssets.script,
        engine: videoEngine,
        aspect_ratio: aspectRatio,
        project_id: projectId || undefined
      };

      const controller = new AbortController();
      setAbortController(controller);
      timeoutId = setTimeout(() => { controller.abort(); setAbortController(null); }, 1800000); 

      const response = await fetch(`${BACKEND_URL}/api/generate-video-clips`, {
        method: 'POST',
        headers,
        body: JSON.stringify(requestBody),
        credentials: 'include',
        signal: controller.signal
      });

      if (!response.ok) {
        let errorDetail = `API Error (${response.status})`;
        try { const errData = await response.json(); if (errData.detail) errorDetail = errData.detail; } catch (e) {}
        throw new Error(errorDetail);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder("utf-8");

      if (reader) {
        let buffer = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() || "";
          for (const part of parts) {
            if (part.startsWith("data: ")) {
               try {
                const dataStr = part.replace("data: ", "");
                const data = JSON.parse(dataStr);
                
                if (data.error) throw new Error(data.error);
                if (data.message) setLoading(true, data.message);
                if (data.scene_update) {
                  setFinalAssets((prev: any) => {
                    if (!prev || !prev.script) return prev;
                    const updatedScript = [...prev.script];
                    const targetIndex = data.scene_update._index;
                    if (updatedScript[targetIndex]) {
                      updatedScript[targetIndex] = { ...updatedScript[targetIndex], ...data.scene_update };
                    }
                    return { ...prev, script: updatedScript };
                  });
                }
                if (data.clips_ready) {
                    setLoading(false);
                    // 클립 생성 완료 표시
                }
              } catch (e: any) {
                if (e.message !== "Unexpected end of JSON input" && !e.message.includes("Unexpected token")) throw e;
              }
            }
          }
        }
      }
    } catch (e: any) {
      console.error('Clip Generation Error:', e);
      let errorMsg = e.message;
      if (e.name === 'AbortError' || e.message?.includes('aborted')) errorMsg = '응답 시간 초과입니다.';
      setErrorMessage(`비디오 클립 생성 오류: ${errorMsg}`);
      const latestAssets = useWorkflowStore.getState().finalAssets;
      if (latestAssets && latestAssets.script) {
        const rolledBackScript = latestAssets.script.map((scene: any) => {
          if (!scene.video_url && !scene.use_image_only) {
            return { ...scene, status: 'error', error: e.message };
          }
          return scene;
        });
        setFinalAssets({ ...latestAssets, script: rolledBackScript });
      }
    } finally {
      if (timeoutId) clearTimeout(timeoutId);
      setLoading(false);
      setAbortController(null);
    }
  };

  const handleRenderFinal = async () => {
    if (!finalAssets?.script) return;
    const allVideosReady = finalAssets.script.every((s: any) => s.video_url || s.use_image_only);
    if (!allVideosReady) {
        alert("모든 비디오 클립이 준비되지 않았습니다. 실패한 씬을 재생성하거나 스틸컷으로 대체하세요.");
        return;
    }

    const store = useWorkflowStore.getState();
    setRenderStatus(true, 50);
    setLoading(true, '최종 영상 조립(렌더링) 직행 중...');
    setErrorMessage(null);
    let timeoutId: any = null;
    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        'Connection': 'keep-alive',
      };
      if (store.kieKey) headers['X-BYOK-KIE'] = store.kieKey;

      let activeCsrfToken = store.csrfToken;
      if (!activeCsrfToken) {
        try {
          const res = await fetch(`${BACKEND_URL}/api/auth/csrf-token`, { method: 'GET', credentials: 'include' });
          if (res.ok) {
            const data = await res.json();
            if (data.csrf_token) {
              store.setCsrfToken(data.csrf_token);
              activeCsrfToken = data.csrf_token;
            }
          }
        } catch (err) {}
      }
      if (activeCsrfToken) headers['X-CSRF-Token'] = activeCsrfToken;

      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) headers['Authorization'] = `Bearer ${session.access_token}`;

      const requestBody = {
        product_name: productData.name,
        scenes: finalAssets.script,
        voice_type: voiceType,
        aspect_ratio: aspectRatio,
        subtitle_position: subtitlePosition,
        render_duration: renderDuration,
        quality: "export",
        watermark_enabled: store.watermarkEnabled,
        watermark_logo: store.watermarkLogo,
        watermark_position: store.watermarkPosition,
        user_id: store.userId,
        upload_package: finalAssets?.upload_package,
        engine: videoEngine,
        rendering_mode: 'full',
        project_id: projectId || undefined
      };

      const controller = new AbortController();
      setAbortController(controller);
      timeoutId = setTimeout(() => { controller.abort(); setAbortController(null); }, 1800000); 

      const response = await fetch(`${BACKEND_URL}/api/render-final`, {
        method: 'POST',
        headers,
        body: JSON.stringify(requestBody),
        credentials: 'include',
        signal: controller.signal
      });

      if (!response.ok) {
        throw new Error(`API Error (${response.status})`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder("utf-8");
      let finalUrl = null;

      if (reader) {
        let buffer = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() || "";
          for (const part of parts) {
            if (part.startsWith("data: ")) {
               try {
                const dataStr = part.replace("data: ", "");
                const data = JSON.parse(dataStr);
                
                if (data.error) throw new Error(data.error);
                if (data.message) setLoading(true, data.message);
                if (data.output_url) {
                  finalUrl = `${BACKEND_URL}${data.output_url}`;
                }
              } catch (e: any) {
                if (e.message !== "Unexpected end of JSON input" && !e.message.includes("Unexpected token")) throw e;
              }
            }
          }
        }
      }

      if (finalUrl) {
        setRenderStatus(false, 100, finalUrl);
        store.setLastRenderTimestamp(Date.now());
      } else {
        throw new Error("결과 URL을 서버로부터 받지 못했습니다.");
      }
    } catch (e: any) {
      console.error('Final Render Error:', e);
      setErrorMessage(`렌더링 중단 안내: ${e.message}`);
      setRenderStatus(false, 0);
    } finally {
      if (timeoutId) clearTimeout(timeoutId);
      setLoading(false);
      setAbortController(null);
    }
  };

  const handleRenderVideoFromScratch = async () => {
    if (!finalAssets?.script) return;
    const cleanScript = finalAssets.script.map((s: any) => ({ ...s, video_url: undefined }));
    setFinalAssets({ ...finalAssets, script: cleanScript });
    handleGenerateClips(cleanScript);
  };

  const handleDownloadPackage = async (url: string, filename: string) => {
    try {
      setLoading(true, '패키지 압축 및 다운로드 중입니다...');
      
      const JSZip = (await import('jszip')).default;
      const zip = new JSZip();

      // 1. 영상 파일 다운로드
      const videoResponse = await fetch(url);
      if (!videoResponse.ok) throw new Error("Network response was not ok");
      const videoBlob = await videoResponse.blob();
      zip.file(`raptor_video.mp4`, videoBlob);

      // 2. 썸네일 이미지 추출 (첫 번째 씬 이미지)
      if (finalAssets?.script && finalAssets.script.length > 0) {
        const firstScene = finalAssets.script[0];
        if (firstScene.image_url) {
          try {
             if (firstScene.image_url.startsWith('data:image')) {
                const base64Data = firstScene.image_url.split(',')[1];
                zip.file('thumbnail.png', base64Data, {base64: true});
             } else {
                const proxyUrl = `${BACKEND_URL}/api/proxy-image?url=${encodeURIComponent(firstScene.image_url)}`;
                const imgResponse = await fetch(proxyUrl);
                if (imgResponse.ok) {
                  const imgBlob = await imgResponse.blob();
                  zip.file('thumbnail.png', imgBlob);
                }
             }
          } catch (e) {
             console.warn("Thumbnail extraction failed", e);
          }
        }
      }

      // 3. 각 씬별 원본 이미지, 프롬프트, 대사 파일 추가
      if (finalAssets?.script) {
        for (let idx = 0; idx < finalAssets.script.length; idx++) {
          const scene = finalAssets.script[idx];
          const sceneNum = scene.scene_number || (idx + 1);
          
          // 3-1) 이미지 저장 (CORS 우회를 위해 프록시 사용)
          if (scene.image_url) {
            try {
              if (scene.image_url.startsWith('data:image')) {
                const base64Data = scene.image_url.split(',')[1];
                zip.file(`scene_${sceneNum}_image.png`, base64Data, { base64: true });
              } else {
                const proxyUrl = `${BACKEND_URL}/api/proxy-image?url=${encodeURIComponent(scene.image_url)}`;
                const imgResponse = await fetch(proxyUrl);
                if (imgResponse.ok) {
                  const imgBlob = await imgResponse.blob();
                  zip.file(`scene_${sceneNum}_image.png`, imgBlob);
                }
              }
            } catch (imgErr) {
              console.warn(`Failed to pack image for scene ${sceneNum}`, imgErr);
            }
          }
          
          // 3-2) 프롬프트 저장
          const promptText = scene.image_prompt || "";
          zip.file(`scene_${sceneNum}_prompt.txt`, promptText);
          
          // 3-3) 대사 저장
          const dialogueText = scene.dialogue || scene.caption_ko || "";
          zip.file(`scene_${sceneNum}_dialogue.txt`, dialogueText);
        }
      }

      // 4. 업로드 패키지(텍스트) 생성
      const pkg = finalAssets?.upload_package;
      let content = `[RAPTOR SHOPPING SHORTS - UPLOAD PACKAGE]\n\n`;
      
      if (pkg) {
         if (pkg.titles && pkg.titles.length > 0) {
           content += `■ 추천 제목 (Titles)\n${pkg.titles.map((t: string) => `- ${t}`).join('\n')}\n\n`;
         }
         if (pkg.hashtags && pkg.hashtags.length > 0) {
           content += `■ 해시태그 (Hashtags)\n${pkg.hashtags.map((h: string) => `#${h}`).join(' ')}\n\n`;
         }
         for (const [key, value] of Object.entries(pkg)) {
            if (key !== 'titles' && key !== 'hashtags') {
               content += `■ ${key.toUpperCase()}\n${Array.isArray(value) ? value.join('\n') : value}\n\n`;
            }
         }
      } else {
         content += `업로드 패키지 정보가 없습니다.\n`;
      }
      zip.file('upload_package.txt', content);

      // 5. YYYYMMDD_HHMMSS 포맷의 파일명 생성
      const now = new Date();
      const yyyymmdd = now.getFullYear() + 
        String(now.getMonth() + 1).padStart(2, '0') + 
        String(now.getDate()).padStart(2, '0');
      const hhmmss = String(now.getHours()).padStart(2, '0') + 
        String(now.getMinutes()).padStart(2, '0') + 
        String(now.getSeconds()).padStart(2, '0');
      const timestamp = `${yyyymmdd}_${hhmmss}`;
      const zipFilename = `raptor_${productData.name || 'shorts'}_${timestamp}.zip`;

      // 6. ZIP 패키징 및 강제 다운로드 (CORS & 무결성 유지)
      const zipBlob = await zip.generateAsync({ type: 'blob' });
      const blobUrl = window.URL.createObjectURL(zipBlob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = zipFilename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      setTimeout(() => {
        window.URL.revokeObjectURL(blobUrl);
      }, 150);

    } catch (e: any) {
      console.error("Package download failed", e);
      setErrorMessage(`패키지 다운로드 실패: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-8 pb-20">
      {/* Raw Error Overlay */}
      {errorMessage && (
        <div className="bg-red-500/10 border border-red-500/50 rounded-2xl p-6 text-red-400 animate-in slide-in-from-top-4 duration-300">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-red-500/20 rounded-full flex items-center justify-center font-black">!</div>
              <div>
                <h4 className="font-bold uppercase tracking-widest text-xs">System Fault Detected</h4>
                <p className="text-sm font-mono">{errorMessage}</p>
              </div>
            </div>
            <button onClick={() => setErrorMessage(null)} className="p-2 hover:bg-white/10 rounded-full transition-all"><Trash2 className="w-4 h-4" /></button>
          </div>
        </div>
      )}

      {/* Video Preview Overlay */}
      {renderedVideoUrl && (
        <div className="fixed inset-0 bg-black/90 backdrop-blur-xl z-[200] flex flex-col items-center justify-center p-6 animate-in zoom-in duration-300">
          <div className="max-w-md w-full space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="text-xl font-bold text-white flex items-center gap-2"><Play className="text-green-400" /> Rendering Complete</h3>
              <button onClick={() => setRenderStatus(false, 0, null)} className="p-2 hover:bg-white/10 rounded-full text-white transition-all"><Trash2 className="w-5 h-5" /></button>
            </div>
            <div className={`relative rounded-2xl overflow-hidden border border-white/20 shadow-2xl bg-black ${aspectRatio === '9:16' ? 'aspect-[9/16] h-[60vh]' : 'aspect-video w-full'}`}>
              <video controls autoPlay preload="auto" className="w-full h-full object-contain">
                <source src={renderedVideoUrl || ''} type="video/mp4" />
              </video>
            </div>
            <div className="flex gap-4">
              <button onClick={() => handleDownloadPackage(renderedVideoUrl, `raptor_${productData.name}.mp4`)} className="flex-1 bg-green-600 hover:bg-green-500 text-white py-4 rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg shadow-green-900/20 transition-all">
                <Download className="w-5 h-5" /> 전체 패키지 일괄 다운로드 (.ZIP)
              </button>
              <button onClick={() => setRenderStatus(false, 0, null)} className="px-6 py-4 bg-white/10 hover:bg-white/20 text-white rounded-xl font-bold transition-all">Close</button>
            </div>
          </div>
        </div>
      )}



      {/* Step Indicator & Global Reset */}
      <div className="flex justify-between items-center bg-white/5 p-4 rounded-2xl border border-white/10 backdrop-blur-xl">
        <div className="flex gap-8">
          {[0, 1, 2, 3, 4].map((s) => (
            <div key={s} className={`flex items-center gap-2 ${step >= s ? 'text-purple-400' : 'text-gray-600'}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold border ${step >= s ? 'border-purple-500 bg-purple-500/10' : 'border-gray-700'}`}>{s}</div>
              <span className="text-[10px] font-bold uppercase tracking-widest">{s === 0 ? '시작 모드' : s === 1 ? '기본 설정' : s === 2 ? '분석 리포트' : s === 3 ? '에셋 확정' : '렌더링'}</span>
            </div>
          ))}
        </div>
        {step > 0 && (
          <div className="flex gap-3">
            <button
              onClick={() => setStep(0)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-500/10 text-blue-400 text-xs font-bold border border-blue-500/20 hover:bg-blue-500/20 transition-all"
            >
              <RotateCcw className="w-4 h-4" /> 데이터 유지 모드
            </button>
            <button
              onClick={() => { if (confirm('모든 데이터를 초기화하고 처음으로 돌아가시겠습니까?')) resetWorkflow(); }}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-red-500/10 text-red-400 text-xs font-bold border border-red-500/20 hover:bg-red-500/20 transition-all"
            >
              <Trash2 className="w-4 h-4" /> 데이터 리셋 모드
            </button>
          </div>
        )}
      </div>

      {/* Step 0: Mode Selection */}
      {step === 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 animate-in fade-in slide-in-from-bottom-8 duration-500">
          <button onClick={() => setErrorMessage('현재 개발 중입니다. 수동입력을 사용하세요.')} className="group relative bg-white/5 border border-white/10 rounded-[2.5rem] p-10 text-left hover:border-blue-500/50 hover:bg-blue-500/5 transition-all overflow-hidden">
            <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:opacity-20 transition-opacity"><LinkIcon className="w-32 h-32 text-blue-400" /></div>
            <div className="relative z-10 space-y-6">
              <div className="w-16 h-16 bg-blue-500/20 rounded-2xl flex items-center justify-center"><LinkIcon className="w-8 h-8 text-blue-400" /></div>
              <div>
                <h3 className="text-2xl font-bold text-white mb-2">상품 URL로 자동 분석</h3>
                <p className="text-gray-400 text-sm leading-relaxed">쿠팡, 네이버 쇼핑 등의 링크를 입력하면<br />AI가 상품명, 이미지, 상세 설명을 자동으로 추출합니다.</p>
              </div>
              <div className="flex items-center gap-2 text-blue-400 font-bold text-sm"><span>지금 시작하기</span><Plus className="w-4 h-4" /></div>
            </div>
          </button>
          <button onClick={() => { setInputMode('manual'); setStep(1); }} className="group relative bg-white/5 border border-white/10 rounded-[2.5rem] p-10 text-left hover:border-purple-500/50 hover:bg-purple-500/5 transition-all overflow-hidden">
            <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:opacity-20 transition-opacity"><ImageIcon className="w-32 h-32 text-purple-400" /></div>
            <div className="relative z-10 space-y-6">
              <div className="w-16 h-16 bg-purple-500/20 rounded-2xl flex items-center justify-center"><ImageIcon className="w-8 h-8 text-purple-400" /></div>
              <div>
                <h3 className="text-2xl font-bold text-white mb-2">직접 정보 입력하기</h3>
                <p className="text-gray-400 text-sm leading-relaxed">준비된 상품 이미지와 텍스트가 있다면<br />직접 업로드하여 초고속으로 기획안을 생성합니다.</p>
              </div>
              <div className="flex items-center gap-2 text-purple-400 font-bold text-sm"><span>수동 입력 시작</span><Plus className="w-4 h-4" /></div>
            </div>
          </button>
        </div>
      )}

      {/* Step 1: Input */}
      {step === 1 && (
        <div className="bg-white/5 border border-white/10 rounded-3xl p-8 shadow-2xl space-y-8 animate-in fade-in slide-in-from-bottom-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="flex items-center gap-4">
              <h2 className="text-2xl font-bold flex items-center gap-2 text-white whitespace-nowrap">
                {inputMode === 'auto' ? <LinkIcon className="text-blue-400 w-6 h-6" /> : <ImageIcon className="text-purple-400 w-6 h-6" />}
                {inputMode === 'auto' ? '1단계: 상품 URL 자동 분석' : '1단계: 직접 정보 입력'}
              </h2>
            </div>
            <div className="flex flex-wrap gap-4 items-center">
              <div className="flex bg-black/40 p-1 rounded-xl border border-white/10">
                <button onClick={() => setAspectRatio('9:16')} className={`flex items-center gap-2 px-3 py-2 rounded-lg text-[10px] font-bold transition-all ${aspectRatio === '9:16' ? 'bg-blue-600 text-white' : 'text-gray-500'}`}><Smartphone className="w-3 h-3" /> 9:16</button>
                <button onClick={() => setAspectRatio('1:1')} className={`flex items-center gap-2 px-3 py-2 rounded-lg text-[10px] font-bold transition-all ${aspectRatio === '1:1' ? 'bg-purple-600 text-white' : 'text-gray-500'}`}><Square className="w-3 h-3" /> 1:1</button>
                <button onClick={() => setAspectRatio('16:9')} className={`flex items-center gap-2 px-3 py-2 rounded-lg text-[10px] font-bold transition-all ${aspectRatio === '16:9' ? 'bg-pink-600 text-white' : 'text-gray-500'}`}><Monitor className="w-3 h-3" /> 16:9</button>
              </div>
              <div className="flex bg-black/40 p-1 rounded-xl border border-white/10">
                {[10, 15, 30].map((sec) => (
                  <button key={sec} onClick={() => setProductData({ duration: sec })} className={`px-3 py-2 rounded-lg text-[10px] font-bold transition-all ${productData.duration === sec ? 'bg-indigo-600 text-white' : 'text-gray-500'}`}>{sec}초</button>
                ))}
              </div>
              <select className="bg-black/60 border border-white/10 rounded-xl px-4 py-2 text-xs text-white outline-none focus:border-purple-500" value={productData.targetLanguage} onChange={(e) => setProductData({ targetLanguage: e.target.value })}>
                <option value="한국어">🇰🇷 한국어</option><option value="English">🇺🇸 English</option><option value="日本語">🇯🇵 日本語</option>
              </select>
              <select className="bg-black/60 border border-white/10 rounded-xl px-4 py-2 text-xs text-white outline-none focus:border-blue-500" value={voiceType} onChange={(e) => setVoiceType(e.target.value)}>
                <option value="여성-발랄한">👩 여성 - 발랄한</option><option value="여성-차분한">👩 여성 - 차분한</option><option value="남성-신뢰감">👨 남성 - 신뢰감</option><option value="남성-차분한">👨 남성 - 차분한</option>
              </select>
              <select className="bg-black/60 border border-white/10 rounded-xl px-4 py-2 text-xs text-white outline-none focus:border-pink-500" value={subtitlePosition} onChange={(e) => setSubtitlePosition(e.target.value)}>
                <option value="상">💬 자막: 상단</option><option value="중">💬 자막: 중앙</option><option value="하">💬 자막: 하단 (쇼츠 권장)</option>
              </select>
              <div className="flex bg-black/40 p-1 rounded-xl border border-white/10">
                <button onClick={() => setInputMode('auto')} className={`px-4 py-2 rounded-lg text-[10px] font-bold transition-all ${inputMode === 'auto' ? 'bg-blue-600 text-white' : 'text-gray-500'}`}>자동 추출</button>
                <button onClick={() => setInputMode('manual')} className={`px-4 py-2 rounded-lg text-[10px] font-bold transition-all ${inputMode === 'manual' ? 'bg-purple-600 text-white' : 'text-gray-500'}`}>수동 입력</button>
              </div>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="space-y-6">
              {inputMode === 'auto' && (
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">상품 URL</label>
                  <div className="relative">
                    <input placeholder="상품 링크를 붙여넣으세요" className="w-full bg-black/60 border border-white/10 p-4 rounded-xl text-white outline-none focus:border-blue-500 pr-32 transition-all" value={productData.url} onChange={(e) => setProductData({ url: e.target.value })} />
                    <button onClick={handleScrape} className="absolute right-2 top-2 bottom-2 bg-blue-600 text-white px-5 rounded-lg text-xs font-bold hover:bg-blue-500">스크래핑</button>
                  </div>
                </div>
              )}
              <div className="space-y-2">
                <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">상품 이미지 ({productData.images.length}/20)</label>
                <div onPaste={handleImageInput} onDrop={handleImageInput} onDragOver={(e) => e.preventDefault()} className="relative min-h-[140px] bg-black/40 border-2 border-dashed border-white/10 rounded-2xl p-4 flex flex-wrap gap-3 overflow-y-auto max-h-[300px]">
                  {isUploading && (
                     <div className="absolute inset-0 bg-black/60 flex items-center justify-center z-10 rounded-xl backdrop-blur-sm">
                       <Loader2 className="w-6 h-6 animate-spin text-white mr-2" />
                       <span className="text-white font-bold text-sm">[⏳ 업로드 중...]</span>
                     </div>
                  )}
                  {productData.images.length === 0 ? <div className="m-auto text-center"><Plus className="w-6 h-6 text-gray-600 mx-auto" /><p className="text-[10px] text-gray-600 font-medium uppercase mt-2">드래그하거나 붙여넣으세요</p></div> :
                    productData.images.map((img, i) => (
                      <div key={i} className="relative w-20 h-20 rounded-xl overflow-hidden border border-white/20 shadow-lg group">
                        <img src={img} className="w-full h-full object-cover" />
                        <button onClick={() => setProductData(prev => ({ ...prev, images: prev.images.filter((_, idx) => idx !== i) }))} className="absolute inset-0 bg-red-500/80 opacity-0 group-hover:opacity-100 flex items-center justify-center"><Trash2 className="w-5 h-5 text-white" /></button>
                      </div>
                    ))
                  }
                </div>
              </div>
            </div>
            <div className="space-y-6">
              <div className="space-y-2">
                <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">상품명</label>
                <input placeholder="예: 얼갈이 열무김치" className="w-full bg-black/40 border border-white/10 p-4 rounded-xl text-white outline-none focus:border-blue-500" value={productData.name} onChange={(e) => setProductData({ name: e.target.value })} />
              </div>
              <div className="space-y-2">
                <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">상세 설명</label>
                <textarea placeholder="상품의 특징, 원재료 등을 입력하세요." className="w-full h-40 bg-black/40 border border-white/10 p-4 rounded-xl text-white outline-none focus:border-blue-500 resize-none" value={productData.description} onChange={(e) => setProductData({ description: e.target.value })} />
              </div>
            </div>
          </div>

          {/* Claude Model Selection for Analysis and Scripting */}
          <div className="p-5 bg-purple-500/5 border border-purple-500/20 rounded-2xl space-y-2">
            <label className="text-[10px] font-bold text-purple-400 uppercase tracking-wider block">🧠 Claude 모델 선택 (분석 및 스크립트용)</label>
            <p className="text-[10px] text-gray-500 leading-normal">
              선택한 모델을 기반으로 상품 소구점 분석 및 숏폼 시나리오 초안이 맞춤형으로 카피라이팅됩니다.
            </p>
            <select 
              className="w-full bg-black/60 border border-white/15 rounded-xl px-4 py-3.5 text-xs text-white outline-none focus:border-purple-500 cursor-pointer transition-all" 
              value={claudeModel || 'claude-sonnet-4-6'} 
              onChange={(e) => setEngineSettings({ claudeModel: e.target.value, textEngine: e.target.value })}
            >
              <option value="claude-sonnet-4-6">📝 Claude Sonnet 4.6 (신속한 정밀 분석 및 대사 도출)</option>
              <option value="claude-opus-4-7">🧠 Claude Opus 4.8 (창의적이고 고도화된 마케팅 문구)</option>
              <option value="claude-haiku-4-5">⚡ Claude Haiku 4.5 (가벼운 분석 및 즉각 피드백)</option>
            </select>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="space-y-2">
              <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">숏폼 목적</label>
              <select className="w-full bg-black/40 border border-white/10 p-4 rounded-xl text-white outline-none focus:border-blue-500" value={productData.purpose || '쇼핑 전환'} onChange={(e) => setProductData({ purpose: e.target.value })}>
                <option value="쇼핑 전환">쇼핑 전환</option>
                <option value="브랜딩">브랜딩</option>
                <option value="신상품 소개">신상품 소개</option>
                <option value="정보 전달">정보 전달</option>
                <option value="바이럴">바이럴</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">타깃층</label>
              <input placeholder="예: 20대 직장인 여성" className="w-full bg-black/40 border border-white/10 p-4 rounded-xl text-white outline-none focus:border-blue-500" value={productData.targetAudience || ''} onChange={(e) => setProductData({ targetAudience: e.target.value })} />
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">영상 톤</label>
              <select className="w-full bg-black/40 border border-white/10 p-4 rounded-xl text-white outline-none focus:border-blue-500" value={productData.tone || '리뷰형'} onChange={(e) => setProductData({ tone: e.target.value })}>
                <option value="자극적">자극적</option>
                <option value="감성적">감성적</option>
                <option value="신뢰형">신뢰형</option>
                <option value="리뷰형">리뷰형</option>
              </select>
            </div>
          </div>

          <div className="bg-black/30 border border-white/5 rounded-2xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-white uppercase tracking-wider">브랜드 로고 (워터마크)</label>
              <button 
                onClick={() => setWatermarkSettings({ watermarkEnabled: !watermarkEnabled })}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${watermarkEnabled ? 'bg-purple-500' : 'bg-gray-700'}`}
              >
                <span className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${watermarkEnabled ? 'translate-x-5' : 'translate-x-1'}`} />
              </button>
            </div>
            
            {watermarkEnabled && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
                <div className="flex gap-2">
                  <label className="flex-1 bg-black/40 border border-white/10 rounded-lg p-3 text-center text-xs cursor-pointer hover:bg-white/5 transition-all text-gray-300">
                    {watermarkLogo ? '로고 변경' : '로고 업로드 (최대 2MB PNG, JPG, JPEG, WEBP)'}
                    <input type="file" accept="image/png, image/jpeg, image/jpg, image/webp" className="hidden" onChange={handleLogoUpload} />
                  </label>
                  {watermarkLogo && (
                    <button onClick={() => setWatermarkSettings({ watermarkLogo: null })} className="px-4 bg-red-500/20 text-red-400 rounded-lg text-xs hover:bg-red-500/30">삭제</button>
                  )}
                </div>
                {watermarkLogo && (
                  <div className="flex justify-center p-2 bg-black/50 rounded-lg">
                    <img src={watermarkLogo} alt="Logo" className="max-h-12 object-contain" />
                  </div>
                )}
                <select 
                  value={watermarkPosition}
                  onChange={(e) => setWatermarkSettings({ watermarkPosition: e.target.value as any })}
                  className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-3 text-xs text-white focus:outline-none focus:ring-1 focus:ring-purple-500/50"
                >
                  <option value="top-right">위치: 우측 상단</option>
                  <option value="bottom-right">위치: 우측 하단 (자막 위)</option>
                </select>
              </div>
            )}
          </div>

          <button onClick={handleAnalyze} disabled={!productData.name || loading} className="w-full h-16 bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 rounded-2xl font-bold text-lg text-white shadow-xl flex items-center justify-center gap-2 hover:scale-[1.01] transition-all disabled:opacity-50">
            {loading ? <><Loader2 className="w-5 h-5 animate-spin" /> {statusMessage}</> : '[상품 분석 및 숏폼 패턴 추천]'}
          </button>
        </div>
      )}

      {/* Step 2: Analysis */}
      {step === 2 && analysis && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 animate-in fade-in slide-in-from-bottom-4">
          <div className="lg:col-span-2 bg-white/5 border border-white/10 rounded-3xl p-8 space-y-8 shadow-2xl backdrop-blur-xl">
            <h3 className="text-xl font-bold text-purple-400">AI Global 분석 리포트</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-4">
                <div className="p-5 bg-red-500/5 rounded-2xl border border-red-500/20">
                  <p className="text-[10px] font-bold text-red-400 mb-3 tracking-widest uppercase">Pain Points</p>
                  <ul className="text-xs text-gray-300 space-y-2">
                    {/* Updated mapping with robust array check */}
                    {analysis?.pain_point ? (
                      Array.isArray(analysis.pain_point)
                        ? analysis.pain_point.map((p: any, i: number) => <li key={`ai-${i}`}>• {p}</li>)
                        : <li key="ai-0">• {analysis.pain_point}</li>
                    ) : (
                      <li className="text-[10px] text-gray-600 italic">No pain points identified</li>
                    )}
                    {manualAdditions?.pain_points?.map((p, i) => (
                      <li key={`manual-${i}`} className="flex justify-between items-center bg-red-500/10 p-2 rounded-lg text-red-200"><span>+ {p}</span><button onClick={() => removeHILItem('pain_points', i)} className="text-red-500"><Trash2 className="w-3 h-3" /></button></li>
                    ))}
                  </ul>
                </div>
                <div className="flex gap-2"><input placeholder="페인 포인트 직접 추가..." className="flex-1 bg-black/40 border border-white/5 p-3 rounded-xl text-xs text-white outline-none focus:border-red-500/40" value={tempInput.pain} onChange={(e) => setTempInput({ pain: e.target.value })} onKeyDown={(e) => e.key === 'Enter' && addHILItem('pain_points')} /><button onClick={() => addHILItem('pain_points')} className="bg-red-600/20 text-red-400 p-3 rounded-xl border border-red-500/20"><Plus className="w-4 h-4" /></button></div>
              </div>
              <div className="space-y-4">
                <div className="p-5 bg-green-500/5 rounded-2xl border border-green-500/20">
                  <p className="text-[10px] font-bold text-green-400 mb-3 tracking-widest uppercase">Core Benefit</p>
                  <ul className="text-xs text-gray-300 space-y-2">
                    {/* Updated mapping to product_analysis.core_benefit */}
                    {analysis.core_benefit && <li key="ai-benefit">• {analysis.core_benefit}</li>}
                    {manualAdditions.strengths.map((s, i) => (
                      <li key={`manual-${i}`} className="flex justify-between items-center bg-green-500/10 p-2 rounded-lg text-green-200"><span>+ {s}</span><button onClick={() => removeHILItem('strengths', i)} className="text-green-500"><Trash2 className="w-3 h-3" /></button></li>
                    ))}
                  </ul>
                </div>
                <div className="flex gap-2"><input placeholder="강점 직접 추가..." className="flex-1 bg-black/40 border border-white/5 p-3 rounded-xl text-xs text-white outline-none focus:border-green-500/40" value={tempInput.strength} onChange={(e) => setTempInput({ strength: e.target.value })} onKeyDown={(e) => e.key === 'Enter' && addHILItem('strengths')} /><button onClick={() => addHILItem('strengths')} className="bg-green-600/20 text-green-400 p-3 rounded-xl border border-green-500/20"><Plus className="w-4 h-4" /></button></div>
              </div>
            </div>
          </div>
          <div className="bg-white/5 border border-white/10 rounded-3xl p-8 space-y-6 shadow-2xl backdrop-blur-xl">
            <h3 className="text-xl font-bold flex items-center gap-2 text-white"><Wand2 className="w-5 h-5 text-yellow-400" /> AI 추천 패턴 선택</h3>
            <p className="text-xs text-gray-400">AI가 상품 설명과 타깃층, 영상 톤을 분석하여 추천하는 상위 2가지 마케팅 패턴입니다.</p>
            <div className="space-y-4">
              {recommendedPatterns && recommendedPatterns.map((pat: any, index: number) => {
                const isSelected = selectedType === pat.pattern_name;
                const isPrimary = index === 0;

                let cardStyle = "";
                let badgeStyle = "";
                let textHighlightStyle = "";
                let indicatorStyle = "";

                if (isPrimary) {
                  // 추천 1: 보라색/메인 하이라이트
                  cardStyle = isSelected
                    ? 'bg-purple-600/20 border-purple-500 ring-2 ring-purple-500/20'
                    : 'bg-purple-950/10 border-purple-500/30 hover:border-purple-500/50 hover:bg-purple-950/20';
                  badgeStyle = 'bg-purple-500 text-white font-bold';
                  textHighlightStyle = isSelected ? 'text-purple-400' : 'text-purple-300';
                  indicatorStyle = 'bg-purple-500';
                } else {
                  // 추천 2: 회색/무채색 서브 톤
                  cardStyle = isSelected
                    ? 'bg-neutral-800/40 border-neutral-400 ring-2 ring-neutral-400/20'
                    : 'bg-neutral-900/40 border-neutral-800 hover:border-neutral-700 hover:bg-neutral-900/60';
                  badgeStyle = 'bg-neutral-600 text-neutral-300 font-bold';
                  textHighlightStyle = isSelected ? 'text-white' : 'text-neutral-400';
                  indicatorStyle = 'bg-neutral-400';
                }
                return (
                  <div
                    key={index}
                    onClick={() => setSelectedType(pat.pattern_name)}
                    className={`p-6 border rounded-2xl cursor-pointer text-left transition-all relative overflow-hidden group ${cardStyle}`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] px-2 py-0.5 rounded-full ${badgeStyle}`}>
                          추천 {index + 1}
                        </span>
                        <span className={`text-base font-black ${textHighlightStyle}`}>
                          {pat.pattern_name}
                        </span>
                      </div>
                      {isSelected && (
                        <div className={`w-4 h-4 rounded-full flex items-center justify-center ${indicatorStyle}`}>
                          <div className="w-2 h-2 bg-white rounded-full" />
                        </div>
                      )}
                    </div>
                    <p className="text-xs text-gray-300 mb-3 font-medium leading-relaxed">
                      💡 {pat.reason}
                    </p>
                    <div className="p-3 bg-black/60 rounded-xl border border-white/5">
                      <p className="text-[9px] font-bold text-gray-500 mb-1 uppercase tracking-wider">대사 샘플</p>
                      <p className="text-xs text-gray-400 italic">
                        "{pat.sample_dialogue}"
                      </p>
                    </div>
                    {isSelected && (
                      <div className={`absolute left-0 top-0 bottom-0 w-1.5 ${indicatorStyle}`} />
                    )}
                  </div>
                );
              })}


              <button
                onClick={() => handleGenerateAssets(selectedType)}
                disabled={!selectedType || loading}
                className="w-full mt-6 py-4 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-2xl font-black text-sm uppercase tracking-widest hover:scale-[1.01] hover:shadow-purple-500/10 hover:shadow-2xl transition-all active:scale-95 disabled:opacity-30 flex items-center justify-center gap-2"
              >
                {loading ? <><Loader2 className="w-5 h-5 animate-spin text-white" /> 스크립트 작성 중...</> : "[선택한 패턴으로 스크립트 작성]"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Step 3: Final Assets (기획안 편집) */}
      {step === 3 && finalAssets && (
        <>
          <div className="animate-in fade-in slide-in-from-bottom-4 space-y-8">
          {(() => {
            const canGoToStep4 = finalAssets?.script && finalAssets.script.length > 0;
            return (
              <>
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="space-y-1">
                    <h2 className="text-3xl font-black text-white whitespace-nowrap">3단계: 에셋(이미지/시나리오) 확정 및 매칭</h2>
                    <p className="text-xs text-gray-500 tracking-widest flex items-center gap-2"><Smartphone className="w-3 h-3" /> {aspectRatio} • {productData?.targetLanguage} Optimized</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                  </div>
                </div>

                {/* [NEW UI] [토큰 방어] 이미지 설정 분기 선택 카드 */}
                <div className="bg-neutral-900/90 border border-purple-500/30 rounded-3xl p-6 shadow-2xl relative overflow-hidden animate-in fade-in duration-500">
                  <div className="absolute top-0 right-0 w-64 h-64 bg-purple-500/5 rounded-full blur-3xl pointer-events-none" />
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative z-10">
                    <div className="space-y-2">
                      <span className="px-2.5 py-1 bg-yellow-500/20 border border-yellow-500/40 rounded-full text-yellow-400 text-[9px] font-black tracking-wider uppercase">
                        Hybrid Image Pipeline
                      </span>
                      <h3 className="text-lg font-black text-white flex items-center gap-2">
                        <Sparkles className="w-5 h-5 text-yellow-400" />
                        AI 이미지 일괄 생성
                      </h3>
                      <p className="text-xs text-gray-400 max-w-xl leading-relaxed">
                        각 씬에 직접 업로드한 이미지가 있거나 이미 생성된 이미지가 있는 경우 AI 요청은 자동으로 스킵됩니다. 이미지가 비어있는 씬에 대해서만 아래의 모델을 이용해 AI 이미지를 일괄 생성합니다.
                      </p>
                    </div>
                    
                    <div className="flex flex-col sm:flex-row gap-4 shrink-0 items-center">
                      <div className="flex flex-col gap-1.5 min-w-[16rem]">
                        <label className="text-[10px] font-black text-purple-400 uppercase tracking-widest">AI 이미지 생성 모델 선택</label>
                        <select 
                          className="w-full bg-black/60 border border-white/10 rounded-xl px-3 py-2.5 text-xs text-white focus:outline-none focus:border-purple-500 cursor-pointer" 
                          value={imageEngine || 'gpt-image-2'} 
                          onChange={(e) => setEngineSettings({ imageEngine: e.target.value })}
                        >
                          <option value="gpt-image-2">📝 GPT-Image-2 (DALL-E 3)</option>
                          <option value="nano-banana-2">⚡ Nano Banana 2</option>
                          <option value="grok">🧠 Grok-Imagine</option>
                        </select>
                        <button 
                          onClick={handleGenerateImages}
                          disabled={allImagesReady || loading}
                          className={`w-full py-3 rounded-xl text-xs font-black uppercase tracking-wider transition-all shadow-md flex items-center justify-center gap-1 ${
                            allImagesReady 
                              ? 'bg-gray-800 text-gray-500 cursor-not-allowed pointer-events-none border border-white/5' 
                              : 'bg-purple-600 hover:bg-purple-500 text-white'
                          }`}
                        >
                          {loading ? (
                            <><Loader2 className="w-3.5 h-3.5 animate-spin" /> 생성 중...</>
                          ) : allImagesReady ? (
                            "AI 이미지 생성 완료"
                          ) : (
                            "AI 이미지 일괄 생성 시작"
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </>
            );
          })()}

          {/* [NEW UI] 대사 모아보기 (Dialogue Review - 간소화) */}
          <div className="bg-white/5 border border-white/10 rounded-3xl p-6 backdrop-blur-xl animate-in slide-in-from-top-4 duration-500">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-8 h-8 bg-blue-500/20 rounded-lg flex items-center justify-center text-blue-400 font-bold text-xs">HIL</div>
              <h3 className="text-sm font-black text-white uppercase tracking-wider">대사 모아보기 (Dialogue Review)</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {finalAssets.script?.map((scene: any, idx: number) => (
                <div key={`diag-${idx}`} className="flex flex-col gap-2 p-4 bg-black/40 border border-white/5 rounded-2xl">
                  <div className="text-[10px] font-black text-blue-500/50">SCENE #{scene.scene_number}</div>
                  <p className="text-xs font-bold text-white leading-relaxed">{scene.dialogue || scene.caption_ko}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 space-y-6">
              {finalAssets.script?.map((scene: any, i: number) => (
                <div key={i} className="bg-white/5 border border-white/10 rounded-3xl p-8 flex flex-col md:flex-row gap-8 hover:border-purple-500/40 transition-all group">
                  <div className={`relative w-full md:w-64 flex-shrink-0 bg-black rounded-2xl overflow-hidden border border-white/10 shadow-2xl ${aspectRatio === '9:16' ? 'aspect-[9/16]' : aspectRatio === '1:1' ? 'aspect-square' : 'aspect-video'}`}>
                    {scene.isRegenerating ? (
                      <div className="w-full h-full flex flex-col items-center justify-center space-y-4 bg-black/80 text-center p-6 animate-in fade-in">
                        <div className="relative">
                          <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
                          <Sparkles className="absolute -top-2 -right-2 w-4 h-4 text-yellow-400 animate-pulse" />
                        </div>
                        <div className="text-center">
                          <p className="text-[10px] font-black text-purple-400 uppercase tracking-wider">Regenerating</p>
                          <p className="text-xs text-gray-300 font-bold animate-pulse mt-1">이미지 재생성 중입니다...</p>
                        </div>
                      </div>
                    ) : scene.status === 'rendering' ? (
                      <div className="w-full h-full flex flex-col items-center justify-center space-y-4 bg-black/85 text-center p-6 animate-in fade-in">
                        <div className="relative">
                          <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
                          <Sparkles className="absolute -top-2 -right-2 w-4 h-4 text-yellow-400 animate-pulse" />
                        </div>
                        <div className="text-center">
                          <p className="text-[10px] font-black text-purple-400 uppercase tracking-wider">Rendering</p>
                          <p className="text-xs text-gray-300 font-bold animate-pulse mt-1">AI 이미지 생성 중입니다...</p>
                        </div>
                      </div>
                    ) : scene.status === 'error' ? (
                      <div className="w-full h-full flex flex-col items-center justify-center p-6 bg-red-950/20 text-center">
                        <AlertCircle className="w-8 h-8 text-red-500 mb-2" />
                        <p className="text-[10px] font-bold text-red-400 break-keep">{scene.error}</p>
                      </div>
                    ) : (scene.user_video_id || (scene.video_url && scene.image_source === 'manual')) ? (
                      <div className="w-full h-full relative group animate-in fade-in duration-500">
                        <video 
                          src={scene.video_url || `${BACKEND_URL}/outputs/${scene.user_video_id}.mp4`} 
                          muted 
                          loop 
                          autoPlay 
                          playsInline 
                          className="w-full h-full object-cover" 
                        />
                        <button 
                          onClick={() => {
                            updateSceneScript(i, 'user_video_id', null);
                            updateSceneScript(i, 'video_url', null);
                            updateSceneScript(i, 'image_source', null);
                            updateSceneScript(i, 'status', 'waiting');
                          }}
                          className="absolute top-3 right-3 px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white text-[10px] font-black rounded-xl opacity-0 group-hover:opacity-100 transition-opacity shadow-lg z-20"
                        >
                          ✕ 제거
                        </button>
                      </div>
                    ) : scene.image_url ? (
                      <div className="w-full h-full relative group">
                        <img src={scene.image_url} className="w-full h-full object-cover animate-in fade-in duration-1000" />
                        <button 
                          onClick={() => {
                            updateSceneScript(i, 'image_url', null);
                            updateSceneScript(i, 'image_source', null);
                            updateSceneScript(i, 'status', 'waiting');
                          }}
                          className="absolute top-3 right-3 px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white text-[10px] font-black rounded-xl opacity-0 group-hover:opacity-100 transition-opacity shadow-lg z-20"
                        >
                          ✕ 제거
                        </button>
                      </div>
                    ) : (
                      <div className="w-full h-full flex flex-col items-center justify-center p-6 bg-neutral-900/60 border border-dashed border-white/10 rounded-2xl text-center space-y-3 relative group">
                        <div className="p-3 bg-white/5 rounded-full border border-white/10 text-gray-500 group-hover:text-purple-400 transition-colors">
                          <Upload className="w-6 h-6" />
                        </div>
                        <div className="space-y-1">
                          <p className="text-xs font-bold text-white">미디어 미설정</p>
                          <p className="text-[9px] text-gray-500">실사 에셋을 직접 등록하거나 AI로 생성</p>
                        </div>
                        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/85 opacity-0 hover:opacity-100 transition-opacity z-10 rounded-2xl p-4">
                          <label className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-[10px] font-black uppercase tracking-wider flex items-center justify-center gap-1.5 shadow-lg cursor-pointer transition-all active:scale-95">
                            <Upload className="w-3.5 h-3.5" /> 📸 이미지 등록
                            <input 
                              type="file" 
                              accept="image/*" 
                              className="hidden" 
                              onChange={(e) => {
                                const file = e.target.files?.[0];
                                if (file) {
                                  const reader = new FileReader();
                                  reader.onload = (event) => {
                                    updateSceneScript(i, 'image_url', event.target?.result as string);
                                    updateSceneScript(i, 'image_source', 'manual');
                                    updateSceneScript(i, 'video_url', null);
                                    updateSceneScript(i, 'status', 'ready');
                                    updateSceneScript(i, 'error', null);
                                  };
                                  reader.readAsDataURL(file);
                                }
                              }}
                            />
                          </label>
                          <label className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-[10px] font-black uppercase tracking-wider flex items-center justify-center gap-1.5 shadow-lg cursor-pointer transition-all active:scale-95">
                            <Film className="w-3.5 h-3.5" /> 🎬 비디오 등록
                            <input 
                              type="file" 
                              accept="video/mp4,video/x-m4v,video/*"
                              className="hidden" 
                                onChange={async (e) => {
                                  const file = e.target.files?.[0];
                                  if (file) {
                                    // [FIX] MP4 업로드 JS 락 해제 (video/* 전면 허용)
                                    if (!file.type.startsWith('video/')) {
                                      alert("비디오 파일만 업로드 가능합니다.");
                                      return;
                                    }
                                    const formData = new FormData();
                                    formData.append('file', file);
                                    setLoading(true, "비디오 업로드 및 정밀 분석 중...");
                                    try {
                                    const res = await fetch(`${BACKEND_URL}/api/user-videos`, {
                                      method: 'POST',
                                      body: formData
                                    });
                                    if (res.ok) {
                                      const data = await res.json();
                                      updateSceneScript(i, 'user_video_id', data.id);
                                      updateSceneScript(i, 'video_url', `${BACKEND_URL}/outputs/${data.id}.mp4`);
                                      updateSceneScript(i, 'image_source', 'manual');
                                      updateSceneScript(i, 'status', 'ready');
                                      updateSceneScript(i, 'error', null);
                                    } else {
                                      alert("MP4 비디오 업로드 실패. 파일 타입을 확인하세요.");
                                    }
                                  } catch (err) {
                                    console.error(err);
                                  } finally {
                                    setLoading(false);
                                  }
                                }
                              }}
                            />
                          </label>
                        </div>
                      </div>
                    )}

                    {!(scene.isRegenerating || scene.status === 'rendering' || (!scene.image_url && !scene.user_video_id && scene.status !== 'error')) && (
                      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-2 opacity-0 group-hover:opacity-100 z-10 transition-opacity">
                        <label className="cursor-pointer bg-black/80 border border-white/20 px-3 py-2 rounded-xl text-[9px] font-bold text-white flex items-center gap-1.5 hover:bg-emerald-500/20 hover:border-emerald-500 transition-colors shadow-xl">
                          <Upload className="w-3.5 h-3.5 text-emerald-400" />
                          이미지 변경
                          <input 
                            type="file" 
                            accept="image/*" 
                            className="hidden" 
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              if (file) {
                                const reader = new FileReader();
                                reader.onload = (event) => {
                                  updateSceneScript(i, 'image_url', event.target?.result as string);
                                  updateSceneScript(i, 'image_source', 'manual');
                                  updateSceneScript(i, 'user_video_id', null);
                                  updateSceneScript(i, 'video_url', null);
                                  updateSceneScript(i, 'status', 'ready');
                                  updateSceneScript(i, 'error', null);
                                };
                                reader.readAsDataURL(file);
                              }
                            }}
                          />
                        </label>
                        <label className="cursor-pointer bg-black/80 border border-white/20 px-3 py-2 rounded-xl text-[9px] font-bold text-white flex items-center gap-1.5 hover:bg-blue-500/20 hover:border-blue-500 transition-colors shadow-xl">
                          <Film className="w-3.5 h-3.5 text-blue-400" />
                          비디오 변경
                          <input 
                            type="file" 
                            accept="video/mp4,video/x-m4v,video/*"
                            className="hidden" 
                            onChange={async (e) => {
                              const file = e.target.files?.[0];
                              if (file) {
                                // [FIX] MP4 업로드 JS 락 해제 (video/* 전면 허용)
                                if (!file.type.startsWith('video/')) {
                                  alert("비디오 파일만 업로드 가능합니다.");
                                  return;
                                }
                                const formData = new FormData();
                                formData.append('file', file);
                                setLoading(true, "비디오 업로드 및 정밀 분석 중...");
                                try {
                                  const res = await fetch(`${BACKEND_URL}/api/user-videos`, {
                                    method: 'POST',
                                    body: formData
                                  });
                                  if (res.ok) {
                                    const data = await res.json();
                                    updateSceneScript(i, 'user_video_id', data.id);
                                    updateSceneScript(i, 'video_url', `${BACKEND_URL}/outputs/${data.id}.mp4`);
                                    updateSceneScript(i, 'image_source', 'manual');
                                    updateSceneScript(i, 'image_url', null);
                                    updateSceneScript(i, 'status', 'ready');
                                    updateSceneScript(i, 'error', null);
                                  } else {
                                    alert("비디오 파일 업로드 실패");
                                  }
                                } catch (err) {
                                  console.error(err);
                                } finally {
                                  setLoading(false);
                                }
                              }
                            }}
                          />
                        </label>
                      </div>
                    )}
                    <div className="absolute top-4 left-4 bg-black/60 px-3 py-1 rounded-lg text-[10px] font-black text-white">SCENE {scene.scene_number}</div>
                  </div>
                  <div className="flex-1 space-y-6">
                    <div className="space-y-4">
                      <div className="space-y-1">
                        <p className="text-[10px] font-bold text-blue-400 flex items-center gap-1"><Languages className="w-3 h-3" /> VOICE OVER</p>
                        <textarea 
                          className="w-full bg-black/40 border border-white/20 p-3 rounded-xl text-lg font-bold text-white outline-none focus:border-blue-500 shadow-inner resize-none min-h-[60px]"
                          value={scene.dialogue || scene.caption_ko || ''}
                          onChange={(e) => updateSceneScript(i, 'dialogue', e.target.value)}
                        />
                        <p className="text-xs text-gray-500 italic">"{scene.caption_en || 'English version'}"</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-[10px] font-bold text-green-400 flex items-center gap-1">VISUAL DESCRIPTION</p>
                        <div className="w-full bg-black/20 border border-white/5 p-3 rounded-xl text-sm text-gray-400 font-medium min-h-[60px] whitespace-pre-wrap select-text">
                          {scene.visual_description || scene.visual_ko || '설명이 없습니다.'}
                        </div>
                      </div>
                    </div>
                    <div className="pt-4 border-t border-white/5 space-y-3">
                      {/* [이사이식] 씬별 상태 배지 및 스틸컷 토글 */}
                      <div className="flex flex-wrap items-center justify-between gap-3 bg-black/35 p-3.5 rounded-2xl border border-white/10 shadow-inner">
                        <div className="flex items-center gap-2">
                          <span className="text-[9px] font-bold text-gray-400 uppercase tracking-widest">생성 방식 설정:</span>
                          {scene.use_image_only && scene.status === 'success' ? (
                            <span className="px-2 py-0.5 rounded bg-orange-500/20 text-orange-400 text-[9px] font-bold border border-orange-500/30">
                              ✅ 스틸컷 연출 준비완료
                            </span>
                          ) : scene.status === 'fallback' ? (
                            <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-[9px] font-bold border border-red-500/30">
                              ❌ 비디오 생성 실패 (스틸컷 대체됨)
                            </span>
                          ) : scene.status === 'error' ? (
                            <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-[9px] font-bold border border-red-500/30">
                              {scene.error ? '❌ 오류 발생' : '❌ 대기/에러'}
                            </span>
                          ) : scene.status === 'success' ? (
                            <span className="px-2 py-0.5 rounded bg-green-500/20 text-green-400 text-[9px] font-bold border border-green-500/30">
                              🎬 비디오 클립 생성 완료
                            </span>
                          ) : scene.taskId && isRendering ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-purple-500/20 text-purple-400 text-[9px] font-bold border border-purple-500/30 animate-pulse">
                              <Loader2 className="w-2.5 h-2.5 animate-spin" /> KIE AI 비디오 생성중
                            </span>
                          ) : isRendering && !scene.use_image_only ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 text-[9px] font-bold border border-blue-500/30 animate-pulse">
                              <Loader2 className="w-2.5 h-2.5 animate-spin" /> 대기 중
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded bg-gray-500/20 text-gray-400 text-[9px] font-bold border border-white/5">
                              비디오 대기중
                            </span>
                          )}
                        </div>
                        <label className="flex items-center gap-2 cursor-pointer select-none">
                          <input 
                            type="checkbox" 
                            className="accent-purple-500 cursor-pointer"
                            checked={scene.use_image_only || false}
                            onChange={(e) => updateSceneScript(i, 'use_image_only', e.target.checked)}
                          />
                          <span className="text-[10px] text-gray-300 font-bold">🖼️ 스틸컷으로 렌더링 (비디오 생성 안 함)</span>
                        </label>
                      </div>

                      <p className="text-[10px] font-bold text-yellow-400 flex items-center gap-1 uppercase tracking-widest"><Sparkles className="w-3 h-3" /> 한글 수정 요청 (이미지 재생성)</p>
                      <div className="flex gap-2">
                        <input
                          id={`feedback-${i}`}
                          className="flex-1 bg-black/60 border border-white/20 p-3 rounded-xl text-xs text-white outline-none focus:border-purple-500 shadow-inner"
                          placeholder="예: 모델을 한국인 남성으로 바꿔주고 배경은 카페로 해줘"
                          value={sceneFeedbacks[i] || ''}
                          onChange={(e) => setSceneFeedbacks(prev => ({ ...prev, [i]: e.target.value }))}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              handleRegenerateScene(i, sceneFeedbacks[i] || '');
                            }
                          }}
                        />
                        <button
                          onClick={() => {
                            handleRegenerateScene(i, sceneFeedbacks[i] || '');
                          }}
                          className="bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded-xl text-[10px] font-bold transition-all shadow-lg"
                        >
                          재생성
                        </button>
                      </div>
                      <p className="text-[9px] text-gray-500 italic">* 입력 시 프롬프트를 보정하여 새로운 이미지를 생성합니다.</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="flex flex-col gap-6">
              <div className="bg-white/5 border border-white/10 rounded-3xl p-8 space-y-6 backdrop-blur-xl h-fit">
                <h3 className="text-xl font-bold text-white flex items-center gap-2"><CheckCircle className="w-5 h-5 text-green-400" /> Global Asset Pack</h3>
                <div className="space-y-6">
                  <div className="space-y-2">
                    <p className="text-[10px] font-bold text-yellow-400 uppercase tracking-widest">Strategy Hook</p>
                    <div className="text-xs font-bold bg-black/60 p-4 rounded-xl border border-yellow-500/20 text-white italic">
                      "{finalAssets?.strategy?.hook || 'Generating hook...'}"
                    </div>
                  </div>
                  <div className="space-y-2">
                    <p className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Global Titles</p>
                    <div className="space-y-2">
                      {finalAssets?.upload_package?.titles?.map((t: string, i: number) => (
                        <div key={i} className="text-[10px] bg-black/40 p-2 rounded-lg border border-white/5 text-gray-300">{t}</div>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-2">
                    <p className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Hashtags</p>
                    <div className="flex flex-wrap gap-2">
                      {finalAssets?.upload_package?.hashtags?.map((h: string) => (
                        <span key={h} className="text-[8px] bg-blue-500/10 text-blue-400 px-2 py-1 rounded-full border border-blue-500/20">#{h}</span>
                      ))}
                    </div>
                  </div>
                </div>
                 {finalAssets?.script && finalAssets.script.length > 0 && (
                  <button 
                    onClick={() => { if (allImagesReady) setStep(4); }} 
                    disabled={!allImagesReady}
                    className={`w-full py-4 rounded-2xl font-black text-xs uppercase tracking-widest flex items-center justify-center gap-2 transition-all mt-4 animate-in fade-in ${
                      allImagesReady 
                        ? 'bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white hover:scale-[1.02] shadow-xl active:scale-95 cursor-pointer' 
                        : 'bg-gray-800 text-gray-500 cursor-not-allowed border border-white/5 opacity-50 pointer-events-none'
                    }`}
                  >
                    <span>🎬 비디오 생성 단계로 이동 (Step 4)</span>
                  </button>
                )}
              </div>
            </div>
          </div>
          </div>
        </>
      )}

      {/* Step 4: Final Video Render (최종 렌더링 및 완성) */}
      {step === 4 && finalAssets && (
        <div className="animate-in fade-in slide-in-from-bottom-4 space-y-8">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-1">
              <h2 className="text-3xl font-black text-white whitespace-nowrap">4단계: 비디오 생성</h2>
              <p className="text-xs text-gray-500 tracking-widest flex items-center gap-2"><Smartphone className="w-3 h-3" /> {aspectRatio} • {productData?.targetLanguage} Optimized</p>
            </div>
          </div>

          {/* [NEW UI] 단계별 시각화 워크플로우 UI (Visual Tracker) */}
          <div className="bg-neutral-900/80 border border-white/10 rounded-3xl p-6 backdrop-blur-xl shadow-2xl">
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-white/10">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-purple-500/20 rounded-xl flex items-center justify-center text-purple-400 font-bold text-xs">VT</div>
                <div>
                  <h3 className="text-base font-black text-white uppercase tracking-wider">파이프라인 진행 트래커 (Visual Tracker)</h3>
                  <p className="text-xs text-gray-400">실시간 생성 상태 모니터링 및 스마트 재개(Resume) 시스템</p>
                </div>
              </div>
            </div>

            {(() => {
              const hasImageError = script.some((s: any) => s.status === 'error');

              const stage1Status = analysis ? 'success' : 'error';
              const stage2Status = totalScenes > 0 ? 'success' : 'error';
              let stage3Status = 'waiting';
              if (completedImages === totalScenes && totalScenes > 0) stage3Status = 'success';
              else if (hasImageError || errorMessage?.includes('이미지')) stage3Status = 'error';
              else if (completedImages > 0) stage3Status = 'active';

              let stage4Status = 'waiting';
              if (completedVideos === totalScenes && totalScenes > 0) stage4Status = 'success';
              else if (errorMessage) stage4Status = 'error';
              else if (isRendering && renderProgress < 50) stage4Status = 'active';
              else if (completedVideos > 0) stage4Status = 'active';

              let stage5Status = 'waiting';
              if (renderedVideoUrl) stage5Status = 'success';
              else if (renderProgress >= 50 && errorMessage) stage5Status = 'error';
              else if (isRendering && renderProgress >= 50) stage5Status = 'active';

              const stages = [
                { id: 1, name: '상품 분석', status: stage1Status, desc: 'AI 상품 기획 및 소구점 도출', action: handleAnalyze, actionLabel: '분석 재시도' },
                { id: 2, name: '시나리오 작성', status: stage2Status, desc: `총 ${totalScenes}개 씬 구성 완료`, action: handleAnalyze, actionLabel: '스크립트 재작성' },
                { id: 3, name: '이미지 생성', status: stage3Status, desc: `이미지 완료 (${completedImages}/${totalScenes})`, action: undefined, actionLabel: '' },
                { id: 4, name: '비디오 생성', status: stage4Status, desc: `비디오 클립 완료 (${completedVideos}/${totalScenes})`, action: undefined, actionLabel: '' },
                { id: 5, name: '최종 렌더링', status: stage5Status, desc: renderedVideoUrl ? '최종 MP4 완성' : isRendering ? `렌더링 진행 중 (${renderProgress}%)` : '대기 중', action: undefined, actionLabel: '' },
              ];

              return (
                <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                  {stages.map((stg) => {
                    const isSuccess = stg.status === 'success';
                    const isError = stg.status === 'error';
                    const isActive = stg.status === 'active';

                    let bgClass = 'bg-black/40 border-white/10';
                    let badgeClass = 'bg-gray-500/20 text-gray-400 border-gray-500/30';
                    let badgeText = '대기중';

                    if (isSuccess) {
                      bgClass = 'bg-green-500/10 border-green-500/40 shadow-[0_0_20px_rgba(34,197,94,0.1)]';
                      badgeClass = 'bg-green-500/20 text-green-400 border-green-500/40';
                      badgeText = '완료됨';
                    } else if (isError) {
                      bgClass = 'bg-red-500/10 border-red-500/50 shadow-[0_0_20px_rgba(239,68,68,0.15)] animate-pulse';
                      badgeClass = 'bg-red-500/20 text-red-400 border-red-500/40';
                      badgeText = '오류/중단';
                    } else if (isActive) {
                      bgClass = 'bg-purple-500/10 border-purple-500/50 shadow-[0_0_20px_rgba(168,85,247,0.15)]';
                      badgeClass = 'bg-purple-500/20 text-purple-400 border-purple-500/40 animate-pulse';
                      badgeText = '진행중';
                    }

                    return (
                      <div key={`vt-stage-${stg.id}`} className={`border rounded-2xl p-5 flex flex-col justify-between transition-all duration-300 ${bgClass}`}>
                        <div>
                          <div className="flex justify-between items-center mb-3">
                            <span className={`text-[10px] font-black px-2.5 py-0.5 rounded-full border tracking-wider uppercase ${badgeClass}`}>{badgeText}</span>
                          </div>
                          <h4 className={`text-sm font-black mb-1 tracking-tight ${isSuccess ? 'text-white' : isError ? 'text-red-200' : isActive ? 'text-purple-200 font-bold' : 'text-gray-400'}`}>{stg.name}</h4>
                          <p className="text-xs text-gray-400 leading-relaxed mb-4">{stg.desc}</p>
                        </div>
                        {isError && stg.action && (
                          <button
                            onClick={() => stg.action()}
                            className="w-full mt-2 bg-red-600/20 hover:bg-red-600/30 border border-red-500/30 text-red-200 py-2 rounded-xl text-[10px] font-bold tracking-wider transition-all"
                          >
                            {stg.actionLabel}
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              );
            })()}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 space-y-6">
              <div className="bg-white/5 border border-white/10 rounded-3xl p-8 space-y-6 backdrop-blur-xl h-fit">
                <h3 className="text-xl font-bold text-white flex items-center gap-2"><CheckCircle className="w-5 h-5 text-green-400" /> Global Asset Pack</h3>
                <div className="space-y-6">
                  <div className="space-y-2">
                    <p className="text-[10px] font-bold text-yellow-400 uppercase tracking-widest">Strategy Hook</p>
                    <div className="text-xs font-bold bg-black/60 p-4 rounded-xl border border-yellow-500/20 text-white italic">
                      "{finalAssets?.strategy?.hook || 'Generating hook...'}"
                    </div>
                  </div>
                  <div className="space-y-2">
                    <p className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Global Titles</p>
                    <div className="space-y-2">
                      {finalAssets?.upload_package?.titles?.map((t: string, i: number) => (
                        <div key={i} className="text-[10px] bg-black/40 p-2 rounded-lg border border-white/5 text-gray-300">{t}</div>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-2">
                    <p className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Hashtags</p>
                    <div className="flex flex-wrap gap-2">
                      {finalAssets?.upload_package?.hashtags?.map((h: string) => (
                        <span key={h} className="text-[8px] bg-blue-500/10 text-blue-400 px-2 py-1 rounded-full border border-blue-500/20">#{h}</span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            <div className="flex flex-col gap-6">
              <div className="bg-white/5 border border-white/10 rounded-3xl p-6 space-y-4 backdrop-blur-xl">
                <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <Sparkles className="w-3.5 h-3.5 text-yellow-400" /> 비디오 생성 엔진 &amp; 렌더링 옵션
                </h4>
                <div className="grid grid-cols-1 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">엔진 선택</label>
                    <select
                      value={videoEngine}
                      onChange={(e) => handleVideoEngineChange(e.target.value as any)}
                      disabled={isRendering}
                      className="w-full bg-black/60 border border-white/20 p-2.5 rounded-xl text-xs font-bold text-white outline-none focus:border-emerald-500 shadow-inner disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <option value="grok">Grok (가성비 모드)</option>
                      <option value="veo_lite">Google Veo 3.1 Lite (안정 범용)</option>
                      <option value="veo_fast">Google Veo 3.1 Fast (고품질)</option>
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">성우 목소리</label>
                    <select
                      value={voiceType}
                      onChange={(e) => setVoiceType(e.target.value)}
                      className="w-full bg-black/60 border border-white/20 p-2.5 rounded-xl text-xs font-bold text-white outline-none focus:border-emerald-500 shadow-inner"
                    >
                      <option value="여성-발랄한">여성 - 발랄한 (Nova)</option>
                      <option value="여성-차분한">여성 - 차분한 (Shimmer)</option>
                      <option value="남성-신뢰감">남성 - 신뢰감 (Echo)</option>
                      <option value="남성-차분한">남성 - 차분한 (Onyx)</option>
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">영상 길이 선택</label>
                    <select
                      value={renderDuration}
                      onChange={(e) => setRenderDuration(e.target.value)}
                      className="w-full bg-black/60 border border-white/20 p-2.5 rounded-xl text-xs font-bold text-white outline-none focus:border-emerald-500 shadow-inner"
                    >
                      <option value="자막 맞춤 길이 (Dynamic Sync)">자막 맞춤 길이 (Dynamic Sync)</option>
                      <option value="15초">15초</option>
                      <option value="30초">30초</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="w-full space-y-4">
                {/* [FIX] 물리적 완전 분리: Step 4 (비디오 생성) 버튼은 아직 생성되지 않은 비디오가 있을 때만 렌더링 */}
                {completedImages === totalScenes && completedVideos < totalScenes && (
                  <button 
                    onClick={() => handleGenerateClips()} 
                    disabled={isRendering || loading} 
                    className="w-full bg-blue-600/20 border border-blue-500/30 text-blue-300 py-3 px-6 rounded-2xl font-bold text-xs uppercase tracking-widest flex items-center justify-center gap-2 hover:bg-blue-600/30 hover:border-blue-500/50 transition-all shadow-lg active:scale-[0.98] disabled:opacity-50"
                  >
                    {loading && !isRendering ? (
                      <><Loader2 className="w-4 h-4 animate-spin text-blue-300" /> <span>클립 생성 중...</span></>
                    ) : (
                      <><Film className="w-5 h-5" /> <span>비디오 클립 생성 시작 (Step 4)</span></>
                    )}
                  </button>
                )}

                {/* [FIX] 물리적 완전 분리: Step 5 (최종 렌더링) 버튼은 모든 비디오(스틸컷 포함) 생성이 완료되었을 때만 렌더링 */}
                {completedVideos === totalScenes && totalScenes > 0 && (
                  <button 
                    onClick={() => handleRenderFinal()} 
                    disabled={isRendering || loading || !(finalAssets?.script && finalAssets.script.every((s: any) => s.video_url || s.use_image_only))} 
                    className="w-full bg-emerald-600/20 border border-emerald-500/30 text-emerald-300 py-3 px-6 rounded-2xl font-bold text-xs uppercase tracking-widest flex items-center justify-center gap-2 hover:bg-emerald-600/30 hover:border-emerald-500/50 transition-all shadow-lg active:scale-[0.98] disabled:opacity-50"
                  >
                    {isRendering && renderProgress > 0 ? (
                      <><Loader2 className="w-4 h-4 animate-spin text-emerald-300" /> <span>최종 렌더링 진행 중 {renderProgress}%</span></>
                    ) : renderQueueCount >= 2 ? (
                      <><AlertCircle className="w-5 h-5 text-red-400" /> <span>서버 포화: 잠시 후 시도해주세요</span></>
                    ) : (
                      <><Upload className="w-5 h-5" /> <span>최종 렌더링 시작 (Step 5)</span></>
                    )}
                  </button>
                )}
              </div>
              
              <div className="flex flex-col md:flex-row justify-between items-center gap-4 bg-slate-800/50 p-4 rounded-xl border border-slate-700/50">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-slate-300">서버 상태:</span>
                  <div className="flex items-center gap-2 px-3 py-1 bg-slate-900/80 rounded-full border border-slate-700">
                    <div className={`w-3 h-3 rounded-full shadow-[0_0_8px_currentColor] ${trafficLight.color}`}></div>
                    <span className="text-sm font-bold text-slate-200">{trafficLight.text} ({renderQueueCount}명 진행중)</span>
                  </div>
                </div>
                {finalAssets?.script && (
                  <button 
                    onClick={async () => {
                      if (!projectId) {
                        alert("프로젝트 ID가 존재하지 않습니다.");
                        return;
                      }
                      const { data: { session } } = await supabase.auth.getSession();
                      if (!session?.access_token) {
                        alert("로그인이 필요합니다.");
                        return;
                      }
                      window.open(`${BACKEND_URL}/api/projects/${projectId}/download-assets?token=${session.access_token}`, '_blank');
                    }}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-bold text-white transition-colors"
                  >
                    <Download className="w-4 h-4" /> CapCut 폴백용 에셋 원본 ZIP 다운로드 (즉시)
                  </button>
                )}
              </div>

              {isRendering && (() => {
                const isKieActive = !!(finalAssets?.script && finalAssets.script.some((s: any) => s.taskId));
                return (
                  <div className="w-full mt-3 space-y-2">
                    <button 
                      onClick={handleCancelRender}
                      className={`w-full py-3 px-6 rounded-2xl font-bold text-xs uppercase tracking-widest flex items-center justify-center gap-2 transition-all shadow-lg active:scale-[0.98] border ${
                        isKieActive 
                          ? 'bg-blue-600 hover:bg-blue-500 text-white border-blue-500' 
                          : 'bg-neutral-800 hover:bg-neutral-700 text-neutral-300 border-neutral-700'
                      }`}
                    >
                      <span>🛑 렌더링 취소</span>
                    </button>
                    <p className="text-[10px] text-center font-bold text-gray-400">
                      {isKieActive 
                        ? "현재 씬 생성 중 - 취소 시 대기 중인 다음 씬 비용 절약" 
                        : "취소 시 크레딧 미소모"
                      }
                    </p>
                  </div>
                );
              })()}
            </div>
          </div>

          {/* 장면별 비디오 생성 상태 모니터링 카드 리스트 */}
          <div className="bg-neutral-900/40 border border-white/5 rounded-3xl p-6 space-y-6">
            <h3 className="text-sm font-black text-white uppercase tracking-wider flex items-center gap-2">
              <ImageIcon className="w-4 h-4 text-emerald-400" /> 장면별 실시간 비디오 생성 모니터 (Scene Monitor)
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {finalAssets.script?.map((scene: any, i: number) => (
                <div key={`step4-scene-${i}`} className="bg-white/5 border border-white/10 rounded-3xl p-6 flex flex-col space-y-4 hover:border-emerald-500/40 transition-all">
                  <div className={`relative w-full aspect-[9/16] bg-black rounded-2xl overflow-hidden border border-white/10 shadow-2xl flex-shrink-0`}>
                    {scene.status === 'success' && scene.video_url ? (
                      <video src={scene.video_url} controls className="w-full h-full object-cover" />
                    ) : scene.use_image_only ? (
                      <div className="w-full h-full relative group">
                        {scene.image_url ? (
                          <img src={scene.image_url} className="w-full h-full object-cover opacity-80 transition-all group-hover:opacity-60" />
                        ) : (
                          <div className="w-full h-full bg-neutral-800 flex items-center justify-center text-xs text-gray-500">이미지 없음</div>
                        )}
                        <div className="absolute inset-0 bg-black/40 flex flex-col items-center justify-center gap-2">
                          <span className="px-3 py-1 bg-orange-500 text-white font-black text-[10px] rounded-lg tracking-wider uppercase">🖼️ 스틸컷 유지</span>
                          <button 
                            onClick={() => {
                              const newScript = [...finalAssets.script];
                              newScript[i].use_image_only = false;
                              setFinalAssets({...finalAssets, script: newScript});
                            }}
                            className="px-3 py-1 bg-red-600/90 hover:bg-red-500 text-white rounded-full text-[10px] font-bold shadow-lg transition-transform active:scale-95"
                          >
                            ✕ 스틸컷 모드 취소 (비디오 대기 상태로 복귀)
                          </button>
                        </div>
                      </div>
                    ) : scene.status === 'fallback' ? (
                      <div className="w-full h-full relative">
                        {scene.image_url ? (
                          <img src={scene.image_url} className="w-full h-full object-cover opacity-80" />
                        ) : (
                          <div className="w-full h-full bg-neutral-800 flex items-center justify-center text-xs text-gray-500">이미지 없음</div>
                        )}
                        <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                          <span className="px-3 py-1 bg-red-500 text-white font-black text-[10px] rounded-lg tracking-wider uppercase">❌ 실패 (스틸컷 대체)</span>
                        </div>
                      </div>
                    ) : scene.status === 'error' ? (
                      <div className="w-full h-full bg-red-950/20 flex flex-col items-center justify-center p-4 text-center space-y-3">
                        <AlertCircle className="w-8 h-8 text-red-500" />
                        <span className="text-[10px] font-bold text-red-400 break-keep">{scene.error || '비디오 생성 실패'}</span>
                        <button
                          onClick={() => handleFallbackToImage(i)}
                          className="px-3 py-2 bg-orange-600 hover:bg-orange-500 text-white text-[10px] font-black rounded-xl shadow-lg transition-all"
                        >
                          🖼️ 비디오 포기하고 스틸컷 대체
                        </button>
                      </div>
                    ) : scene.taskId && isRendering ? (
                      <div className="w-full h-full bg-purple-950/20 flex flex-col items-center justify-center space-y-3">
                        <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
                        <span className="text-[10px] font-black text-purple-400 animate-pulse uppercase tracking-widest">KIE AI 비디오 생성중</span>
                      </div>
                    ) : isRendering && !scene.use_image_only ? (
                      <div className="w-full h-full bg-neutral-900/60 flex flex-col items-center justify-center space-y-2">
                        {scene.image_url ? (
                          <img src={scene.image_url} className="w-full h-full object-cover opacity-30" />
                        ) : (
                          <div className="w-full h-full bg-neutral-950/60" />
                        )}
                        <div className="absolute inset-0 flex flex-col items-center justify-center space-y-1">
                          <Loader2 className="w-6 h-6 text-blue-500 animate-spin mb-1" />
                          <span className="text-[10px] text-blue-400 font-bold">비디오 대기중</span>
                        </div>
                      </div>
                    ) : (
                      <div className="w-full h-full bg-neutral-900/60 flex flex-col items-center justify-center space-y-2">
                        {scene.image_url ? (
                          <img src={scene.image_url} className="w-full h-full object-cover opacity-30" />
                        ) : (
                          <div className="w-full h-full bg-neutral-950/60" />
                        )}
                        <div className="absolute inset-0 flex flex-col items-center justify-center space-y-1">
                          <span className="text-[10px] text-gray-500 font-bold">비디오 생성 대기중</span>
                        </div>
                      </div>
                    )}
                    <div className="absolute top-4 left-4 bg-black/75 px-3 py-1 rounded-lg text-[10px] font-black text-white">SCENE {scene.scene_number}</div>
                  </div>
                  <div className="space-y-2">
                    <div className="text-[10px] font-bold text-blue-400 flex items-center gap-1 uppercase tracking-widest"><Languages className="w-3 h-3" /> 대사 (Voice Over)</div>
                    <p className="text-xs font-bold text-white leading-relaxed line-clamp-3 bg-black/30 p-3 rounded-xl border border-white/5">{scene.dialogue || scene.caption_ko}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
