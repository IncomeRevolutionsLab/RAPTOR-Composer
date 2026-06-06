import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

interface ProductData {
  name: string;
  url: string;
  images: string[];
  description: string;
  duration: number;
  includeTag: boolean;
  targetLanguage: string;
  purpose: string;
  targetAudience: string;
  tone: string;
}

interface ManualAdditions {
  pain_points: string[];
  strengths: string[];
}

interface WorkflowState {
  // Volatile UI State (Not Persisted)
  step: number;
  loading: boolean;
  statusMessage: string;
  inputMode: 'auto' | 'manual' | null;
  isRendering: boolean;
  renderProgress: number;
  renderedVideoUrl: string | null;
  tempInput: { pain: string; strength: string };

  // Core Data (Persisted)
  productData: ProductData;
  analysis: any;
  recommendedPatterns: any[] | null;
  selectedType: string;
  finalAssets: any;
  manualAdditions: ManualAdditions;
  aspectRatio: string;
  voiceType: string;
  subtitlePosition: string; // Added for subtitle position control
  renderDuration: string;

  // Auth State (Persisted)
  user: any | null;
  userId: string;
  setUser: (user: any | null) => void;
  lastRenderTimestamp: number;
  setLastRenderTimestamp: (ts: number) => void;
  isAuthLoading: boolean;
  setIsAuthLoading: (loading: boolean) => void;

  // BYOK Keys (Persisted)
  isKeyConfigured: boolean;
  kieKey: string;
  csrfToken: string | null;
  claudeModel: string; // Added for dynamic model selection
  imageEngine: string;
  textEngine: string;

  // Watermark Settings
  watermarkEnabled: boolean;
  watermarkLogo: string | null;
  watermarkPosition: 'top-right' | 'bottom-right';

  errorMessage: string | null;
  setErrorMessage: (msg: string | null) => void;
  projectId: string | null;
  setProjectId: (id: string | null) => void;
  // Actions
  setStep: (step: number) => void;
  setLoading: (loading: boolean, message?: string) => void;
  setInputMode: (mode: 'auto' | 'manual' | null) => void;
  setProductData: (data: Partial<ProductData> | ((prev: ProductData) => ProductData)) => void;
  setAnalysis: (analysis: any) => void;
  setRecommendedPatterns: (patterns: any[] | null) => void;
  setSelectedType: (type: string) => void;
  setFinalAssets: (assets: any) => void;
  setManualAdditions: (additions: Partial<ManualAdditions> | ((prev: ManualAdditions) => ManualAdditions)) => void;
  setAspectRatio: (ratio: string) => void;
  setVoiceType: (voice: string) => void;
  setSubtitlePosition: (position: string) => void;
  setRenderDuration: (duration: string) => void;
  setWatermarkSettings: (settings: Partial<{ watermarkEnabled: boolean; watermarkLogo: string | null; watermarkPosition: 'top-right' | 'bottom-right' }>) => void;
  setRenderStatus: (isRendering: boolean, progress: number, url?: string | null) => void;
  setTempInput: (temp: Partial<{ pain: string; strength: string }>) => void;
  setIsKeyConfigured: (isConfigured: boolean) => void;
  setKieKey: (key: string) => void;
  setCsrfToken: (token: string | null) => void;
  setEngineSettings: (settings: Partial<{ imageEngine: string; textEngine: string; claudeModel: string }>) => void;
  hasHydrated: boolean;
  setHasHydrated: (state: boolean) => void;
  resetWorkflow: () => void;
}

const initialProductData: ProductData = {
  name: '',
  url: '',
  images: [],
  description: '',
  duration: 15,
  includeTag: false,
  targetLanguage: '한국어',
  purpose: '쇼핑 전환',
  targetAudience: '',
  tone: '리뷰형'
};

const initialManualAdditions: ManualAdditions = {
  pain_points: [],
  strengths: []
};

export const useWorkflowStore = create<WorkflowState>()(
  persist(
    (set) => ({
      // Volatile initial state
      step: 0,
      loading: false,
      statusMessage: '',
      inputMode: null,
      isRendering: false,
      renderProgress: 0,
      renderedVideoUrl: null,
      tempInput: { pain: '', strength: '' },
      hasHydrated: false,
      isAuthLoading: false,

      // Persisted initial state
      user: null,
      userId: '',
      lastRenderTimestamp: 0,
      productData: initialProductData,
      analysis: null,
      recommendedPatterns: null,
      selectedType: '',
      finalAssets: null,
      manualAdditions: initialManualAdditions,
      aspectRatio: '9:16',
      voiceType: '여성-발랄한',
      subtitlePosition: '하',
      renderDuration: '자막 맞춤 길이 (Dynamic Sync)',
      isKeyConfigured: false,
      kieKey: '',
      csrfToken: null,
      claudeModel: 'claude-sonnet-4-6', // Default 2026 model
      imageEngine: 'gpt-image-2',
      textEngine: 'claude-sonnet-4-6',
      watermarkEnabled: false,
      watermarkLogo: null,
      watermarkPosition: 'top-right',

      errorMessage: null,
      setErrorMessage: (errorMessage) => set({ errorMessage }),
      setHasHydrated: (hasHydrated) => set({ hasHydrated }),
      setIsAuthLoading: (isAuthLoading) => set({ isAuthLoading }),
      
      projectId: null,
      setProjectId: (projectId) => set({ projectId }),

      // Actions
      setUser: (user) => set((state) => {
        const nextUserId = user?.id || '';
        return { 
          user, 
          userId: nextUserId,
          errorMessage: null,
          isRendering: false,
          renderProgress: 0
        };
      }),
      setLastRenderTimestamp: (lastRenderTimestamp) => set({ lastRenderTimestamp }),
      setStep: (step) => set({ step }),
      setLoading: (loading, message = '') => set({ loading, statusMessage: message }),
      setInputMode: (inputMode) => set({ inputMode }),
      setProductData: (data) => set((state) => ({
        productData: typeof data === 'function' ? data(state.productData) : { ...state.productData, ...data }
      })),
      setAnalysis: (analysis) => set({ analysis }),
      setRecommendedPatterns: (recommendedPatterns) => set({ recommendedPatterns }),
      setSelectedType: (selectedType) => set({ selectedType }),
      setFinalAssets: (assets) => set((state) => ({
        finalAssets: typeof assets === 'function' ? assets(state.finalAssets) : assets
      })),
      setManualAdditions: (additions) => set((state) => ({
        manualAdditions: typeof additions === 'function' ? additions(state.manualAdditions) : { ...state.manualAdditions, ...additions }
      })),
      setAspectRatio: (aspectRatio) => set({ aspectRatio }),
      setVoiceType: (voiceType) => set({ voiceType }),
      setSubtitlePosition: (subtitlePosition) => set({ subtitlePosition }),
      setRenderDuration: (renderDuration) => set({ renderDuration }),
      setWatermarkSettings: (settings) => set((state) => ({ ...state, ...settings })),
      setRenderStatus: (isRendering, renderProgress, renderedVideoUrl = null) => 
        set({ isRendering, renderProgress, renderedVideoUrl }),
      setTempInput: (temp) => set((state) => ({
        tempInput: { ...state.tempInput, ...temp }
      })),
      setIsKeyConfigured: (isKeyConfigured) => set({ isKeyConfigured }),
      setKieKey: (kieKey) => set({ kieKey }),
      setCsrfToken: (csrfToken) => set({ csrfToken }),
      setEngineSettings: (settings) => set((state) => ({ ...state, ...settings })),
      resetWorkflow: () => {
        set((state) => ({
          step: 0,
          loading: false,
          inputMode: null,
          productData: initialProductData,
          analysis: null,
          recommendedPatterns: null,
          selectedType: '',
          finalAssets: null,
          manualAdditions: initialManualAdditions,
          renderedVideoUrl: null,
          errorMessage: null,
          projectId: null,
          // Do NOT reset BYOK keys, Watermark settings, and Auth
          user: state.user,
          userId: state.userId,
          isKeyConfigured: state.isKeyConfigured,
          kieKey: state.kieKey,
          csrfToken: state.csrfToken,
          claudeModel: state.claudeModel,
          imageEngine: state.imageEngine,
          textEngine: state.textEngine,
          watermarkEnabled: state.watermarkEnabled,
          watermarkLogo: state.watermarkLogo,
          watermarkPosition: state.watermarkPosition
        }));
      },
    }),
    {
      name: 'raptor-workflow-storage',
      storage: createJSONStorage(() => {
        if (typeof window !== 'undefined') {
          return window.localStorage;
        }
        return {
          getItem: () => null,
          setItem: () => {},
          removeItem: () => {},
        } as any;
      }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.setHasHydrated(true);
          state.setErrorMessage(null);
          state.setRenderStatus(false, 0, null);
          if (state.step === 4) {
            state.setStep(3);
          }
          // 404 및 에러 캐시 잔재 클리어 (False Positive 방지 구조)
          if (state.finalAssets && state.finalAssets.script) {
            const cleanScript = state.finalAssets.script.map((s: any) => {
              let isBroken = false;
              if (s.image_url) {
                const url = s.image_url.trim();
                const isSchemeValid = url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:image/');
                const hasErrorText = url.toLowerCase().includes('error') || url.toLowerCase().includes('fail') || url.toLowerCase().includes('broken_image');
                if (!isSchemeValid || hasErrorText) {
                  isBroken = true;
                }
              }
              return {
                ...s,
                image_url: isBroken ? null : s.image_url,
                status: isBroken ? 'waiting' : s.status,
                error: isBroken ? null : s.error
              };
            });
            state.setFinalAssets({
              ...state.finalAssets,
              script: cleanScript
            });
          }
        }
      },
      partialize: (state) => {
        let safeAssets = state.finalAssets;
        if (safeAssets && safeAssets.script) {
          safeAssets = {
            ...safeAssets,
            script: safeAssets.script.map((s: any) => ({
              ...s,
              image_url: s.image_url?.startsWith('data:image') ? null : s.image_url
            }))
          };
        }
        return {
          step: state.step,
          inputMode: state.inputMode,
          productData: { 
            ...state.productData, 
            images: state.productData.images.filter((img: string) => img && !img.startsWith('data:image')) 
          }, 
          voiceType: state.voiceType,
          aspectRatio: state.aspectRatio,
          subtitlePosition: state.subtitlePosition,
          renderDuration: state.renderDuration,
          analysis: state.analysis,
          recommendedPatterns: state.recommendedPatterns,
          selectedType: state.selectedType,
          finalAssets: safeAssets,
          manualAdditions: state.manualAdditions,
          tempInput: state.tempInput,
          user: state.user,
          userId: state.userId,
          isKeyConfigured: state.isKeyConfigured,
          kieKey: state.kieKey,
          claudeModel: state.claudeModel,
          imageEngine: state.imageEngine,
          textEngine: state.textEngine,
          watermarkEnabled: state.watermarkEnabled,
          watermarkLogo: state.watermarkLogo,
          watermarkPosition: state.watermarkPosition,
          lastRenderTimestamp: state.lastRenderTimestamp,
          projectId: state.projectId
        };
      }
    }

  )
);
