/* 右栏：资产引用 + 项目成本小计 + 任务状态（P-02） */
'use client';

import { useEffect, useState } from 'react';
import { api, assetUrl } from '@/lib/api';
import { useStudioStore } from '@/store/useStudioStore';
import { Badge, statusTone } from '@/components/ui';
import { TaskList } from '@/components/layout/TaskCenter';
import type { CostSummary, Shot } from '@/lib/types';

export default function RightPanel() {
  const projectId = useStudioStore((s) => s.projectId);
  const [cost, setCost] = useState<CostSummary | null>(null);
  const [shots, setShots] = useState<Shot[]>([]);

  useEffect(() => {
    if (!projectId) return;
    api.get<CostSummary>(`/api/costs/projects/${projectId}`).then(setCost).catch(() => {});
    api.get<Shot[]>(`/api/projects/${projectId}/shots`).then(setShots).catch(() => {});
  }, [projectId]);

  return (
    <aside className="w-[280px] shrink-0 border-l border-subtle bg-surface h-full overflow-y-auto p-4 space-y-5">
      {/* 成本小计 */}
      <section>
        <span className="section-title block mb-2">项目成本</span>
        {cost ? (
          <div className="card p-3 space-y-2">
            <div className="flex items-end justify-between">
              <span className="text-tertiary text-[12px]">已消耗</span>
              <span className="num text-[20px] font-semibold" style={{ background: 'var(--brand-gradient)', WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' }}>
                ¥{cost.total.toFixed(2)}
              </span>
            </div>
            <div className="flex items-center justify-between text-[12px]">
              <span className="text-tertiary">预算</span>
              <span className="num">¥{cost.budget_limit.toFixed(2)}</span>
            </div>
            <div className="progress-track">
              <div
                className="progress-bar"
                style={{
                  width: `${Math.min(100, cost.usage_percent)}%`,
                  background: cost.blocked_100 ? 'var(--danger)' : cost.warn_80 ? 'var(--warning)' : 'var(--brand-gradient)',
                }}
              />
            </div>
            <div className="flex justify-between">
              <span className="num text-[11px] text-tertiary">{cost.usage_percent}%</span>
              {cost.warn_80 && !cost.blocked_100 && <Badge tone="warning">预算达 80%</Badge>}
              {cost.blocked_100 && <Badge tone="danger">预算已用尽</Badge>}
            </div>
          </div>
        ) : (
          <p className="text-tertiary text-[12px]">请先选择项目</p>
        )}
      </section>

      {/* 当前镜头引用 */}
      <section>
        <span className="section-title block mb-2">镜头素材</span>
        <div className="space-y-1.5">
          {shots.length === 0 && <p className="text-tertiary text-[12px]">暂无分镜</p>}
          {shots.slice(0, 8).map((s) => (
            <div key={s.id} className="card p-2 flex items-center gap-2">
              <span className="num text-[11px] text-tertiary shrink-0">#{s.shot_no}</span>
              <span className="text-[12px] truncate flex-1">{s.prompt_zh.slice(0, 18)}…</span>
              <Badge tone={statusTone(s.status)}>{s.status}</Badge>
            </div>
          ))}
        </div>
      </section>

      {/* 任务状态 */}
      <section>
        <span className="section-title block mb-2">任务中心</span>
        <TaskList />
      </section>
    </aside>
  );
}
