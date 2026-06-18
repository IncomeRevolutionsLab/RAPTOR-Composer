# P3 장기 백로그: 프론트엔드 에러 Sanitizer 레이어 도입

**우선순위**: P3 (장기 과제)
**발견 출처**: `v2.19.12` [P2-P3] 리팩토링 클로드 3차 Post-Review
**관련 모듈**: `src/components/RaptorWorkflow.tsx` 내 `extractErrorMessage` 헬퍼

## 배경 및 이슈 설명
에러 로깅 및 디스플레이 고도화 작업 과정에서 `extractErrorMessage` 헬퍼 함수가 `typeof e === 'object'` 인 경우 `JSON.stringify(e)`를 반환하도록 고도화되었습니다. 
이로 인해 런타임에서 알 수 없는 포맷의 에러 객체가 던져질 때 `[object Object]`로 뭉개지지 않고 직렬화되어 추적이 쉬워지는 장점을 얻었습니다.

하지만, **백엔드(혹은 타 API)에서 반환하는 에러 객체 내에 내부 디렉토리 경로, 스택 트레이스 등 민감한 서버 정보가 포함될 경우, 이를 프론트엔드 UI(`setErrorMessage`)로 그대로 노출할 위험(정보 과잉 노출)**이 존재합니다.

## 조치 목표 (To-Do)
- [ ] 현재 백엔드가 내려주는 에러 객체의 스키마를 점검하여 민감 정보가 포함되는지 확인
- [ ] 필요 시 프론트엔드 단에 **Error Sanitizer (에러 정제) 레이어**를 도입
- [ ] `extractErrorMessage`에서 `JSON.stringify`를 호출하기 전에, 정제 함수를 거쳐 안전하게 필터링된 정보만 직렬화하도록 파이프라인 수정
  
```typescript
// 도입 예상 슈도코드:
const sanitizeErrorObject = (obj: any) => {
  // 민감 키워드(stack, path, trace 등) 제거 로직 구현
  const { stack, path, ...safeObj } = obj; 
  return safeObj;
}

const extractErrorMessage = (e: any): string => 
  e instanceof Error ? e.message : (typeof e === 'object' && e !== null ? JSON.stringify(sanitizeErrorObject(e)) : String(e));
```

*(본 백로그는 VIBE 프레임워크의 Security/Integrity 강화의 일환으로 차후 스프린트에서 검토 후 반영할 예정입니다.)*
