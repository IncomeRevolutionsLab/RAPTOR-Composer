import re

with open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

# Pattern 1 (no system prompt)
content = re.sub(
    r'(messages=\[\{"role": "user", "content": \[\{"type": "text", "text": [^\]]+\]\}\]\n\s*)\)',
    r'\1, extra_body={"thinkingFlag": True}\n        )',
    content
)

# Pattern 2 (with system prompt and content variable)
content = re.sub(
    r'(messages=\[\{"role": "user", "content": content\}\]\n\s*)\)',
    r'\1, extra_body={"thinkingFlag": True}\n                    )',
    content
)

with open("main.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
