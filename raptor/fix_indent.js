const fs = require('fs');
const file = 'src/components/RaptorWorkflow.tsx';
let code = fs.readFileSync(file, 'utf8');

// The exact string to replace (indentation is 8 spaces too deep)
// In the first SSE parsing block
code = code.replace(
    /\} catch \(e: any\) \{\n                          const msg = extractErrorMessage\(e\);\n                          if \(\!msg\.includes\(\"Unexpected end of JSON input\"\) && \!msg\.includes\(\"Unexpected token\"\)\) throw e;\n                        \}/g,
    '} catch (e: any) {\n                const msg = extractErrorMessage(e);\n                if (!msg.includes("Unexpected end of JSON input") && !msg.includes("Unexpected token")) throw e;\n              }'
);

fs.writeFileSync(file, code);
