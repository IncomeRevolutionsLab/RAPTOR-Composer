# RAPTOR v2.19.x 아키텍처 & 소스코드 무결성 감사 보고서

**감사 일시:** 2026-06-14  
**감사 범위:** `C:\Antigravity Work\RAPTOR` (RAPTOR-Composer.git)  
**감사 항목:** 4개 영역 / 심각도 P0~P2 분류

---

## 1. 디렉토리 및 Git 형상 관리 정합성

### 1-1. 로컬 폴더 구조

| 경로 | 역할 | Git 상태 |
|------|------|----------|
| `C:\Antigravity Work\RAPTOR\` | **메인 모노레포** — `backend/`(FastAPI) + `src/`(Next.js) 통합 | `main` 브랜치 체크아웃 |
| `C:\Antigravity Work\RAPTOR\main.py` | FastAPI 진입점 (백엔드 루트) | 추적 중 |
| `C:\Antigravity Work\RAPTOR\src/` | Next.js 프론트엔드 | 추적 중 |
| `C:\Antigravity Work\RAPTOR-Composer/` | **상태 불명 디렉토리** | `??` (git 미추적) |
| `C:\Antigravity Work\RAPTOR_NEO` | 별도 파생 프로젝트 | `m` (서브모듈/별도 repo) |
| `C:\Antigravity Work\raptor/Risk_Tracker.md` | 운영 문서 | ` M` (수정됨) |

> **주목**: `C:\Antigravity Work\RAPTOR`는 내부에 `backend/`와 `src/` 모두를 포함하는 **백엔드-프론트엔드 통합 모노레포**다. 즉, "백엔드 폴더"와 "프론트엔드 폴더"가 물리적으로 분리된 별개 저장소가 아니라 단일 저장소 내에 공존한다.

### 1-2. Remote Origin 및 브랜치 상태 — 🔴 정합성 결함

```bash
Remote: https://github.com/IncomeRevolutionsLab/RAPTOR-Composer.git
현재 브랜치: main  
Remote HEAD: origin/master  ← 불일치!
```

**발견된 결함:**

| 항목 | 현황 | 문제 |
|------|------|------|
| 로컬 작업 브랜치 | `main` | Vercel/Render 기본 배포 트리거 브랜치가 `master`인 경우, `main`에 push해도 자동 배포가 **트리거되지 않음** |
| Origin HEAD | `origin/master` | GitHub 저장소의 기본 브랜치가 `master`로 설정되어 있어, 새 기여자는 `master`를 기준으로 작업하게 됨 |
| 로컬 폴더명 | `RAPTOR` | GitHub 저장소명 `RAPTOR-Composer`와 불일치 (혼란 유발) |
| `RAPTOR-Composer/` 디렉토리 | 미추적(`??`) | 이 폴더의 용도와 origin이 불명확. 별도 저장소인지, 작업 복사본인지 검증 필요 |

**권고:** Vercel 대시보드에서 **프로덕션 배포 트리거 브랜치를 `main`으로 통일**하거나, GitHub 저장소 기본 브랜치를 `main`으로 변경하여 정합성을 확보해야 한다.

---

## 2. 클라우드 인프라 연동 상태 진단

### 2-1. Vercel → Render.com 자동 배포 구조 — 🟢 설계 정상

`vercel.json` 분석 결과:

```json
{
  "rewrites": [
    { "source": "/api/:path*",     "destination": "https://raptor-composer.onrender.com/api/:path*" },
    { "source": "/outputs/:path*", "destination": "https://raptor-composer.onrender.com/outputs/:path*" }
  ]
}
```

Vercel이 Next.js 프론트엔드를 서빙하고, 모든 `/api/*` 및 `/outputs/*` 요청을 Render.com 백엔드로 **서버사이드 프록시**하는 구조다. CORS 문제가 원천 차단되는 올바른 설계이며, 프론트엔드 코드에서 `NEXT_PUBLIC_BACKEND_URL`을 빈 문자열(`""`)로 설정하면 상대경로 `/api/...` 호출이 Vercel rewrite 룰을 자연스럽게 타게 된다.

### 2-2. 핵심 환경변수 매핑 — 🔴 치명적 누락 발견

`.env.local` 현재 정의:

```
SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
COOKIE_ENCRYPTION_KEY=...
SUPABASE_JWT_SECRET=...
WEBHOOK_SECRET=...
```

**`NEXT_PUBLIC_BACKEND_URL`이 정의되어 있지 않다.**

`RaptorWorkflow.tsx:9`와 `AuthDashboard.tsx:34`의 폴백 로직:
```tsx
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
```

| 환경 | 동작 |
|------|------|
| 로컬 개발 | `http://localhost:8000`으로 직접 호출 (Vercel rewrite 미경유) |
| Vercel 프로덕션 | `NEXT_PUBLIC_BACKEND_URL`이 미설정이면 동일하게 `http://localhost:8000` 호출 → **API 전체 단절** |

**Vercel 환경변수 대시보드에서 `NEXT_PUBLIC_BACKEND_URL`을 명시적으로 빈 문자열(`""`)로 설정**하거나, 코드를 수정해야 한다. Supabase 연동 자체(Auth, Storage)는 ANON_KEY가 `NEXT_PUBLIC_`으로 노출되므로 브라우저에서 정상 접근 가능하다.

---

## 3. 비즈니스 로직 MVP 부합성 평가

### 3-1. 회원가입·API키 진입 통제 — 🟡 조건부 PASS

| 통제 지점 | 현황 |
|-----------|------|
| 회원가입 UI | **없음** — 이메일 OTP 인증으로만 접근 가능 (Supabase OTP 기반, 별도 가입 폼 없음) ✅ |
| Mock/테스트 계정 차단 | `handleAnalyze` 내 프로덕션 환경 Mock 계정(`@example.com`, `@mock.com`, `test` 포함) 차단 로직 존재 ✅ |
| BYOK KIE API 키 필수 | `api-client.ts:13` — API 키 미설정 시 모든 API 호출 즉시 차단 ✅ |
| B2B 관리자 콘솔 진입 전 단계 안내 | **없음** — 인증 후 워크플로우 페이지로 바로 진입, "현재 내부 테스트 단계" 같은 가이드 문구 부재 ⚠️ |

### 3-2. 현재 코드의 MVP 핵심 결함 — 🔴 P0 2건

**[P0-B01] 미정의 컴포넌트 `<TrafficLightUX />` (`RaptorWorkflow.tsx:1289`)**

```tsx
{step === 3 && finalAssets && (
  <TrafficLightUX />   // ← 이 이름의 컴포넌트가 파일 내 어디에도 import/define 없음
<div className="animate-in ...">
```

`next.config.ts`에 `ignoreBuildErrors` 설정이 없으므로 TypeScript `TS2304` 빌드 오류가 발생하여 **Vercel 배포 자체가 실패**한다. Step 3 이후 전체 워크플로우 사용 불가.

**[P0-B02] IIFE 스코프 버그 — Step 4/5 버튼 영구 미표시 (`lines 1917, 1932`)**

`completedImages`, `completedVideos`, `totalScenes` 세 변수는 **line 1753의 IIFE 블록 내부**에서 정의되고 `})()}`(line 1834)에서 스코프 종료. 하지만 버튼 조건식은 IIFE **외부**에서 이 변수들을 참조:

```tsx
// IIFE 블록 외부 (line 1917) → completedImages는 undefined
{completedImages === totalScenes && completedVideos < totalScenes && (
  <button onClick={() => handleGenerateClips()}>비디오 클립 생성 시작 (Step 4)</button>
)}
// undefined === N → false → 버튼 절대 미표시
{completedVideos === totalScenes && totalScenes > 0 && (
  <button onClick={() => handleRenderFinal()}>최종 렌더링 시작 (Step 5)</button>
)}
```

**결과:** Step 4에서 사용자가 어떤 조작을 해도 "비디오 클립 생성 시작"과 "최종 렌더링 시작" 버튼이 **절대로 화면에 나타나지 않아** 워크플로우 진행 완전 불가.

---

## 4. 코어 파이프라인 폭주 원인 분석 및 해결 방안

### 4-1. 현재 코드 기준 useEffect 전수 분석

`RaptorWorkflow.tsx` 전체에 `useEffect`는 **단 2개**만 존재한다:

```tsx
// useEffect #1 (line 79): 렌더링 큐 상태 폴링 (5초 interval)
// → /api/status/render에서 active_renders 숫자를 가져와 신호등 UI 업데이트
// → 파이프라인 자동 실행 없음

// useEffect #2 (line 123): 컴포넌트 mount 초기화
// → setMounted(true), setErrorMessage(null), renderStatus 리셋
// → 파이프라인 자동 실행 없음
```

**현재 코드에는 이미지 완료 후 자동으로 Step 4/5를 실행하는 useEffect가 존재하지 않는다.** P0-B02 스코프 버그로 인해 Step 4 버튼 자체가 렌더링되지 않는 상태다.

### 4-2. 폭주의 실제 발생 경로 — 🚨 핵심 발견

**"폭주"는 현재 사용자가 실서비스에서 사용 중인 이전 배포 버전에서 발생하고 있다.** 현재 `main` 브랜치의 코드가 Vercel에 정상 배포되지 않은 상태(P0-B01 빌드 에러)이므로, 사용자는 이전 빌드를 사용 중일 가능성이 높다.

이전 버전들의 리뷰 보고서를 역추적하면, 초기 파이프라인 설계에는 다음과 같은 **자동 연쇄 실행 useEffect** 패턴이 있었을 것으로 강하게 추정된다:

```tsx
// [구 버전 추정 코드 — 폭주 유발 패턴]
useEffect(() => {
  if (allImagesReady && step === 3) {
    setStep(4);
    handleGenerateClips(); // ← 이미지 완료 즉시 Step 4 자동 실행
  }
}, [allImagesReady]);

useEffect(() => {
  const allDone = finalAssets?.script?.every(
    (s: any) => s.video_url || s.use_image_only
  );
  if (allDone && step === 4) {
    handleRenderFinal(); // ← 클립 완료 즉시 Step 5 자동 실행
  }
}, [finalAssets?.script]);
```

또한 현재 코드에서도 **잠재적 폭주 씨앗**이 남아있다:

```tsx
// line 1783 — Visual Tracker Stage 4
{ action: handleGenerateClips, actionLabel: '실패한 씬 비디오 생성 재시도' }
// → isError 상태가 되면 버튼이 UI에 출현하는 구조
// → 에러 상태 판정 조건이 느슨하면 사용자 의도 없이 실행 가능

// line 771-776 — handleRenderVideoFromScratch
const handleRenderVideoFromScratch = async () => {
  const cleanScript = finalAssets.script.map((s) => ({ ...s, video_url: undefined }));
  setFinalAssets({ ...finalAssets, script: cleanScript });
  handleGenerateClips(cleanScript); // ← 직접 호출
};
// 이 함수가 어떤 버튼에 연결되어 있는지, 실수로 호출되는 경로가 없는지 검증 필요
```

### 4-3. 완전 수동 통제 전환 — 확정 코드 스니펫

아래는 파이프라인 관절을 물리적으로 절단하고 100% 수동 클릭 기반으로 전환하는 패치다. P0-B01(TrafficLightUX), P0-B02(IIFE 스코프)를 동시에 수정한다.

**[패치 1] `RaptorWorkflow.tsx` — IIFE 변수 스코프를 컴포넌트 레벨로 호이스팅**

```tsx
// ❌ 기존: IIFE 내부에서만 정의됨 (line 1753 블록 안)
// ✅ 수정: 컴포넌트 최상위 레벨에 상수로 선언

// useWorkflowStore 훅 호출 직후, return문 위에 배치
const script = finalAssets?.script || [];
const totalScenes = script.length || 0;
const completedImages = script.filter((s: any) => s.image_url).length;
const completedVideos = script.filter((s: any) => s.video_url || s.use_image_only).length;
const allVideosReady = completedVideos === totalScenes && totalScenes > 0;
```

**[패치 2] `RaptorWorkflow.tsx` — `<TrafficLightUX />` 제거**

```tsx
// ❌ 기존 (line 1289)
{step === 3 && finalAssets && (
  <TrafficLightUX />
<div className="animate-in fade-in slide-in-from-bottom-4 space-y-8">

// ✅ 수정
{step === 3 && finalAssets && (
  <div className="animate-in fade-in slide-in-from-bottom-4 space-y-8">
```

**[패치 3] `RaptorWorkflow.tsx` — Step 3 실행 게이트 추가 (이미지 완료 후 자동 진행 차단)**

```tsx
// handleGenerateImages 함수 내 finally 블록
} finally {
  setLoading(false);
  // 이미지 생성 완료 후 어떠한 자동 전환도 없음.
  // 사용자가 명시적으로 "Step 4로 이동" 버튼을 눌러야만 진행 가능.
}
```

**[패치 4] Step 4 버튼 완전 수동 통제 — 스코프 버그 수정 및 실행 잠금**

```tsx
{/* Step 4: Final Video Render */}
{step === 4 && finalAssets && (() => {
  // 이 IIFE 내부에서 변수를 재선언해도 되고,
  // 위에서 컴포넌트 레벨로 호이스팅한 변수를 직접 사용해도 됨
  return (
    <div className="w-full space-y-4">
      {/* 
        [물리적 수동 통제 게이트]
        조건: 이미지가 전부 완료되었고 & 아직 비디오가 없을 때만 버튼 표시
        절대로 자동 실행되지 않음 — onClick만이 유일한 실행 경로
      */}
      {completedImages === totalScenes && completedVideos < totalScenes && (
        <button
          onClick={() => handleGenerateClips()}
          disabled={isRendering || loading}
          className="w-full bg-blue-600/20 border border-blue-500/30 text-blue-300 
                     py-3 px-6 rounded-2xl font-bold text-xs uppercase tracking-widest 
                     flex items-center justify-center gap-2 
                     hover:bg-blue-600/30 hover:border-blue-500/50 transition-all 
                     shadow-lg active:scale-[0.98] disabled:opacity-50"
        >
          {loading && !isRendering ? (
            <><Loader2 className="w-4 h-4 animate-spin text-blue-300" /> 클립 생성 중...</>
          ) : (
            <><Film className="w-5 h-5" /> 비디오 클립 생성 시작 (Step 4)</>
          )}
        </button>
      )}

      {/* 
        [물리적 수동 통제 게이트]
        조건: 모든 비디오(스틸컷 포함)가 준비된 후에만 버튼 표시
        Step 4 완료 → 자동으로 렌더링 시작 절대 없음
      */}
      {allVideosReady && (
        <button
          onClick={() => handleRenderFinal()}
          disabled={isRendering || loading}
          className="w-full bg-emerald-600/20 border border-emerald-500/30 text-emerald-300 
                     py-3 px-6 rounded-2xl font-bold text-xs uppercase tracking-widest 
                     flex items-center justify-center gap-2 
                     hover:bg-emerald-600/30 hover:border-emerald-500/50 transition-all 
                     shadow-lg active:scale-[0.98] disabled:opacity-50"
        >
          {isRendering ? (
            <><Loader2 className="w-4 h-4 animate-spin text-emerald-300" /> 최종 렌더링 진행 중 {renderProgress}%</>
          ) : (
            <><Upload className="w-5 h-5" /> 최종 시퀀스 렌더링 시작 (Step 5)</>
          )}
        </button>
      )}
    </div>
  );
})()}
```

**[패치 5] handleGenerateClips 내 clips_ready 처리 — 렌더링 자동 연쇄 원천 차단**

```tsx
// handleGenerateClips 내부 SSE 스트림 처리 (line 618)
if (data.clips_ready) {
  setLoading(false);
  // ⚠️ 절대 여기서 handleRenderFinal()을 호출하지 말 것.
  // 최종 렌더링은 사용자가 "최종 렌더링 시작" 버튼을 클릭했을 때만 실행.
}
```

---

## 종합 액션 아이템

| 우선순위 | 항목 | 파일 | 조치 |
|---------|------|------|------|
| 🔴 P0 | `<TrafficLightUX />` 미정의 컴포넌트 제거 | `RaptorWorkflow.tsx:1289` | 태그 삭제, JSX 구조 정상화 |
| 🔴 P0 | IIFE 스코프 버그 수정 (Step 4/5 버튼 복구) | `RaptorWorkflow.tsx:1917,1932` | 변수 컴포넌트 레벨 호이스팅 |
| 🔴 P0 | `NEXT_PUBLIC_BACKEND_URL` 환경변수 설정 | Vercel 대시보드 | 빈 문자열(`""`)로 설정 |
| 🟡 P1 | Git 배포 브랜치 통일 (`main` ↔ `master`) | GitHub + Vercel/Render 설정 | Vercel/Render 배포 트리거 브랜치를 `main`으로 통일 |
| 🟡 P1 | `RAPTOR-Composer/` 미추적 디렉토리 정리 | 로컬 파일시스템 | 용도 확인 후 삭제 또는 `.gitignore` 추가 |
| 🟢 P2 | 스틸컷 배지 조건 수정 (`use_image_only && !!image_url`) | `RaptorWorkflow.tsx:1615` | 조건식 교체 |
| 🟢 P2 | MVP 단계 안내 문구 추가 | `AuthDashboard.tsx` | 로그인 후 "내부 테스트 버전" 배너 표시 |
