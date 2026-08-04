/* 左栏：项目列表（增删改查）+ 9 步流程导航（P-02） */
'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { useStudioStore } from '@/store/useStudioStore';
import { Badge, statusTone } from '@/components/ui';
import ProjectModal from '@/components/studio/ProjectModal';
import type { Project, ProjectFlow } from '@/lib/types';

const FLOW_LABELS: [string, string, string][] = [
  ['project', '项目', '/dashboard'],
  ['novel', '小说', '/script'],
  ['script', '剧本', '/script'],
  ['character', '角色', '/characters'],
  ['shot', '分镜', '/storyboard'],
  ['keyframe', '抽卡', '/keyframes'],
  ['video', '视频', '/video'],
  ['audio', '配音', '/audio'],
  ['final', '成片', '/export'],
];

export default function Sidebar() {
  const [flow, setFlow] = useState<ProjectFlow | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create');
  const [editing, setEditing] = useState<Project | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const pathname = usePathname();
  const router = useRouter();
  const projects = useStudioStore((s) => s.projects);
  const setProjects = useStudioStore((s) => s.setProjects);
  const projectId = useStudioStore((s) => s.projectId);
  const setProject = useStudioStore((s) => s.setProject);

  const loadProjects = async (keepCurrent = false) => {
    try {
      const list = await api.get<Project[]>('/api/projects');
      setProjects(list);
      if (!keepCurrent) {
        const cur = useStudioStore.getState().projectId;
        if (!cur && list.length) setProject(list[0].id);
      }
    } catch { /* 未登录等 */ }
  };

  useEffect(() => { loadProjects(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!projectId) return;
    api.get<ProjectFlow>(`/api/projects/${projectId}/flow`)
      .then(setFlow)
      .catch(() => {});
  }, [projectId, pathname]);

  /** 切换当前项目：更新 store 并同步 URL query（保留当前页面路径） */
  const switchProject = (id: number) => {
    setProject(id);
    router.replace(`${pathname}?project=${id}`, { scroll: false });
  };

  const openCreate = () => { setModalMode('create'); setEditing(null); setModalOpen(true); };
  const openEdit = (p: Project) => { setModalMode('edit'); setEditing(p); setModalOpen(true); };

  const onSaved = async (p: Project) => {
    setModalOpen(false);
    await loadProjects(true);          // 先刷新列表，再切换，避免时序不一致
    switchProject(p.id);
  };

  const onDelete = async (p: Project) => {
    await api.delete(`/api/projects/${p.id}`);
    setDeletingId(null);
    await loadProjects(true);
    if (useStudioStore.getState().projectId === p.id) {
      const rest = useStudioStore.getState().projects;
      if (rest.length) switchProject(rest[0].id);
      else setProject(null);
    }
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
          onClick={openCreate}
          title="新建项目"
        >+ 新建</button>
      </div>
      <div className="px-3 space-y-1 overflow-y-auto flex-1 min-h-0">
        {projects.map((p) => (
          <div
            key={p.id}
            className={`group relative card p-2.5 cursor-pointer ${projectId === p.id ? '' : 'opacity-80'}`}
            style={projectId === p.id ? { boxShadow: 'var(--glow-brand)' } : undefined}
            onClick={() => switchProject(p.id)}
          >
            <div className="flex items-center justify-between">
              <div className="text-[13px] truncate flex-1">{p.name}</div>
              {/* hover 操作：编辑 / 删除（二次确认） */}
              <div className="hidden group-hover:flex items-center gap-1 ml-2 shrink-0" onClick={(e) => e.stopPropagation()}>
                <button className="text-tertiary hover:text-primary text-[11px] px-1" title="编辑项目"
                  onClick={() => openEdit(p)}>✎</button>
                {deletingId === p.id ? (
                  <button className="text-[11px] px-1 font-medium"
                    style={{ color: 'var(--danger, #E5484D)' }} title="再次点击确认删除"
                    onClick={() => onDelete(p)}>确认?</button>
                ) : (
                  <button className="text-tertiary hover:text-danger text-[11px] px-1" title="删除项目"
                    onClick={() => setDeletingId(p.id)}>🗑</button>
                )}
              </div>
            </div>
            <div className="flex items-center justify-between mt-1">
              <span className="text-tertiary text-[10px]">{p.genre}</span>
              <span className="num text-[10px] text-tertiary">{p.progress}%</span>
            </div>
          </div>
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

      <ProjectModal
        open={modalOpen}
        mode={modalMode}
        project={editing}
        onClose={() => setModalOpen(false)}
        onSaved={onSaved}
      />
    </aside>
  );
}

/** 当前步骤状态映射（供页面判断完成度） */
export function flowStatus(flow: ProjectFlow | null, key: string): string {
  return flow?.steps.find((s) => s.key === key)?.status ?? 'pending';
}
