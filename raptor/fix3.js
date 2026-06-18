const fs = require('fs');
const file = 'src/components/RaptorWorkflow.tsx';
let code = fs.readFileSync(file, 'utf8');

// 1. Add extractErrorMessage helper function right before `const uploadFile = ...`
if (!code.includes('const extractErrorMessage')) {
    code = code.replace(
        /const uploadFile = async \(endpoint: string, file: File\) => \{/,
        'const extractErrorMessage = (e: any): string => e instanceof Error ? e.message : String(e);\n\nconst uploadFile = async (endpoint: string, file: File) => {'
    );
}

// 2. Replace existing `e instanceof Error ? e.message : String(e)` with `extractErrorMessage(e)`
code = code.replace(/e instanceof Error \? e\.message : String\(e\)/g, 'extractErrorMessage(e)');

// 3. Fix L678 logic (Clip Generation Error)
// Original:
// let errorMsg = e.message;
// if (e.name === 'AbortError' || e.message?.includes('aborted')) errorMsg = '응답 시간 초과입니다.';
// setErrorMessage(`비디오 클립 생성 오류: ${errorMsg instanceof Error ? errorMsg.message : String(errorMsg)}`);
// 
// Should be:
// let errorMsg = extractErrorMessage(e);
// if (e.name === 'AbortError' || errorMsg.includes('aborted')) errorMsg = '응답 시간 초과입니다.';
// setErrorMessage(`비디오 클립 생성 오류: ${errorMsg}`);
code = code.replace(
    /let errorMsg = e\.message;\s*if \(e\.name === 'AbortError' \|\| e\.message\?\.includes\('aborted'\)\) errorMsg = '응답 시간 초과입니다\.';\s*setErrorMessage\(\`비디오 클립 생성 오류: \$\{errorMsg instanceof Error \? errorMsg\.message : String\(errorMsg\)\}\`\);/g,
    'let errorMsg = extractErrorMessage(e);\n      if (e.name === \'AbortError\' || errorMsg.includes(\'aborted\')) errorMsg = \'응답 시간 초과입니다.\';\n      setErrorMessage(\`비디오 클립 생성 오류: ${errorMsg}\`);'
);

// 4. Fix L684: rollback script error reference
code = code.replace(/error: e\.message \};/g, 'error: extractErrorMessage(e) };');

// 5. Fix L409-411: error.message.includes() crash
// Original:
// let displayError = error.message;
// if (error.message.includes('401') || error.message.includes('403') || error.message.includes('Tier') || error.message.includes('model_not_found') || error.message.includes('not exist')) {
//   displayError = `${error.message}`;
// }
// 
// Should be:
// let displayError = extractErrorMessage(error);
// if (displayError.includes('401') || displayError.includes('403') || displayError.includes('Tier') || displayError.includes('model_not_found') || displayError.includes('not exist')) {
//   // do nothing, displayError is already set
// }
code = code.replace(
    /let displayError = error\.message;\s*if \(error\.message\.includes\('401'\) \|\| error\.message\.includes\('403'\) \|\| error\.message\.includes\('Tier'\) \|\| error\.message\.includes\('model_not_found'\) \|\| error\.message\.includes\('not exist'\)\) \{\s*displayError = \`\$\{error\.message\}\`; \/\/ 에러 마스킹 해제 \(실제 에러 원문 노출\)\s*\}/g,
    'let displayError = extractErrorMessage(error);\n          // 에러 마스킹 해제 조건 (필요 시 로직 유지)\n          if (displayError.includes(\'401\') || displayError.includes(\'403\') || displayError.includes(\'Tier\') || displayError.includes(\'model_not_found\') || displayError.includes(\'not exist\')) {\n            displayError = displayError;\n          }'
);

// 6. Fix L679, L693: Remove duplicated setLoading(false) in catch
// We should remove `setLoading(false);` from the catch block of handleGenerateClips
// Wait, the catch block in handleGenerateClips looks like this:
// setErrorMessage(...);
// setLoading(false);
// setRenderStatus(false, 0);
// const latestAssets = ...
code = code.replace(/setErrorMessage\(\`비디오 클립 생성 오류: \$\{errorMsg\}\`\);\s*setLoading\(false\);\s*setRenderStatus\(false, 0\);/g, 'setErrorMessage(\`비디오 클립 생성 오류: ${errorMsg}\`);\n      setRenderStatus(false, 0);');

// 7. Fix L174: useEffect deps
code = code.replace(/\}, \[setErrorMessage\]\);/g, '}, [setErrorMessage, setRenderStatus]);');

// Double check handleGenerateImages catch block just in case `error` is used for `setErrorMessage`
code = code.replace(/setErrorMessage\(\`이미지 일괄 생성 실패: \$\{error instanceof Error \? error\.message : String\(error\)\}\`\);/g, 'setErrorMessage(\`이미지 일괄 생성 실패: \${extractErrorMessage(error)}\`);');

fs.writeFileSync(file, code);
console.log('Fixed post-review issues.');
