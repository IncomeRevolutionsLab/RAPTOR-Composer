import { api } from './api-client';

describe('api-client BYOK headers', () => {
  beforeEach(() => {
    // Mock localStorage
    const localStorageMock = (function() {
      let store: Record<string, string> = {};
      return {
        getItem: (key: string) => store[key] || null,
        setItem: (key: string, value: string) => { store[key] = value.toString(); },
        clear: () => { store = {}; }
      };
    })();
    Object.defineProperty(window, 'localStorage', { value: localStorageMock });
    window.localStorage.clear();
  });

  test('Test 1: Injects X-BYOK-Grok header from localStorage', async () => {
    window.localStorage.setItem('raptor_grok_key', 'test-xai-key');
    
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true }),
    });
    global.fetch = mockFetch;

    await api.post('/generate-plan', { product_name: 'Test' }, 'preview');

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/generate-plan'),
      expect.objectContaining({
        headers: expect.objectContaining({
          'X-BYOK-Grok': 'test-xai-key'
        })
      })
    );
  });
});
