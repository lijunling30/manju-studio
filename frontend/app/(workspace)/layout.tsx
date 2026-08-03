/* 三栏工作台骨架（P-02）：左栏项目/流程 + 中栏内容 + 右栏资产/成本/任务 */
'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import RightPanel from '@/components/layout/RightPanel';
import TaskCenter from '@/components/layout/TaskCenter';
import ConfirmCard from '@/components/studio/ConfirmCard';
import { useStudioStore } from '@/store/useStudioStore';
import { useTaskStore } from '@/store/useTaskStore';

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const projectId = useStudioStore((s) => s.projectId);
  const setProject = useStudioStore((s) => s.setProject);

  // 从 URL ?project= 恢复当前项目
  useEffect(() => {
    const p = new URLSearchParams(window.location.search).get('project');
    if (p) setProject(Number(p));
  }, [setProject]);

  // 启动任务轮询（stop 在组件卸载时清理）
  useEffect(() => {
    const stop = useTaskStore.getState().startPolling();
    return stop;
  }, []);

  return (
    <div className="flex h-full">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        {/* 顶栏 */}
        <header className="h-12 shrink-0 border-b border-subtle bg-surface/80 backdrop-blur px-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="section-title">工作台</span>
            {projectId && (
              <Link href={`/dashboard?project=${projectId}`} className="text-tertiary hover:text-primary text-[12px]">
                项目 #{projectId}
              </Link>
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
