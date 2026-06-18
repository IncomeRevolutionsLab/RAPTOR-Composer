import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from backend.services.ffmpeg_worker import ffmpeg_worker

async def test():
    scenes = [
        {
            # A valid image that httpx can download
            "image_url": "https://raw.githubusercontent.com/github/explore/80688e429a7d4ef2fca1e82350fe8e3517d3494d/topics/python/python.png",
            "dialogue": "테스트 문구입니다.",
            "duration_seconds": 3.0
        }
    ]
    try:
        async for status in ffmpeg_worker.render_video(
            task_id="debug_task_1",
            scenes=scenes,
            watermark_enabled=False
        ):
            print("Status:", status)
    except Exception as e:
        print("Render Exception:", e)

if __name__ == "__main__":
    asyncio.run(test())
