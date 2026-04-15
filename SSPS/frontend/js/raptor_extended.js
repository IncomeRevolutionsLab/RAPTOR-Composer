/**
 * RAPTOR Extended (BYOK) Management Module
 * - Handles API Key storage in LocalStorage
 * - Estimates costs for different video engines
 * - Orchestrates extended generation requests
 */

class RaptorExtendedManager {
    constructor() {
        this.STORAGE_KEY = 'raptor_api_keys';
        this.engines = {
            'veo-3-standard': {
                name: 'Google Veo 3.1 Standard',
                pricePerSec: 0.38, // $0.35 - $0.40 range
                quality: 'Premium (4K, Native Audio)',
                provider: 'google'
            },
            'veo-3-fast': {
                name: 'Google Veo 3.1 Fast',
                pricePerSec: 0.15,
                quality: 'Standard (High Speed)',
                provider: 'google'
            },
            'veo-3-lite': {
                name: 'Google Veo 3.1 Lite',
                pricePerSec: 0.07, // Approx 50% of Fast
                quality: 'Economy (1080p)',
                provider: 'google'
            },
            'kling-pro': {
                name: 'Kling AI Pro',
                pricePerSec: 0.22,
                quality: 'Artistic (1080p Motion)',
                provider: 'kling'
            },
            'kling-standard': {
                name: 'Kling AI Standard',
                pricePerSec: 0.12,
                quality: 'Daily (720p)',
                provider: 'kling'
            },
            'grok-4-fast': {
                name: 'xAI Grok 4.1 Fast (Script Only)',
                pricePerSec: 0.001, // Token based, very cheap
                quality: 'Text/Script Logic',
                provider: 'xai'
            }
        };
    }

    /**
     * API 키를 로컬 스토리지에 저장합니다. (보안을 위해 실제 운영 시 암호화 권장)
     */
    saveKey(provider, key) {
        const keys = this.getAllKeys();
        keys[provider] = key;
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(keys));
        console.log(`[Raptor] ${provider} API Key saved.`);
    }

    /**
     * 특정 프로바이더의 키를 가져옵니다.
     */
    getKey(provider) {
        return this.getAllKeys()[provider] || null;
    }

    /**
     * 모든 저장된 키를 가져옵니다.
     */
    getAllKeys() {
        const data = localStorage.getItem(this.STORAGE_KEY);
        return data ? JSON.parse(data) : {};
    }

    /**
     * 엔진별 소요 비용을 추정합니다.
     * @param {string} engineId 
     * @param {number} durationSeconds (기본 15초)
     */
    estimateCost(engineId, durationSeconds = 15) {
        const engine = this.engines[engineId];
        if (!engine) return 0;
        return (engine.pricePerSec * durationSeconds).toFixed(2);
    }

    /**
     * 특정 엔진을 사용할 수 있는지 확인합니다 (키 존재 여부).
     */
    isEngineAvailable(engineId) {
        const engine = this.engines[engineId];
        if (!engine) return false;
        return !!this.getKey(engine.provider);
    }

    /**
     * 동영상 생성 요청 (v2.48 하이브리드)
     */
    async generateVideo(engineId, productData) {
        const engine = this.engines[engineId];
        if (!engine) throw new Error("유효하지 않은 엔진입니다.");

        const key = this.getKey(engine.provider);
        if (!key) {
            alert(`${engine.name}을(를) 사용하기 위한 API 키가 설정되지 않았습니다. [설정] 메뉴에서 키를 입력해 주세요.`);
            return;
        }

        console.log(`[Raptor] Launching ${engineId} video generation for product:`, productData);
        
        try {
            const response = await fetch('/api/v1/raptor/generate-video', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    engine: engineId,
                    api_key: key,
                    payload: {
                        product_name: productData.title || productData.name,
                        price: productData.price,
                        image_url: productData.image_url,
                        duration: 15
                    }
                })
            });

            const result = await response.json();
            if (result.status === 'success') {
                alert(`🎬 영상 생성이 시작되었습니다!\n엔진: ${result.engine}\n작업 ID: ${result.task_id}\n\n메시지: ${result.message}`);
                return result;
            } else {
                throw new Error(result.message || "영상 생성 요청 중 오류가 발생했습니다.");
            }
        } catch (error) {
            console.error("[Raptor] API Error:", error);
            alert(`❌ 오류 발생: ${error.message}`);
            throw error;
        }
    }
}

const raptorManager = new RaptorExtendedManager();
window.raptorManager = raptorManager;
export default raptorManager;
