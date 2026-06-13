# Claude Code Architecture Pre-Review: RAPTOR Classic v2.16.4 (Traffic Light UX & Infrastructure Defense)

## 🔍 Overview
I have reviewed the `20260612_RAPTOR_Implementation_Plan_v2.16.4_TrafficLightUX.md` plan which implements an `asyncio.Semaphore` based queue restriction for local FFmpeg, a traffic light UI for real-time queue visibility, and an always-on ZIP streaming fallback.

## 🚨 Architectural Findings

### 1. [Resolved] FFmpeg Worker Overload Defense
*   **Assessment:** The plan correctly proposes wrapping the entire `async def render_video` block inside `ffmpeg_worker.py` with `async with self.render_semaphore`. Because `render_video` is an asynchronous generator (`yield`), `async with` will safely hold the lock throughout the entire streaming lifecycle and release it even if the client disconnects (raising `asyncio.CancelledError`).
*   **Approval:** Good. This prevents FFmpeg from exhausting server resources.

### 2. [Resolved] ZIP Stream Availability Independent of Queue
*   **Assessment:** The new `/api/tasks/{task_id}/download-assets` endpoint correctly bypasses the FFmpeg worker's semaphore queue and uses pure `httpx` streaming combined with `zipstream` to provide the raw assets.
*   **Approval:** Good. This guarantees the user can download assets while waiting for the saturated render queue.

### 3. [Pending] Traffic Light Race Conditions & Stale Tasks
*   **Risk:** The `/api/status/render` API queries DB `tasks` where `status` is `pending` or `processing`. However, if the Node.js frontend or a proxy crashes, some tasks might remain stuck in `pending` or `processing` indefinitely without actually being processed by the worker.
*   **Action Required:** Ensure that dead tasks are periodically marked as `failed` or ignored by the counter, OR strictly rely on the Semaphore's internal count (`self.render_semaphore._value`) if possible. For now, querying the DB is acceptable but keep an eye on stale tasks.

### 4. [New] Button Disable State UX Issue
*   **Risk:** The UI will disable the `[AI 영상 렌더링]` button when the status is Red (>= 2). If a user has already triggered a render and it's currently processing, the UI might show a disabled button, which could confuse the user if they navigate away and come back.
*   **Action Required:** Ensure the UI provides clear feedback: "현재 다른 사용자들의 작업으로 인해 서버가 렌더링을 처리 중입니다. 완료될 때까지 잠시 대기해 주세요."

## ✅ Conclusion
The planned logic for the Infrastructure Defense Mode and Traffic Light UX is solid. I recommend proceeding with the implementation of these 3 core requirements. Ensure the ZIP stream generator efficiently yields chunks.
