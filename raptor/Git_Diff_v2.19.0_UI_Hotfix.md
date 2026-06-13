```diff
diff --git a/src/components/RaptorWorkflow.tsx b/src/components/RaptorWorkflow.tsx
index current..modified
--- a/src/components/RaptorWorkflow.tsx
+++ b/src/components/RaptorWorkflow.tsx
@@ -1481,7 +1481,7 @@
                                   const file = e.target.files?.[0];
                                   if (file) {
                                     if (!file.type.startsWith('video/')) {
-                                      alert("MP4 비디오 업로드 실패. 파일 타입을 확인하세요.");
+                                      alert("비디오 파일만 업로드 가능합니다.");
                                       return;
                                     }
@@ -1551,7 +1551,7 @@
                               const file = e.target.files?.[0];
                               if (file) {
                                 if (!file.type.startsWith('video/')) {
-                                  alert("MP4 비디오 업로드 실패. 파일 타입을 확인하세요.");
+                                  alert("비디오 파일만 업로드 가능합니다.");
                                   return;
                                 }
@@ -1647,7 +1647,7 @@
                         <label className="flex items-center gap-2 cursor-pointer bg-black/40 px-3 py-1.5 rounded-xl border border-white/10 hover:bg-white/5 transition-colors">
                           <input 
                             type="checkbox"
                             checked={scene.use_image_only || false}
@@ -1649,7 +1649,7 @@
                           />
                           <span className="text-[10px] text-gray-300 font-bold">
-                            🖼️ 스틸컷으로 렌더링 (비디오 생성 안 함)
+                            🖼️ 스틸컷 유지 (비디오 생성 안 함)
                           </span>
@@ -1715,7 +1715,7 @@
                         : 'bg-gray-800 text-gray-500 cursor-not-allowed border border-white/5 opacity-50 pointer-events-none'
                     }`}
                   >
-                    <span>🎬 비디오 생성/렌더링 단계로 이동 (Step 4)</span>
+                    <span>🎬 비디오 생성 단계로 이동 (Step 4)</span>
                   </button>
@@ -1728,7 +1728,7 @@
         <div className="animate-in fade-in slide-in-from-bottom-4 space-y-8">
           <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
             <div className="space-y-1">
-              <h2 className="text-3xl font-black text-white whitespace-nowrap">4단계: 최종 비디오 렌더링 및 모니터</h2>
+              <h2 className="text-3xl font-black text-white whitespace-nowrap">4단계: 비디오 클립 생성 및 모니터</h2>
               <p className="text-xs text-gray-500 tracking-widest flex items-center gap-2">
@@ -1753,7 +1753,7 @@
               const totalScenes = script.length || 0;
               const completedImages = script.filter((s: any) => s.image_url).length;
               const hasImageError = script.some((s: any) => s.status === 'error');
-              const completedVideos = script.filter((s: any) => s.video_url).length;
+              const completedVideos = script.filter((s: any) => s.video_url || s.use_image_only).length;
 
               const stage1Status = analysis ? 'success' : 'error';
@@ -1910,13 +1910,25 @@
-              <div className="w-full">
-                <button 
-                  onClick={() => handleRenderVideo()} 
-                  disabled={isRendering} 
-                  className="..."
-                >
-                  ...
-                </button>
+              <div className="w-full space-y-4">
+                {completedImages === totalScenes && completedVideos < totalScenes && (
+                  <button 
+                    onClick={() => handleGenerateClips()} 
+                    disabled={isRendering || loading} 
+                    className="w-full bg-blue-600/20 border border-blue-500/30 text-blue-300 py-3 px-6 rounded-2xl font-bold text-xs uppercase tracking-widest flex items-center justify-center gap-2 hover:bg-blue-600/30 hover:border-blue-500/50 transition-all shadow-lg active:scale-[0.98] disabled:opacity-50"
+                  >
+                    {loading && !isRendering ? (
+                      <><Loader2 className="w-4 h-4 animate-spin text-blue-300" /> <span>클립 생성 중...</span></>
+                    ) : (
+                      <><Film className="w-5 h-5" /> <span>비디오 클립 생성 시작 (Step 4)</span></>
+                    )}
+                  </button>
+                )}
+
+                {completedVideos === totalScenes && totalScenes > 0 && (
+                  <button 
+                    onClick={() => handleRenderFinal()} 
+                    disabled={isRendering || loading || !(finalAssets?.script && finalAssets.script.every((s: any) => s.video_url || s.use_image_only))} 
+                    className="w-full bg-emerald-600/20 border border-emerald-500/30 text-emerald-300 py-3 px-6 rounded-2xl font-bold text-xs uppercase tracking-widest flex items-center justify-center gap-2 hover:bg-emerald-600/30 hover:border-emerald-500/50 transition-all shadow-lg active:scale-[0.98] disabled:opacity-50"
+                  >
+                    ...
+                  </button>
+                )}
               </div>
@@ -1995,7 +1995,7 @@
           <div className="bg-neutral-900/40 border border-white/5 rounded-3xl p-6 space-y-6">
             <h3 className="text-sm font-black text-white uppercase tracking-wider flex items-center gap-2">
-              <ImageIcon className="w-4 h-4 text-emerald-400" /> 장면별 실시간 렌더링 모니터 (Scene Monitor)
+              <ImageIcon className="w-4 h-4 text-emerald-400" /> 장면별 실시간 비디오 생성 모니터 (Scene Monitor)
             </h3>
@@ -2003,14 +2003,24 @@
                     {scene.status === 'success' && scene.video_url ? (
                       <video src={scene.video_url} controls className="w-full h-full object-cover" />
                     ) : scene.use_image_only ? (
-                      <div className="w-full h-full relative">
+                      <div className="w-full h-full relative group">
                         {scene.image_url ? (
-                          <img src={scene.image_url} className="w-full h-full object-cover opacity-80" />
+                          <img src={scene.image_url} className="w-full h-full object-cover opacity-80 transition-all group-hover:opacity-60" />
                         ) : (
                           <div className="w-full h-full bg-neutral-800 flex items-center justify-center text-xs text-gray-500">이미지 없음</div>
                         )}
-                        <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
-                          <span className="px-3 py-1 bg-orange-500 text-white font-black text-[10px] rounded-lg tracking-wider uppercase">🖼️ 스틸컷 연출</span>
+                        <div className="absolute inset-0 bg-black/40 flex flex-col items-center justify-center gap-2">
+                          <span className="px-3 py-1 bg-orange-500 text-white font-black text-[10px] rounded-lg tracking-wider uppercase">🖼️ 스틸컷 유지</span>
+                          <button 
+                            onClick={() => {
+                              const newScript = [...finalAssets.script];
+                              newScript[i].use_image_only = false;
+                              setFinalAssets({...finalAssets, script: newScript});
+                            }}
+                            className="px-3 py-1 bg-red-600/90 hover:bg-red-500 text-white rounded-full text-[10px] font-bold shadow-lg transition-transform active:scale-95"
+                          >
+                            비디오 생성으로 전환
+                          </button>
                         </div>
                       </div>
```
