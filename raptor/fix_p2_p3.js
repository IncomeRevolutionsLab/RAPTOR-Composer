const fs = require('fs');
const file = 'src/components/RaptorWorkflow.tsx';
let code = fs.readFileSync(file, 'utf8');

// 1. Update extractErrorMessage
code = code.replace(
    /const extractErrorMessage = \(e: any\): string => e instanceof Error \? e\.message : String\(e\);/g,
    "const extractErrorMessage = (e: any): string => e instanceof Error ? e.message : (typeof e === 'object' && e !== null ? JSON.stringify(e) : String(e));"
);

// 2. Remove dead code at L412-415
code = code.replace(
    /let displayError = extractErrorMessage\(error\);\s*\/\/\s*에러 마스킹 해제 조건 \(필요 시 로직 유지\)\s*if \(displayError\.includes\('401'\) \|\| displayError\.includes\('403'\) \|\| displayError\.includes\('Tier'\) \|\| displayError\.includes\('model_not_found'\) \|\| displayError\.includes\('not exist'\)\) \{\s*displayError = displayError;\s*\}/g,
    'const displayError = extractErrorMessage(error);'
);

// 3. Fix SSE internal catch blocks (L670-L672)
code = code.replace(
    /\} catch \(e: any\) \{\s*if \(e\.message !== \"Unexpected end of JSON input\" && !e\.message\.includes\(\"Unexpected token\"\)\) throw e;\s*\}/g,
    '} catch (e: any) {\n                          const msg = extractErrorMessage(e);\n                          if (!msg.includes("Unexpected end of JSON input") && !msg.includes("Unexpected token")) throw e;\n                        }'
);

fs.writeFileSync(file, code);
console.log('Fixed P2-P3 post-review issues.');
