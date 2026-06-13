```diff
diff --git a/main.py b/main.py
--- a/main.py
+++ b/main.py
@@ -1181,9 +1181,7 @@
                             "model": map_image_model(request.model),
                             "input": {
                                 "prompt": full_prompt,
-                                "n": 1,
-                                "size": img_size,
-                                "quality": "medium"
+                                "aspect_ratio": request.aspect_ratio if hasattr(request, 'aspect_ratio') and request.aspect_ratio else "auto"
                             }
                         },
                         timeout=60.0
@@ -1583,10 +1583,7 @@
                             "model": map_image_model(request.model),
                             "input": {
                                 "prompt": full_prompt,
-                                "n": 1,
-                                "size": img_size,
-                                "quality": "medium",
-                                "aspect_ratio": request.aspect_ratio
+                                "aspect_ratio": request.aspect_ratio if hasattr(request, 'aspect_ratio') and request.aspect_ratio else "auto"
                             }
                         },
                         timeout=60.0
```
