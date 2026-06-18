const fs = require('fs');

// 1. Update src/store/useWorkflowStore.ts
const storeFile = 'src/store/useWorkflowStore.ts';
let storeCode = fs.readFileSync(storeFile, 'utf8');

if (!storeCode.includes('subtitleFont: string;')) {
    storeCode = storeCode.replace(
        /subtitlePosition: string;/g,
        "subtitlePosition: string;\n  subtitleFont: string;"
    );
    storeCode = storeCode.replace(
        /setSubtitlePosition: \(position: string\) => void;/g,
        "setSubtitlePosition: (position: string) => void;\n  setSubtitleFont: (font: string) => void;"
    );
    storeCode = storeCode.replace(
        /subtitlePosition: '하',/g,
        "subtitlePosition: '하',\n      subtitleFont: 'BlackHanSans',"
    );
    storeCode = storeCode.replace(
        /setSubtitlePosition: \(subtitlePosition\) => set\(\{ subtitlePosition \}\),/g,
        "setSubtitlePosition: (subtitlePosition) => set({ subtitlePosition }),\n      setSubtitleFont: (subtitleFont) => set({ subtitleFont }),"
    );
    storeCode = storeCode.replace(
        /subtitlePosition: state\.subtitlePosition,/g,
        "subtitlePosition: state.subtitlePosition,\n          subtitleFont: state.subtitleFont,"
    );
    fs.writeFileSync(storeFile, storeCode);
    console.log('Updated useWorkflowStore.ts');
}

// 2. Update src/components/RaptorWorkflow.tsx
const raptorFile = 'src/components/RaptorWorkflow.tsx';
let raptorCode = fs.readFileSync(raptorFile, 'utf8');

// Update step arrays
raptorCode = raptorCode.replace(
    /\{\[0, 1, 2, 3, 4\]\.map\(\(s\) => \(/g,
    '{[0, 1, 2, 3, 4, 5].map((s) => ('
);

raptorCode = raptorCode.replace(
    /s === 0 \? '시작 모드' : s === 1 \? '기본 설정' : s === 2 \? '분석 리포트' : s === 3 \? '에셋 확정' : '렌더링'/g,
    "s === 0 ? '시작 모드' : s === 1 ? '기본 설정' : s === 2 ? '분석 리포트' : s === 3 ? '이미지 생성' : s === 4 ? '비디오 생성' : '최종 렌더링'"
);

// Add subtitle font to API request
raptorCode = raptorCode.replace(
    /subtitle_position: subtitlePosition,/g,
    "subtitle_position: subtitlePosition,\n        subtitle_font: store.subtitleFont,"
);

// Add subtitle font UI selector
const subtitleUI = `<div className="space-y-4 bg-white/5 p-6 rounded-2xl border border-white/10">
                <div className="flex items-center gap-2 mb-4">
                  <Type className="w-5 h-5 text-purple-400" />
                  <h3 className="font-bold text-white">자막 폰트</h3>
                </div>
                <select
                  value={store.subtitleFont}
                  onChange={(e) => store.setSubtitleFont(e.target.value)}
                  className="w-full bg-black/40 border border-white/10 rounded-xl p-4 text-white"
                >
                  <option value="BlackHanSans">강렬한 강조체 (Black Han Sans)</option>
                  <option value="NotoSansKR">깔끔한 고딕체 (Noto Sans KR)</option>
                  <option value="NanumGothic">부드러운 고딕체 (Nanum Gothic)</option>
                </select>
              </div>`;

if (!raptorCode.includes('store.subtitleFont')) {
    // find a place to insert the UI, near subtitle position
    const subtitlePosUI = /<div className="flex items-center gap-2 mb-4">\s*<Type className="w-5 h-5 text-purple-400" \/>\s*<h3 className="font-bold text-white">자막 위치<\/h3>\s*<\/div>/;
    
    // We can insert it before or after subtitle position div. Let's insert before subtitle position block.
    // The subtitle position block starts with <div className="space-y-4 bg-white/5 p-6 rounded-2xl border border-white/10">
    const posBlockStartRegex = /<div className="space-y-4 bg-white\/5 p-6 rounded-2xl border border-white\/10">\s*<div className="flex items-center gap-2 mb-4">\s*<Type className="w-5 h-5 text-purple-400" \/>\s*<h3 className="font-bold text-white">자막 위치<\/h3>/;
    
    raptorCode = raptorCode.replace(posBlockStartRegex, subtitleUI + "\n              <div className=\"space-y-4 bg-white/5 p-6 rounded-2xl border border-white/10\">\n                <div className=\"flex items-center gap-2 mb-4\">\n                  <Type className=\"w-5 h-5 text-purple-400\" />\n                  <h3 className=\"font-bold text-white\">자막 위치</h3>");
    fs.writeFileSync(raptorFile, raptorCode);
    console.log('Updated RaptorWorkflow.tsx');
}

// 3. Update main.py
const mainFile = 'main.py';
let mainCode = fs.readFileSync(mainFile, 'utf8');

if (!mainCode.includes('subtitle_font: str = "BlackHanSans"')) {
    mainCode = mainCode.replace(
        /subtitle_position: str = "하"/g,
        'subtitle_position: str = "하"\n    subtitle_font: str = "BlackHanSans"'
    );
    mainCode = mainCode.replace(
        /subtitle_position=request\.subtitle_position,/g,
        'subtitle_position=request.subtitle_position,\n                subtitle_font=request.subtitle_font,'
    );
    fs.writeFileSync(mainFile, mainCode);
    console.log('Updated main.py');
}

// 4. Update backend/services/ffmpeg_worker.py
const ffmpegFile = 'backend/services/ffmpeg_worker.py';
let ffmpegCode = fs.readFileSync(ffmpegFile, 'utf8');

if (!ffmpegCode.includes('subtitle_font: str = "BlackHanSans"')) {
    ffmpegCode = ffmpegCode.replace(
        /rendering_mode: str = "full"\):/g,
        'rendering_mode: str = "full", subtitle_font: str = "BlackHanSans"):'
    );

    // Ensure _ensure_font exists
    const ensureFontFunc = `
    async def _ensure_font(self, font_id: str):
        font_map = {
            "BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
            "NotoSansKR": "https://github.com/google/fonts/raw/main/ofl/notosanskr/NotoSansKR-Bold.ttf",
            "NanumGothic": "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf"
        }
        url = font_map.get(font_id, font_map["BlackHanSans"])
        filename = url.split("/")[-1]
        
        # Save fonts in a stable cache directory
        import os
        cache_dir = os.path.join(os.getcwd(), "fonts_cache")
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
            
        font_path = os.path.join(cache_dir, filename)
        if not os.path.exists(font_path) or os.path.getsize(font_path) < 1000:
            import httpx
            try:
                print(f"[FONT] Downloading {filename} from {url}...")
                async with httpx.AsyncClient() as client:
                    res = await client.get(url, timeout=30.0, follow_redirects=True)
                    if res.status_code == 200:
                        with open(font_path, "wb") as f:
                            f.write(res.content)
                        print(f"[FONT] Downloaded {filename} successfully.")
                    else:
                        print(f"[FONT] Download failed with status {res.status_code}")
            except Exception as e:
                print(f"[FONT ERROR] Failed to download {font_id}: {e}")
                
        # Fallback
        if not os.path.exists(font_path) or os.path.getsize(font_path) < 1000:
            import platform
            system_name = platform.system().lower()
            if os.name == 'nt' or 'windows' in system_name:
                return "C:/Windows/Fonts/malgun.ttf".replace(":", "\\\\:")
            else:
                return "DejaVu Sans"
                
        return os.path.abspath(font_path).replace("\\\\", "/").replace(":", "\\\\:")
`;
    ffmpegCode = ffmpegCode.replace(
        /async def _check_output\(self, cmd, \*\*kwargs\):/,
        ensureFontFunc + '\n    async def _check_output(self, cmd, **kwargs):'
    );

    // Replace the old RISK-003 font logic
    const oldFontLogicRegex = /# RISK-003: 크로스 플랫폼 폰트 경로 동적 매핑 \(리눅스 크래시 및 CJK 깨짐 방어\)[\s\S]*?font_path = .*?\.replace\(":", "\\\\:"\)/;
    const newFontLogic = `# Dynamic OFL Font Download & Cache
                    font_path = await self._ensure_font(subtitle_font)`;
    
    ffmpegCode = ffmpegCode.replace(oldFontLogicRegex, newFontLogic);
    
    fs.writeFileSync(ffmpegFile, ffmpegCode);
    console.log('Updated ffmpeg_worker.py');
}
