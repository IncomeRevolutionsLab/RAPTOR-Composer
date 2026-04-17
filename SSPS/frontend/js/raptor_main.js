/**
 * RAPTOR GEM Production Engine (v3.5)
 * - Stage 1: AI Planning (Script & Scene Generation)
 * - Stage 2: Video Synthesis (Rendering via Engine)
 */

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? `${window.location.origin}/api/v1` 
    : 'https://ssps-engine-api.onrender.com/api/v1';

document.addEventListener('DOMContentLoaded', () => {
    // UI Elements
    const generateBtn = document.getElementById('generate-btn');      // Step 1: Planning
    const synthesisBtn = document.getElementById('synthesis-btn');    // Step 2: Synthesis
    const slider = document.getElementById('duration-slider');
    const durationVal = document.getElementById('duration-val');
    const sourceStatus = document.getElementById('source-status');
    const welcome = document.getElementById('welcome-message');
    const production = document.getElementById('production-interface');
    const loader = document.getElementById('loader');
    const loaderStatus = document.getElementById('loader-status');
    const content = document.getElementById('raptor-content');
    const videoEngine = document.getElementById('video-engine');
    const renderingOverlay = document.getElementById('rendering-overlay');

    let currentProduct = null;
    let currentPlan = null;

    // 1. URL 파라미터에서 데이터 읽기 (SSPS에서 전송된 경우)
    const params = new URLSearchParams(window.location.search);
    const encodedData = params.get('product');
    if (encodedData) {
        try {
            currentProduct = JSON.parse(decodeURIComponent(encodedData));
            sourceStatus.innerHTML = `
                <div style="color:var(--raptor-gold); font-weight:700;">[연결됨]</div>
                <div style="font-size:0.75rem;">${(currentProduct.title || currentProduct.name).substring(0,25)}...</div>
            `;
            generateBtn.innerHTML = `<i data-lucide="zap"></i> [1단계] AI 기획 시작`;
        } catch (e) {
            console.error("데이터 파싱 에러", e);
            sourceStatus.textContent = "데이터 오류";
        }
    }

    // 2. 슬라이더 연동
    slider.addEventListener('input', (e) => {
        durationVal.textContent = `${e.target.value}s`;
    });

    // 3. PHASE 1: AI 기획안 및 타임라인 생성 시작
    generateBtn.addEventListener('click', async () => {
        if (!currentProduct) {
            alert("기획할 상품 데이터가 없습니다. SSPS에서 상품을 선택해 주세요.");
            return;
        }

        welcome.style.display = 'none';
        production.style.display = 'none';
        loader.style.display = 'block';
        loaderStatus.textContent = "AI가 고난도 숏폼 기획안을 도출 중입니다...";

        try {
            const response = await fetch(`${API_BASE_URL}/raptor/generate-plan`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ssps_data: { items: [currentProduct], domain: currentProduct.title },
                    duration: slider.value
                })
            });

            const result = await response.json();
            
            if (result.status === 'success' || result.status === 'mock') {
                currentPlan = result;
                loader.style.display = 'none';
                production.style.display = 'block';
                content.innerHTML = marked.parse(result.planning_document);
                renderingOverlay.style.display = 'flex'; // 대기 상태 표시
                
                // 타임라인에 비디오 프리뷰 썸네일 세팅 (상품 이미지 활용)
                document.getElementById('preview-thumbnail').src = currentProduct.image_url;
                
                // 탭 활성화 로직 등 추가 가능
            } else {
                throw new Error(result.message || "기획 실패");
            }
        } catch (e) {
            alert(`AI 기획 중 오류 발생: ${e.message}`);
            loader.style.display = 'none';
            welcome.style.display = 'block';
        }
        lucide.createIcons();
    });

    // 4. PHASE 2: 비디오 실제 합성 엔진 호출
    synthesisBtn.addEventListener('click', async () => {
        const engineId = videoEngine.value;
        if (engineId === 'none') {
            alert("비디오 합성 엔진을 선택해 주세요 (예: Google Veo 3.1)");
            return;
        }

        // 로컬 스토리지에서 API Key 가져오기
        const keys = JSON.parse(localStorage.getItem('raptor_api_keys') || '{}');
        const provider = engineId.startsWith('veo') ? 'google' : (engineId.startsWith('kling') ? 'kling' : 'xai');
        const key = keys[provider];

        if (!key) {
            alert(`해당 엔진 사용을 위한 ${provider} API Key가 설정되지 않았습니다.`);
            return;
        }

        // 렌더링 애니메이션 시작
        renderingOverlay.innerHTML = `
            <div class="spinner" style="width: 50px; height: 50px; border-width: 4px; border-color: #e91e63 transparent #e91e63 transparent;"></div>
            <p style="color:#fff; margin-top:20px; font-weight:600; animation: pulse 1.5s infinite;">SYNTHESIZING VIDEO...</p>
            <p style="font-size:0.75rem; color:#aaa; margin-top:5px;">Engine: ${engineId}</p>
        `;

        try {
            const response = await fetch(`${API_BASE_URL}/raptor/generate-video`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    engine: engineId,
                    api_key: key,
                    payload: {
                        product_name: currentProduct.title,
                        script: currentPlan.planning_document,
                        duration: slider.value
                    }
                })
            });

            const result = await response.json();
            if (result.status === 'success') {
                renderingOverlay.innerHTML = `
                    <i data-lucide="check-circle" style="width:48px; height:48px; color:#00c853;"></i>
                    <p style="color:#fff; margin-top:15px; font-weight:700;">SYNTHESIS STARTED!</p>
                    <p style="font-size:0.75rem; color:#aaa;">Task ID: ${result.task_id}</p>
                    <button onclick="location.reload()" style="margin-top:20px; background:rgba(255,255,255,0.1); border:none; color:#fff; padding:8px 16px; border-radius:4px; font-size:0.7rem;">새 작업 시작</button>
                `;
            } else {
                throw new Error(result.error || result.message);
            }
        } catch (e) {
            alert(`비디오 합성 요청 실패: ${e.message}`);
            renderingOverlay.style.display = 'none';
        }
        lucide.createIcons();
    });

    // 5. 유틸리티 (복사/인수)
    document.getElementById('copy-script-btn')?.addEventListener('click', () => {
        navigator.clipboard.writeText(content.innerText).then(() => alert("대본이 복사되었습니다."));
    });
});
