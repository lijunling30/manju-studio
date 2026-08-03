/* 左栏：项目列表 + 9 步流程导航（P-02） */
'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { api } from '@/lib/api';
import { useStudioStore } from '@/store/useStudioStore';
import { Badge, statusTone } from '@/components/ui';
import type { Project, ProjectFlow } from '@/lib/types';

const FLOW_LABELS: [string, string, string][] = [
  ['project', '项目', '/dashboard'],
  ['novel', '小说', '/script'],
  ['script', '剧本', '/script'],
  ['shot', '分镜', '/storyboard'],
  ['character', '角色', '/characters'],
  ['keyframe', '抽卡', '/keyframes'],
  ['video', '视频', '/video'],
  ['audio', '配音', '/audio'],
  ['final', '成片', '/export'],
];

export default function Sidebar() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [flow, setFlow] = useState<ProjectFlow | null>(null);
  const [creating, setCreating] = useState(false);
  const pathname = usePathname();
  const projectId = useStudioStore((s) => s.projectId);
  const setProject = useStudioStore((s) => s.setProject);

  const loadProjects = async () => {
    try {
      const list = await api.get<Project[]>('/api/projects');
      setProjects(list);
      if (!projectId && list.length) setProject(list[0].id);
    } catch { /* 未登录等 */ }
  };

  useEffect(() => { loadProjects(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!projectId) return;
    api.get<ProjectFlow>(`/api/projects/${projectId}/flow`)
      .then(setFlow)
      .catch(() => {});
  }, [projectId, pathname]);

  const onCreate = async () => {
    setCreating(true);
    try {
      const p = await api.post<Project>('/api/projects', {
        name: `新项目 ${projects.length + 1}`, genre: '都市', description: '',
        style_id: 'style_01', style_name: '默认', target_platform: 'douyin_9_16', budget_limit: 500,
      });
      await loadProjects();
      setProject(p.id);
      window.location.href = `/dashboard?project=${p.id}`;
    } finally { setCreating(false); }
  };

  return (
    <aside className="w-[200px] shrink-0 border-r border-subtle bg-surface flex flex-col h-full">
      {/* 品牌 */}
      <div className="px-4 py-4">
        <Link href="/dashboard" className="flex items-center gap-2">
          <span
            className="h-8 w-8 rounded-sm flex items-center justify-center text-white text-[13px] font-serif"
            style={{ background: 'var(--brand-gradient)' }}
          >镜</span>
          <div>
            <div className="text-[14px] font-serif font-semibold leading-none">漫镜工场</div>
            <div className="text-tertiary text-[10px] mt-0.5 tracking-widest">MANJU STUDIO</div>
          </div>
        </Link>
      </div>

      {/* 项目列表 */}
      <div className="px-3 mb-2 flex items-center justify-between">
        <span className="section-title">项目</span>
        <button
          className="text-brand-purple text-[13px] hover:opacity-80"
          onClick={onCreate}
          disabled={creating}
          title="新建项目"
        >+ 新建</button>
      </div>
      <div className="px-3 space-y-1 overflow-y-auto flex-1 min-h-0">
        {projects.map((p) => (
          <button
            key={p.id}
            onClick={() => setProject(p.id)}
            className={`w-full text-left card p-2.5 card-hover ${projectId === p.id ? '' : 'opacity-80'}`}
            style={projectId === p.id ? { boxShadow: 'var(--glow-brand)' } : undefined}
          >
            <div className="text-[13px] truncate">{p.name}</div>
            <div className="flex items-center justify-between mt-1">
              <span className="text-tertiary text-[10px]">{p.genre}</span>
              <span className="num text-[10px] text-tertiary">{p.progress}%</span>
            </div>
          </button>
        ))}
        {projects.length === 0 && (
          <p className="text-tertiary text-[12px] py-6 text-center">暂无项目，点击右上角新建</p>
        )}
      </div>

      {/* 9 步流程导航 */}
      {flow && (
        <div className="border-t border-subtle px-4 py-3">
          <span className="section-title block mb-2">制作流程</span>
          <ol className="space-y-1">
            {flow.steps.map((s, i) => {
              const [, label] = FLOW_LABELS[i] ?? [s.key, s.label, ''];
              return (
                <li key={s.key}>
                  <span className={`flex items-center gap-2 text-[12px] ${s.status === 'done' ? 'text-success' : s.status === 'active' ? 'text-primary' : 'text-tertiary'}`}>
                    <span className={`num inline-flex h-4 w-4 items-center justify-center rounded-pill text-[10px] ${s.status === 'done' ? 'bg-success text-white' : 'bg-elevated border border-subtle'}`}>
                      {s.status === 'done' ? '✓' : i + 1}
                    </span>
                    {label}
                    {s.status === 'active' && <Badge tone="brand">进行中</Badge>}
                  </span>
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </aside>
  );
}

/** 当前步骤状态映射（供页面判断完成度） */
export function flowStatus(flow: ProjectFlow | null, key: string): string {
  return flow?.steps.find((s) => s.key === key)?.status ?? 'pending';
}
