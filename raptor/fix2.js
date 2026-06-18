const fs = require('fs');
const file = 'src/components/RaptorWorkflow.tsx';
let code = fs.readFileSync(file, 'utf8');

// Fix P1: errorMsg instanceof Error -> e instanceof Error
code = code.replace(/setErrorMessage\(\`비디오 클립 생성 오류: \$\{errorMsg instanceof Error \? errorMsg\.message : String\(errorMsg\)\}\`\);/g, 'setErrorMessage(\`비디오 클립 생성 오류: ${errorMsg}\`);');

code = code.replace(/let errorMsg = e\.message;/g, 'let errorMsg = e instanceof Error ? e.message : String(e);');
code = code.replace(/if \(e\.name === \'AbortError\' \|\| e\.message\?\.includes\(\'aborted\'\)\)/g, 'if (e.name === \'AbortError\' || (typeof errorMsg === \'string\' && errorMsg.includes(\'aborted\')))');

// Fix P2: duplicated setLoading(false)
code = code.replace(/setErrorMessage\(\`비디오 클립 생성 오류: \$\{errorMsg\}\`\);\n      setLoading\(false\);\n      setRenderStatus\(false, 0\);/g, 'setErrorMessage(\`비디오 클립 생성 오류: ${errorMsg}\`);\n      setRenderStatus(false, 0);');

// Remove redundant setLoading(false); setRenderStatus(false, 0); from finally blocks (which I injected earlier incorrectly)
code = code.replace(/setLoading\(false\);\n      setRenderStatus\(false, 0\);\n    \}/g, 'setLoading(false);\n    }');

// Fix P2: useEffect deps
code = code.replace(/\}, \[setErrorMessage\]\);/g, '}, [setErrorMessage, setRenderStatus]);');

fs.writeFileSync(file, code);
console.log('Fixed post-review issues.');
