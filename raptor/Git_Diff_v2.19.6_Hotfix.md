# Git Diff: v2.19.6 동적 종횡비(Aspect Ratio) 롤백 패치

```diff
--- a/main.py
+++ b/main.py
@@ -1175,27 +1175,15 @@
                     
                     # 베이스 페이로드 구성 (KIE 기술지원팀 공식 스펙 완전 일치화)
                     input_payload = {
-                        "prompt": full_prompt
-                    }
-                    
-                    if model_val == "nano-banana-2":
-                        input_payload.update({
-                            "image_input": [],
-                            "aspect_ratio": "auto",
-                            "resolution": "1K",
-                            "output_format": "png"
-                        })
-                    elif model_val == "grok-imagine/text-to-image":
-                        input_payload.update({
-                            "aspect_ratio": "3:2"
-                        })
-                    elif model_val == "gpt-image-2-text-to-image":
-                        input_payload.update({
-                            "aspect_ratio": "auto"
-                        })
-                    else:
-                        input_payload.update({
-                            "aspect_ratio": request.aspect_ratio if hasattr(request, 'aspect_ratio') and request.aspect_ratio else "auto"
+                        "prompt": full_prompt,
+                        "aspect_ratio": request.aspect_ratio if hasattr(request, 'aspect_ratio') and request.aspect_ratio else "auto"
+                    }
+                    
+                    if model_val == "nano-banana-2":
+                        input_payload.update({
+                            "image_input": [],
+                            "resolution": "1K",
+                            "output_format": "png"
                         })
                     
                     create_res = await client.post(
@@ -1598,27 +1598,15 @@
                     model_val = map_image_model(request.model)
                     # 베이스 페이로드 구성 (KIE 기술지원팀 공식 스펙 완전 일치화)
                     input_payload = {
-                        "prompt": full_prompt
-                    }
-                    
-                    if model_val == "nano-banana-2":
-                        input_payload.update({
-                            "image_input": [],
-                            "aspect_ratio": "auto",
-                            "resolution": "1K",
-                            "output_format": "png"
-                        })
-                    elif model_val == "grok-imagine/text-to-image":
-                        input_payload.update({
-                            "aspect_ratio": "3:2"
-                        })
-                    elif model_val == "gpt-image-2-text-to-image":
-                        input_payload.update({
-                            "aspect_ratio": "auto"
-                        })
-                    else:
-                        input_payload.update({
-                            "aspect_ratio": request.aspect_ratio if hasattr(request, 'aspect_ratio') and request.aspect_ratio else "auto"
+                        "prompt": full_prompt,
+                        "aspect_ratio": request.aspect_ratio if hasattr(request, 'aspect_ratio') and request.aspect_ratio else "auto"
+                    }
+                    
+                    if model_val == "nano-banana-2":
+                        input_payload.update({
+                            "image_input": [],
+                            "resolution": "1K",
+                            "output_format": "png"
                         })
```
