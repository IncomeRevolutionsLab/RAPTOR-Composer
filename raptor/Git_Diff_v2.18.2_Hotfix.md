```diff
diff --git a/main.py b/main.py
index 4b8d7a1..e2f7b1a 100644
--- a/main.py
+++ b/main.py
@@ -171,10 +171,10 @@ def require_api_key(request: Request):
 
 def map_image_model(model_name: Optional[str]) -> str:
     if not model_name:
-        return "gpt image 2, text-to-image, 1k"
+        return "gpt-image-2-text-to-image"
     normalized = model_name.lower().strip()
-    if "openai" in normalized or normalized == "gpt-image-2" or normalized == "gpt image 2, text-to-image, 1k":
-        return "gpt image 2, text-to-image, 1k"
+    if "openai" in normalized or "gpt-image-2" in normalized or "gpt image 2" in normalized:
+        return "gpt-image-2-text-to-image"
     elif "grok" in normalized:
         return "grok-imagine/text-to-image"
     elif "banana" in normalized:
@@ -329,7 +329,7 @@ class ImageGenRequest(BaseModel):
     product_name: str
     scenes: List[dict]
     aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"
-    model: Optional[str] = "gpt image 2, text-to-image, 1k"
+    model: Optional[str] = "gpt-image-2-text-to-image"
 
 class VideoGenRequest(BaseModel):
     product_name: str
@@ -1824,8 +1824,8 @@ def delete_all_my_tasks(jwt_user_id: str = Depends(get_jwt_user_id)):
 
 @app.post("/api/user-videos")
 async def upload_user_video(file: UploadFile = File(...), jwt_user_id: str = Depends(get_jwt_user_id)):
-    if file.content_type != "video/mp4" or not file.filename.endswith(".mp4"):
-        raise HTTPException(status_code=422, detail="Only MP4 video files are allowed.")
+    if not file.content_type.startswith("video/"):
+        raise HTTPException(status_code=422, detail="Only video files are allowed.")
         
     video_id = f"uv_{uuid.uuid4().hex[:8]}"
     file_path = f"outputs/{video_id}.mp4"
     
diff --git a/src/components/RaptorWorkflow.tsx b/src/components/RaptorWorkflow.tsx
index 8e7a9f2..12b8c9d 100644
--- a/src/components/RaptorWorkflow.tsx
+++ b/src/components/RaptorWorkflow.tsx
@@ -1477,13 +1477,17 @@ export default function RaptorWorkflow() {
                               type="file" 
                               accept="video/mp4,video/x-m4v,video/*"
                               className="hidden" 
-                              onChange={async (e) => {
-                                const file = e.target.files?.[0];
-                                if (file) {
-                                  const formData = new FormData();
-                                  formData.append('file', file);
-                                  setLoading(true, "비디오 업로드 및 정밀 분석 중...");
-                                  try {
+                                onChange={async (e) => {
+                                  const file = e.target.files?.[0];
+                                  if (file) {
+                                    if (!file.type.startsWith('video/')) {
+                                      alert("MP4 비디오 업로드 실패. 파일 타입을 확인하세요.");
+                                      return;
+                                    }
+                                    const formData = new FormData();
+                                    formData.append('file', file);
+                                    setLoading(true, "비디오 업로드 및 정밀 분석 중...");
+                                    try {
                                     const res = await fetch(`${BACKEND_URL}/api/user-videos`, {
                                       method: 'POST',
                                       body: formData
@@ -1546,6 +1550,10 @@ export default function RaptorWorkflow() {
                             onChange={async (e) => {
                               const file = e.target.files?.[0];
                               if (file) {
+                                if (!file.type.startsWith('video/')) {
+                                  alert("MP4 비디오 업로드 실패. 파일 타입을 확인하세요.");
+                                  return;
+                                }
                                 const formData = new FormData();
                                 formData.append('file', file);
                                 setLoading(true, "비디오 업로드 및 정밀 분석 중...");
```
