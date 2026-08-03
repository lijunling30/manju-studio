/* 成本中心（P-13）：指标卡 + 模块明细 + 预算滑杆 + 用户账单 */
'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useStudioStore } from '@/store/useStudioStore';
import { Badge, Button, Card } from '@/components/ui';
import type { Bill, CostSummary, Project } from '@/lib/types';

const MODULE_LABEL: Record<string, string> = {
  novel: '小说生成', script: '剧本', shot: '分镜', character: '角色形象',
  keyframe: '关键帧抽卡', video: '视频生成', audio_tts: '配音', bgm: 'BGM',
  sfx: '音效', render: '剪辑合成', compliance: '合规检验',
};

export default function CostsPage() {
  const projectId = useStudioStore((s) => s.projectId);
  const [cost, setCost] = useState<CostSummary | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [bill, setBill] = useState<Bill | null>(null);
  const [budget, setBudget] = useState(500);

  const load = async (pid?: number | null) => {
    const active = pid ?? projectId;
    if (!active) return;
    try { setCost(await api.get<CostSummary>(`/api/costs/projects/${active}`)); } catch { setCost(null); }
  };

  useEffect(() => {
    api.get<Project[]>('/api/projects').then(setProjects).catch(() => {});
    api.get<Bill>('/api/bills').then(setBill).catch(() => {});
  }, []);

  useEffect(() => { load(); }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const saveBudget = async (v: number) => {
    const r = await api.put<{ budget_limit: number }>('/api/users/me/budget', undefined, `budget_limit=${v}`);
    setBudget(r.budget_limit);
    if (projectId) load(projectId);
  };

  const modules = Object.entries(cost?.by_module ?? {}).sort((a, b) => b[1] - a[1]);

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-[15px]">成本中心</h1>

      {/* 项目切换 + 预算 */}
      <Card className="p-4 flex flex-wrap items-center gap-4">
        <select className="select w-48" value={projectId ?? ''}
          onChange={(e) => useStudioStore.getState().setProject(Number(e.target.value))}>
          <option value="" disabled>选择项目</option>
          {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <label className="flex items-center gap-2 text-[12px] text-tertiary">
          项目预算（元）
          <input className="input w-28 num" type="number" min={0} value={budget}
            onChange={(e) => setBudget(Number(e.target.value))} />
          <Button variant="ghost" onClick={() => saveBudget(budget)}>保存</Button>
        </label>
        {cost?.warn_80 && <Badge tone="warning">预算已达 80%，注意控制</Badge>}
        {cost?.blocked_100 && <Badge tone="danger">预算已用尽，AI 生成将被拦截</Badge>}
      </Card>

      {/* 指标卡 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: '已消耗', value: `¥${cost?.total.toFixed(2) ?? '0.00'}`, tone: 'var(--brand-purple)' },
          { label: '预算上限', value: `¥${(cost?.budget_limit ?? 0).toFixed(2)}`, tone: 'var(--brand-blue)' },
          { label: '使用率', value: `${cost?.usage_percent ?? 0}%`, tone: cost?.warn_80 ? 'var(--warning)' : 'var(--brand-teal)' },
          { label: '单分钟成本', value: '≈ ¥0.5', tone: 'var(--brand-teal)' },
        ].map((m) => (
          <Card key={m.label} className="p-4">
            <div className="section-title mb-2">{m.label}</div>
            <div className="num text-[22px] font-semibold" style={{ color: m.tone }}>{m.value}</div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* 模块明细 */}
        <Card className="p-4">
          <span className="section-title block mb-3">按模块消耗</span>
          {modules.length === 0 && <p className="text-tertiary text-[12px]">暂无成本记录</p>}
          <div className="space-y-2">
            {modules.map(([mod, amt]) => {
              const max = modules[0]?.[1] || 1;
              return (
                <div key={mod} className="flex items-center gap-3">
                  <span className="w-24 text-[12px] text-secondary">{MODULE_LABEL[mod] ?? mod}</span>
                  <div className="progress-track flex-1">
                    <div className="progress-bar" style={{ width: `${(amt / max) * 100}%` }} />
                  </div>
                  <span className="num text-[12px] w-20 text-right">¥{amt.toFixed(2)}</span>
                </div>
              );
            })}
          </div>
        </Card>

        {/* 用户账单 */}
        <Card className="p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="section-title">用户账单</span>
            <Badge tone="info">{bill?.plan ?? 'free'}</Badge>
          </div>
          <div className="space-y-2">
            {bill?.items.map((i) => (
              <div key={i.project_id} className="card p-3 flex items-center justify-between">
                <div>
                  <div className="text-[13px]">{i.project_name}</div>
                  <div className="num text-[11px] text-tertiary">{i.calls} 次调用</div>
                </div>
                <span className="num text-[14px]">¥{i.total.toFixed(2)}</span>
              </div>
            ))}
            {!bill?.items?.length && <p className="text-tertiary text-[12px]">暂无账单</p>}
          </div>
        </Card>
      </div>

      {/* 成本流水 */}
      <Card className="p-4">
        <span className="section-title block mb-3">成本流水（镜头级记账）</span>
        <table className="w-full text-left">
          <thead>
            <tr className="text-tertiary text-[11px]">
              <th className="pb-2 font-normal">时间</th>
              <th className="pb-2 font-normal">模块</th>
              <th className="pb-2 font-normal">厂商</th>
              <th className="pb-2 font-normal">量</th>
              <th className="pb-2 font-normal text-right">金额</th>
            </tr>
          </thead>
          <tbody>
            {cost?.logs.map((l) => (
              <tr key={l.id} className="border-t border-subtle text-[12px]">
                <td className="py-1.5 num text-tertiary">{l.created_at.slice(5, 19).replace('T', ' ')}</td>
                <td className="py-1.5">{MODULE_LABEL[l.module] ?? l.module}</td>
                <td className="py-1.5 num text-tertiary">{l.vendor}</td>
                <td className="py-1.5 num text-tertiary">
                  {l.tokens ? `${l.tokens} tok` : l.duration ? `${l.duration}s` : `${l.count} 次`}
                </td>
                <td className="py-1.5 num text-right">¥{l.amount.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
