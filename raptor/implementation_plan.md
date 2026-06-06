# [Goal Description]
최종 Human Validation 과정에서 발견된 5가지 치명적 결함을 긴급 수술하여, 클라우드 실서버의 API 통신 장애를 해결하고 사용자 인증(Auth) 및 메인 UI/UX 편의성을 완성합니다.

## User Review Required
> [!IMPORTANT]
> **v2.14.1 주요 핫픽스 조치 항목:**
> 1. **CORS 새 도메인 즉시 반영 (`main.py`):** Koyeb 백엔드 환경변수 외에도 소스 코드 레벨에서 `origins`에 `https://raptor-composer.vercel.app`을 명시적으로 추가하여 환경변수 누락 시의 Fallback 리스크를 원천 차단합니다.
> 2. **네트워크 에러 한글화 (`api-client.ts` & `AuthDashboard.tsx`):** 백엔드 오프라인 혹은 CORS 차단으로 발생하는 `Failed to fetch` 에러 감지 시, 사용자에게 "서버와 연결할 수 없습니다. 잠시 후 다시 시도해주세요."라는 친절한 한글 안내를 출력합니다.
> 3. **비밀번호 찾기 기능 도입 (`AuthDashboard.tsx`):** 로그인 화면에 "비밀번호 찾기" 토글 모드를 구현하고, Supabase의 `resetPasswordForEmail` 재설정 링크 발송 로직을 연결합니다.
> 4. **회원가입 비밀번호 정책 안내 및 6자 가드 (`AuthDashboard.tsx`):** 회원가입 모드일 때 비밀번호 필드 아래에 정책 안내를 표시하고, 6자 미만 가입 시도 시 프론트엔드에서 즉각 오류("비밀번호는 최소 6자 이상이어야 합니다.")를 띄워 가드합니다.
> 5. **로그인 버튼 레이아웃 겹침 수정 (`AuthDashboard.tsx`):** 로그인 버튼의 CSS 포지셔닝을 `absolute top-12 right-24 z-[40]`에서 `fixed top-6 right-6 z-[999]`로 변경하여, 랩터 타이틀 및 하단 조작계 레이아웃과의 물리적 겹침 현상을 해결합니다.

## Open Questions
- Supabase 비밀번호 재설정(`resetPasswordForEmail`) 완료 후 사용자가 도메인으로 돌아올 때의 redirect 경로 설정은 `https://raptor-composer.vercel.app`으로 고정하는 것이 적절합니까? 본 계획에서는 `window.location.origin`을 이용해 배포/로컬 환경에 맞춰 유연하게 리다이렉트되도록 설계했습니다.

---

## Proposed Changes

### 백엔드 (Backend)

#### [MODIFY] [main.py](file:///c:/Antigravity%20Work/RAPTOR/main.py)
- CORS 허용 `origins` 목록에 새 도메인인 `https://raptor-composer.vercel.app`을 기본값으로 추가 주입하여 환경변수 미반영 등의 실수를 이중으로 방어합니다.

---

### 프론트엔드 (Frontend)

#### [MODIFY] [api-client.ts](file:///c:/Antigravity%20Work/RAPTOR/src/lib/api-client.ts)
- `fetch` 요청의 `catch` 블록에서 `TypeError`나 메시지에 `failed to fetch`, `networkerror` 등이 포함된 네트워크 예외 발생 시, "서버와 연결할 수 없습니다. 잠시 후 다시 시도해주세요."라는 커스텀 Error를 throw하도록 개선합니다.

#### [MODIFY] [AuthDashboard.tsx](file:///c:/Antigravity%20Work/RAPTOR/src/components/AuthDashboard.tsx)
- 하드코딩된 백엔드 호스트(`http://localhost:8000`)를 환경 변수 기반 `BACKEND_URL` 상수로 교체합니다.
- 로그인 폼 내부의 raw `fetch` 통신(로그인, 회원가입) 및 프로젝트 내역 조회 API에서 발생하는 네트워크 예외도 한글 에러 메시지로 가드 및 매핑합니다.
- `isForgotPasswordMode` 상태 변수를 도입하여, 이메일만 입력받고 Supabase `supabase.auth.resetPasswordForEmail`을 호출하는 UI 모드를 구현합니다.
- 회원가입 모드 시 비밀번호 안내 문구(`* 비밀번호는 최소 6자 이상이어야 합니다.`)를 표시하고, 가입 서브밋 전 6자 미만 여부를 프론트엔드 레벨에서 체크하여 `authError`로 가드합니다.
- 로그인/프로필 버튼의 래퍼 클래스를 `fixed top-6 right-6 z-[999]`로 교정하여 UI 겹침 문제를 제거합니다.

---

## Verification Plan

### Automated Tests
- `npm run build`를 통해 프론트엔드 빌드 무결성 확인 및 Next.js 정적 타입 검사 수행.
- 로컬 Uvicorn 및 Next.js 데브 서버 기동 상태에서 로그인 및 비밀번호 초기화 흐름 검증.

### Manual Verification
1. **CORS 및 백엔드 연결 확인:**
   - 로컬 프론트엔드와 백엔드가 정상적으로 통신하는지 검증하고, 백엔드를 일시적으로 다운시킨 후 "서버와 연결할 수 없습니다..." 한글 메시지가 팝업되는지 확인합니다.
2. **비밀번호 찾기 메일 발송 검증:**
   - 로그인 모달에서 "비밀번호 찾기" 링크를 클릭하고, 유효한 이메일을 입력한 후 발송을 요청하여 Supabase 이메일 재설정 메일이 전송되는지 확인합니다.
3. **비밀번호 6자 정책 및 가입 제한 검증:**
   - 회원가입 창에서 5글자 비밀번호 입력 후 가입 시도를 했을 때, API를 호출하지 않고 프론트에서 가드하는지 확인합니다.
4. **로그인 버튼 겹침 확인:**
   - 브라우저 해상도를 다양하게 변경해가며 로그인 버튼이 타이틀 이미지 및 하단 패널 등과 겹치지 않고 잘 배치되어 있는지 육안으로 검증합니다.
