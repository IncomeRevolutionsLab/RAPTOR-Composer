충분한 데이터를 확보했습니다. 2차 사후 리뷰 보고서를 작성합니다.

---

# RAPTOR 2차 사후 리뷰 보고서 (Post-Review v2)

| 항목 | 내용 |
|---|---|
| **검토 대상** | `src/components/RaptorWorkflow.tsx` — `handleRenderVideo` 함수 및 렌더링 상태 트래커 로직 |
| **검토 범위** | 1차 리뷰 5대 결함(R-1 ~ R-5) 핫픽스 적용 여부 |
| **작성일** | 2026-06-04 |

---

## ✅ 조치 완료 항목

### R-1 · 하드코딩 계정 덮어쓰기 버그
**판정: 완료**

`handleRenderVideo` L.472에 `if (!store.user)` 가드가 명확히 구현되어 있음. 로그인이 없는 상태에서 렌더 요청 자체가 차단됨.

---

### R-2 · 비용 UI 조기 노출
**판정: 완료**

Step 4 헤더 섹션(L.1490–1498)에서 비용 블록 코드가 완전히 제거되었음. 해당 영역에는 타이틀과 메타 정보만 남아 있음.

---

### R-4 · AI 이미지 일괄 생성 버튼 비활성화 누락
**판정: 완료 (단, 조건 범위에 미세 간극 존재)**

`allImagesReady` 도출 및 `disabled={allImagesReady || loading}` 적용이 L.1172~1228에 구현됨. 조건은 아래와 같이 정의됨:

```ts
// L.1172–1176
finalAssets.script.every((s: any) =>
  s.image_url &&
  (s.image_url.startsWith('http') || s.image_url.startsWith('data:image')) &&
  s.status !== 'rendering' &&
  s.status !== 'error'
)
```

사전 리뷰 N-3에서 권고했던 `status !== 'generating'` 조건은 이 프로젝트에서 생성 중 상태를 `'rendering'`으로 쓰므로 실질적으로 동등하게 방어됨. **단, `image_url`이 빈 문자열(`""`)인 경우 falsy 체크를 통과하여 `allImagesReady`가 `true`로 오판될 수 있는 엣지케이스는 미반영.**

---

### R-5 · KIE 비디오 파싱 에러 및 예외 처리 오류
**판정: 완료**

`handleRenderVideo` 내 에러 처리 파이프라인이 전면 보강됨:

- **HTTP 비정상 응답:** L.551–565, `response.ok` 실패 시 `errorData.detail` 추출 후 명시적으로 throw
- **SSE 스트림 오류:** L.588–590, `data.error` 수신 시 즉시 throw
- **미완료 씬 롤백:** L.636–644, 예외 발생 시 `video_url` 미확보 씬 전체를 `status: 'error'`로 명시 롤백하여 무한 대기 UX 방지

---

## 🔴 미조치 / 잔존 결함

### R-3 · 404 및 에러 캐시 잔재
**판정: 확인 불가 (RaptorWorkflow.tsx 범위 외)**

해당 수정은 `useWorkflowStore.ts`의 `onRehydrateStorage` 콜백에서 이루어져야 하며, 본 리뷰 대상 파일에서는 직접 확인 불가. **별도로 `useWorkflowStore.ts` 검증이 필요함.**

---

### P-5 잔존 · 수동 업로드 씬 덮어쓰기 위험
**판정: 부분 조치, 취약 경로 잔존**

`handleGenerateImages` L.298의 `if (scene.image_url)` 조건으로 이미 이미지가 있는 씬은 스킵되지만, `image_source: 'manual'`이 설정되어 있어도 `image_url`이 아직 `null`인 씬(예: 사용자가 업로드 시도 중이나 URL 미확정 상태)은 AI 생성 루프에서 스킵되지 않음. 사전 리뷰 P-5의 핵심 위험인 "혼합 씬 상태에서의 수동 업로드 덮어쓰기"가 완전히 해소되지 않음.

---

## 📊 종합

| 결함 | 판정 | 비고 |
|---|---|---|
| R-1 user 가드 | ✅ 완료 | |
| R-2 비용 UI | ✅ 완료 | |
| R-3 에러 캐시 | ⚠️ 확인 불가 | `useWorkflowStore.ts` 별도 검증 필요 |
| R-4 버튼 비활성화 | ✅ 완료 (미세 간극) | `image_url: ""` 엣지케이스 미처리 |
| R-5 에러 처리 | ✅ 완료 | |

**조치 필요 잔존 사항 2건:**
1. `useWorkflowStore.ts`의 `onRehydrateStorage` 수정 여부를 확인하여 R-3 결론을 확정할 것
2. `allImagesReady` 조건에 `s.image_url !== ''` 명시적 비교를 추가하고, `handleGenerateImages`의 스킵 조건을 `if (scene.image_url || scene.image_source === 'manual')`로 강화할 것
