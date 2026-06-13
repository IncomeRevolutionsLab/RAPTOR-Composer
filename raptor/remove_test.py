file_path = r'c:\Antigravity Work\RAPTOR\main.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
in_test_func = False
for line in lines:
    if line.startswith('@app.post("/api/render-stream-test")'):
        in_test_func = True
    elif in_test_func and line.startswith('@app.post("/api/render-stream")'):
        in_test_func = False
    
    if not in_test_func:
        new_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('Deleted /api/render-stream-test from main.py')
