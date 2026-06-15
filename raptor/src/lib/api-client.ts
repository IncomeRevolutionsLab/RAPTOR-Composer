import { useWorkflowStore } from "@/store/useWorkflowStore";
import { supabase } from "@/lib/supabaseClient";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

export const api = {
  async request(method: 'GET' | 'POST', path: string, body: any = null, quality: string = 'preview') {
    const store = useWorkflowStore.getState();
    const { isKeyConfigured, csrfToken, claudeModel } = store;

    const isAuthRoute = path.startsWith('/auth/');

    if (!isAuthRoute && !isKeyConfigured) {
      throw new Error("API 키가 설정되지 않았습니다. Global Settings에서 KIE API Key를 입력해 주세요.");
    }

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (store.kieKey) {
      headers['X-BYOK-KIE'] = store.kieKey;
    }

    // [P1 FIX] Authorization: Bearer — Supabase 세션 JWT 동적 첨부 (401 원천 차단)
    if (!isAuthRoute) {
      try {
        const { data: sessionData } = await supabase.auth.getSession();
        const accessToken = sessionData?.session?.access_token;
        if (accessToken) {
          headers['Authorization'] = `Bearer ${accessToken}`;
        }
      } catch (err) {
        console.warn('[api-client] Failed to attach Authorization header:', err);
      }
    }

    let activeCsrfToken = csrfToken;

    if (!activeCsrfToken && path !== '/auth/csrf-token') {
      try {
        const res = await fetch(`${BACKEND_URL}/api/auth/csrf-token`, {
          method: 'GET',
          credentials: 'include',
        });
        if (res.ok) {
          const data = await res.json();
          if (data.csrf_token) {
            store.setCsrfToken(data.csrf_token);
            activeCsrfToken = data.csrf_token;
          }
        }
      } catch (err) {
        console.error("Failed to pre-fetch CSRF token", err);
      }
    }

    if (activeCsrfToken) {
      headers['X-CSRF-Token'] = activeCsrfToken;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 1800000); // 30 mins timeout for heavy pipelines

    let fetchOptions: RequestInit = {
      method: method,
      headers: headers,
      credentials: 'include',
      signal: controller.signal
    };

    if (method === 'POST' && body) {
      const requestBody: any = { ...body, quality };
      if (path === '/generate-plan' && claudeModel) {
        requestBody.model = claudeModel;
      }
      fetchOptions.body = JSON.stringify(requestBody);
    }

    try {
      const response = await fetch(`${BACKEND_URL}/api${path}`, fetchOptions);

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorText = await response.text();
        let detail = errorText;
        try {
          const json = JSON.parse(errorText);
          detail = json.detail || errorText;
        } catch (e) {}

        let userMessage: string;
        if (response.status === 401) {
          userMessage = 'API 키가 누락되었거나 만료되었습니다. 우측 상단에 API 키를 다시 입력해 주세요.';
        } else if (response.status === 403) {
          userMessage = `접근이 거부되었습니다. CSRF 토큰이 만료되었을 수 있습니다. 페이지를 새로고침 후 다시 시도해 주세요. (${detail})`;
        } else if (response.status === 500) {
          userMessage = `서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해 주세요. (${detail})`;
        } else {
          userMessage = `API Error (${response.status}): ${detail}`;
        }
        throw new ApiError(response.status, userMessage);
      }

      return await response.json();
    } catch (err: any) {
      if (err.name === 'AbortError') {
        throw new Error('요청 시간이 초과되었습니다. 서버 연결을 확인해 주세요.');
      }
      const errMsg = (err.message || '').toLowerCase();
      if (err instanceof TypeError || errMsg.includes('failed to fetch') || errMsg.includes('networkerror') || errMsg.includes('network error')) {
        throw new Error('서버와 연결할 수 없습니다. (CORS 오류, 서드파티 쿠키 차단 또는 백엔드 장애 의심)');
      }
      throw err;
    }
  },

  async post(path: string, body: any, quality: string = 'preview') {
    return this.request('POST', path, body, quality);
  },

  async get(path: string) {
    return this.request('GET', path);
  }
};

