"use client";

import { useState, useEffect } from 'react';
import { User, LogOut, Key, FolderSync, Download, Calendar, Settings, Lock, Mail, AlertCircle, CheckCircle, Loader2, Play } from 'lucide-react';
import { useWorkflowStore } from '@/store/useWorkflowStore';
import { supabase } from '@/lib/supabaseClient';
import { api } from '@/lib/api-client';

// Helper function to resolve relative video URL to absolute backend URL
const getAbsoluteVideoUrl = (url: string) => {
  if (!url) return "";
  if (url.startsWith("http://") || url.startsWith("https://")) {
    return url;
  }
  const baseUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const cleanBase = baseUrl.replace(/\/$/, "");
  const cleanUrl = url.startsWith("/") ? url : `/${url}`;
  return `${cleanBase}${cleanUrl}`;
};

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

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

  // Project List State
  const [rows, setRows] = useState<any[]>([]);
  const [rowsLoading, setRowsLoading] = useState(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [previewVideoUrl, setPreviewVideoUrl] = useState<string | null>(null);

  // KIE Key Setting State (within Settings Tab)
  const [kieKey, setKieKey] = useState('');
  const [visibility, setVisibility] = useState(false);
  const [saved, setSaved] = useState(false);

  // Check Session on Mount
  useEffect(() => {
    if (!hasHydrated) return;
    // Check KIE Key Configuration locally from store
    const store = useWorkflowStore.getState();
    if (store.kieKey) {
      setIsKeyConfigured(true);
    } else {
      setIsKeyConfigured(false);
    }
  }, [setUser, setIsKeyConfigured, hasHydrated]);

  // Clear password on modal close to ensure form security and state reset (guarded against login attempt)
  useEffect(() => {
    if (!isModalOpen && !authLoading) {
      setPassword('');
    }
  }, [isModalOpen, authLoading]);

  // Fetch dashboard projects when user or renders occur
  useEffect(() => {
    const fetchDashboardData = async () => {
      if (!user) {
        setRows([]);
        return;
      }
      setRowsLoading(true);
      try {
        const res = await fetch(`${BACKEND_URL}/api/dashboard/projects?user_id=${user.id}`);
        if (res.ok) {
          const data = await res.json();
          setRows(data.rows || []);
        }
      } catch (err) {
        console.warn("Failed to fetch dashboard rows:", err);
      } finally {
        setRowsLoading(false);
      }
    };
    fetchDashboardData();
  }, [user, lastRenderTimestamp, isModalOpen]);

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(null);
    setAuthSuccess(null);
    setAuthLoading(true);

    try {
      if (isForgotPasswordMode) {
        const { error } = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}`
        });
        if (error) {
          throw error;
        }
        setAuthSuccess("비밀번호 재설정 이메일이 발송되었습니다. 이메일을 확인해 주세요.");
        return;
      }

      if (process.env.NODE_ENV === 'production') {
        const lowerEmail = email.toLowerCase();
        const isMock = lowerEmail.endsWith('@example.com') || 
                       lowerEmail.endsWith('@mock.com') || 
                       lowerEmail.includes('mock') || 
                       lowerEmail.includes('test');
        if (isMock) {
          throw new Error("프로덕션 환경에서는 Mock/테스트 계정을 생성하거나 사용할 수 없습니다. 일반 이메일을 이용해 주세요.");
        }
      }

      if (!isLoginMode && password.length < 6) {
        throw new Error("비밀번호는 최소 6자 이상이어야 합니다.");
      }

      if (isLoginMode) {
        const res = await fetch(`${BACKEND_URL}/api/auth/signin`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || "로그인 실패");
        }
        if (data.user) {
          if (data.access_token && data.refresh_token) {
            try {
              await supabase.auth.setSession({
                access_token: data.access_token,
                refresh_token: data.refresh_token
              });
            } catch (err) {
              console.warn("Failed to set supabase session on signin", err);
            }
          }
          const store = useWorkflowStore.getState();
          let localUserId = '';
          if (typeof window !== 'undefined') {
            try {
              const localData = localStorage.getItem('raptor-workflow-storage');
              if (localData) {
                const parsed = JSON.parse(localData);
                localUserId = parsed?.state?.userId || '';
              }
            } catch (e) {
              console.warn("Failed to parse local storage in auth submit", e);
            }
          }
          if (store.userId !== data.user.id || localUserId !== data.user.id) {
            store.resetWorkflow();
          }
          setUser(data.user);
          setAuthSuccess("로그인 성공!");
          setPassword('');
          setTimeout(() => setIsModalOpen(true), 500);
        }
      } else {
        const res = await fetch(`${BACKEND_URL}/api/auth/signup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || "회원가입 실패");
        }
        if (data.user) {
          const store = useWorkflowStore.getState();
          let localUserId = '';
          if (typeof window !== 'undefined') {
            try {
              const localData = localStorage.getItem('raptor-workflow-storage');
              if (localData) {
                const parsed = JSON.parse(localData);
                localUserId = parsed?.state?.userId || '';
              }
            } catch (e) {
              console.warn("Failed to parse local storage in auth signup", e);
            }
          }
          if (store.userId !== data.user.id || localUserId !== data.user.id) {
            store.resetWorkflow();
          }
          // 이메일 인증 방식: 바로 로그인 처리하지 않고 인증 안내 메시지만 표시
          setAuthSuccess("가입하신 이메일로 인증 메일이 발송되었습니다. 메일함의 인증 링크를 클릭하여 가입을 완료해 주세요.");
          setPassword('');
          setEmail('');
        }
      }
    } catch (err: any) {
      console.warn("Auth failed", err);
      let displayError = err.message || "로그인에 실패했습니다.";
      const errLower = displayError.toLowerCase();
      if (errLower.includes("failed to fetch") || errLower.includes("networkerror") || errLower.includes("network error") || err instanceof TypeError) {
        displayError = "서버와 연결할 수 없습니다. 잠시 후 다시 시도해주세요.";
      } else if (errLower.includes("email not confirmed") || errLower.includes("email_not_confirmed")) {
        // [P1] 이메일 미인증 상태 전용 에러 메시지 — 일반 credentials 오류와 분리
        displayError = "이메일 인증이 완료되지 않았습니다. 메일함의 인증 링크를 확인해 주세요.";
      } else if (errLower.includes("already") || errLower.includes("registered")) {
        displayError = "이미 사용 중인 이메일입니다.";
      } else if (errLower.includes("invalid login credentials") || errLower.includes("invalid credential") || errLower.includes("credentials")) {
        displayError = "이메일 또는 비밀번호가 올바르지 않습니다.";
      }
      setAuthError(displayError);
      setPassword('');
    } finally {
      setAuthLoading(false);
      if (!isForgotPasswordMode) {
        setPassword('');
      }
    }
  };

  const handleLogout = async () => {
    // Zustand 스토어 완벽 초기화
    const store = useWorkflowStore.getState();
    store.setUser(null);
    store.setKieKey('');
    store.setIsKeyConfigured(false);
    store.setCsrfToken(null);

    setRows([]);
    setIsModalOpen(false);
    setIsLoginMode(true); // 로그아웃 시 다음 모달 열릴 때 로그인 모드로 전환 보장
    setIsForgotPasswordMode(false); // 비밀번호 찾기 모드 리셋
    store.resetWorkflow(); // 기획 데이터 초기화
    setEmail('');
    setPassword('');

    // 로컬 스토리지 강제 제거
    if (typeof window !== 'undefined') {
      localStorage.removeItem('raptor-workflow-storage');
    }
  };

  const handleSaveKey = async () => {
    const store = useWorkflowStore.getState();
    if (!kieKey || kieKey.trim() === "") {
      if (isKeyConfigured) {
        alert("이미 API 키가 구성되어 있습니다. 변경하시려면 새 키를 입력해 주세요.");
        return;
      }
      alert("KIE API Key를 입력해 주세요.");
      return;
    }

    // Save KIE key directly to Zustand store for Header bypass proxying
    store.setKieKey(kieKey);
    setIsKeyConfigured(true);
    setKieKey("");
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleDownloadVideo = async (row: any) => {
    if (!row.result_url) return;
    try {
      setDownloadingId(row.task_id);
      const res = await fetch(getAbsoluteVideoUrl(row.result_url));
      if (!res.ok) throw new Error("비디오 파일 수신 실패");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `raptor_${row.project_id}_${row.task_id}.mp4`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (err: any) {
      alert(`다운로드 실패: ${err.message}`);
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <>
      {/* 1. Header Profile Button */}
      <div className="fixed top-6 right-6 z-[999]">
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
                onClick={() => { setIsModalOpen(false); setPreviewVideoUrl(null); setAuthSuccess(null); setAuthError(null); }}
                className="text-xs font-bold text-gray-500 hover:text-white transition-colors"
              >
                ✕ CLOSE
              </button>
            </div>

            {!user ? (
              /* --- LOGGED OUT AUTHENTICATION VIEW --- */
              <div className="flex-1 flex items-center justify-center overflow-y-auto">
                <div className="max-w-md w-full bg-neutral-950 border border-white/5 rounded-2xl p-8 shadow-inner relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-32 h-32 bg-purple-500/5 rounded-full blur-3xl pointer-events-none" />
                  
                  <div className="flex items-center gap-3 mb-6">
                    <Lock className="w-6 h-6 text-purple-400" />
                    <div>
                      <h4 className="text-base font-black text-white">
                        {isForgotPasswordMode ? '비밀번호 재설정' : '베타 테스터 로그인'}
                      </h4>
                      <p className="text-[10px] text-gray-500">
                        {isForgotPasswordMode ? '가입하신 이메일로 재설정 링크를 보내드립니다.' : '대시보드와 클라우드 렌더링 내역 저장을 제공합니다.'}
                      </p>
                    </div>
                  </div>

                  {authError && (
                    <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-start gap-2 w-full max-w-md z-10 break-words">
                      <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                      <div className="break-words min-w-0 flex-1">{authError}</div>
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
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="name@company.com" 
                        className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 text-white text-xs focus:ring-2 focus:ring-purple-500/50 outline-none"
                      />
                    </div>
                    {!isForgotPasswordMode && (
                      <div>
                        <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1.5">비밀번호</label>
                        <input 
                          type="password" 
                          required
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          placeholder="••••••••" 
                          className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 text-white text-xs focus:ring-2 focus:ring-purple-500/50 outline-none"
                        />
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
                      {authLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : isForgotPasswordMode ? '재설정 이메일 전송' : isLoginMode ? '로그인' : '회원가입'}
                    </button>

                    {/* [P1] 약관 동의 안내 문구 - 회원가입 모드에서만 표시, 실제 링크 연결 */}
                    {!isLoginMode && !isForgotPasswordMode && (
                      <p className="text-[10px] text-gray-500 text-center leading-relaxed mt-1 break-words">
                        가입 시 랩터 숏폼 메이커의{' '}
                        <a
                          href="https://docs.google.com/document/d/18YmLQIcpjq8cghU5zukMWhu6W13QJo7WrGm-hl7TQuw/edit?usp=sharing"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-purple-400 hover:text-purple-300 underline underline-offset-2 transition-colors"
                        >이용약관</a>{' '}및{' '}
                        <a
                          href="https://docs.google.com/document/d/18YmLQIcpjq8cghU5zukMWhu6W13QJo7WrGm-hl7TQuw/edit?usp=sharing"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-purple-400 hover:text-purple-300 underline underline-offset-2 transition-colors"
                        >개인정보 처리방침</a>에
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
                          <span>{isLoginMode ? "계정이 없으신가요?" : "이미 계정이 있으신가요?"}</span>
                          <button 
                            onClick={() => { setIsLoginMode(!isLoginMode); setPassword(''); setAuthError(null); setAuthSuccess(null); }}
                            className="text-purple-400 hover:text-purple-300 font-bold underline"
                          >
                            {isLoginMode ? "가입하기" : "로그인하기"}
                          </button>
                        </div>
                        {isLoginMode && (
                          <div className="flex items-center justify-between">
                            <span>비밀번호를 분실하셨나요?</span>
                            <button 
                              onClick={() => { setIsForgotPasswordMode(true); setPassword(''); setAuthError(null); setAuthSuccess(null); }}
                              className="text-purple-400 hover:text-purple-300 font-bold underline"
                            >
                              비밀번호 찾기
                            </button>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              /* --- LOGGED IN WORKSPACE --- */
              <div className="flex-1 min-h-0 flex flex-col md:flex-row gap-6 pt-6">
                
                {/* 2.1 Tab Navigation Side Bar */}
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

                {/* 2.2 Workspace Content View */}
                <div className="flex-1 min-h-0 bg-neutral-950/40 border border-white/5 rounded-2xl p-6 overflow-hidden flex flex-col">
                  
                  {/* --- TAB 1: PROJECT LIST BOARD --- */}
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
                          {/* Board Grid Table */}
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
                                {rows.map((row) => (
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
                                            onClick={() => setPreviewVideoUrl(getAbsoluteVideoUrl(row.result_url))}
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

                          {/* Video Preview Player Panel */}
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

                  {/* --- TAB 2: KIE API KEY CONFIG --- */}
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
                              type={visibility ? "text" : "password"} 
                              value={kieKey}
                              onChange={(e) => setKieKey(e.target.value)}
                              placeholder={isKeyConfigured ? "***... (이미 설정됨)" : "API Key 입력..."}
                              className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 text-white text-xs focus:ring-2 focus:ring-purple-500/50 outline-none"
                            />
                            <button 
                              onClick={() => setVisibility(!visibility)}
                              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white text-xs"
                            >
                              {visibility ? "HIDE" : "SHOW"}
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

                  {/* --- TAB 3: ACCOUNT & LOGOUT --- */}
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
