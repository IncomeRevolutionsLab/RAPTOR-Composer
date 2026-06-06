"use client";
 
import { useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { supabase } from '@/lib/supabaseClient';
import { useWorkflowStore } from '@/store/useWorkflowStore';
import { Loader2 } from 'lucide-react';

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { setUser, resetWorkflow, isAuthLoading, setIsAuthLoading, hasHydrated } = useWorkflowStore();

  // 1. Listen for Auth State Changes (전역 리스너)
  useEffect(() => {
    if (!hasHydrated) return;

    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
      console.log(`[AUTH EVENT] ${event}`);
      if (event === 'SIGNED_OUT') {
        // SIGNED_OUT 시에만 상태 리셋 및 세션 파괴
        resetWorkflow();
        setUser(null);
        if (typeof window !== 'undefined') {
          localStorage.removeItem('raptor-workflow-storage');
        }
      } else if (session?.user) {
        setUser(session.user);
      }
    });

    return () => {
      subscription.unsubscribe();
    };
  }, [hasHydrated, setUser, resetWorkflow]);

  // 2. Initial Session Check with Loader (첫 세션 로드 시 로딩바)
  useEffect(() => {
    if (!hasHydrated) return;
    const checkSession = async () => {
      setIsAuthLoading(true);
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (session?.user) {
          setUser(session.user);
        }
        // getSession()이 null이거나 로딩 중이더라도 Zustand store의 user 값을 강제로 null로 덮어쓰지 않고 보존하여 
        // 새로고침 시의 상태 누수(Zustand 데이터 증발) 레이스 컨디션을 근본적으로 해결합니다.
      } catch (err) {
        console.warn("Supabase session check failed:", err);
      } finally {
        setIsAuthLoading(false);
      }
    };
    checkSession();
  }, [pathname, setUser, setIsAuthLoading, hasHydrated]);

  // 3. Loader UI Render (로딩 시 강제 차단 스피너)
  if (!hasHydrated || isAuthLoading) {
    return (
      <div className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-neutral-950/90 backdrop-blur-md">
        <Loader2 className="w-10 h-10 text-purple-500 animate-spin mb-4" />
        <p className="text-xs text-gray-400 uppercase tracking-widest font-black">RAPTOR SECURE AUTH SYNC...</p>
      </div>
    );
  }

  return <>{children}</>;
}
