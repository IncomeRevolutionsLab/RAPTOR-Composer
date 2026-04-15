// ─────────────────────────────────────────────
// 전역 상태 및 환경 변수
// ─────────────────────────────────────────────
const IS_LOCAL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
// [v2.343 Official Sync] Direct-Sync 아키텍처: Vercel 프록시 404 회피를 위한 백엔드 직접 연결
const API_BASE_URL = IS_LOCAL ? `${window.location.origin}/api/v1` : 'https://ssps-engine-api.onrender.com/api/v1';

// [Render 무료플랜 Cold Start 대응] 페이지 로드 시 백엔드 웜업 (Vercel Proxy 경로 사용)
if (!IS_LOCAL) {
  fetch(`${API_BASE_URL}/health`, { method: 'GET' }).catch(() => {});
}
const TOP_LEVEL_CATEGORIES = [
    '패션의류','패션잡화','화장품/미용','디지털/가전','가구/인테리어',
    '출산/육아','식품','스포츠/레저','생활/건강','여가/생활편의','도서','면세점'
];

let weightChartInstance = null;
let trendChartInstance  = null;
let p1TrendChartInstance = null;

// [v2.4] RAPTOR GEM 데이터 연동을 위한 전역 상태
let currentAppData = null;

// Phase1 결과 캐시 (뒤로가기용) 삭제 - N-Depth 탐색으로 전환

// ─────────────────────────────────────────────
// 패널 표시 제어
// ─────────────────────────────────────────────
const PANELS = ['main-3d-chart-container','search-panel-section','loading-state',
                'phase1-state','phase2-state','result-state'];

function showPanels(...ids) {
    PANELS.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.add('hidden');
    });
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.remove('hidden');
    });
}

// ─────────────────────────────────────────────
// 브레드크럼 (경로 네비게이션) 랜더링
// ─────────────────────────────────────────────
function renderBreadcrumbs(containerId, pathArray) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';
    
    pathArray.forEach((part, idx) => {
        const span = document.createElement('span');
        const a = document.createElement('a');
        a.textContent = part;
        a.href = '#';
        a.style.color = (idx === pathArray.length - 1) ? '#e2e8f0' : 'var(--primary)';
        a.style.fontWeight = (idx === pathArray.length - 1) ? '600' : '400';
        a.style.textDecoration = 'none';
        
        a.addEventListener('click', (e) => {
            e.preventDefault();
            const newPath = pathArray.slice(0, idx + 1);
            loadCategoryNode({path: newPath}); // 즉시 롤백 이동
        });
        
        span.appendChild(a);
        container.appendChild(span);
        
        if (idx < pathArray.length - 1) {
            const arrow = document.createElement('i');
            arrow.setAttribute('data-lucide', 'chevron-right');
            arrow.style.width = '16px';
            arrow.style.color = '#7d8590';
            arrow.style.margin = '0 6px';
            container.appendChild(arrow);
        }
    });
    lucide.createIcons();
}

// ─────────────────────────────────────────────
// 초기화 (홈)
// ─────────────────────────────────────────────
function resetToHome() {
    showPanels('main-3d-chart-container', 'search-panel-section');
    document.getElementById('domain-input').value = '';
    document.getElementById('submit-btn').disabled = false;
    lucide.createIcons();
}

// ─────────────────────────────────────────────
// 근본 통합 라우터 (N-Depth 및 자유검색 공용)
// ─────────────────────────────────────────────

async function fetchWithRetry(url, options = {}, retries = 3, delay = 1000) {
    for (let i = 0; i < retries; i++) {
        const controller = new AbortController();
        // [v2.46 긴급 수정] Render 무료 서버의 콜드 스타트(Wake-up) 시간(최대 50초)을 고려하여 타임아웃을 60초로 대폭 연장
        const timeoutId = setTimeout(() => controller.abort(new Error("Request Timeout: 서버 응답이 지연되었습니다.")), 60000); 
        
        try {
            const res = await fetch(url, { ...options, signal: controller.signal });
            clearTimeout(timeoutId);
            
            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.error || `HTTP error! status: ${res.status}`);
            }
            return await res.json();
        } catch (e) {
            clearTimeout(timeoutId);
            if (i === retries - 1) throw e;
            console.warn(`[API Retry] ${i + 1}회 실패. 재시도 중... (${url})`, e.message);
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
}


async function loadCategoryNode(payload) {
    if (!payload || (!payload.path && !payload.keyword)) return;
    
    showPanels('loading-state');
    simulateLoadingSteps();

    try {
        // [v2.35] 수동 입력 데이터 추출 (있는 경우에만)
        const manualOlive = document.getElementById('manual_oliveyoung')?.value || "";
        const manualDaiso = document.getElementById('manual_daiso')?.value || "";
        
        const payloadWithManual = { ...payload, 
                                    manual_olive: manualOlive, 
                                    manual_daiso: manualDaiso };

        const data = await fetchWithRetry(`${API_BASE_URL}/category_node`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payloadWithManual)
        });
        
        setTimeout(() => {
            if (data.is_leaf) {
                renderPhase2(data, data.path || [payload.keyword]);
            } else {
                renderPhase1(data, data.path || [payload.keyword]);
            }
            // [v2.4] RAPTOR GEM 연동을 위해 최신 분석 데이터 세이브
            currentAppData = data;
            
            // [v2.35] 분석 성공 시 하단 실시간 통계 즉시 갱신 (손맛 구현)
            loadSiteStats();
        }, 400);
    } catch (err) {
        console.error(err);
        alert(`[에러] ${err.message}`);
        resetToHome();
    }
}

function renderPhase1(data, pathArray) {
    showPanels('phase1-state');
    renderBreadcrumbs('p1-breadcrumb-container', pathArray);

    // 트렌드 라인 차트
    renderPhase1TrendChart(data.trend_series);

    // TOP3 선택 카드
    const grid = document.getElementById('p1-cards-grid');
    grid.innerHTML = '';
    const rankColors = ['#f1c40f','#a1a1aa','#cd7f32'];
    const rankLabels = ['🥇 1위','🥈 2위','🥉 3위'];

    (data.ranking || []).forEach((item, idx) => {
        const card = document.createElement('div');
        card.className = 'glass-card';
        card.style.cssText = `
            padding:20px; border-radius:12px; cursor:pointer; text-align:center;
            border:2px solid transparent; transition:all 0.25s; position:relative; overflow:hidden;
        `;
        card.innerHTML = `
            <div style="font-size:1.4rem; font-weight:800; color:${rankColors[idx]}; margin-bottom:8px;">${rankLabels[idx]}</div>
            <div style="font-size:1.1rem; font-weight:600; color:#e2e8f0; margin-bottom:10px;">${item.name}</div>
            <div style="font-size:0.8rem; color:#7d8590;">연평균 클릭 지수</div>
            <div style="font-size:1.5rem; font-weight:700; color:var(--primary); margin-top:4px;">${item.avg_score}</div>
            <div style="margin-top:14px; background:var(--primary); color:#fff; padding:8px 0; border-radius:8px; font-size:0.9rem; font-weight:600;">
                선택 → 하위 파고들기
            </div>
        `;
        card.addEventListener('mouseenter', () => {
            card.style.borderColor = 'var(--primary)';
            card.style.transform = 'translateY(-4px)';
            card.style.boxShadow = '0 8px 24px rgba(88,166,255,0.25)';
        });
        card.addEventListener('mouseleave', () => {
            card.style.borderColor = 'transparent';
            card.style.transform = '';
            card.style.boxShadow = '';
        });
        const currentPath = pathArray.filter(e => e !== undefined && e !== "");
        card.addEventListener('click', () => loadCategoryNode({path: [...currentPath, item.name]}));
        grid.appendChild(card);
    });

    lucide.createIcons();
}

function renderPhase1TrendChart(trendSeries) {
    const container = document.getElementById('p1-trend-chart');
    if (!container) return;
    if (p1TrendChartInstance) { p1TrendChartInstance.dispose(); }

    p1TrendChartInstance = echarts.init(container);
    const colors = ['#58a6ff','#3fb950','#f1c40f'];

    const option = {
        tooltip: {trigger:'axis'},
        legend: {
            data: (trendSeries.series||[]).map(s=>s.name),
            textStyle:{color:'#a1a1aa'}, bottom:0
        },
        grid: {left:'5%', right:'5%', bottom:'15%', top:'5%', containLabel:true},
        xAxis: {
            type:'category', boundaryGap:false,
            data: trendSeries.categories || [],
            axisLabel:{color:'#888', fontSize:11}
        },
        yAxis: {
            type:'value', min:0, max:100,
            axisLabel:{color:'#888'},
            splitLine:{lineStyle:{color:'rgba(255,255,255,0.05)'}}
        },
        series: (trendSeries.series||[]).map((s,i)=>({
            name: s.name, type:'line', smooth:true,
            data: s.data, lineStyle:{width:3, color:colors[i]},
            itemStyle:{color:colors[i]},
            symbol:'circle', symbolSize:7,
            areaStyle:{color:colors[i], opacity:0.08}
        }))
    };
    p1TrendChartInstance.setOption(option);
    window.addEventListener('resize', () => p1TrendChartInstance?.resize());
}

function renderPhase2(data, pathArray) {
    showPanels('phase2-state');

    // 브레드크럼
    renderBreadcrumbs('p2-breadcrumb-container', pathArray);
    document.getElementById('p2-title').textContent = `[${pathArray[pathArray.length-1]}] 쿠팡 Top 10 랭킹`;

    // 쿠팡 검색 링크 (상단 버튼)
    const linkEl = document.getElementById('p2-coupang-link');
    linkEl.href = data.coupang_search_url;

    const productGrid = document.getElementById('p2-product-grid');
    const fallbackNotice = document.getElementById('p2-fallback-notice');
    productGrid.innerHTML = '';

    if (data.is_coupang_available && data.products.length > 0) {
        fallbackNotice.style.display = 'none';
        data.products.forEach(product => {
            const card = document.createElement('div');
            card.className = 'sku-card';
            card.style.flexDirection = 'column'; // 세로 스택형으로 변경 (확장 기능 수용)
            
            // 엔진별 비용 추정 (15초 기준)
            const veoCost = 2.25; // Standard 0.15 * 15 (Fast 기준 추정)
            const klingCost = 1.8; // Standard 0.12 * 15
            
            card.innerHTML = `
                <div style="display:flex; flex-direction:row; width:100%;">
                    <a href="${product.source_url}" target="_blank" style="text-decoration:none; color:inherit; display:flex; flex-direction:row; flex:1;">
                        <img src="${product.image_url || 'https://via.placeholder.com/300?text=No+Image'}"
                             alt="${product.title}" class="sku-img"
                             onerror="this.src='https://via.placeholder.com/300?text=No+Image'">
                        <div class="sku-info" style="flex:1;">
                            <div class="sku-rank">Top ${product.rank || 'N/A'} <span style="color:#f1c40f;">[Coupang]</span></div>
                            <div class="sku-title" style="margin-top:8px;">${product.title || product.name || '상품 정보 없음'}</div>
                            <div class="sku-price" style="margin-top:6px;">₩${(product.price || 0).toLocaleString()}</div>
                        </div>
                    </a>
                    <div style="width:1px; background:var(--glass-border); margin:15px 0;"></div>
                    <div style="padding: 20px; display:flex; flex-direction:column; justify-content:center; gap:10px; width:220px;">
                         <div style="font-size:0.7rem; color:var(--primary); margin-bottom:2px; text-align:center;">복사 없이 즉시 기획 시작 ↓</div>
                         <button class="coupang-btn" style="background:#58a6ff;" onclick="window.triggerRaptorBasic('${encodeURIComponent(JSON.stringify(product))}')" title="이 버튼을 클릭하면 URL 복사 없이 상품 정보가 RAPTOR AI로 즉시 연동됩니다.">
                            <i data-lucide="file-text" style="width:14px;"></i> RAPTOR 기획안 생성
                         </button>
                    </div>
                </div>
                
                <!-- [NEW] RAPTOR Extended (BYOK) Section -->
                <div style="padding: 0 20px 20px 20px; border-top: 1px dashed var(--glass-border);">
                    <div style="font-size: 0.75rem; color:var(--text-muted); margin: 12px 0 8px 0; display:flex; align-items:center; gap:5px;">
                        <i data-lucide="video" style="width:12px;"></i> RAPTOR Extended (Video BYOK) - 엔진별 15초 제작 예측 비용
                    </div>
                    <div class="raptor-engine-grid">
                        <div class="engine-card" onclick="window.raptorManager.generateVideo('veo-3-fast', ${JSON.stringify(product).replace(/"/g, '&quot;')})">
                            <span class="cost-badge">$${veoCost}</span>
                            <div class="engine-name">Google Veo 3.1</div>
                            <div class="engine-quality">Fast / High Speed Sync</div>
                        </div>
                        <div class="engine-card" onclick="window.raptorManager.generateVideo('kling-pro', ${JSON.stringify(product).replace(/"/g, '&quot;')})">
                            <span class="cost-badge">$${klingCost}</span>
                            <div class="engine-name">Kling AI Pro</div>
                            <div class="engine-quality">1080p / Artistic Motion</div>
                        </div>
                    </div>
                </div>
            `;
            productGrid.appendChild(card);
        });
    } else {
        // 스크래핑 차단 → 링크 버튼 표시
        fallbackNotice.style.display = 'block';
        document.getElementById('p2-fallback-btn').href = data.coupang_search_url;
        document.getElementById('p2-fallback-label').textContent =
            `쿠팡에서 [${data.depth2}] 검색하기`;
    }

    lucide.createIcons();
}

// startAnalysis 및 renderResults 통폐합 (단일 파이프라인 적용으로 제거됨)

// ─────────────────────────────────────────────
// DOMContentLoaded
// ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const form      = document.getElementById('analyze-form');
    const input     = document.getElementById('domain-input');
    const submitBtn = document.getElementById('submit-btn');

    // 폼 제출: 무조건 단일 라우터로 통과시킴
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const domain = input.value.trim();
        if (!domain) return;
        
        if (TOP_LEVEL_CATEGORIES.includes(domain)) {
            loadCategoryNode({path: [domain]});
        } else {
            // [v2.35] 특정 키워드 검색 시에도 수동 입력값은 loadCategoryNode 내에서 처리됨
            loadCategoryNode({keyword: domain});
        }
    });

    // 칩 클릭 → N-Depth 1차 카테고리 진입
    document.querySelectorAll('.chip-btn').forEach(chip => {
        chip.addEventListener('click', (e) => {
            const val = e.target.getAttribute('data-val');
            input.value = val;
            loadCategoryNode({path: [val]});
        });
    });

    // [v2.45] 페이지 로드 즉시 첫 번째 분야(패션의류) 인기 키워드 로드
    const firstDomain = TOP_LEVEL_CATEGORIES[0] || '패션의류';
    loadPopularKeywords(firstDomain);

    // 수동 업로드 확인
    document.getElementById('verify-manual-btn')?.addEventListener('click', () => {
        showToast('✅ 올리브영/다이소 수동 데이터가 반영되었습니다.');
    });

    // JSON 복사
    document.getElementById('copy-json-btn')?.addEventListener('click', () => {
        const text = document.getElementById('json-output')?.innerText;
        if (text) navigator.clipboard.writeText(text).then(() => showToast('JSON이 복사되었습니다.'));
    });

    // [NEW] Settings Modal Controls
    const settingsBtn = document.getElementById('open-settings-btn');
    const closeSettingsBtn = document.getElementById('close-settings-btn');
    const settingsModal = document.getElementById('settings-modal');
    const saveSettingsBtn = document.getElementById('save-settings-btn');

    settingsBtn?.addEventListener('click', () => {
        // 기존 키 로드
        const keys = JSON.parse(localStorage.getItem('raptor_api_keys') || '{}');
        if (keys.google) document.getElementById('key-google').value = keys.google;
        if (keys.kling) document.getElementById('key-kling').value = keys.kling;
        if (keys.xai) document.getElementById('key-xai').value = keys.xai;
        
        settingsModal.classList.add('active');
    });

    closeSettingsBtn?.addEventListener('click', () => {
        settingsModal.classList.remove('active');
    });

    saveSettingsBtn?.addEventListener('click', () => {
        const keys = {
            google: document.getElementById('key-google').value,
            kling: document.getElementById('key-kling').value,
            xai: document.getElementById('key-xai').value
        };
        localStorage.setItem('raptor_api_keys', JSON.stringify(keys));
        showToast('✅ API 설정이 안전하게 저장되었습니다.');
        settingsModal.classList.remove('active');
    });

    // [v2.4] RAPTOR GEM UI 제어 로직 등록
    initRaptorHandlers();

    // 초기 데이터 로드 (차트, 키워드, 마이크로 통계)
    setTimeout(() => {
        initMain3DChart();
        loadPopularKeywords("패션의류");
        loadSiteStats(); // [v2.35] DB 실제 통계 로드
    }, 500);
});

// V1 시절 자유 텍스트 결과 렌더링 (단일 파이프라인으로 제거됨)

// ─────────────────────────────────────────────
// 3D 메인 차트 (2개 분할 렌더링)
// ─────────────────────────────────────────────
function initMain3DChart() {
    const container1 = document.getElementById('main-3d-chart-1');
    const container2 = document.getElementById('main-3d-chart-2');
    const container3 = document.getElementById('main-3d-chart-3');
    if (!container1 || !container2 || !container3) return;
    
    const chart1 = echarts.init(container1);
    const chart2 = echarts.init(container2);
    const chart3 = echarts.init(container3);
    chart1.showLoading({text: 'Loading...'});
    chart2.showLoading({text: 'Loading...'});
    chart3.showLoading({text: 'Loading...'});

    const filterData = (cats, data, start, end) => {
        const slicedCats = cats.slice(start, end);
        const filteredData = [];
        data.forEach(item => {
            if (item[1] >= start && item[1] < end) {
                filteredData.push([item[0], item[1] - start, item[2]]);
            }
        });
        return { cats: slicedCats, data: filteredData };
    };

    // [v2.50] 12개 분야 (4+4+4) 동적 앵커링 보정 보정 API 호출
    fetch(`${API_BASE_URL}/domains/trend`)
        .then(r => r.json())
        .then(json => { 
            if (json.status !== 'success') throw new Error('API Error');
            
            const p1 = filterData(json.categories, json.data, 0, 4);
            const p2 = filterData(json.categories, json.data, 4, 8);
            const p3 = filterData(json.categories, json.data, 8, 12);
            render3DChart(chart1, p1.cats, json.months, p1.data);
            render3DChart(chart2, p2.cats, json.months, p2.data);
            render3DChart(chart3, p3.cats, json.months, p3.data);
            
            // [v2.44] 차트가 블랙아웃되는 현상을 방지하기 위해 강제 리사이즈 시도
            setTimeout(() => { chart1.resize(); chart2.resize(); chart3.resize(); }, 200);
            
            chart1.hideLoading(); chart2.hideLoading(); chart3.hideLoading();
        })
        .catch(() => {
            // [v2.44] 12개 분야 Fallback 리스트 및 데이터 생성 (도서, 면세점 포함)
            const cats = ['패션의류','패션잡화','화장품/미용','디지털/가전','가구/인테리어','출산/육아','식품','스포츠/레저','생활/건강','여가/생활편의','도서','면세점'];
            const mnts = ['25-04','25-05','25-06','25-07','25-08','25-09','25-10','25-11','25-12','26-01','26-02','26-03'];
            const baseScores = [70,45,80,62,55,64,85,65,72,47,40,30];
            const seasonBias = [
                [0,5,10,15,8,0,8,18,28,-12,-18,-2],
                [-2,4,8,12,5,-3,10,14,22,-8,-14,0],
                [5,12,18,10,14,8,10,20,8,-5,0,28],
                [-5,-2,0,3,7,12,22,17,35,-5,-8,-7],
                [0,4,10,7,4,12,16,22,12,-10,-5,10],
                [0,5,8,5,7,8,12,10,5,10,-3,5],
                [5,8,0,15,14,-2,5,15,18,10,-3,5],
                [0,22,38,30,26,10,-5,-10,-14,-20,-10,0],
                [0,4,8,10,6,10,12,10,8,4,0,5],
                [0,8,18,24,20,10,-3,-5,8,-3,-10,8],
                [0,5,10,5,3,8,12,15,25,10,5,12], // 도서 (학기초/연말 효과)
                [5,10,15,20,25,10,5,15,30,-5,-10,0] // 면세점 (휴가시즌 효과)
            ];
            const fallbackData = [];
            for (let i = 0; i < cats.length; i++) {
                for (let j = 0; j < mnts.length; j++) {
                    fallbackData.push([j, i, Math.min(100, Math.max(10, baseScores[i]+seasonBias[i][j]+Math.floor(Math.random()*8-4)))]);
                }
            }
            
            const p1 = filterData(cats, fallbackData, 0, 4);
            const p2 = filterData(cats, fallbackData, 4, 8);
            const p3 = filterData(cats, fallbackData, 8, 12);
            render3DChart(chart1, p1.cats, mnts, p1.data, '(기본 데이터)');
            render3DChart(chart2, p2.cats, mnts, p2.data, '(기본 데이터)');
            render3DChart(chart3, p3.cats, mnts, p3.data, '(기본 데이터)');
            // [v2.44] 예비 데이터 로딩 시에도 블랙아웃 방지 리사이즈
            setTimeout(() => { chart1.resize(); chart2.resize(); chart3.resize(); }, 200);
            
            chart1.hideLoading(); chart2.hideLoading(); chart3.hideLoading();
        });
}

function render3DChart(myChart, categories, months, data, suffix='') {
    const option = {
        title: {
            text: `SSPS 지능형 쇼핑 숏폼 상품 선정 시스템 — 네이버 10대 분야 1년 클릭 트렌드 비교 (3D) ${suffix}`,
            textStyle:{color:'#a1a1aa', fontSize:13, fontWeight:'normal'}, left:'center', top:0
        },
        tooltip: { formatter: p => `[${categories[p.value[1]]}]<br>${months[p.value[0]]}: <b>${p.value[2]}</b>` },
        visualMap: {
            show:true, min:0, max:100,
            inRange:{color:['#313695','#4575b4','#74add1','#abd9e9','#e0f3f8','#ffffbf','#fee090','#fdae61','#f46d43','#d73027','#a50026']},
            textStyle:{color:'#a1a1aa'}, calculable:true, bottom:'10%'
        },
        xAxis3D:{type:'category', data:months, name:'월', nameTextStyle:{color:'#888'}, axisLabel:{textStyle:{color:'#888'}}},
        yAxis3D:{type:'category', data:categories, name:'분야', nameTextStyle:{color:'#888'}, axisLabel:{textStyle:{color:'#888'}}},
        zAxis3D:{type:'value', name:'트렌드 지수', nameTextStyle:{color:'#888'}, axisLabel:{textStyle:{color:'#888'}}},
        grid3D:{
            boxWidth:220, boxDepth:120, boxHeight:80,
            viewControl:{projection:'perspective', autoRotate:false, rotateSensitivity:1, distance:300, alpha:25, beta:20},
            light:{main:{intensity:1.2}, ambient:{intensity:0.3}}, environment:'transparent'
        },
        series:[{
            type:'scatter3D', data,
            symbolSize: val => Math.max(5, val[2]/10),
            itemStyle:{opacity:0.85},
            emphasis:{label:{show:true, formatter: p=>`${categories[p.value[1]]}\n${months[p.value[0]]}: ${p.value[2]}`, textStyle:{color:'#fff', fontSize:12}}}
        }]
    };
    myChart.setOption(option);
    window.addEventListener('resize', () => myChart.resize());
}

// ─────────────────────────────────────────────
// 유틸리티
// ─────────────────────────────────────────────
function renderChart(weights) {
    const ctx = document.getElementById('weightChart')?.getContext('2d');
    if (!ctx) return;
    if (weightChartInstance) weightChartInstance.destroy();
    Chart.defaults.color = '#7d8590';
    Chart.defaults.font.family = "'Outfit', sans-serif";
    weightChartInstance = new Chart(ctx, {
        type:'doughnut',
        data:{
            labels:['Naver','OliveYoung','Daiso'],
            datasets:[{
                data:[weights.naver*100, weights.oliveyoung*100, weights.daiso*100],
                backgroundColor:['#03c75a','#f27b9b','#f1c40f'],
                borderWidth:0, hoverOffset:4
            }]
        },
        options:{responsive:true, maintainAspectRatio:false, cutout:'70%',
                 plugins:{legend:{position:'right', labels:{boxWidth:12, usePointStyle:true}}}}
    });
}

function renderTrendChart(trendSeries) {
    const container = document.getElementById('drill-trend-chart');
    if (!container) return;
    if (trendChartInstance) trendChartInstance.dispose();
    trendChartInstance = echarts.init(container);
    const option = {
        tooltip:{trigger:'axis'},
        legend:{data:trendSeries.series.map(s=>s.name), textStyle:{color:'#a1a1aa'}},
        grid:{left:'3%', right:'4%', bottom:'3%', containLabel:true},
        xAxis:{type:'category', boundaryGap:false, data:trendSeries.categories, axisLabel:{color:'#888'}},
        yAxis:{type:'value', axisLabel:{color:'#888'}, splitLine:{lineStyle:{color:'rgba(255,255,255,0.05)'}}},
        series:trendSeries.series.map(s=>({name:s.name, type:'line', smooth:true, data:s.data, lineStyle:{width:3}, symbol:'circle', symbolSize:8}))
    };
    trendChartInstance.setOption(option);
    window.addEventListener('resize', () => trendChartInstance?.resize());
}

function simulateLoadingSteps() {
    const steps = [1,2,3,4].map(n => document.getElementById(`step-${n}`));
    steps.forEach(s => { if(s) s.className = 'pending'; });
    if (steps[0]) steps[0].className = 'active';
    [600,1200,2000].forEach((t,i) => {
        setTimeout(() => {
            if (steps[i]) { steps[i].className = 'done'; steps[i].innerHTML = steps[i].innerHTML.replace('중','완료'); }
            if (steps[i+1]) steps[i+1].className = 'active';
        }, t);
    });
}

function syntaxHighlight(json) {
    json = json.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    return json.replace(/(\"(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*\"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, match => {
        let cls = 'number';
        if (/^"/.test(match)) cls = /:$/.test(match) ? 'key' : 'string';
        else if (/true|false/.test(match)) cls = 'boolean';
        else if (/null/.test(match)) cls = 'null';
        return `<span class="${cls}">${match}</span>`;
    });
}

function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `<i data-lucide="check-circle"></i> ${message}`;
    document.body.appendChild(toast);
    lucide.createIcons();
    setTimeout(() => toast.classList.add('show'), 100);
    setTimeout(() => { toast.classList.remove('show'); setTimeout(() => toast.remove(), 300); }, 3000);
}

// ─────────────────────────────────────────────
// 인기 검색어 로드 및 탭 렌더링
// ─────────────────────────────────────────────
function renderPopularTabs(activeDomain) {
    const tabsContainer = document.getElementById('popular-kw-tabs');
    if (!tabsContainer || TOP_LEVEL_CATEGORIES.length === 0) return;
    
    tabsContainer.innerHTML = '';
    
    TOP_LEVEL_CATEGORIES.forEach(domain => {
        const btn = document.createElement('button');
        btn.textContent = domain;
        const isActive = domain === activeDomain;
        
        btn.style.cssText = `
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.8rem;
            cursor: pointer;
            border: 1px solid ${isActive ? 'var(--primary)' : 'rgba(255,255,255,0.1)'};
            background: ${isActive ? 'rgba(88,166,255,0.15)' : 'rgba(255,255,255,0.02)'};
            color: ${isActive ? '#fff' : '#a1a1aa'};
            font-weight: ${isActive ? '600' : '400'};
            transition: all 0.2s ease;
            white-space: nowrap;
        `;
        
        btn.onmouseenter = () => { if(!isActive) btn.style.background = 'rgba(255,255,255,0.08)'; };
        btn.onmouseleave = () => { if(!isActive) btn.style.background = 'rgba(255,255,255,0.02)'; };
        
        btn.addEventListener('click', () => {
            // 다른 분야 클릭 시 독립적으로 업데이트
            if (!isActive) loadPopularKeywords(domain);
        });
        
        tabsContainer.appendChild(btn);
    });
}

async function loadPopularKeywords(domain) {
    const container = document.getElementById('popular-keywords-section');
    const listEl = document.getElementById('popular-kw-list');
    const periodEl = document.getElementById('popular-kw-period');
    
    if (!container || !listEl) return;
    
    // 탭 상태 업데이트
    renderPopularTabs(domain);
    
    try {
        const data = await fetchWithRetry(`${API_BASE_URL}/popular_keywords?domain=${encodeURIComponent(domain)}`, {}, 3, 1000);
        
        
        periodEl.textContent = `조회기간: ${data.period || '-'}`;
        listEl.innerHTML = '';
        
        data.items.forEach(item => {
            const chip = document.createElement('a');
            chip.href = `https://www.coupang.com/np/search?q=${encodeURIComponent(item.keyword)}`;
            chip.target = "_blank";
            chip.style.cssText = `
                display:flex; align-items:center; gap:8px; 
                padding:8px 16px; background:rgba(255,255,255,0.05); 
                border:1px solid rgba(255,255,255,0.1); border-radius:20px; 
                text-decoration:none; color:#e2e8f0; white-space:nowrap;
                transition: background 0.2s, border-color 0.2s;
            `;
            chip.onmouseenter = () => chip.style.background = 'rgba(88,166,255,0.15)';
            chip.onmouseleave = () => chip.style.background = 'rgba(255,255,255,0.05)';
            
            let statusIcon = '<i data-lucide="minus" style="width:14px; color:#aaa;"></i>';
            if (item.trend_status === 'UP') statusIcon = '<i data-lucide="trending-up" style="width:14px; color:#f1c40f;"></i>';
            else if (item.trend_status === 'NEW') statusIcon = '<span style="color:#03c75a; font-size:0.75rem; font-weight:bold;">NEW</span>';
            
            const badgeRank = `<span style="display:inline-block; width:18px; height:18px; line-height:18px; text-align:center; background:#4a4a5a; border-radius:50%; font-size:0.7rem;">${item.rank}</span>`;
            
            chip.innerHTML = `${badgeRank} <span style="font-weight:500;">${item.keyword}</span> ${statusIcon}`;
            listEl.appendChild(chip);
        });
        
        container.style.display = 'block';
        lucide.createIcons();
        
    } catch(e) {
        console.error("Failed to load popular keywords:", e);
        listEl.innerHTML = '<span style="color:#a1a1aa; font-size:0.85rem; padding: 10px;">실시간 트렌드 데이터를 불러오는 중입니다. 잠시만 기다려 주시거나 잠시 후 다시 시도해 주세요.</span>';
        container.style.display = 'block';
    }
}

/**
 * [v2.35] 백엔드에서 실시간 통계(누적 분석 횟수, 주간 Top 분야) 정보를 가져와 화면에 출력합니다.
 */
async function loadSiteStats() {
    const analysisEl = document.getElementById('stat-total-analysis');
    const domainEl = document.getElementById('stat-top-domain');
    
    if (!analysisEl || !domainEl) return;
    
    try {
        const stats = await fetch(`${API_BASE_URL}/stats`).then(res => res.json());
        
        if (stats) {
            // 카운트 애니메이션 효과 (선택사항이나 여기서는 즉시 반영)
            analysisEl.textContent = Number(stats.total_analysis || 0).toLocaleString();
            domainEl.textContent = stats.top_domain || '식품';
        }
    } catch (e) {
        console.error("Failed to load site stats:", e);
    }
}

/**
 * [v2.4] RAPTOR GEM: AI 숏폼 기획안 생성 및 모달 처리
 */
function initRaptorHandlers() {
    const slider = document.getElementById('raptor-duration-slider');
    const valText = document.getElementById('raptor-duration-val');
    const planBtn = document.getElementById('raptor-plan-btn');
    const modal = document.getElementById('raptor-modal');
    const closeModal = document.getElementById('close-raptor-btn');
    const resultContent = document.getElementById('raptor-result-content');
    
    if (!slider || !planBtn) return;

    // 1. 슬라이더 값 실시간 변경 인식 (대표님 피드백 반영: 15~60s)
    slider.addEventListener('input', (e) => {
        valText.textContent = `${e.target.value}s`;
    });

    // 2. AI 기획안 생성 실행
    planBtn.addEventListener('click', async () => {
        if (!currentAppData) {
            alert("먼저 분석을 수행하여 데이터를 생성해 주세요!");
            return;
        }

        const duration = slider.value;
        
        // UI 로딩 상태 시작
        modal.classList.add('active');
        resultContent.innerHTML = `
            <div style="text-align: center; padding: 60px 0;">
                <div class="spinner" style="border-width:4px; width:50px; height:50px; margin: 0 auto 20px;"></div>
                <h3 style="color:var(--primary); font-size:1.2rem; margin-bottom:10px;">RAPTOR GEM AI Reasoning...</h3>
                <p style="color:#888;">Gemini 3.1 Pro (High)가 ${duration}초 분량의 최적화된 기획안을 작성하고 있습니다.</p>
            </div>
        `;

        try {
            const response = await fetch(`${API_BASE_URL}/raptor/generate-plan`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ssps_data: currentAppData,
                    duration: duration
                })
            });

            const result = await response.json();

            if (result.status === 'success' || result.status === 'mock') {
                // 상단 메타 정보 업데이트
                document.getElementById('raptor-res-duration').textContent = `${duration}초`;
                
                // 마크다운 렌더링 (marked.js 활용)
                resultContent.innerHTML = marked.parse(result.planning_document);
                lucide.createIcons();
            } else {
                throw new Error(result.error || "AI 엔진 호출 중 오류가 발생했습니다.");
            }
        } catch (e) {
            resultContent.innerHTML = `
                <div style="padding: 40px; text-align: center; color: #ff4d4f; border: 1px dashed rgba(255,77,79,0.3); border-radius: 12px;">
                    <i data-lucide="alert-triangle" style="width:48px; height:48px; margin-bottom:15px;"></i>
                    <p style="font-weight:600;">기획안 생성 실패</p>
                    <p style="font-size:0.9rem; margin-top:10px;">${e.message}</p>
                </div>
            `;
            lucide.createIcons();
        }
    });

    // 3. 모달 닫기
    closeModal?.addEventListener('click', () => modal.classList.remove('active'));
    
    // 4. 복사 및 인쇄 버튼
    document.getElementById('copy-raptor-btn')?.addEventListener('click', () => {
        const text = resultContent.innerText;
        navigator.clipboard.writeText(text).then(() => showToast("📋 기획안이 클립보드에 복사되었습니다."));
    });

    document.getElementById('print-raptor-btn')?.addEventListener('click', () => {
        window.print();
    });
    // 5. [v2.48] 특정 상품 기반 기획안 생성 헬퍼
    window.triggerRaptorBasic = (encodedProduct) => {
        const product = JSON.parse(decodeURIComponent(encodedProduct));
        const slider = document.getElementById('raptor-duration-slider');
        const planBtn = document.getElementById('raptor-plan-btn');
        
        // 데이터 강제 주입: 전체 데이터가 아닌 클릭한 상품 데이터를 분석 맥락에 포함
        const originalData = currentAppData;
        currentAppData = {
            ...originalData,
            domain: product.title || product.name,
            items: [product], // 단일 상품 기획 모드
            raw_scores: { ...originalData.raw_scores, price_tier: (product.price < 30000 ? "LOWPRICE" : "GENERAL") }
        };
        
        // 모달 열기 및 자동 실행 트리거
        planBtn.click();
        
        // 실행 후 데이터 원복
        setTimeout(() => { currentAppData = originalData; }, 500);
    };
}

