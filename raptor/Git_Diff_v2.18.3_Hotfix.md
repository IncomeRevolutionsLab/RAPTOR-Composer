```diff
diff --git a/backend/services/kie_ai_client.py b/backend/services/kie_ai_client.py
index f9b8c2d..4a9e1d8 100644
--- a/backend/services/kie_ai_client.py
+++ b/backend/services/kie_ai_client.py
@@ -19,7 +19,8 @@ class KieAiClient:
             "model": "grok-imagine/text-to-image",
             "quality": res_map.get(quality, "480p"),
             "input": {
                 "image_url": image_url,
-                "duration": str(duration)
+                "duration": str(duration),
+                "aspect_ratio": "9:16"
             }
         }

diff --git a/main.py b/main.py
index e2f7b1a..d81f2ab 100644
--- a/main.py
+++ b/main.py
@@ -1582,7 +1582,8 @@ class VideoGenRequest(BaseModel):
                                 "prompt": full_prompt,
                                 "n": 1,
                                 "size": img_size,
-                                "quality": "medium"
+                                "quality": "medium",
+                                "aspect_ratio": request.aspect_ratio
                             }
                         },
                         timeout=60.0

diff --git a/src/components/RaptorWorkflow.tsx b/src/components/RaptorWorkflow.tsx
index 12b8c9d..f9a12c8 100644
--- a/src/components/RaptorWorkflow.tsx
+++ b/src/components/RaptorWorkflow.tsx
@@ -768,14 +768,6 @@ export default function RaptorWorkflow() {
     }
   };
 
-  useEffect(() => {
-    if (completedImages === totalScenes && totalScenes > 0) {
-      handleGenerateClips();
-    }
-    if (completedVideos === totalScenes && totalScenes > 0) {
-      handleRenderFinal();
-    }
-  }, [completedImages, completedVideos, totalScenes]);
 
   const handleRenderVideoFromScratch = async () => {
     if (!finalAssets?.script) return;
@@ -1910,24 +1902,28 @@ export default function RaptorWorkflow() {
               </div>
 
               <div className="w-full space-y-4">
-                <button 
-                  onClick={() => handleGenerateClips()} 
-                  disabled={isRendering || loading} 
-                  className="w-full bg-blue-600/20 border border-blue-500/30 text-blue-300 py-3 px-6 rounded-2xl font-bold text-xs uppercase tracking-widest flex items-center justify-center gap-2 hover:bg-blue-600/30 hover:border-blue-500/50 transition-all shadow-lg active:scale-[0.98] disabled:opacity-50"
-                >
-                  {loading && !isRendering ? (
-                    <><Loader2 className="w-4 h-4 animate-spin text-blue-300" /> <span>클립 생성 중...</span></>
-                  ) : (
-                    <><Film className="w-5 h-5" /> <span>비디오 클립 생성 (Step 4)</span></>
-                  )}
-                </button>
-
-                <button 
-                  onClick={() => handleRenderFinal()} 
-                  disabled={isRendering || loading || !(finalAssets?.script && finalAssets.script.every((s: any) => s.video_url || s.use_image_only))} 
-                  className="w-full bg-emerald-600/20 border border-emerald-500/30 text-emerald-300 py-3 px-6 rounded-2xl font-bold text-xs uppercase tracking-widest flex items-center justify-center gap-2 hover:bg-emerald-600/30 hover:border-emerald-500/50 transition-all shadow-lg active:scale-[0.98] disabled:opacity-50"
-                >
-                  {isRendering && renderProgress > 0 ? (
-                    <><Loader2 className="w-4 h-4 animate-spin text-emerald-300" /> <span>최종 렌더링 진행 중 {renderProgress}%</span></>
-                  ) : renderQueueCount >= 2 ? (
-                    <><AlertCircle className="w-5 h-5 text-red-400" /> <span>서버 포화: 잠시 후 시도해주세요</span></>
-                  ) : (
-                    <><Upload className="w-5 h-5" /> <span>최종 영상 조립(렌더링) (Step 5)</span></>
-                  )}
-                </button>
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
+                    {isRendering && renderProgress > 0 ? (
+                      <><Loader2 className="w-4 h-4 animate-spin text-emerald-300" /> <span>최종 렌더링 진행 중 {renderProgress}%</span></>
+                    ) : renderQueueCount >= 2 ? (
+                      <><AlertCircle className="w-5 h-5 text-red-400" /> <span>서버 포화: 잠시 후 시도해주세요</span></>
+                    ) : (
+                      <><Upload className="w-5 h-5" /> <span>최종 렌더링 시작 (Step 5)</span></>
+                    )}
+                  </button>
+                )}
              </div>
```
