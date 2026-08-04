/* 三栏工作台骨架（P-02）：左栏项目/流程 + 中栏内容 + 右栏资产/成本/任务 */
'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import RightPanel from '@/components/layout/RightPanel';
import TaskCenter from '@/components/layout/TaskCenter';
import ConfirmCard from '@/components/studio/ConfirmCard';
import { useStudioStore } from '@/store/useStudioStore';
import { useTaskStore } from '@/store/useTaskStore';

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const projectId = useStudioStore((s) => s.projectId);
  const setProject = useStudioStore((s) => s.setProject);
  const projects = useStudioStore((s) => s.projects);
  const pathname = usePathname();
  const router = useRouter();

  // URL ?project= ↔ store 双向同步：进入/切换页面时，无参数则把当前项目写回 URL
  useEffect(() => {
    const p = new URLSearchParams(window.location.search).get('project');
    const urlPid = p ? Number(p) : null;
    if (urlPid && urlPid !== useStudioStore.getState().projectId) {
      setProject(urlPid);
    } else if (!urlPid) {
      const pid = useStudioStore.getState().projectId;
      if (pid) router.replace(`${pathname}?project=${pid}`, { scroll: false });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname, router, setProject]);

  // 启动任务轮询（stop 在组件卸载时清理）
  useEffect(() => {
    const stop = useTaskStore.getState().startPolling();
    return stop;
  }, []);

  const activeName = projects.find((p) => p.id === projectId)?.name;
  const isDashboard = pathname === '/dashboard';

  return (
    <div className="flex h-full">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        {/* 顶栏 */}
        <header className="h-12 shrink-0 border-b border-subtle bg-surface/80 backdrop-blur px-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {!isDashboard && (
              <Link
                href={`/dashboard${projectId ? `?project=${projectId}` : ''}`}
                className="flex items-center gap-1 text-[13px] text-brand-purple hover:opacity-80"
                title="返回工作台"
              >
                ← 工作台
              </Link>
            )}
            {isDashboard && <span className="section-title">工作台</span>}
            {projectId && activeName && (
              <span className="badge badge-brand">当前项目：{activeName}</span>
            )}
          </div>
          <TaskCenter />
        </header>
        <main className="flex-1 min-h-0 overflow-y-auto" style={{ animation: 'mirrorSlide 400ms var(--ease-out)' }}>
          {children}
        </main>
      </div>
      <RightPanel />
      <ConfirmCard />
    </div>
  );
}
