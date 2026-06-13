// UI Elements
const unifiedStartBtn = document.getElementById('unifiedStartBtn');
const mainVideoId = document.getElementById('mainVideoId');
const apiKeyInput = document.getElementById('apiKeyInput');
const progressSection = document.getElementById('progressSection');
const progressBar = document.getElementById('progressBar');
const collectedCount = document.getElementById('collectedCount');
const videoTitle = document.getElementById('videoTitle');
const aiSummary = document.getElementById('aiSummary');
const aiScore = document.getElementById('aiScore');
const topCommentsBody = document.getElementById('topCommentsBody');
const keywordCloud = document.getElementById('keywordCloud');
const snaContainer = document.getElementById('snaContainer');
const detectionList = document.getElementById('detectionList');

// Charts
let sentimentChart = null;
let temporalChart = null;
let dayChart = null;

function initCharts() {
    const ctxSenti = document.getElementById('sentimentChart').getContext('2d');
    sentimentChart = new Chart(ctxSenti, {
        type: 'doughnut',
        data: {
            labels: ['Positive', 'Neutral', 'Negative'],
            datasets: [{
                data: [0, 100, 0],
                backgroundColor: ['#10b981', '#334155', '#ef4444'],
                borderWidth: 0
            }]
        },
        options: { cutout: '80%', plugins: { legend: { display: false } } }
    });

    const ctxTemp = document.getElementById('temporalChart').getContext('2d');
    temporalChart = new Chart(ctxTemp, {
        type: 'bar',
        data: {
            labels: Array.from({length: 24}, (_, i) => `${i}h`),
            datasets: [
                { label: 'Main Comments', data: Array(24).fill(0), backgroundColor: '#38bdf8', borderRadius: 5 },
                { label: 'Replies', data: Array(24).fill(0), backgroundColor: 'rgba(56, 189, 248, 0.3)', borderRadius: 5 }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } },
            plugins: { legend: { display: false } }
        }
    });

    const ctxDay = document.getElementById('dayChart').getContext('2d');
    dayChart = new Chart(ctxDay, {
        type: 'bar',
        data: {
            labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            datasets: [{ label: 'Activity', data: Array(7).fill(0), backgroundColor: '#818cf8', borderRadius: 10 }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
    });
}

function resetDashboard() {
    // Reset Progress
    progressBar.style.width = '0%';
    collectedCount.innerText = "0 / 0 collected";
    videoTitle.innerText = "비디오 분석 준비 중...";
    document.getElementById('currentStatus').innerText = "RUNNING";
    document.getElementById('phaseInfo').innerText = "Phase: Initializing...";
    
    // Reset Insights
    aiSummary.innerText = "분석 엔진 가동 중... 잠시만 기다려 주세요.";
    aiScore.innerText = "0";
    
    // Reset Charts
    if (sentimentChart) {
        sentimentChart.data.datasets[0].data = [0, 100, 0];
        sentimentChart.update();
    }
    
    // Reset Tables & Lists
    topCommentsBody.innerHTML = '<tr><td colspan="4" style="text-align:center;">데이터 수집 중...</td></tr>';
    keywordCloud.innerHTML = '분석 후 키워드가 추출됩니다.';
    snaContainer.innerHTML = '';
    detectionList.innerHTML = '<li>분석 진행 중...</li>';
}

async function startUnifiedAnalysis() {
    const rawId = mainVideoId.value.trim();
    if (!rawId) return;

    resetDashboard();
    // Clear input after starting as per user request
    mainVideoId.value = '';
    
    progressSection.style.display = 'block';
    unifiedStartBtn.disabled = true;
    
    try {
        const startRes = await fetch('/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_id: rawId, api_key: apiKeyInput.value })
        });
        const startData = await startRes.json();
        const vId = startData.video_id;

        // Trigger Analysis
        fetch('/analysis/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_id: vId, api_key: apiKeyInput.value })
        });

        const poll = setInterval(async () => {
            try {
                // 1. Check Collection Status
                const statusRes = await fetch(`/status?video_id=${vId}`);
                const statusData = await statusRes.json();
                
                if (statusData.checkpoint) {
                    const total = statusData.checkpoint.total_collected || 0;
                    const target = statusData.checkpoint.total_count || 1;
                    const percent = Math.min(100, (total / target) * 100);
                    progressBar.style.width = `${percent}%`;
                    collectedCount.innerText = `${total.toLocaleString()} / ${target.toLocaleString()} collected`;
                    videoTitle.innerText = statusData.checkpoint.video_title;
                    
                    if (statusData.checkpoint.status === "completed") {
                        document.getElementById('phaseInfo').innerText = "Phase: Collection Finished. Analyzing...";
                    } else if (statusData.checkpoint.status === "running") {
                        document.getElementById('phaseInfo').innerText = "Phase: Collecting Comments & Replies...";
                    }

                    if (statusData.checkpoint.error) {
                        aiSummary.innerText = "Error: " + statusData.checkpoint.error;
                        clearInterval(poll);
                        finishUI();
                        return;
                    }
                }

                // 2. Check Analysis Results & Stage
                const resultsRes = await fetch(`/analysis/results?video_id=${vId}`);
                if (resultsRes.ok) {
                    const resultsData = await resultsRes.json();
                    updateDashboard(resultsData);
                    
                    if (resultsData.status) {
                        const statusMap = {
                            "preprocessing": "Phase: Loading data to Database...",
                            "analyzing": "Phase: Sentiment & Keyword Analysis (NLP)...",
                            "finalizing": "Phase: Generating AI Summary & Statistics...",
                            "completed": "Phase: All Analysis Completed."
                        };
                        if (statusMap[resultsData.status]) {
                            document.getElementById('phaseInfo').innerText = statusMap[resultsData.status];
                        }
                    }

                    // Termination: is not running AND results are finalized (not default msg)
                    if (statusData.server_status.is_running === false && 
                        resultsData.status === "completed" || 
                        (resultsData.insight !== "AI 요약 대기 중..." && statusData.server_status.is_running === false)) {
                        clearInterval(poll);
                        finishUI();
                        document.getElementById('currentStatus').innerText = "COMPLETED";
                        document.getElementById('phaseInfo').innerText = "Phase: Finished.";
                    }
                }
            } catch (err) { console.error(err); }
        }, 2000);
    } catch (e) {
        unifiedStartBtn.disabled = false;
        console.error("Start Error:", e);
    }
}

function finishUI() {
    unifiedStartBtn.disabled = false;
    document.getElementById('loadingSpinner').style.display = 'none';
}

function updateDashboard(data) {
    if (!data) return;

    // 1. Sentiment
    if (data.sentiment_distribution) {
        const d = data.sentiment_distribution;
        const total = (d.positive || 0) + (d.neutral || 0) + (d.negative || 0);
        if (total > 0) {
            sentimentChart.data.datasets[0].data = [d.positive, d.neutral, d.negative];
            sentimentChart.update();
            document.getElementById('statPos').innerText = `${Math.round((d.positive/total)*100)}%`;
            document.getElementById('posCount').innerText = d.positive;
            document.getElementById('neuCount').innerText = d.neutral;
            document.getElementById('negCount').innerText = d.negative;
        }
    }

    if (data.insight) aiSummary.innerText = data.insight;
    if (data.ai_score) aiScore.innerText = data.ai_score;

    if (data.temporal) {
        temporalChart.data.datasets[0].data = data.temporal.comments;
        temporalChart.data.datasets[1].data = data.temporal.replies;
        temporalChart.update();
    }

    if (data.temporal_day) {
        dayChart.data.datasets[0].data = data.temporal_day;
        dayChart.update();
    }

    if (data.top_comments && data.top_comments.length > 0) {
        topCommentsBody.innerHTML = data.top_comments.map(c => `
            <tr>
                <td><small>${c.author_name}</small></td>
                <td class="content-cell">${c.content}</td>
                <td><strong class="accent">${c.like_count}</strong></td>
                <td><span class="badge ${c.is_reply ? 'reply' : 'main'}">${c.is_reply ? 'Reply' : 'Main'}</span></td>
            </tr>
        `).join('');
    }

    if (data.keywords) {
        const maxCount = Math.max(...data.keywords.map(k => k[1])) || 1;
        keywordCloud.innerHTML = data.keywords.map(([word, count]) => {
            const size = 0.8 + (count / maxCount) * 1.2;
            return `<span class="tag" style="font-size: ${size}rem">${word}</span>`;
        }).join('');
    }

    if (data.top_posters) {
        detectionList.innerHTML = data.top_posters.map(p => `
            <li><span>${p.author_name}</span><strong>${p.cnt} posts</strong></li>
        `).join('');
    }
}

unifiedStartBtn.addEventListener('click', startUnifiedAnalysis);
window.onload = initCharts;
