import os

file_path = r'c:\Antigravity Work\RAPTOR\backend\services\ffmpeg_worker.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
in_block = False
for i, line in enumerate(lines):
    if i == 145:  # line 146 (0-indexed 145) is await self.render_semaphore.acquire()
        new_lines.append('        async with self.render_semaphore:\n')
    elif i == 146:  # line 147 is try:
        new_lines.append('            try:\n')
        in_block = True
    elif in_block and i >= 147 and i <= 399:
        if line.strip() == '':
            new_lines.append(line)
        else:
            new_lines.append('    ' + line)
    elif i >= 400 and i <= 423:
        pass # we will manually append the ending part
    else:
        if not in_block:
            new_lines.append(line)

ending_part = '''            cmd_final = [
                self.ffmpeg_path, "-y",
                "-f", "concat", "-safe", "0", "-i", os.path.abspath(concat_file),
                "-c", "copy", os.path.abspath(final_output)
            ]
            try:
                await self._run_subprocess(cmd_final, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                print(f"[RENDER LOG] Final Concat Failed: {e.stderr}")
                raise e

            if os.path.exists(final_output):
                yield {
                    "task_id": task_id,
                    "status": "completed",
                    "output_url": f"/outputs/raptor_{task_id}.mp4",
                    "size_bytes": os.path.getsize(final_output)
                }
            else:
                raise Exception("Physical MP4 creation failed.")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
'''
new_lines.insert(len(new_lines), ending_part)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('Fixed ffmpeg_worker.py')
