```diff
diff --git a/main.py b/main.py
--- a/main.py
+++ b/main.py
@@ -1171,6 +1171,18 @@
             for attempt in range(max_retries + 1):
                 try:
                     # 1. createTask 호출
+                    model_val = map_image_model(request.model)
+                    input_payload = {
+                        "prompt": full_prompt,
+                        "aspect_ratio": request.aspect_ratio if hasattr(request, 'aspect_ratio') and request.aspect_ratio else "auto"
+                    }
+                    if model_val == "nano-banana-2":
+                        input_payload.update({
+                            "image_input": [],
+                            "resolution": "1K",
+                            "output_format": "png"
+                        })
+                    
                     create_res = await client.post(
                         "https://api.kie.ai/api/v1/jobs/createTask",
                         headers={
@@ -1177,13 +1189,9 @@
                             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                         },
                         json={
-                            "model": map_image_model(request.model),
-                            "input": {
-                                "prompt": full_prompt,
-                                "aspect_ratio": request.aspect_ratio if hasattr(request, 'aspect_ratio') and request.aspect_ratio else "auto"
-                            }
+                            "model": model_val,
+                            "input": input_payload
                         },
                         timeout=60.0
                     )
@@ -1579,6 +1579,18 @@
             
             for attempt in range(max_retries + 1):
                 try:
+                    model_val = map_image_model(request.model)
+                    input_payload = {
+                        "prompt": full_prompt,
+                        "aspect_ratio": request.aspect_ratio if hasattr(request, 'aspect_ratio') and request.aspect_ratio else "auto"
+                    }
+                    if model_val == "nano-banana-2":
+                        input_payload.update({
+                            "image_input": [],
+                            "resolution": "1K",
+                            "output_format": "png"
+                        })
+                    
                     dalle_res = await http_client.post(
                         "https://api.kie.ai/api/v1/jobs/createTask",
                         headers={
@@ -1585,13 +1585,9 @@
                             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                         },
                         json={
-                            "model": map_image_model(request.model),
-                            "input": {
-                                "prompt": full_prompt,
-                                "aspect_ratio": request.aspect_ratio if hasattr(request, 'aspect_ratio') and request.aspect_ratio else "auto"
-                            }
+                            "model": model_val,
+                            "input": input_payload
                         },
                         timeout=60.0
                     )
```
