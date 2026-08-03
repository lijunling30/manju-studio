/* 项目工作台主页（P-02）：项目总览 + 9 步流程入口 + 闸口状态 */
'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api, sessionId } from '@/lib/api';
import { useStudioStore } from '@/store/useStudioStore';
import { Badge, Card, statusTone } from '@/components/ui';
import type { CostSummary, GateSetting, Project, ProjectFlow } from '@/lib/types';

const MODULES: { key: string; label: string; desc: string; href: (id: number) => string }[] = [
  { key: 'novel', label: '小说生成', desc: '题材/人设/章纲', href: (id) => `/script/${id}` },
  { key: 'script', label: '剧本结构化', desc: '分场 + 情绪曲线', href: (id) => `/script/${id}` },
  { key: 'shot', label: '分镜设计', desc: '镜头语言 + 纯中文提示词', href: (id) => `/storyboard/${id}` },
  { key: 'character', label: '角色资产库', desc: '三视图 + 表情集', href: () => '/characters' },
  { key: 'keyframe', label: '关键帧抽卡', desc: '候选帧 + AI 评分', href: (id) => `/keyframes/${id}` },
  { key: 'video', label: '多镜头视频', desc: 'Vidu/豆包/可灵聚合', href: (id) => `/video/${id}` },
  { key: 'audio', label: '配音音效', desc: 'TTS + BGM + 音效', href: (id) => `/audio/${id}` },
  { key: 'final', label: '剪辑合成', desc: '成片 + AI 标识强制', href: (id) => `/export/${id}` },
  { key: 'cost', label: '成本中心', desc: '预算 + 账单', href: () => '/costs' },
];

export default function DashboardPage() {
  const projectId = useStudioStore((s) => s.projectId);
  const setProject = useStudioStore((s) => s.setProject);
  const [projects, setProjects] = useState<Project[]>([]);
  const [flow, setFlow] = useState<ProjectFlow | null>(null);
  const [cost, setCost] = useState<CostSummary | null>(null);
  const [gate, setGate] = useState<GateSetting | null>(null);

  const load = async (pid?: number | null) => {
    try {
      const list = await api.get<Project[]>('/api/projects');
      setProjects(list);
      const active = pid ?? projectId ?? list[0]?.id ?? null;
      if (active) {
        setProject(active);
        api.get<ProjectFlow>(`/api/projects/${active}/flow`).then(setFlow).catch(() => {});
        api.get<CostSummary>(`/api/costs/projects/${active}`).then(setCost).catch(() => {});
      }
    } catch { /* 未登录 */ }
  };

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    api.get<GateSetting>(`/api/ai/settings/gate?session_id=${sessionId()}`).then(setGate).catch(() => {});
  }, []);

  const toggleGate = async () => {
    if (!gate) return;
    const next = !gate.global_enabled;
    const g = await api.put<GateSetting>('/api/ai/settings/gate', { global_enabled: next });
    setGate(g);
  };

  const activeProject = projects.find((p) => p.id === projectId);

  return (
    <div className="p-6 space-y-6">
      {/* 闸口状态条 */}
      <div className="flex items-center justify-between">
        <h1 className="text-[15px]">项目工作台</h1>
        <div className="flex items-center gap-2">
          {gate && (
            <button
              className={gate.global_enabled ? 'badge badge-info' : 'badge badge-warning'}
              onClick={toggleGate}
              title="会话级/模块级/全局三级开关，成本护栏不受影响"
            >
              {gate.global_enabled ? '确认闸口已开启（点击关闭）' : '确认闸口已关闭（点击恢复）'}
            </button>
          )}
          <Badge tone="brand">AI 标识强制</Badge>
        </div>
      </div>

      {/* 项目选择 */}
      <div className="flex gap-3 overflow-x-auto pb-1">
        {projects.map((p) => (
          <button
            key={p.id}
            onClick={() => load(p.id)}
            className={`card px-4 py-2 text-[13px] whitespace-nowrap ${projectId === p.id ? '' : 'opacity-70'}`}
            style={projectId === p.id ? { boxShadow: 'var(--glow-brand)' } : undefined}
          >
            {p.name}
            <span className="num text-tertiary text-[11px] ml-2">{p.progress}%</span>
          </button>
        ))}
      </div>

      {!activeProject ? (
        <Card className="p-16 text-center text-secondary">
          请先在左侧「+ 新建」创建项目
        </Card>
      ) : (
        <>
          {/* 项目概览 */}
          <Card className="p-5 flex items-center justify-between">
            <div>
              <div className="text-[15px] font-medium">{activeProject.name}</div>
              <div className="text-tertiary text-[12px] mt-1">
                {activeProject.genre} · {activeProject.style_name} · {activeProject.target_platform}
              </div>
            </div>
            <div className="flex items-center gap-6 text-right">
              <div>
                <div className="num text-[18px] font-semibold" style={{ color: 'var(--brand-teal)' }}>¥{cost?.total.toFixed(2) ?? '0.00'}</div>
                <div className="text-tertiary text-[11px]">已消耗 / 预算 ¥{activeProject.budget_limit}</div>
              </div>
              <div>
                <div className="num text-[18px] font-semibold">{flow?.steps.filter((s) => s.status === 'done').length ?? 0}/{flow?.steps.length ?? 9}</div>
                <div className="text-tertiary text-[11px]">流程完成</div>
              </div>
            </div>
          </Card>

          {/* 模块入口 */}
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
            {MODULES.map((m) => {
              const st = flow?.steps.find((s) => s.key === m.key)?.status ?? 'pending';
              return (
                <Link key={m.key} href={m.href(projectId!)} className="card p-4 card-hover block">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[13px] font-medium">{m.label}</span>
                    <Badge tone={statusTone(st)}>{st === 'done' ? '完成' : st === 'active' ? '进行中' : '待开始'}</Badge>
                  </div>
                  <p className="text-tertiary text-[12px]">{m.desc}</p>
                </Link>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
