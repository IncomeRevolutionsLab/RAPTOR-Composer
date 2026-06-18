const fs = require('fs');

// 1. Update useWorkflowStore.ts
const storeFile = 'src/store/useWorkflowStore.ts';
let storeCode = fs.readFileSync(storeFile, 'utf8');

storeCode = storeCode.replace(
    /      onRehydrateStorage: \(\) => \(state\) => \{\n        if \(state\) \{\n          state\.setHasHydrated\(true\);/g,
    '      onRehydrateStorage: () => (state) => {\n        if (state) {\n          const allowedVoices = ["ko-KR-SunHiNeural", "ko-KR-InJoonNeural", "ko-KR-BongJinNeural"];\n          if (!allowedVoices.includes(state.voiceType)) {\n            state.setVoiceType("ko-KR-SunHiNeural");\n          }\n          state.setHasHydrated(true);'
);

fs.writeFileSync(storeFile, storeCode);

// 2. Update ffmpeg_worker.py
const ffmpegFile = 'backend/services/ffmpeg_worker.py';
let ffmpegCode = fs.readFileSync(ffmpegFile, 'utf8');

const oldTTSBlock = `    async def generate_tts(self, text: str, voice: str, output_path: str, openai_key: str):
        """Generates high-quality TTS using MS Edge-TTS."""
        try:
            cmd = ['edge-tts', '--voice', voice, '--text', text, '--write-media', output_path]
            await self._run_subprocess(cmd, check=True)
            return output_path
        except Exception as e:
            print(f"[TTS ERROR] {str(e)}")
            raise e`;

const newTTSBlock = `    async def generate_tts(self, text: str, voice: str, output_path: str):
        """Generates high-quality TTS using MS Edge-TTS via Native API."""
        allowed_voices = {"ko-KR-SunHiNeural", "ko-KR-InJoonNeural", "ko-KR-BongJinNeural"}
        if voice not in allowed_voices:
            voice = "ko-KR-SunHiNeural"
            
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)
            
            if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
                raise Exception(f"Edge-TTS output empty or missing: {output_path}")
            return output_path
        except Exception as e:
            print(f"[TTS ERROR] {str(e)}")
            raise e`;

ffmpegCode = ffmpegCode.replace(oldTTSBlock, newTTSBlock);

// Remove openai_key from generate_tts caller
ffmpegCode = ffmpegCode.replace(
    /await self\.generate_tts\(dialogue, voice_type, local_audio, openai_key\)/g,
    'await self.generate_tts(dialogue, voice_type, local_audio)'
);

fs.writeFileSync(ffmpegFile, ffmpegCode);

console.log('Fixed post-review issues successfully.');
