/**
 * api-client.test.ts
 * RAPTOR v2.14.2 — 최신 단일 KIE 키 아키텍처(Zustand store.kieKey + X-BYOK-KIE) 기반 테스트
 *
 * 갱신 이력:
 *   v2.14.2-hotfix: 구형 멀티키(raptor_grok_key, X-BYOK-Grok) 잔재 완전 철거
 *                   Zustand store.kieKey 모킹 + X-BYOK-KIE 헤더 검증으로 전면 교체
 */

import { api } from './api-client';

// ─── Zustand store 모킹 ──────────────────────────────────────────────────────
// api-client.ts는 useWorkflowStore.getState()를 직접 호출하므로 모듈 단위로 mock
jest.mock('@/store/useWorkflowStore', () => ({
  useWorkflowStore: {
    getState: jest.fn(),
  },
}));

import { useWorkflowStore } from '@/store/useWorkflowStore';
const mockGetState = useWorkflowStore.getState as jest.Mock;

// ─── fetch 모킹 유틸 ─────────────────────────────────────────────────────────
const createMockFetch = (responseData: any = { success: true }) =>
  jest.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(responseData),
    text: () => Promise.resolve(JSON.stringify(responseData)),
  });

// ─── 기본 store 상태 팩토리 ──────────────────────────────────────────────────
const makeStore = (overrides: Partial<{
  kieKey: string;
  isKeyConfigured: boolean;
  csrfToken: string | null;
  claudeModel: string;
  setCsrfToken: (t: string | null) => void;
}> = {}) => ({
  kieKey: '',
  isKeyConfigured: false,
  csrfToken: 'test-csrf-token',
  claudeModel: 'claude-sonnet-4-6',
  setCsrfToken: jest.fn(),
  ...overrides,
});

// ─────────────────────────────────────────────────────────────────────────────

describe('api-client — X-BYOK-KIE 헤더 전송 (v2.14.2 단일 KIE 아키텍처)', () => {

  let mockFetch: jest.Mock;

  beforeEach(() => {
    mockFetch = createMockFetch();
    global.fetch = mockFetch;
    jest.clearAllMocks();
  });

  // ── T1: KIE 키가 store에 있을 때 헤더 정상 전송 ──────────────────────────
  test('T1: store.kieKey 있을 때 X-BYOK-KIE 헤더 전송', async () => {
    mockGetState.mockReturnValue(makeStore({
      kieKey: 'test-kie-api-key-12345',
      isKeyConfigured: true,
    }));

    await api.post('/generate-plan', { product_name: 'Test Product' });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/generate-plan'),
      expect.objectContaining({
        headers: expect.objectContaining({
          'X-BYOK-KIE': 'test-kie-api-key-12345',
        }),
      })
    );
  });

  // ── T2: KIE 키가 없을 때 헤더 미포함 ────────────────────────────────────
  test('T2: store.kieKey 없을 때 X-BYOK-KIE 헤더 미포함', async () => {
    mockGetState.mockReturnValue(makeStore({
      kieKey: '',
      isKeyConfigured: false,
    }));

    // isKeyConfigured=false이면 auth route 외엔 에러를 throw하므로 catch
    await expect(
      api.post('/generate-plan', { product_name: 'Test' })
    ).rejects.toThrow('API 키가 설정되지 않았습니다');

    // fetch가 호출되지 않았어야 함 (키 없어 early throw)
    expect(mockFetch).not.toHaveBeenCalled();
  });

  // ── T3: X-CSRF-Token 헤더도 함께 전송 ───────────────────────────────────
  test('T3: csrfToken 있을 때 X-CSRF-Token 헤더 전송', async () => {
    mockGetState.mockReturnValue(makeStore({
      kieKey: 'test-kie-api-key-12345',
      isKeyConfigured: true,
      csrfToken: 'csrf-abc-123',
    }));

    await api.post('/generate-plan', { product_name: 'Test Product' });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/generate-plan'),
      expect.objectContaining({
        headers: expect.objectContaining({
          'X-CSRF-Token': 'csrf-abc-123',
          'X-BYOK-KIE': 'test-kie-api-key-12345',
        }),
      })
    );
  });

  // ── T4: auth 라우트는 키 없어도 통과 ────────────────────────────────────
  test('T4: auth 라우트(/auth/*)는 isKeyConfigured 체크 스킵', async () => {
    mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ csrf_token: 'new-csrf' }),
    });
    global.fetch = mockFetch;

    mockGetState.mockReturnValue(makeStore({
      kieKey: '',
      isKeyConfigured: false,
      csrfToken: 'some-token',
    }));

    // auth 라우트는 키 없어도 요청 통과
    await expect(api.get('/auth/csrf-token')).resolves.toEqual({ csrf_token: 'new-csrf' });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/auth/csrf-token'),
      expect.any(Object)
    );
  });

  // ── T5: 구형 헤더(X-BYOK-Grok 등) 미전송 확인 ──────────────────────────
  test('T5: 구형 X-BYOK-Grok 헤더는 전송되지 않음', async () => {
    mockGetState.mockReturnValue(makeStore({
      kieKey: 'test-kie-api-key-12345',
      isKeyConfigured: true,
    }));

    await api.post('/generate-plan', { product_name: 'Test Product' });

    const calledHeaders = mockFetch.mock.calls[0][1].headers;
    expect(calledHeaders).not.toHaveProperty('X-BYOK-Grok');
    expect(calledHeaders).not.toHaveProperty('X-BYOK-Haiku');
    expect(calledHeaders).not.toHaveProperty('X-BYOK-Claude');
  });

  // ── T6: credentials: 'include' 포함 확인 ────────────────────────────────
  test('T6: 모든 요청에 credentials: include 포함', async () => {
    mockGetState.mockReturnValue(makeStore({
      kieKey: 'test-kie-api-key-12345',
      isKeyConfigured: true,
    }));

    await api.post('/generate-plan', { product_name: 'Test Product' });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        credentials: 'include',
      })
    );
  });
});
