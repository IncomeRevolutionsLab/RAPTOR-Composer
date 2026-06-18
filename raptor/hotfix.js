const fs = require('fs');
const path = require('path');

const ffmpegFile = 'backend/services/ffmpeg_worker.py';
let ffmpegCode = fs.readFileSync(ffmpegFile, 'utf8');

// 1. Fix BUG-M2 and BUG-M3 in _ensure_font
const oldCacheStr = `        import os
        cache_dir = os.path.join(os.getcwd(), "fonts_cache")
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
            
        font_path = os.path.join(cache_dir, filename)
        if not os.path.exists(font_path) or os.path.getsize(font_path) < 1000:`;

const newCacheStr = `        import os
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../fonts_cache")
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
            
        font_path = os.path.join(cache_dir, filename)
        if not os.path.exists(font_path) or os.path.getsize(font_path) < 20000:`;
ffmpegCode = ffmpegCode.replace(oldCacheStr, newCacheStr);

// 2. Fix BUG-H1 and BUG-M3 (fallback part) in _ensure_font
const oldFallbackStr = `        # Fallback
        if not os.path.exists(font_path) or os.path.getsize(font_path) < 1000:
            import platform
            system_name = platform.system().lower()
            if os.name == 'nt' or 'windows' in system_name:
                return "C:/Windows/Fonts/malgun.ttf".replace(":", "\\\\:")
            else:
                return "DejaVu Sans"`;

const newFallbackStr = `        # Fallback
        if not os.path.exists(font_path) or os.path.getsize(font_path) < 20000:
            import platform
            system_name = platform.system().lower()
            if os.name == 'nt' or 'windows' in system_name:
                return "C:/Windows/Fonts/malgun.ttf".replace(":", "\\\\:")
            else:
                candidates = [
                    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                ]
                for c in candidates:
                    if os.path.exists(c):
                        return c.replace(":", "\\\\:")
                return "DejaVu Sans"`;
ffmpegCode = ffmpegCode.replace(oldFallbackStr, newFallbackStr);

// 3. Fix BUG-C1 (remove dangling else block)
const oldElseBlock = `                    # Dynamic OFL Font Download & Cache
                    font_path = await self._ensure_font(subtitle_font)
                    else:
                        font_candidates = [
                            # 1. Nanum Gothic
                            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                            "/usr/share/fonts/nanum/NanumGothic.ttf",
                            "/usr/share/fonts/NanumGothic.ttf",
                            # 2. Noto Sans CJK
                            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                            "/usr/share/fonts/noto/NotoSansCJK-Regular.ttc",
                            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                            "/usr/share/fonts/NotoSansCJK-Regular.ttc",
                            # 3. Un Dotum
                            "/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf",
                            "/usr/share/fonts/unfonts-core/UnDotum.ttf",
                            "/usr/share/fonts/UnDotum.ttf",
                            # 4. DejaVu Sans (Latin fallback)
                            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                            # 5. Liberation Sans (Latin fallback)
                            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
                        ]
                        selected_font = None
                        for candidate in font_candidates:
                            if os.path.exists(candidate):
                                selected_font = candidate.replace(":", "\\\\:")
                                break
                        if selected_font:
                            font_path = selected_font
                        else:
                            font_path = "DejaVu Sans"
                    safe_text_file_path = os.path.abspath(text_file_path).replace("\\\\", "/").replace(":", "\\\\:")`;

const newElseBlock = `                    # Dynamic OFL Font Download & Cache
                    font_path = await self._ensure_font(subtitle_font)
                    safe_text_file_path = os.path.abspath(text_file_path).replace("\\\\", "/").replace(":", "\\\\:")`;
ffmpegCode = ffmpegCode.replace(oldElseBlock, newElseBlock);

fs.writeFileSync(ffmpegFile, ffmpegCode);

// 4. Fix BUG-M1 in RaptorWorkflow.tsx
const raptorFile = 'src/components/RaptorWorkflow.tsx';
let raptorCode = fs.readFileSync(raptorFile, 'utf8');

// Step indicator says 6 steps, but setStep(5) is never called.
// Where is setStep(4) called? We will just change step < 4 to step < 5 or something, or better yet, revert the UI to 5 steps since there is no step 5 UI!
// Wait, the user literally asked for 6 steps. Let's find where render is done.
// In handleRender(), it does setStep(4) and starts rendering.
// When it finishes, it sets isRendering(false). We can setStep(5) there!
if (!raptorCode.includes('setStep(5)')) {
    // In handleRender, after the polling loop succeeds:
    // setRenderStatus("success");
    // setRenderedVideoUrl(resultData.result_url || "");
    // => add setStep(5);
    raptorCode = raptorCode.replace(
        /setRenderStatus\("success"\);\s*setRenderedVideoUrl\(resultData\.result_url \|\| ""\);/g,
        'setRenderStatus("success");\n        setRenderedVideoUrl(resultData.result_url || "");\n        setStep(5);'
    );
    fs.writeFileSync(raptorFile, raptorCode);
}

// 5. Fix BUG-M4 in useWorkflowStore.ts
const storeFile = 'src/store/useWorkflowStore.ts';
let storeCode = fs.readFileSync(storeFile, 'utf8');
storeCode = storeCode.replace(
    /subtitleFont: string; \/\/ Added for subtitle position control/g,
    'subtitleFont: string; // Subtitle font selection for OFL pipeline'
);
fs.writeFileSync(storeFile, storeCode);

console.log("All fixes applied via node script");
