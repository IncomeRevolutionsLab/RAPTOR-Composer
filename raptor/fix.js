const fs = require('fs');
const file = 'src/components/RaptorWorkflow.tsx';
let code = fs.readFileSync(file, 'utf8');

// Fix 1: setErrorMessage
code = code.replace(/setErrorMessage\(\`(.*?)\$\{e\.message\}(.*?)\`\)/g, 'setErrorMessage(\`$1${e instanceof Error ? e.message : String(e)}$2\`)');
code = code.replace(/setErrorMessage\(\`(.*?)\$\{errorMsg\}\`\)/g, 'setErrorMessage(\`$1${errorMsg instanceof Error ? errorMsg.message : String(errorMsg)}\`)');
code = code.replace(/setErrorMessage\(\`(.*?)\$\{error\.message\}(.*?)\`\)/g, 'setErrorMessage(\`$1${error instanceof Error ? error.message : String(error)}$2\`)');

// Fix 2: 'data' undefined crash on handleGenerateImages and handleRefinePrompt
// handleGenerateImages: const item = res?.data?.[0];
code = code.replace(/const item = res\?\.data\?\.\[0\];/g, 'const item = res?.data?.[0];\n          if (!item) throw new Error("서버로부터 유효한 이미지 데이터를 받지 못했습니다.");');

// handleRefinePrompt:
// extractedUrl = refineRes?.image_url;
// if (!extractedUrl) throw new Error(...) -> ensure this uses the text user provided
code = code.replace(/if \(\!extractedUrl\) throw new Error\("이미지 데이터가 없습니다\. 다시 시도해주세요\."\);/g, 'if (!extractedUrl) throw new Error("서버로부터 유효한 이미지 데이터를 받지 못했습니다.");');

// Fix 3: Force stop pipeline on error
// Since we changed errorMsg above, we also replace the lines in handleGenerateClips catch
// The previous code was:
// setErrorMessage(`비디오 클립 생성 오류: ${errorMsg}`);
// After Fix 1, it becomes:
// setErrorMessage(`비디오 클립 생성 오류: ${errorMsg instanceof Error ? errorMsg.message : String(errorMsg)}`);
code = code.replace(/setErrorMessage\(\`비디오 클립 생성 오류: \$\{errorMsg instanceof Error \? errorMsg\.message : String\(errorMsg\)\}\`\);/g, 'setErrorMessage(\`비디오 클립 생성 오류: ${errorMsg instanceof Error ? errorMsg.message : String(errorMsg)}\`);\n      setLoading(false);\n      useWorkflowStore.getState().setRenderStatus(false, 0);');

// For other catch blocks, ensure setLoading(false) and setRenderStatus(false, 0)
// wait, handleRenderFinal catch block already has setRenderStatus(false, 0) and setLoading(false) in finally:
// 807:       setRenderStatus(false, 0);
// 810:       setLoading(false);
// So we just need to make sure handleAnalyze, handleGenerateAssets, handleGenerateImages, handleGenerateClips etc have them.

fs.writeFileSync(file, code);
console.log('Done!');
