import os
import subprocess
import httpx
import asyncio
import edge_tts
from typing import List
import time
import imageio_ffmpeg
import shutil
import platform

class FFmpegWorker:
    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Determine FFmpeg path
        self.ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        # Determine ffprobe path (P-005)
        self.ffprobe_path = shutil.which("ffprobe") or (os.path.join(os.getcwd(), "ffprobe.exe") if os.path.exists(os.path.join(os.getcwd(), "ffprobe.exe")) else "ffprobe")

    async def _run_subprocess(self, cmd, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: subprocess.run(cmd, **kwargs))

    async def _check_output(self, cmd, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: subprocess.check_output(cmd, **kwargs))

    async def generate_tts(self, text: str, voice: str, output_path: str, openai_key: str):
        """Generates high-quality TTS using OpenAI API."""
        if not openai_key:
            raise Exception("OpenAI API Key is required for TTS generation.")

        # OpenAI Voice Mapping
        voice_map = {
            "여성-발랄한": "nova",
            "여성-차분한": "shimmer",
            "남성-신뢰감": "echo",
            "남성-차분한": "onyx"
        }
        selected_voice = voice_map.get(voice, "nova")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.kie.ai/v1/audio/speech",
                    headers={
                        "Authorization": f"Bearer {openai_key}",
                        "X-BYOK-KIE": openai_key
                    },
                    json={
                        "model": "tts-1",
                        "input": text,
                        "voice": selected_voice
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    with open(output_path, "wb") as f:
                        f.write(response.content)
                    return output_path
                else:
                    error_detail = response.text
                    raise Exception(f"OpenAI TTS API Error ({response.status_code}): {error_detail}")
        except Exception as e:
            print(f"[TTS ERROR] {str(e)}")
            raise e

    async def download_image(self, url: str, target_path: str):
        if url.startswith('data:image') or ';base64,' in url:
            import base64
            try:
                if ',' in url:
                    header, encoded = url.split(",", 1)
                else:
                    encoded = url
                data = base64.b64decode(encoded.strip())
                with open(target_path, "wb") as f:
                    f.write(data)
                return True
            except Exception as e:
                print(f"[RENDER LOG] Base64 Decode Failed: {str(e)}")
                return False
        
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(url, timeout=10.0)
                if res.status_code == 200:
                    with open(target_path, "wb") as f:
                        f.write(res.content)
                    if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
                        return True
        except Exception:
            pass
        return False

    def wrap_text(self, text, aspect_ratio="9:16"):
        """Raptor Optimization: Helper to wrap text for vertical video."""
        if not text: return ""
        
        # Determine max_chars dynamically based on aspect ratio
        if aspect_ratio == "16:9":
            max_chars = 30
        elif aspect_ratio == "1:1":
            max_chars = 20
        else:
            max_chars = 15

        lines = []
        current_line = ""
        
        for char in text:
            current_line += char
            # Simple heuristic: wrap every max_chars
            if len(current_line) >= max_chars and char in [' ', '.', ',', '!', '?', '은', '는', '이', '가', '을', '를']:
                lines.append(current_line.strip())
                current_line = ""
            elif len(current_line) >= max_chars + 2: # Force wrap if too long
                lines.append(current_line.strip())
                current_line = ""
        
        if current_line:
            lines.append(current_line.strip())
            
        return "\n".join(lines)

    async def render_video(self, task_id: str, scenes: list, voice_type: str = "여성-발랄한", aspect_ratio: str = "9:16", subtitle_position: str = "하", render_duration: str = "자막 맞춤 길이 (Dynamic Sync)", openai_key: str = None, watermark_enabled: bool = False, watermark_logo: str = None, watermark_position: str = "top-right", rendering_mode: str = "full"):
        ratio_map = {
            "9:16": (720, 1280),
            "1:1": (720, 720),
            "16:9": (1280, 720)
        }
        w, h = ratio_map.get(aspect_ratio, (720, 1280))

        temp_dir = os.path.join(self.output_dir, f"temp_{task_id}")
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        final_output = os.path.join(self.output_dir, f"raptor_{task_id}.mp4")

        try:
            # Watermark download
            local_watermark = None
            if watermark_enabled and watermark_logo:
                local_watermark = os.path.join(temp_dir, "watermark.png")
                success = await self.download_image(watermark_logo, local_watermark)
                if not success:
                    local_watermark = None
            
            # Phase 1: Prepare assets (Images + TTS)
            yield "비디오 생성 대기 중"
            
            local_assets = []
            for i, scene in enumerate(scenes):
                dialogue = str(scene.get('dialogue') or scene.get('narration') or scene.get('voiceover') or scene.get('text') or "").strip()
                if not dialogue:
                    print(f"\n[TTS CRITICAL WARNING] 빈 대사 감지! Scene: {scene}")
                    dialogue = "."
                    
                image_url = scene.get('image_url') or scene.get('original_image')
                
                local_img = os.path.join(temp_dir, f"bg_{i}.jpg")
                if image_url:
                    await self.download_image(image_url, local_img)
                else:
                    cmd_bg = [self.ffmpeg_path, "-y", "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:d=1", "-vframes", "1", local_img]
                    await self._run_subprocess(cmd_bg, check=True, capture_output=True)

                local_audio = os.path.join(temp_dir, f"audio_{i}.mp3")
                await self.generate_tts(dialogue, voice_type, local_audio, openai_key)
                
                for fpath, label in [(local_img, "Image"), (local_audio, "Audio")]:
                    if not os.path.exists(fpath) or os.path.getsize(fpath) < 1000:
                        raise Exception(f"Integrity Check Failed: {label} file missing or too small (<1KB). Path: {fpath}")
                        
                local_assets.append({
                    "local_img": local_img,
                    "local_audio": local_audio,
                    "dialogue": dialogue
                })

            # Phase 2: Render individual scene clips
            yield "KIE AI 비디오 렌더링 중"
            
            scene_files = []
            for i, scene in enumerate(scenes):
                assets = local_assets[i]
                local_img = assets["local_img"]
                local_audio = assets["local_audio"]
                dialogue = assets["dialogue"]
                
                try:
                    cmd_dur = [
                        self.ffprobe_path,
                        "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", local_audio
                    ]
                    dur_out = await self._check_output(cmd_dur)
                    actual_audio_duration = float(dur_out.decode().strip())
                    planned_duration = float(scene.get('duration_seconds', 4))
                    if render_duration == "15초":
                        duration = 15.0
                    elif render_duration == "30초":
                        duration = 30.0
                    else:
                        duration = actual_audio_duration + 0.5
                except Exception:
                    duration = 4.0

                scene_mp4 = os.path.join(temp_dir, f"scene_{i}.mp4")
                video_url = scene.get('video_url')
                user_video_id = scene.get('user_video_id')
                local_video = os.path.join(temp_dir, f"vid_{i}.mp4")
                
                use_video = False
                if user_video_id:
                    supabase_url = os.getenv("SUPABASE_URL")
                    if supabase_url:
                        video_url_for_download = f"{supabase_url.rstrip('/')}/storage/v1/object/public/assets/{user_video_id}.mp4"
                        use_video = await self.download_image(video_url_for_download, local_video)
                    
                    if not use_video:
                        source_video_path = os.path.join(self.output_dir, f"{user_video_id}.mp4")
                        if os.path.exists(source_video_path):
                            shutil.copy(source_video_path, local_video)
                            use_video = True
                elif video_url:
                    use_video = await self.download_image(video_url, local_video)

                # 비디오 재생 시간 측정
                video_duration = 0.0
                if use_video:
                    try:
                        cmd_dur_vid = [
                            self.ffprobe_path,
                            "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", local_video
                        ]
                        dur_vid_out = await self._check_output(cmd_dur_vid)
                        video_duration = float(dur_vid_out.decode().strip())
                    except Exception as ve:
                        print(f"[FFMPEG] Failed to get video duration: {ve}")
                        video_duration = 0.0

                    # 씬 길이보다 비디오가 짧은 경우 에러 반환 (v2.1 설계 명세 준수)
                    if video_duration > 0.0 and video_duration < duration:
                        raise Exception(f"Scene {i+1}에 지정된 비디오 길이({video_duration}초)가 씬 시간({duration}초)보다 짧습니다.")

                    # -t 플래그로 앞 N초(duration)만 정밀 Trim 처리
                    trimmed_video = os.path.join(temp_dir, f"trimmed_{i}.mp4")
                    cmd_trim = [
                        self.ffmpeg_path, "-y",
                        "-i", os.path.abspath(local_video),
                        "-t", str(duration),
                        "-c", "copy",
                        os.path.abspath(trimmed_video)
                    ]
                    try:
                        await self._run_subprocess(cmd_trim, check=True, capture_output=True, text=True, cwd=temp_dir)
                        if os.path.exists(trimmed_video):
                            local_video = trimmed_video
                            video_duration = duration
                    except Exception as te:
                        print(f"[FFMPEG TRIM ERROR] {te}")

                y_coord = "h-200"
                if subtitle_position == "상": y_coord = f"{h}*(1.5/12.8)"
                elif subtitle_position == "중": y_coord = "(h-text_h)/2"
                elif subtitle_position == "하": y_coord = "h*(5/7)"

                wrapped_caption = self.wrap_text(dialogue, aspect_ratio)
                text_file_basename = f"scene_{i}_text.txt"
                text_file_path = os.path.join(temp_dir, text_file_basename)
                with open(text_file_path, "w", encoding="utf-8") as f:
                    f.write(wrapped_caption)
                
                # RISK-003: 크로스 플랫폼 폰트 경로 동적 매핑 (리눅스 크래시 및 CJK 깨짐 방어)
                system_name = platform.system().lower()
                if os.name == 'nt' or 'windows' in system_name:
                    font_path = "C:/Windows/Fonts/malgun.ttf".replace(":", "\\:")
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
                            selected_font = candidate.replace(":", "\\:")
                            break
                    if selected_font:
                        font_path = selected_font
                    else:
                        font_path = "DejaVu Sans"
                safe_text_file_path = os.path.abspath(text_file_path).replace("\\", "/").replace(":", "\\:")
                
                # Base video filter
                is_hybrid_image = not use_video
                if is_hybrid_image:
                    # 30fps 고정 및 절대 프레임 번호(on) 기반 줌팬 공식 (줌인/줌아웃 교사 적용)
                    if i % 2 == 0:
                        filter_str = f"[0:v]zoompan=z='1+0.0015*on':d={int(duration*30)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps=30,scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
                    else:
                        filter_str = f"[0:v]zoompan=z='1.5-0.0015*on':d={int(duration*30)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps=30,scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
                else:
                    filter_str = f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
                    # 비디오보다 오디오가 길면 마지막 프레임을 정지(Freeze)하여 연장 (CORS/FFmpeg 예외 대응)
                    if video_duration > 0.0 and duration > video_duration:
                        freeze_dur = duration - video_duration
                        filter_str += f",tpad=stop_mode=clone:stop_duration={freeze_dur}"
                
                # Subtitle overlay (tpad 필터 뒤에 위치하여 늘어난 프레임에도 자막 온전 노출)
                if wrapped_caption.strip():
                    filter_str += (
                        f",drawtext=fontfile='{font_path}':textfile='{safe_text_file_path}':"
                        f"fontcolor=white:fontsize=40:x=(w-text_w)/2:y={y_coord}:"
                        f"box=1:boxcolor=black@0.6:boxborderw=10"
                    )
                
                filter_str += "[bg];"

                # Watermark Overlay logic
                if local_watermark:
                    # scale watermark to reasonable width, e.g. 150px
                    if watermark_position == "top-right":
                        overlay_pos = "W-w-30:30"
                    else:
                        # bottom-right avoiding subtitle. H * 5/8 = 1280 * 5/8 = 800. So we put it at H*(5/8)
                        overlay_pos = "W-w-30:H*(5/8)"
                    filter_str += f"[2:v]scale=150:-1[wm];[bg][wm]overlay={overlay_pos}[v]"
                else:
                    filter_str += "[bg]copy[v]"

                cmd_scene = [
                    self.ffmpeg_path, "-y"
                ]
                
                abs_local_img = os.path.abspath(local_img)
                abs_local_audio = os.path.abspath(local_audio)
                abs_local_video = os.path.abspath(local_video) if use_video else None
                abs_local_watermark = os.path.abspath(local_watermark) if local_watermark else None
                abs_scene_mp4 = os.path.abspath(scene_mp4)
                
                if use_video:
                    cmd_scene.extend(["-i", abs_local_video])
                else:
                    # 하이브리드 이미지 슬라이드: zoompan이 동작하도록 loop를 주고 프레임 수를 제한
                    cmd_scene.extend(["-loop", "1", "-i", abs_local_img])
                    
                cmd_scene.extend(["-i", abs_local_audio])
                
                if abs_local_watermark:
                    cmd_scene.extend(["-i", abs_local_watermark])
                    
                cmd_scene.extend([
                    "-filter_complex", filter_str,
                    "-map", "[v]", "-map", "1:a",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-t", str(duration)
                ])
                
                if not use_video:
                    cmd_scene.extend(["-frames:v", str(int(duration * 30))])
                    
                cmd_scene.append(abs_scene_mp4)

                try:
                    await self._run_subprocess(cmd_scene, check=True, capture_output=True, text=True, cwd=temp_dir)
                except subprocess.CalledProcessError as e:
                    print(f"\n[FFMPEG CRITICAL ERROR] Scene {i} Rendering Failed")
                    print(f"[STDERR]: {e.stderr}")
                    raise e
                scene_files.append(abs_scene_mp4)

            # Phase 3: Concatenate
            yield "KIE AI 비디오 렌더링 중"
            
            concat_file = os.path.join(temp_dir, "concat.txt")
            with open(concat_file, "w") as f:
                for sf in scene_files:
                    f.write(f"file '{os.path.abspath(sf)}'\n")
            
            cmd_final = [
                self.ffmpeg_path, "-y",
                "-f", "concat", "-safe", "0", "-i", os.path.abspath(concat_file),
                "-c", "copy", os.path.abspath(final_output)
            ]
            try:
                await self._run_subprocess(cmd_final, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                print(f"[RENDER LOG] Final Concat Failed: {e.stderr}")
                raise e

            if os.path.exists(final_output):
                yield {
                    "task_id": task_id,
                    "status": "completed",
                    "output_url": f"/outputs/raptor_{task_id}.mp4",
                    "size_bytes": os.path.getsize(final_output)
                }
            else:
                raise Exception("Physical MP4 creation failed.")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

ffmpeg_worker = FFmpegWorker()
