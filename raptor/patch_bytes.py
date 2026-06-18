with open("main.py", "rb") as f:
    content = f.read()

target1 = b'messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}]\r\n        )'
replacement1 = b'messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],\r\n            extra_body={"thinkingFlag": True}\r\n        )'

target2 = b'messages=[{"role": "user", "content": content}]\r\n                    )'
replacement2 = b'messages=[{"role": "user", "content": content}],\r\n                        extra_body={"thinkingFlag": True}\r\n                    )'

target3 = b'messages=[{"role": "user", "content": [{"type": "text", "text": refine_prompt_text}]}]\r\n                )'
replacement3 = b'messages=[{"role": "user", "content": [{"type": "text", "text": refine_prompt_text}]}],\r\n                    extra_body={"thinkingFlag": True}\r\n                )'

target1_lf = target1.replace(b'\r\n', b'\n')
replacement1_lf = replacement1.replace(b'\r\n', b'\n')
target2_lf = target2.replace(b'\r\n', b'\n')
replacement2_lf = replacement2.replace(b'\r\n', b'\n')
target3_lf = target3.replace(b'\r\n', b'\n')
replacement3_lf = replacement3.replace(b'\r\n', b'\n')

content = content.replace(target1, replacement1)
content = content.replace(target1_lf, replacement1_lf)

content = content.replace(target2, replacement2)
content = content.replace(target2_lf, replacement2_lf)

content = content.replace(target3, replacement3)
content = content.replace(target3_lf, replacement3_lf)

with open("main.py", "wb") as f:
    f.write(content)

print("Patch applied successfully.")
