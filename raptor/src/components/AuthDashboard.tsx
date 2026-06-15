"use client";

import { useState, useEffect, useRef, useCallback } from 'react';
import { User, LogOut, FolderSync, Download, Settings, Lock, Mail, AlertCircle, CheckCircle, Loader2, Eye, EyeOff, RefreshCw } from 'lucide-react';
import { useWorkflowStore } from '@/store/useWorkflowStore';
import { supabase } from '@/lib/supabaseClient';

// ============================================================
// [UTIL] localStorage 파싱 공통 함수 (중복 제거)
// ============================================================
const getLocalStoredUserId = (): string => {
  if (typeof window === 'undefined') return '';
  try {
    const raw = localStorage.getItem('raptor-workflow-storage');
    if (!raw) return '';
    return JSON.parse(raw)?.state?.userId || '';
  } catch {
    return '';
  }
};

// ============================================================
// [UTIL] 비디오 URL 절대경로 변환
// ============================================================
const getAbsoluteVideoUrl = (url: string) => {
  if (!url) return "";
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  const baseUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const cleanBase = baseUrl.replace(/\/$/, "");
  const cleanUrl = url.startsWith("/") ? url : `/${url}`;
  return `${cleanBase}${cleanUrl}`;
};

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

// ============================================================
// [TYPE] 프로젝트 행 타입 명시
// ============================================================
interface ProjectRow {
  task_id: string;
  project_id: string;
  product_name: string;
  description: string;
  status: 'success' | 'failed' | 'pending' | string;
  result_url?: string;
}

// ============================================================
// 토스트 컴포넌트
// ============================================================
interface ToastProps {
  message: string;
  type: 'success' | 'error' | 'info';
  onClose: () => void;
}

function Toast({ message, type, onClose }: ToastProps) {
  // [FIX] onClose를 deps에 포함 — 부모에서 useCallback으로 안정화됨
  useEffect(() => {
    const timer = setTimeout(onClose, 4000);
    return () => clearTimeout(timer);
  }, [onClose]);

  const bgColor =
    type === 'success' ? 'bg-green-500/20 border-green-500/40 text-green-300' :
    type === 'error' ? 'bg-red-500/20 border-red-500/40 text-red-300' :
    'bg-blue-500/20 border-blue-500/40 text-blue-300';

  const Icon = type === 'success' ? CheckCircle : type === 'error' ? AlertCircle : Mail;

  return (
    <div className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-[9999] flex items-center gap-3 px-5 py-3.5 rounded-2xl border backdrop-blur-md shadow-2xl text-xs font-bold animate-in slide-in-from-bottom-4 duration-300 max-w-sm w-full ${bgColor}`}>
      <Icon className="w-4 h-4 shrink-0" />
      <span className="flex-1">{message}</span>
      <button onClick={onClose} className="text-current opacity-60 hover:opacity-100 transition-opacity">✕</button>
    </div>
  );
}

// ============================================================
// OTP 입력 컴포넌트 (6자리) — [P2] onComplete 자동 제출 지원
// ============================================================
interface OtpInputProps {
  value: string;
  onChange: (val: string) => void;
  onComplete?: (otp: string) => void;
  disabled?: boolean;
}

function OtpInput({ value, onChange, onComplete, disabled }: OtpInputProps) {
  const inputs = useRef<(HTMLInputElement | null)[]>([]);

  const handleChange = (index: number, char: string) => {
    const digit = char.replace(/\D/g, '').slice(-1);
    const arr = value.split('').concat(Array(6).fill('')).slice(0, 6);
    arr[index] = digit;
    const next = arr.join('');
    onChange(next);
    if (digit && index < 5) {
      inputs.current[index + 1]?.focus();
    } else if (digit && index === 5 && next.replace(/\D/g, '').length === 6) {
      // [P2] 6자리 완성 시 자동 제출
      onComplete?.(next);
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace') {
      const arr = value.split('').concat(Array(6).fill('')).slice(0, 6);
      if (!arr[index] && index > 0) {
        arr[index - 1] = '';
        onChange(arr.join(''));
        inputs.current[index - 1]?.focus();
      } else {
        arr[index] = '';
        onChange(arr.join(''));
      }
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    const next = pasted.padEnd(6, '').slice(0, 6);
    onChange(next);
    const lastIdx = Math.min(pasted.length, 5);
    inputs.current[lastIdx]?.focus();
    if (pasted.length === 6) onComplete?.(next);
  };

  return (
    <div className="flex gap-2 justify-center" onPaste={handlePaste}>
      {Array(6).fill(null).map((_, i) => (
        <input
          key={i}
          ref={el => { inputs.current[i] = el; }}
          type="text"
          inputMode="numeric"
          maxLength={1}
          disabled={disabled}
          value={value[i] || ''}
          onChange={e => handleChange(i, e.target.value)}
          onKeyDown={e => handleKeyDown(i, e)}
          className="w-10 h-12 text-center text-lg font-black bg-black/60 border border-white/10 rounded-xl text-white focus:ring-2 focus:ring-purple-500/70 focus:border-purple-500/50 outline-none transition-all caret-transparent disabled:opacity-40"
        />
      ))}
    </div>
  );
}


export default function AuthDashboard() {
  const { user, setUser, lastRenderTimestamp, hasHydrated, isKeyConfigured, setIsKeyConfigured, setCsrfToken, resetWorkflow } = useWorkflowStore();

  // Dashboard Modal Toggle
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'project' | 'settings' | 'account'>('project');

  // Auth Form State (Logged Out)
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoginMode, setIsLoginMode] = useState(true);
  const [isForgotPasswordMode, setIsForgotPasswordMode] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [authSuccess, setAuthSuccess] = useState<string | null>(null);

  // 비밀번호 눈동자 토글
  const [showPassword, setShowPassword] = useState(false);

  // OTP 인증 상태
  const [otpMode, setOtpMode] = useState(false);
  const [otpEmail, setOtpEmail] = useState('');
  const [otpValue, setOtpValue] = useState('');
  const [otpLoading, setOtpLoading] = useState(false);
  const [otpError, setOtpError] = useState<string | null>(null);
  // [P1 FIX] OTP 목적 상태 — 'signup'(회원가입) | 'recovery'(비밀번호 재설정) 동적 분기
  const [otpPurpose, setOtpPurpose] = useState<'signup' | 'recovery'>('signup');

  // [v2.16.0] 새 비밀번호 설정 모드 상태
  const [updatePasswordMode, setUpdatePasswordMode] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [newPasswordConfirm, setNewPasswordConfirm] = useState('');
  const [updatePasswordLoading, setUpdatePasswordLoading] = useState(false);
  const [updatePasswordError, setUpdatePasswordError] = useState<string | null>(null);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showNewPasswordConfirm, setShowNewPasswordConfirm] = useState(false);
  // [P0 Fix] setUser 지연: recovery 세션 user 임시 보관
  const [recoveryUser, setRecoveryUser] = useState<any>(null);

  // 재발송 쿨다운 + 로딩
  const [resendCooldown, setResendCooldown] = useState(0);
  const [isResendLoading, setIsResendLoading] = useState(false);

  // [FIX] Toast — useCallback으로 안정적 참조, 타이머 리셋 버그 방지
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);
  const closeToast = useCallback(() => setToast(null), []);

  // Project List State
  const [rows, setRows] = useState<ProjectRow[]>([]);
  const [rowsLoading, setRowsLoading] = useState(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [previewVideoUrl, setPreviewVideoUrl] = useState<string | null>(null);

  // KIE Key Setting State
  const [kieKey, setKieKey] = useState('');
  const [visibility, setVisibility] = useState(false);
  const [saved, setSaved] = useState(false);

  // 재발송 쿨다운 타이머
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = setTimeout(() => setResendCooldown(c => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [resendCooldown]);

  // Check KIE Key on Mount
  useEffect(() => {
    if (!hasHydrated) return;
    const store = useWorkflowStore.getState();
    setIsKeyConfigured(!!store.kieKey);
  }, [setIsKeyConfigured, hasHydrated]);

  // Clear password on modal close
  useEffect(() => {
    if (!isModalOpen && !authLoading) {
      setPassword('');
      setShowPassword(false);
    }
  }, [isModalOpen, authLoading]);

  // [SECURITY FIX] Fetch dashboard — Authorization 헤더 추가 (IDOR 방지)
  useEffect(() => {
    if (!isModalOpen) return; // 모달 닫힐 때 불필요한 fetch 방지
    const fetchDashboardData = async () => {
      if (!user) {
        setRows([]);
        return;
      }
      setRowsLoading(true);
      try {
        const { data: sessionData } = await supabase.auth.getSession();
        const accessToken = sessionData?.session?.access_token;
        const res = await fetch(`${BACKEND_URL}/api/dashboard/projects?user_id=${user.id}`, {
          headers: {
            ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
          },
        });
        if (!res.ok) {
          if (res.status === 401) {
            throw new Error('API 키가 누락되었거나 만료되었습니다. 우측 상단에 API 키를 다시 입력해 주세요.');
          } else if (res.status === 403) {
            throw new Error('접근이 거부되었습니다. 페이지를 새로고침 후 다시 시도해 주세요.');
          } else if (res.status === 500) {
            throw new Error('서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.');
          }
          throw new Error('서버 응답 오류가 발생했습니다.');
        }
        const data = await res.json();
        setRows(data.rows || []);
      } catch (err: any) {
        console.warn("Failed to fetch dashboard rows:", err);
        setToast({ message: err.message || "대시보드 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.", type: "error" });
      } finally {
        setRowsLoading(false);
      }
    };
    fetchDashboardData();
  }, [user, lastRenderTimestamp, isModalOpen]);

  // ============================================================
  // OTP 검증 핸들러
  // ============================================================
  const handleVerifyOtp = useCallback(async (autoOtp?: string | React.MouseEvent) => {
    const finalOtp = typeof autoOtp === 'string' ? autoOtp : otpValue;
    if (finalOtp.replace(/\D/g, '').length < 6) {
      setOtpError('6자리 인증번호를 모두 입력해 주세요.');
      return;
    }
    setOtpLoading(true);
    setOtpError(null);
    try {
      const { data, error } = await supabase.auth.verifyOtp({
        email: otpEmail,
        token: finalOtp.replace(/\D/g, ''),
        // [P1 FIX] otpPurpose 기반 동적 분기: 'signup' | 'recovery'
        type: otpPurpose,
      });
      if (error) throw error;
      if (data?.user) {
        const store = useWorkflowStore.getState();
        if (store.userId !== data.user.id) store.resetWorkflow();
        if (otpPurpose === 'recovery') {
          // [v2.16.0 P0 Fix] setUser 지연 — Auth View(!user) 언마운트 방지
          // [v2.16.1] getSession() fallback — verifyOtp session null 시 SDK 타이밍 이슈 대응
          let recoverySession = data.session;
          if (!recoverySession) {
            const { data: fallbackData } = await supabase.auth.getSession();
            recoverySession = fallbackData?.session ?? null;
          }
          if (!recoverySession) {
            setOtpError('세션을 생성할 수 없습니다. 처음부터 다시 시도해 주세요.');
            return;
          }
          // [Condition 2] await setSession 명시 호출 — updateUser() 401 방지
          await supabase.auth.setSession({
            access_token: recoverySession.access_token,
            refresh_token: recoverySession.refresh_token,
          });
          setRecoveryUser(data.user);
          setOtpMode(false);
          setOtpValue('');
          setUpdatePasswordMode(true);
          setToast({ message: '✅ 인증 완료! 새 비밀번호를 설정해 주세요.', type: 'info' });
        } else {
          // signup: 기존 로그인 처리 유지
          setUser(data.user);
          setOtpMode(false);
          setOtpValue('');
          setOtpEmail('');
          setToast({ message: '🎉 이메일 인증 완료! 로그인되었습니다.', type: 'success' });
          setTimeout(() => setIsModalOpen(true), 400);
        }
      } else {
        setOtpError('인증 처리 중 오류가 발생했습니다. 다시 시도해 주세요.');
      }
    } catch (err: any) {
      console.warn('OTP verify failed', err);
      const msg = err.message || '';
      if (msg.includes('Token has expired') || msg.includes('expired')) {
        setOtpError('인증번호가 만료되었습니다. 재발송 버튼을 클릭해 새 번호를 받아주세요.');
      } else if (msg.includes('invalid') || msg.includes('Invalid')) {
        setOtpError('인증번호가 올바르지 않습니다. 다시 확인해 주세요.');
      } else {
        setOtpError(`인증 실패: ${msg}`);
      }
    } finally {
      setOtpLoading(false);
    }
  }, [otpValue, otpEmail, otpPurpose, setUser]);

  // ============================================================
  // [v2.16.0] 새 비밀번호 업데이트 핸들러
  // ============================================================
  const handleUpdatePassword = async () => {
    if (newPassword.length < 6) {
      setUpdatePasswordError('비밀번호는 최소 6자 이상이어야 합니다.');
      return;
    }
    if (newPassword !== newPasswordConfirm) {
      setUpdatePasswordError('비밀번호가 일치하지 않습니다.');
      return;
    }
    setUpdatePasswordLoading(true);
    setUpdatePasswordError(null);
    try {
      const { error } = await supabase.auth.updateUser({ password: newPassword });
      if (error) throw error;
      // [Condition 4] updateUser 성공 후 recoveryUser 대신 getUser() 재호출 (최신 user 객체 사용)
      const { data: freshData } = await supabase.auth.getUser();
      setUser(freshData?.user ?? recoveryUser);
      // 전체 상태 초기화
      setUpdatePasswordMode(false);
      setNewPassword('');
      setNewPasswordConfirm('');
      setRecoveryUser(null);
      setOtpEmail('');
      setOtpPurpose('signup');
      setIsForgotPasswordMode(false);
      setToast({ message: '🔐 비밀번호가 성공적으로 변경되었습니다!', type: 'success' });
      setTimeout(() => setIsModalOpen(true), 400);
    } catch (err: any) {
      console.warn('updateUser failed', err);
      setUpdatePasswordError(err.message || '비밀번호 변경에 실패했습니다. 다시 시도해 주세요.');
    } finally {
      setUpdatePasswordLoading(false);
    }
  };

  // ============================================================
  // [v2.16.0] 새 비밀번호 입력 취소 핸들러 (Recovery 세션 정리)
  // ============================================================
  const handleCancelUpdatePassword = async () => {
    // [P2 + Condition 3] try-finally: signOut 실패에도 상태 초기화 보장
    try {
      await supabase.auth.signOut();
    } catch (e) {
      console.warn('signOut failed on cancel update password', e);
    } finally {
      setUpdatePasswordMode(false);
      setNewPassword('');
      setNewPasswordConfirm('');
      setUpdatePasswordError(null);
      setRecoveryUser(null);
      setOtpEmail('');
      setOtpPurpose('signup');
      setIsForgotPasswordMode(false);
      setIsLoginMode(true);
    }
  };

  // ============================================================
  // 인증번호 재발송 핸들러 (OTP 폼)
  // ============================================================
  const handleResendOtp = async () => {
    if (resendCooldown > 0 || isResendLoading) return;
    setIsResendLoading(true);
    try {
      // [P1 FIX] otpPurpose 기반 재발송 분기:
      // - 'recovery': resetPasswordForEmail() 재호출 (supabase.auth.resend()는 'recovery' 타입 미지원)
      // - 'signup': 기존 resend() 호출
      let error: any = null;
      if (otpPurpose === 'recovery') {
        const result = await supabase.auth.resetPasswordForEmail(otpEmail, {
          redirectTo: `${window.location.origin}`
        });
        error = result.error;
      } else {
        const result = await supabase.auth.resend({ type: 'signup', email: otpEmail });
        error = result.error;
      }
      if (error) throw error;
      setResendCooldown(60);
      setOtpValue('');
      setOtpError(null);
      setToast({ message: '인증번호가 재발송되었습니다. 이메일을 확인해 주세요.', type: 'info' });
    } catch (err: any) {
      console.warn('Resend OTP failed', err);
      setToast({ message: `재발송 실패: ${err.message || '잠시 후 다시 시도해 주세요.'}`, type: 'error' });
    } finally {
      setIsResendLoading(false);
    }
  };

  // ============================================================
  // 재발송 핸들러 (로그인 흐름 — 이메일 미인증 에러 시)
  // ============================================================
  const handleResendFromLogin = async () => {
    if (!email || resendCooldown > 0 || isResendLoading) return;
    setIsResendLoading(true);
    try {
      const { error } = await supabase.auth.resend({ type: 'signup', email });
      if (error) throw error;
      setResendCooldown(60);
      setAuthError(null);
      setOtpError(null);
      setOtpEmail(email);
      setOtpValue('');
      setOtpMode(true);
      setToast({ message: '인증번호가 재발송되었습니다. 이메일을 확인해 주세요.', type: 'info' });
    } catch (err: any) {
      console.warn('Resend from login failed', err);
      setToast({ message: `재발송 실패: ${err.message || '잠시 후 다시 시도해 주세요.'}`, type: 'error' });
    } finally {
      setIsResendLoading(false);
    }
  };

  // ============================================================
  // 메인 인증 핸들러
  // ============================================================
  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(null);
    setAuthSuccess(null);
    setAuthLoading(true);

    try {
      // [SECURITY FIX] 비밀번호 재설정 — alert() 제거, 정제된 Toast/에러 메시지로 교체
      if (isForgotPasswordMode) {
        const { error } = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}`
        });
        if (error) {
          console.warn('resetPasswordForEmail error:', error);
          const errMsg = (error.message || '').toLowerCase();
          const isConfigError =
            errMsg.includes('invalid api key') ||
            errMsg.includes('api key') ||
            errMsg.includes('unauthorized') ||
            (error as any)?.status === 401;
          const userMsg = isConfigError
            ? '비밀번호 재설정을 처리할 수 없습니다. 관리자에게 문의해 주세요.'
            : '비밀번호 재설정 이메일 발송에 실패했습니다. 잠시 후 다시 시도해 주세요.';
          setAuthError(userMsg);
          setToast({ message: userMsg, type: 'error' });
        } else {
          // [v2.15.1] Dead-end 픽스: 재설정 메일 발송 성공 시 OTP 입력창으로 즉시 전환
          setOtpPurpose('recovery');
          setOtpEmail(email);
          setOtpValue('');
          setOtpError(null);
          setResendCooldown(0);
          setOtpMode(true);
          setToast({ message: '비밀번호 재설정 이메일이 발송되었습니다. 6자리 인증번호를 입력해 주세요.', type: 'info' });
        }
        return;
      }

      if (process.env.NODE_ENV === 'production') {
        const lowerEmail = email.toLowerCase();
        const isMock =
          lowerEmail.endsWith('@example.com') ||
          lowerEmail.endsWith('@mock.com') ||
          lowerEmail.includes('mock') ||
          lowerEmail.includes('test');
        if (isMock) {
          throw new Error('프로덕션 환경에서는 Mock/테스트 계정을 생성하거나 사용할 수 없습니다. 일반 이메일을 이용해 주세요.');
        }
      }

      if (!isLoginMode && password.length < 6) {
        throw new Error('비밀번호는 최소 6자 이상이어야 합니다.');
      }

      if (isLoginMode) {
        const res = await fetch(`${BACKEND_URL}/api/auth/signin`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || '로그인 실패');
        if (data.user) {
          if (data.access_token && data.refresh_token) {
            try {
              await supabase.auth.setSession({
                access_token: data.access_token,
                refresh_token: data.refresh_token
              });
            } catch (err) {
              console.warn('Failed to set supabase session on signin', err);
            }
          }
          const store = useWorkflowStore.getState();
          const localUserId = getLocalStoredUserId(); // [REFACTOR] 공통 함수
          if (store.userId !== data.user.id || localUserId !== data.user.id) {
            store.resetWorkflow();
          }
          setUser(data.user);
          setAuthSuccess('로그인 성공!');
          setTimeout(() => setIsModalOpen(true), 500);
        }
      } else {
        // 회원가입 → OTP 입력 폼으로 전환
        const res = await fetch(`${BACKEND_URL}/api/auth/signup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || '회원가입 실패');
        if (data.user) {
          const store = useWorkflowStore.getState();
          const localUserId = getLocalStoredUserId(); // [REFACTOR] 공통 함수
          if (store.userId !== data.user.id || localUserId !== data.user.id) {
            store.resetWorkflow();
          }
          setOtpEmail(email);
          setOtpValue('');
          setOtpError(null);
          setResendCooldown(0);
          setOtpPurpose('signup'); // [P1 FIX] 회원가입 OTP
          setOtpMode(true);
          setEmail('');
        }
      }
    } catch (err: any) {
      console.warn('Auth failed', err);
      let displayError = err.message || '로그인에 실패했습니다.';
      const errLower = displayError.toLowerCase();
      if (errLower.includes('failed to fetch') || errLower.includes('networkerror') || errLower.includes('network error') || err instanceof TypeError) {
        displayError = '서버와 연결할 수 없습니다. 잠시 후 다시 시도해주세요.';
      } else if (errLower.includes('email not confirmed') || errLower.includes('email_not_confirmed')) {
        displayError = "이메일 인증이 완료되지 않았습니다. 아래 '인증번호 재발송' 버튼을 눌러 인증을 완료해 주세요.";
      } else if (errLower.includes('already') || errLower.includes('registered')) {
        displayError = '이미 사용 중인 이메일입니다.';
      } else if (errLower.includes('invalid login credentials') || errLower.includes('invalid credential') || errLower.includes('credentials')) {
        displayError = '이메일 또는 비밀번호가 올바르지 않습니다.';
      }
      setAuthError(displayError);
    } finally {
      setAuthLoading(false);
      setPassword(''); // [REFACTOR] finally 한 곳에서만 처리
    }
  };

  const handleLogout = async () => {
    try { await supabase.auth.signOut(); } catch (e) {}
    const store = useWorkflowStore.getState();
    store.setUser(null);
    store.setKieKey('');
    store.setIsKeyConfigured(false);
    store.setCsrfToken(null);
    store.resetWorkflow();

    setRows([]);
    setIsModalOpen(false);
    setIsLoginMode(true);
    setIsForgotPasswordMode(false);
    setOtpMode(false);
    setOtpValue('');
    setOtpEmail('');
    setOtpPurpose('signup'); // [P1 FIX] 로그아웃 시 OTP 목적 리셋
    // [v2.16.0] 신규 상태 리셋
    setUpdatePasswordMode(false);
    setNewPassword('');
    setNewPasswordConfirm('');
    setUpdatePasswordError(null);
    setRecoveryUser(null);
    setEmail('');
    setPassword('');
    setShowPassword(false);

    if (typeof window !== 'undefined') {
      localStorage.removeItem('raptor-workflow-storage');
    }
  };

  // [UX FIX] alert() → setToast()로 전면 교체
  const handleSaveKey = () => {
    const store = useWorkflowStore.getState();
    if (!kieKey.trim()) {
      setToast({
        message: isKeyConfigured
          ? '이미 API 키가 구성되어 있습니다. 변경하시려면 새 키를 입력해 주세요.'
          : 'KIE API Key를 입력해 주세요.',
        type: 'error',
      });
      return;
    }
    store.setKieKey(kieKey);
    setIsKeyConfigured(true);
    setKieKey('');
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleDownloadVideo = async (row: ProjectRow) => {
    if (!row.result_url) return;
    const objectUrl: string[] = [];
    try {
      setDownloadingId(row.task_id);
      const res = await fetch(getAbsoluteVideoUrl(row.result_url));
      if (!res.ok) throw new Error('비디오 파일 수신 실패');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      objectUrl.push(url);
      const a = document.createElement('a');
      a.href = url;
      a.download = `raptor_${row.project_id}_${row.task_id}.mp4`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (err: any) {
      // [UX FIX] alert() → setToast()
      setToast({ message: `다운로드 실패: ${err.message}`, type: 'error' });
    } finally {
      setDownloadingId(null);
      // [FIX] URL.revokeObjectURL — 메모리 누수 방지
      if (objectUrl[0]) window.URL.revokeObjectURL(objectUrl[0]);
    }
  };

  const isEmailNotConfirmedError = authError?.includes('인증번호 재발송');

  return (
    <>
      {/* [FIX] closeToast — useCallback 안정적 참조로 Toast 타이머 버그 방지 */}
      {toast && (
        <Toast message={toast.message} type={toast.type} onClose={closeToast} />
      )}

      {/* 1. Header Profile Button */}
      <div className="absolute top-6 right-6 z-[999]">
        {user ? (
          <button
            onClick={() => { setIsModalOpen(true); setActiveTab('project'); }}
            className="flex items-center gap-2 px-5 py-3 rounded-full backdrop-blur-md border bg-neutral-900/50 border-white/10 hover:border-purple-500/50 text-gray-300 hover:text-white transition-all shadow-2xl"
          >
            <User className="w-4 h-4 text-purple-400" />
            <span className="text-xs font-black tracking-wider">{user.email}</span>
          </button>
        ) : (
          <button
            onClick={() => { setIsModalOpen(true); }}
            className="flex items-center gap-2 px-5 py-3 rounded-full backdrop-blur-md border bg-purple-500/10 border-purple-500/30 hover:bg-purple-500/20 text-purple-400 hover:text-purple-300 transition-all shadow-2xl font-black uppercase tracking-widest text-[10px]"
          >
            <Lock className="w-3.5 h-3.5" />
            Sign In / API Settings
          </button>
        )}
      </div>

      {/* 2. Unified Dashboard Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4 md:p-8">
          <div
            className="absolute inset-0 bg-black/85 backdrop-blur-md"
            onClick={() => { setIsModalOpen(false); setPreviewVideoUrl(null); setAuthSuccess(null); setAuthError(null); }}
          />

          <div className="relative w-full max-w-6xl bg-neutral-900 border border-white/10 rounded-3xl h-[85vh] overflow-hidden flex flex-col p-8 shadow-[0_0_80px_rgba(0,0,0,0.8)] animate-in zoom-in-95 duration-300">

            {/* Modal Header */}
            <div className="flex items-center justify-between pb-6 border-b border-white/10 shrink-0">
              <h3 className="text-xl font-black text-white flex items-center gap-3">
                <FolderSync className="w-6 h-6 text-purple-400" />
                <span>RAPTOR 통합 대시보드</span>
              </h3>
              <button
                onClick={async () => {
                  // [Condition 3] updatePasswordMode 중 모달 강제 닫기 시 Recovery 세션 정리
                  if (updatePasswordMode) {
                    try { await supabase.auth.signOut(); } catch (e) {}
                    finally {
                      setUpdatePasswordMode(false);
                      setNewPassword('');
                      setNewPasswordConfirm('');
                      setUpdatePasswordError(null);
                      setRecoveryUser(null);
                      setOtpEmail('');
                      setOtpPurpose('signup');
                      setIsForgotPasswordMode(false);
                      setIsLoginMode(true);
                    }
                  }
                  setIsModalOpen(false);
                  setPreviewVideoUrl(null);
                  setAuthSuccess(null);
                  setAuthError(null);
                }}
                className="text-xs font-bold text-gray-500 hover:text-white transition-colors"
              >
                ✕ CLOSE
              </button>
            </div>

            {!user ? (
              /* --- LOGGED OUT AUTH VIEW --- */
              <div className="flex-1 flex items-center justify-center overflow-y-auto">
                <div className="max-w-md w-full bg-neutral-950 border border-white/5 rounded-2xl p-8 shadow-inner relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-32 h-32 bg-purple-500/5 rounded-full blur-3xl pointer-events-none" />

                  {/* [v2.16.0] 새 비밀번호 설정 폼 */}
                  {updatePasswordMode ? (
                    <>
                      <div className="flex items-center gap-3 mb-6">
                        <Lock className="w-6 h-6 text-purple-400" />
                        <div>
                          <h4 className="text-base font-black text-white">새 비밀번호 설정</h4>
                          <p className="text-[10px] text-gray-500 mt-0.5">인증이 완료되었습니다. 사용할 새 비밀번호를 입력해 주세요.</p>
                        </div>
                      </div>

                      {updatePasswordError && (
                        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-start gap-2">
                          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                          <div className="break-words min-w-0 flex-1">{updatePasswordError}</div>
                        </div>
                      )}

                      <div className="space-y-4">
                        <div>
                          <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2">새 비밀번호</label>
                          <div className="relative">
                            <input
                              id="new-password-input"
                              type={showNewPassword ? 'text' : 'password'}
                              value={newPassword}
                              onChange={e => setNewPassword(e.target.value)}
                              placeholder="6자 이상 입력"
                              disabled={updatePasswordLoading}
                              className="w-full bg-black/60 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-600 focus:ring-2 focus:ring-purple-500/70 focus:border-purple-500/50 outline-none pr-10 disabled:opacity-40"
                            />
                            <button type="button" onClick={() => setShowNewPassword(v => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300">
                              {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            </button>
                          </div>
                        </div>

                        <div>
                          <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2">비밀번호 확인</label>
                          <div className="relative">
                            <input
                              id="new-password-confirm-input"
                              type={showNewPasswordConfirm ? 'text' : 'password'}
                              value={newPasswordConfirm}
                              onChange={e => setNewPasswordConfirm(e.target.value)}
                              placeholder="비밀번호를 다시 입력"
                              disabled={updatePasswordLoading}
                              onKeyDown={e => e.key === 'Enter' && !updatePasswordLoading && handleUpdatePassword()}
                              className="w-full bg-black/60 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-600 focus:ring-2 focus:ring-purple-500/70 focus:border-purple-500/50 outline-none pr-10 disabled:opacity-40"
                            />
                            <button type="button" onClick={() => setShowNewPasswordConfirm(v => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300">
                              {showNewPasswordConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            </button>
                          </div>
                        </div>

                        <button
                          id="update-password-submit"
                          onClick={handleUpdatePassword}
                          disabled={updatePasswordLoading}
                          className="w-full py-3 bg-gradient-to-r from-purple-600 to-purple-800 hover:from-purple-500 hover:to-purple-700 text-white text-sm font-black rounded-xl transition-all disabled:opacity-40 flex items-center justify-center gap-2"
                        >
                          {updatePasswordLoading ? <><Loader2 className="w-4 h-4 animate-spin" /> 변경 중...</> : '🔐 비밀번호 변경'}
                        </button>

                        <div className="text-center">
                          <button
                            onClick={handleCancelUpdatePassword}
                            disabled={updatePasswordLoading}
                            className="text-[10px] text-gray-600 hover:text-gray-400 transition-colors disabled:opacity-40"
                          >
                            ← 로그인 화면으로 돌아가기
                          </button>
                        </div>
                      </div>
                    </>
                  ) : otpMode ? (
                    <>
                      <div className="flex items-center gap-3 mb-6">
                        <Mail className="w-6 h-6 text-purple-400" />
                        <div>
                          <h4 className="text-base font-black text-white">이메일 인증번호 입력</h4>
                          <p className="text-[10px] text-gray-500 mt-0.5 break-all">
                            <span className="text-purple-300 font-bold">{otpEmail}</span>로 발송된 6자리 인증번호를 입력해 주세요.
                          </p>
                        </div>
                      </div>

                      {otpError && (
                        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-start gap-2 break-words">
                          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                          <div className="break-words min-w-0 flex-1">{otpError}</div>
                        </div>
                      )}

                      <div className="space-y-6">
                        <div>
                          <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3 text-center">
                            6자리 인증번호
                          </label>
                          {/* [P2] onComplete → 6자리 완성 시 자동 제출 */}
                          <OtpInput
                            value={otpValue}
                            onChange={setOtpValue}
                            onComplete={handleVerifyOtp}
                            disabled={otpLoading}
                          />
                        </div>

                        <button
                          onClick={handleVerifyOtp}
                          disabled={otpLoading || otpValue.replace(/\D/g, '').length < 6}
                          className="w-full py-3.5 bg-gradient-to-r from-purple-500 to-blue-500 hover:opacity-90 disabled:opacity-40 rounded-xl font-black text-xs text-white uppercase tracking-widest flex items-center justify-center gap-2 shadow-xl transition-all"
                        >
                          {otpLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                          인증 완료
                        </button>

                        {/* 재발송 버튼 */}
                        <div className="flex flex-col items-center gap-2 pt-2 border-t border-white/5">
                          <p className="text-[10px] text-gray-500">인증번호를 받지 못하셨나요?</p>
                          <button
                            onClick={handleResendOtp}
                            disabled={resendCooldown > 0 || isResendLoading}
                            className="flex items-center gap-2 text-xs font-bold text-purple-400 hover:text-purple-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                          >
                            <RefreshCw className={`w-3.5 h-3.5 ${isResendLoading ? 'animate-spin' : ''}`} />
                            {isResendLoading
                              ? '발송 중...'
                              : resendCooldown > 0
                              ? `재발송 가능 (${resendCooldown}초 후)`
                              : '인증번호 재발송'}
                          </button>
                        </div>

                        <div className="text-center">
                          <button
                            onClick={() => {
                              setOtpMode(false);
                              setOtpValue('');
                              setOtpError(null);
                              // [v2.15.1 Loop1] otpPurpose 분기 — recovery: 비밀번호 재설정 폼 복귀 / signup: 회원가입 폼 복귀
                              if (otpPurpose === 'recovery') {
                                setIsLoginMode(true);
                                setIsForgotPasswordMode(true);
                                setEmail(otpEmail); // [Claude Code 권고] 이메일 필드 자동 복원
                              } else {
                                setIsLoginMode(false);
                              }
                              setAuthError(null);
                              setAuthSuccess(null);
                            }}
                            className="text-[10px] text-gray-600 hover:text-gray-400 transition-colors"
                          >
                            ← {otpPurpose === 'recovery' ? '비밀번호 찾기 화면으로 돌아가기' : '회원가입 화면으로 돌아가기'}
                          </button>
                        </div>
                      </div>
                    </>
                  ) : (
                    /* 로그인 / 회원가입 / 비밀번호 재설정 폼 */
                    <>
                      <div className="flex items-center gap-3 mb-6">
                        <Lock className="w-6 h-6 text-purple-400" />
                        <div>
                          <h4 className="text-base font-black text-white">
                            {isForgotPasswordMode ? '비밀번호 재설정' : '베타 테스터 로그인'}
                          </h4>
                          <p className="text-[10px] text-gray-500">
                            {isForgotPasswordMode
                              ? '가입하신 이메일로 재설정 링크를 보내드립니다.'
                              : '대시보드와 클라우드 렌더링 내역 저장을 제공합니다.'}
                          </p>
                        </div>
                      </div>

                      {authError && (
                        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-start gap-2 w-full max-w-md z-10 break-words">
                          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                          <div className="break-words min-w-0 flex-1">
                            <p>{authError}</p>
                            {isEmailNotConfirmedError && (
                              <button
                                onClick={handleResendFromLogin}
                                disabled={resendCooldown > 0 || isResendLoading}
                                className="mt-2 flex items-center gap-1.5 text-purple-400 hover:text-purple-300 font-bold disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                              >
                                <RefreshCw className={`w-3 h-3 ${isResendLoading ? 'animate-spin' : ''}`} />
                                {isResendLoading
                                  ? '발송 중...'
                                  : resendCooldown > 0
                                  ? `재발송 가능 (${resendCooldown}초 후)`
                                  : '인증번호 재발송'}
                              </button>
                            )}
                          </div>
                        </div>
                      )}

                      {authSuccess && (
                        <div className="mb-4 p-3 bg-green-500/10 border border-green-500/30 rounded-xl text-green-400 text-xs flex items-start gap-2 w-full max-w-md z-10 break-words">
                          <CheckCircle className="w-4 h-4 shrink-0 mt-0.5" />
                          <div className="break-words min-w-0 flex-1">{authSuccess}</div>
                        </div>
                      )}

                      <form onSubmit={handleAuthSubmit} className="space-y-4">
                        <div>
                          <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1.5">이메일</label>
                          <input
                            type="email"
                            required
                            value={email}
                            onChange={e => setEmail(e.target.value)}
                            placeholder="name@company.com"
                            className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 text-white text-xs focus:ring-2 focus:ring-purple-500/50 outline-none"
                          />
                        </div>
                        {!isForgotPasswordMode && (
                          <div>
                            <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1.5">비밀번호</label>
                            <div className="relative">
                              <input
                                type={showPassword ? 'text' : 'password'}
                                required
                                value={password}
                                onChange={e => setPassword(e.target.value)}
                                placeholder="••••••••"
                                className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 pr-12 text-white text-xs focus:ring-2 focus:ring-purple-500/50 outline-none"
                              />
                              <button
                                type="button"
                                onClick={() => setShowPassword(p => !p)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-purple-400 transition-colors p-1"
                                tabIndex={-1}
                                aria-label={showPassword ? '비밀번호 숨기기' : '비밀번호 표시'}
                              >
                                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                              </button>
                            </div>
                            {!isLoginMode && (
                              <p className="text-[10px] text-purple-400 mt-1">* 비밀번호는 최소 6자 이상이어야 합니다.</p>
                            )}
                          </div>
                        )}

                        <button
                          type="submit"
                          disabled={authLoading}
                          className="w-full py-3.5 bg-gradient-to-r from-purple-500 to-blue-500 hover:opacity-90 rounded-xl font-black text-xs text-white uppercase tracking-widest flex items-center justify-center gap-2 shadow-xl"
                        >
                          {authLoading
                            ? <Loader2 className="w-4 h-4 animate-spin" />
                            : isForgotPasswordMode ? '재설정 이메일 전송' : isLoginMode ? '로그인' : '회원가입'}
                        </button>

                        {!isLoginMode && !isForgotPasswordMode && (
                          <p className="text-[10px] text-gray-500 text-center leading-relaxed mt-1 break-words">
                            가입 시 랩터 숏폼 메이커의{' '}
                            <a href="https://docs.google.com/document/d/18YmLQIcpjq8cghU5zukMWhu6W13QJo7WrGm-hl7TQuw/edit?usp=sharing" target="_blank" rel="noopener noreferrer" className="text-purple-400 hover:text-purple-300 underline underline-offset-2 transition-colors">이용약관</a>{' '}및{' '}
                            <a href={process.env.NEXT_PUBLIC_PRIVACY_URL || '#privacy'} target="_blank" rel="noopener noreferrer" className="text-purple-400 hover:text-purple-300 underline underline-offset-2 transition-colors">개인정보 처리방침</a>에
                            동의하는 것으로 간주됩니다.
                          </p>
                        )}
                      </form>

                      <div className="mt-6 pt-6 border-t border-white/5 flex flex-col gap-3 text-xs text-gray-400">
                        {isForgotPasswordMode ? (
                          <div className="flex items-center justify-between">
                            <span>로그인 화면으로 돌아가시겠습니까?</span>
                            <button
                              onClick={() => { setIsForgotPasswordMode(false); setAuthError(null); setAuthSuccess(null); }}
                              className="text-purple-400 hover:text-purple-300 font-bold underline"
                            >
                              로그인하기
                            </button>
                          </div>
                        ) : (
                          <>
                            <div className="flex items-center justify-between">
                              <span>{isLoginMode ? '계정이 없으신가요?' : '이미 계정이 있으신가요?'}</span>
                              <button
                                onClick={() => { setIsLoginMode(!isLoginMode); setShowPassword(false); setAuthError(null); setAuthSuccess(null); }}
                                className="text-purple-400 hover:text-purple-300 font-bold underline"
                              >
                                {isLoginMode ? '가입하기' : '로그인하기'}
                              </button>
                            </div>
                            {isLoginMode && (
                              <div className="flex items-center justify-between">
                                <span>비밀번호를 분실하셨나요?</span>
                                <button
                                  onClick={() => { setIsForgotPasswordMode(true); setShowPassword(false); setAuthError(null); setAuthSuccess(null); }}
                                  className="text-purple-400 hover:text-purple-300 font-bold underline"
                                >
                                  비밀번호 찾기
                                </button>
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </div>
            ) : (
              /* --- LOGGED IN WORKSPACE --- */
              <div className="flex-1 min-h-0 flex flex-col md:flex-row gap-6 pt-6">

                {/* Tab Navigation */}
                <div className="w-full md:w-[200px] flex md:flex-col gap-2 shrink-0">
                  <button
                    onClick={() => setActiveTab('project')}
                    className={`flex-1 md:flex-none py-3.5 px-4 rounded-xl font-black text-xs uppercase tracking-wider text-left flex items-center gap-2 transition-all ${activeTab === 'project' ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30' : 'bg-white/5 text-gray-400 hover:text-white border border-transparent'}`}
                  >
                    <FolderSync className="w-4 h-4" />
                    <span>프로젝트 관리</span>
                  </button>
                  <button
                    onClick={() => setActiveTab('settings')}
                    className={`flex-1 md:flex-none py-3.5 px-4 rounded-xl font-black text-xs uppercase tracking-wider text-left flex items-center gap-2 transition-all ${activeTab === 'settings' ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30' : 'bg-white/5 text-gray-400 hover:text-white border border-transparent'}`}
                  >
                    <Settings className="w-4 h-4" />
                    <span>KIE API 설정</span>
                  </button>
                  <button
                    onClick={() => setActiveTab('account')}
                    className={`flex-1 md:flex-none py-3.5 px-4 rounded-xl font-black text-xs uppercase tracking-wider text-left flex items-center gap-2 transition-all ${activeTab === 'account' ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30' : 'bg-white/5 text-gray-400 hover:text-white border border-transparent'}`}
                  >
                    <User className="w-4 h-4" />
                    <span>계정</span>
                  </button>
                </div>

                {/* Workspace Content */}
                <div className="flex-1 min-h-0 bg-neutral-950/40 border border-white/5 rounded-2xl p-6 overflow-hidden flex flex-col">

                  {/* TAB 1: PROJECT LIST */}
                  {activeTab === 'project' && (
                    <div className="flex-1 flex flex-col min-h-0">
                      <div className="mb-4">
                        <h4 className="text-sm font-black text-white">프로젝트 태스크 리스트</h4>
                        <p className="text-[10px] text-gray-500 mt-0.5">동일 프로젝트 내 재시도(Retry) 히스토리가 모두 개별 보존됩니다.</p>
                      </div>

                      {rowsLoading ? (
                        <div className="flex-1 flex flex-col items-center justify-center py-20 text-gray-500 gap-2">
                          <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
                          <span className="text-xs uppercase tracking-widest">프로젝트 내역 로드 중...</span>
                        </div>
                      ) : rows.length === 0 ? (
                        <div className="flex-1 flex flex-col items-center justify-center py-20 text-gray-600 gap-4 text-center">
                          <FolderSync className="w-10 h-10 stroke-1" />
                          <div>
                            <p className="text-xs font-black text-white">생성된 프로젝트가 없습니다</p>
                            <p className="text-[10px] text-gray-500 mt-1">새 비디오 작성을 시작하면 프로젝트가 개설됩니다.</p>
                          </div>
                        </div>
                      ) : (
                        <div className="flex-1 min-h-0 flex flex-col md:flex-row gap-6">
                          <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar">
                            <table className="w-full text-left border-collapse text-xs">
                              <thead>
                                <tr className="border-b border-white/5 text-[10px] uppercase font-bold text-gray-500 tracking-wider">
                                  <th className="pb-3 pr-2">상품명</th>
                                  <th className="pb-3 pr-2">프로젝트 번호</th>
                                  <th className="pb-3 pr-2">TASK ID</th>
                                  <th className="pb-3 pr-2">작업 설명</th>
                                  <th className="pb-3 pr-2">상태</th>
                                  <th className="pb-3 text-right">결과</th>
                                </tr>
                              </thead>
                              <tbody>
                                {rows.map(row => (
                                  <tr key={row.task_id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                                    <td className="py-4 pr-2 font-bold text-white max-w-[120px] truncate">{row.product_name}</td>
                                    <td className="py-4 pr-2 font-mono text-[9px] text-gray-500 truncate max-w-[100px]" title={row.project_id}>
                                      {row.project_id.split('-')[0]}...
                                    </td>
                                    <td className="py-4 pr-2 font-mono text-[9px] text-gray-500 truncate max-w-[100px]" title={row.task_id}>
                                      {row.task_id.split('_').slice(-1)[0]}
                                    </td>
                                    <td className="py-4 pr-2 text-gray-300 font-medium max-w-[150px] truncate" title={row.description}>
                                      {row.description}
                                    </td>
                                    <td className="py-4 pr-2">
                                      <span className={`px-2.5 py-0.5 rounded-full text-[9px] font-black uppercase ${
                                        row.status === 'success' ? 'bg-green-500/20 text-green-400 border border-green-500/30' :
                                        row.status === 'failed' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                                        'bg-blue-500/20 text-blue-400 border border-blue-500/30 animate-pulse'
                                      }`}>
                                        {row.status}
                                      </span>
                                    </td>
                                    <td className="py-4 text-right flex items-center justify-end gap-1.5">
                                      {row.result_url && (
                                        <>
                                          <button
                                            onClick={() => setPreviewVideoUrl(getAbsoluteVideoUrl(row.result_url!))}
                                            className="px-2 py-1 bg-white/5 hover:bg-purple-500 hover:text-white rounded text-[9px] font-bold transition-all"
                                          >
                                            재생
                                          </button>
                                          <button
                                            onClick={() => handleDownloadVideo(row)}
                                            disabled={downloadingId === row.task_id}
                                            className="p-1 bg-purple-500/10 hover:bg-purple-500 rounded text-purple-300 hover:text-white border border-purple-500/20 transition-all"
                                            title="동영상 다운로드"
                                          >
                                            <Download className="w-3 h-3" />
                                          </button>
                                        </>
                                      )}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>

                          {previewVideoUrl && (
                            <div className="w-full md:w-[280px] bg-black/40 border border-white/5 rounded-xl p-4 shrink-0 flex flex-col gap-4 animate-in slide-in-from-right-4 duration-300">
                              <div className="flex justify-between items-center pb-2 border-b border-white/5">
                                <span className="text-[10px] font-bold text-purple-400 uppercase tracking-widest">미리보기</span>
                                <button onClick={() => setPreviewVideoUrl(null)} className="text-[10px] text-gray-500 hover:text-white">✕ 닫기</button>
                              </div>
                              <div className="aspect-[9/16] max-h-[40vh] bg-neutral-900 rounded-lg overflow-hidden border border-white/10 shadow-inner">
                                <video src={previewVideoUrl} controls className="w-full h-full object-cover" />
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* TAB 2: KIE API KEY CONFIG */}
                  {activeTab === 'settings' && (
                    <div className="max-w-md space-y-6">
                      <div>
                        <h4 className="text-sm font-black text-white">KIE AI Engine Configuration</h4>
                        <p className="text-[10px] text-gray-500 mt-0.5">로컬 쿠키 암호화 방식으로 백엔드 서버에 API 키를 저장하지 않습니다.</p>
                      </div>
                      <div className="space-y-4">
                        <div>
                          <label className="block text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1.5">KIE API Key</label>
                          <div className="relative">
                            <input
                              type={visibility ? 'text' : 'password'}
                              value={kieKey}
                              onChange={e => setKieKey(e.target.value)}
                              placeholder={isKeyConfigured ? '***... (이미 설정됨)' : 'API Key 입력...'}
                              className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 text-white text-xs focus:ring-2 focus:ring-purple-500/50 outline-none"
                            />
                            <button
                              onClick={() => setVisibility(!visibility)}
                              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white text-xs"
                            >
                              {visibility ? 'HIDE' : 'SHOW'}
                            </button>
                          </div>
                        </div>
                        <button
                          onClick={handleSaveKey}
                          className={`w-full py-3 rounded-xl font-black text-xs uppercase tracking-widest flex items-center justify-center gap-2 transition-all ${saved ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-white text-black hover:bg-gray-200'}`}
                        >
                          {saved ? <CheckCircle className="w-4 h-4" /> : <Settings className="w-4 h-4" />}
                          <span>{saved ? '설정 저장 완료' : 'KIE 설정 업데이트'}</span>
                        </button>
                      </div>
                    </div>
                  )}

                  {/* TAB 3: ACCOUNT & LOGOUT */}
                  {activeTab === 'account' && (
                    <div className="max-w-md space-y-6">
                      <div>
                        <h4 className="text-sm font-black text-white">베타 테스터 세션 계정</h4>
                        <p className="text-[10px] text-gray-500 mt-0.5">현재 접속된 인증 정보입니다.</p>
                      </div>
                      <div className="bg-white/5 border border-white/5 rounded-xl p-4 space-y-2">
                        <div className="flex justify-between text-[10px]">
                          <span className="text-gray-500">EMAIL ACCOUNT</span>
                          <span className="text-white font-bold">{user.email}</span>
                        </div>
                        <div className="flex justify-between text-[10px]">
                          <span className="text-gray-500">MEMBER ID</span>
                          <span className="text-white font-mono">{user.id}</span>
                        </div>
                      </div>
                      <div className="flex gap-4">
                        <button
                          onClick={handleLogout}
                          className="py-3 px-5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 hover:border-red-500/50 text-red-400 rounded-xl text-xs font-black uppercase tracking-widest flex items-center justify-center gap-2 transition-all shadow-md active:scale-95"
                        >
                          <LogOut className="w-4 h-4" />
                          <span>안전한 로그아웃</span>
                        </button>
                      </div>
                    </div>
                  )}

                </div>
              </div>
            )}

            {/* Modal Footer */}
            <div className="pt-6 border-t border-white/10 shrink-0 text-center">
              <p className="text-[9px] text-gray-600 uppercase tracking-widest font-black">
                RAPTOR V2.2 Unified Dashboard & Project Controller
              </p>
            </div>

          </div>
        </div>
      )}
    </>
  );
}
