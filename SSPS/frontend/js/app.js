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

function resetToHome() {
    showPanels('main-3d-chart-container', 'search-panel-section');
    document.getElementById('domain-input').value = '';
    document.getElementById('submit-btn').disabled = false;
    lucide.createIcons();
}

// ─────────────────────────────────────────────
// 근본 통합 라우터 및 유틸리티
// ─────────────────────────────────────────────

async function fetchWithRetry(url, options = {}, retries = 3, delay = 1000) {
    for (let i = 0; i < retries; i++) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(new Error("Request Timeout")), 60000); 
        try {
            const separator = url.includes('?') ? '&' : '?';
            const cacheBustUrl = `${url}${separator}t=${Date.now()}`;
            const res = await fetch(cacheBustUrl, { ...options, signal: controller.signal });
            clearTimeout(timeoutId);
            if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
            return await res.json();
        } catch (e) {
            clearTimeout(timeoutId);
            if (i === retries - 1) throw e;
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
}

async function loadCategoryNode(payload) {
    if (!payload || (!payload.path && !payload.keyword)) return;
    showPanels('loading-state');
    simulateLoadingSteps();
    try {
        const manualOlive = document.getElementById('manual_oliveyoung')?.value || "";
        const manualDaiso = document.getElementById('manual_daiso')?.value || "";
        const data = await fetchWithRetry(`${API_BASE_URL}/category_node`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ ...payload, manual_olive: manualOlive, manual_daiso: manualDaiso })
        });
        setTimeout(() => {
            if (data.is_leaf) renderPhase2(data, data.path || [payload.keyword]);
            else renderPhase1(data, data.path || [payload.keyword]);
            currentAppData = data;
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
    renderPhase1TrendChart(data.trend_series);
    const grid = document.getElementById('p1-cards-grid');
    grid.innerHTML = '';
    const rankColors = ['#f1c40f','#a1a1aa','#cd7f32'];
    (data.ranking || []).forEach((item, idx) => {
        const card = document.createElement('div');
        card.className = 'glass-card';
        card.style.cssText = `padding:20px; border-radius:12px; cursor:pointer; text-align:center; border:2px solid transparent; transition:all 0.25s; position:relative; overflow:hidden;`;
        card.innerHTML = `
            <div style="font-size:1.4rem; font-weight:800; color:${rankColors[idx] || '#7d8590'}; margin-bottom:8px;">${idx + 1}위</div>
            <div style="font-size:1.1rem; font-weight:600; color:#e2e8f0; margin-bottom:10px;">${item.name}</div>
            <div style="font-size:1.5rem; font-weight:700; color:var(--primary); margin-top:4px;">${item.avg_score}</div>
        `;
        card.addEventListener('click', () => loadCategoryNode({path: [...pathArray, item.name]}));
        grid.appendChild(card);
    });
    lucide.createIcons();
}

function renderPhase1TrendChart(trendSeries) {
    const container = document.getElementById('p1-trend-chart');
    if (!container) return;
    if (p1TrendChartInstance) p1TrendChartInstance.dispose();
    p1TrendChartInstance = echarts.init(container);
    const colors = ['#58a6ff','#3fb950','#f1c40f'];
    p1TrendChartInstance.setOption({
        tooltip: {trigger:'axis'},
        legend: {data: (trendSeries.series||[]).map(s=>s.name), textStyle:{color:'#a1a1aa'}, bottom:0},
        xAxis: {type:'category', boundaryGap:false, data: trendSeries.categories || [], axisLabel:{color:'#888'}},
        yAxis: {type:'value', min:0, max:100, axisLabel:{color:'#888'}, splitLine:{lineStyle:{color:'rgba(255,255,255,0.05)'}}},
        series: (trendSeries.series||[]).map((s,i)=>({name:s.name, type:'line', smooth:true, data:s.data, lineStyle:{width:3, color:colors[i]}}))
    });
}

function renderPhase2(data, pathArray) {
    showPanels('phase2-state');
    renderBreadcrumbs('p2-breadcrumb-container', pathArray);
    const finalTerm = (pathArray && pathArray.length > 0 ? pathArray[pathArray.length - 1] : (data.search_query || "상품"));
    document.getElementById('p2-title').textContent = `[${finalTerm}] 분석 결과`;
    const productGrid = document.getElementById('p2-product-grid');
    productGrid.innerHTML = '';
    (data.products || []).forEach(product => {
        const card = document.createElement('div');
        card.className = 'sku-card';
        card.innerHTML = `
            <div style="display:flex; flex-direction:row; width:100%;">
                <img src="${product.image_url}" class="sku-img" style="width:80px;height:80px;">
                <div class="sku-info" style="flex:1; padding-left:15px;">
                    <div class="sku-title">${product.title}</div>
                    <div class="sku-price">₩${(product.price || 0).toLocaleString()}</div>
                    <button class="btn-primary" style="margin-top:10px; font-size:0.7rem;" onclick="window.triggerRaptorBasic('${encodeURIComponent(JSON.stringify(product))}')">RAPTOR 기획</button>
                </div>
            </div>
        `;
        productGrid.appendChild(card);
    });
    lucide.createIcons();
}

// ─────────────────────────────────────────────
// 초기화 및 부팅 로직 (v3.19)
// ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('analyze-form');
    const input = document.getElementById('domain-input');
    form?.addEventListener('submit', (e) => {
        e.preventDefault();
        const domain = input.value.trim();
        if (domain) loadCategoryNode(TOP_LEVEL_CATEGORIES.includes(domain) ? {path: [domain]} : {keyword: domain});
    });

    document.querySelectorAll('.chip-btn').forEach(chip => {
        chip.addEventListener('click', (e) => loadCategoryNode({path: [e.target.getAttribute('data-val')]}));
    });

    // 실시간 시스템 텔레메트리 (디버그 모니터 보고용)
    const updateDebug = (msg) => {
        const el = document.getElementById('debug-status');
        if (el) el.innerHTML = `> ${msg}`;
        console.log(`[DEBUG] ${msg}`);
    };
    window.sspsDebug = updateDebug;

    updateDebug("System core initialized.");

    setTimeout(() => { updateDebug("Keywords loading..."); loadPopularKeywords("패션의류"); }, 100);
    setTimeout(() => { updateDebug("Stats loading..."); loadSiteStats(); }, 400);
    setTimeout(() => {
        updateDebug("Initializing 3D Chart...");
        if (typeof echarts === 'undefined') { updateDebug("CRITICAL: ECharts missing!"); return; }
        initMain3DChart();
    }, 800);
});

function initMain3DChart() {
    const containers = [1,2,3].map(i => document.getElementById(`main-3d-chart-${i}`));
    if (containers.some(c => !c)) return;
    const charts = containers.map(c => echarts.init(c));
    const trendUrl = `${API_BASE_URL}/domains/trend?t=${Date.now()}`;
    
    window.sspsDebug("Step 6: Hardcoded Test Phase...");
    
    fetch(trendUrl).then(r => r.json()).then(json => {
        if (json.status !== 'success') throw new Error('API Fail');
        
        // [v3.21] 정밀 데이터 관측
        const monthsCount = json.months ? json.months.length : 0;
        const catsCount = json.categories ? json.categories.length : 0;
        window.sspsDebug(`Data: ${json.data.length} rows, Months: ${monthsCount}, Cats: ${catsCount}`);

        [0, 4, 8].forEach((start, idx) => {
            const slicedCats = json.categories.slice(start, start + 4);
            const filtered = json.data.filter(item => item[1] >= start && item[1] < start + 4).map(item => [item[0], item[1]-start, item[2]]);
            
            if (idx === 0) {
                // 1번 차트에만 "6단계: 하드코딩 테스트" 적용
                const mockData = [[0, 0, 100], [1, 1, 80], [2, 2, 60], [3, 3, 40]];
                window.sspsDebug("Chart1: Injecting mock data...");
                render3DChart(charts[idx], slicedCats, json.months, mockData);
            } else {
                render3DChart(charts[idx], slicedCats, json.months, filtered);
            }
            charts[idx].hideLoading();
        });
        window.sspsDebug("Check Chart 1 visibility.");
        setTimeout(() => charts.forEach(c => c.resize()), 200);
    }).catch(e => { window.sspsDebug(`!! Error: ${e.message}`); });
}

function render3DChart(myChart, categories, months, data) {
    try {
        myChart.setOption({
            backgroundColor: 'transparent',
            tooltip: { show: true, formatter: p => `[${categories[p.value[1]]}]<br>${months[p.value[0]]}: <b>${p.value[2]}</b>` },
            visualMap: {
                show: true, min: 0, max: 100,
                inRange: { color: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'] },
                textStyle: { color: '#a1a1aa' }, bottom: '5%'
            },
            xAxis3D: { type: 'category', data: months, name: '월', axisLabel: { textStyle: { color: '#888' } } },
            yAxis3D: { type: 'category', data: categories, name: '분류', axisLabel: { textStyle: { color: '#888' } } },
            zAxis3D: { type: 'value', name: '지수', axisLabel: { textStyle: { color: '#888' } } },
            grid3D: {
                boxWidth: 200, boxDepth: 100, boxHeight: 80,
                viewControl: { projection: 'perspective', autoRotate: false, alpha: 30, beta: 30 },
                light: {
                    main: { intensity: 1.5, shadow: true, alpha: 40, beta: 40 },
                    ambient: { intensity: 0.5 }
                },
                postEffect: { enable: false }
            },
            series: [{
                type: 'bar3D', data: data,
                shading: 'lambert',
                label: { show: false },
                emphasis: { label: { show: true, textStyle: { fontSize: 16, color: '#fff' } } }
            }]
        });
        window.sspsDebug("Chart drawing command sent.");
    } catch (e) {
        window.sspsDebug(`!! Render Fail: ${e.message}`);
        console.error("3D Fail:", e);
    }
    window.addEventListener('resize', () => myChart.resize());
}

async function loadPopularKeywords(domain) {
    window.sspsDebug(`Keywords: fetching ${domain}...`);
    const listEl = document.getElementById('popular-kw-list');
    if (!listEl) return;
    try {
        const data = await fetchWithRetry(`${API_BASE_URL}/popular_keywords?domain=${encodeURIComponent(domain)}`);
        listEl.innerHTML = '';
        data.items.forEach(item => {
            const chip = document.createElement('a');
            chip.style.cssText = `display:inline-block; padding:6px 14px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); border-radius:20px; text-decoration:none; color:#e2e8f0; margin:4px; font-size:0.8rem;`;
            chip.innerHTML = `${item.rank}. ${item.keyword}`;
            listEl.appendChild(chip);
        });
    } catch(e) { console.error(e); }
}

async function loadSiteStats() {
    try {
        const stats = await fetch(`${API_BASE_URL}/stats`).then(res => res.json());
        if (stats) {
            document.getElementById('stat-total-analysis').textContent = (stats.total_analysis || 0).toLocaleString();
            document.getElementById('stat-top-domain').textContent = stats.top_domain || '식품';
        }
    } catch (e) { console.error(e); }
}

function simulateLoadingSteps() {
    const steps = [1,2,3,4].map(n => document.getElementById(`step-${n}`));
    steps.forEach(s => { if(s) s.className = 'pending'; });
    if (steps[0]) steps[0].className = 'active';
    [600,1200,2000].forEach((t,i) => {
        setTimeout(() => {
            if (steps[i]) { steps[i].className = 'done'; steps[i].textContent += ' 완료'; }
            if (steps[i+1]) steps[i+1].className = 'active';
        }, t);
    });
}

window.triggerRaptorBasic = (encodedProduct) => { window.location.href = `raptor.html?product=${encodedProduct}`; };
function showToast(m) { alert(m); } // Simple toast for now
