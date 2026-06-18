const fs = require('fs');

// 1. Update RaptorWorkflow.tsx
const raptorFile = 'src/components/RaptorWorkflow.tsx';
let raptorCode = fs.readFileSync(raptorFile, 'utf8');

// The dropdown at ~L1071
raptorCode = raptorCode.replace(
    /<option value="여성-발랄한">👩 여성 - 발랄한<\/option><option value="여성-차분한">👩 여성 - 차분한<\/option><option value="남성-신뢰감">👨 남성 - 신뢰감<\/option><option value="남성-차분한">👨 남성 - 차분한<\/option>/g,
    '<option value="ko-KR-SunHiNeural">여성 - 선히 (SunHi)</option><option value="ko-KR-InJoonNeural">남성 - 인준 (InJoon)</option><option value="ko-KR-BongJinNeural">남성 - 봉진 (BongJin)</option>'
);

// The dropdown at ~L1962
raptorCode = raptorCode.replace(
    /<option value="여성-발랄한">여성 - 발랄한 \(Nova\)<\/option>\s*<option value="여성-차분한">여성 - 차분한 \(Shimmer\)<\/option>\s*<option value="남성-신뢰감">남성 - 신뢰감 \(Echo\)<\/option>\s*<option value="남성-차분한">남성 - 차분한 \(Onyx\)<\/option>/g,
    '<option value="ko-KR-SunHiNeural">여성 - 선히 (SunHi)</option>\n                      <option value="ko-KR-InJoonNeural">남성 - 인준 (InJoon)</option>\n                      <option value="ko-KR-BongJinNeural">남성 - 봉진 (BongJin)</option>'
);

fs.writeFileSync(raptorFile, raptorCode);

// 2. Update useWorkflowStore.ts
const storeFile = 'src/store/useWorkflowStore.ts';
let storeCode = fs.readFileSync(storeFile, 'utf8');
storeCode = storeCode.replace(
    /voiceType: '여성-발랄한'/g,
    "voiceType: 'ko-KR-SunHiNeural'"
);
fs.writeFileSync(storeFile, storeCode);

// 3. Update ffmpeg_worker.py
const ffmpegFile = 'backend/services/ffmpeg_worker.py';
let ffmpegCode = fs.readFileSync(ffmpegFile, 'utf8');

const oldTTS = `    async def generate_tts(self, text: str, voice: str, output_path: str, openai_key: str):
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
            raise e`;

const newTTS = `    async def generate_tts(self, text: str, voice: str, output_path: str, openai_key: str):
        """Generates high-quality TTS using MS Edge-TTS."""
        try:
            cmd = ['edge-tts', '--voice', voice, '--text', text, '--write-media', output_path]
            await self._run_subprocess(cmd, check=True)
            return output_path
        except Exception as e:
            print(f"[TTS ERROR] {str(e)}")
            raise e`;

if (ffmpegCode.includes(oldTTS)) {
    ffmpegCode = ffmpegCode.replace(oldTTS, newTTS);
    fs.writeFileSync(ffmpegFile, ffmpegCode);
    console.log('ffmpeg_worker.py updated.');
} else {
    console.log('oldTTS not found in ffmpeg_worker.py. Looking for substring...');
    // fallback if regex or exact string doesn't match
    const regex = /async def generate_tts[\s\S]*?raise e/g;
    ffmpegCode = ffmpegCode.replace(regex, newTTS);
    fs.writeFileSync(ffmpegFile, ffmpegCode);
    console.log('ffmpeg_worker.py updated with regex.');
}

console.log('Frontend files updated.');
