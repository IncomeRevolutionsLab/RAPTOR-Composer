```diff
diff --git a/main.py b/main.py
index d81f2ab..a2d7f8d 100644
--- a/main.py
+++ b/main.py
@@ -1347,6 +1347,7 @@
                         "prompt": scene.get('image_prompt', 'Animate this image'),
                         "imageUrls": [public_url],
                         "model": model_name,
+                        "watermark": "",
                         "aspect_ratio": request.aspect_ratio,
                         "generationType": gen_type,
                         "enableFallback": False,
@@ -1996,6 +1996,7 @@
                             "prompt": scene.get('image_prompt', 'Animate this image'),
                             "imageUrls": [public_url],
                             "model": model_name,
+                            "watermark": "",
                             "aspect_ratio": request.aspect_ratio,
                             "generationType": gen_type,
                             "enableFallback": False,
@@ -2002,6 +2002,6 @@
                         }
                         if callback_url:
-                            payload["webhook_url"] = callback_url
+                            payload["callBackUrl"] = callback_url
                     else:
                         url = "https://api.kie.ai/api/v1/jobs/createTask"
                         model_name = "grok-imagine/image-to-video"
```
