```diff
diff --git a/backend/services/kie_ai_client.py b/backend/services/kie_ai_client.py
index e833f2c..f9b8c2d 100644
--- a/backend/services/kie_ai_client.py
+++ b/backend/services/kie_ai_client.py
@@ -16,7 +16,7 @@ class KieAiClient:
             "export": "720p"
         }
         return {
-            "model": "grok-imagine/image-to-video",
+            "model": "grok-imagine/text-to-image",
             "quality": res_map.get(quality, "480p"),
             "input": {
                 "image_url": image_url,

diff --git a/main.py b/main.py
index 4b8d7a1..9c2e1f4 100644
--- a/main.py
+++ b/main.py
@@ -171,10 +171,10 @@ def require_api_key(request: Request):
 
 def map_image_model(model_name: Optional[str]) -> str:
     if not model_name:
-        return "gpt-image-2"
+        return "gpt image 2, text-to-image, 1k"
     normalized = model_name.lower().strip()
-    if "openai" in normalized or normalized == "gpt-image-2":
-        return "gpt-image-2"
+    if "openai" in normalized or normalized == "gpt-image-2" or normalized == "gpt image 2, text-to-image, 1k":
+        return "gpt image 2, text-to-image, 1k"
     elif "grok" in normalized:
         return "grok-imagine/text-to-image"
     elif "banana" in normalized:
@@ -329,7 +329,7 @@ class ImageGenRequest(BaseModel):
     product_name: str
     scenes: List[dict]
     aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"
-    model: Optional[str] = "gpt-image-2"
+    model: Optional[str] = "gpt image 2, text-to-image, 1k"
 
 class VideoGenRequest(BaseModel):
     product_name: str

diff --git a/src/components/RaptorWorkflow.tsx b/src/components/RaptorWorkflow.tsx
index 3f9c2d1..8e7a9f2 100644
--- a/src/components/RaptorWorkflow.tsx
+++ b/src/components/RaptorWorkflow.tsx
@@ -1475,7 +1475,7 @@ export default function RaptorWorkflow() {
                             <Film className="w-3.5 h-3.5" /> 🎬 비디오 등록
                             <input 
                               type="file" 
-                              accept="video/mp4" 
+                              accept="video/mp4,video/x-m4v,video/*"
                               className="hidden" 
                               onChange={async (e) => {
                                 const file = e.target.files?.[0];
@@ -1541,7 +1541,7 @@ export default function RaptorWorkflow() {
                           비디오 변경
                           <input 
                             type="file" 
-                            accept="video/mp4" 
+                            accept="video/mp4,video/x-m4v,video/*"
                             className="hidden" 
                             onChange={async (e) => {
                               const file = e.target.files?.[0];
```
