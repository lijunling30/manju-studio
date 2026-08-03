/* 分镜时间线（P-04）：镜头卡片流 + 批量生成（确认闸口联动） */
'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { useStudioStore } from '@/store/useStudioStore';
import { useConfirmGate } from '@/lib/useConfirmGate';
import { Badge, Button, Card, EmptyState, statusTone } from '@/components/ui';
import type { Shot } from '@/lib/types';

const TYPE_LABEL: Record<string, string> = {
  特写: '特写', 近景: '近景', 中景: '中景', 远景: '远景', 大远景: '大远景', 俯拍: '俯拍',
};

export default function StoryboardPage({ params }: { params: { id: string } }) {
  const projectId = Number(params.id);
  const setProject = useStudioStore((s) => s.setProject);
  const gate = useConfirmGate();
  const [shots, setShots] = useState<Shot[]>([]);
  const [count, setCount] = useState(9);
  const [busy, setBusy] = useState(false);
  const [dragId, setDragId] = useState<number | null>(null);

  useEffect(() => { setProject(projectId); }, [projectId, setProject]);

  const load = async () => {
    try {
      setShots(await api.get<Shot[]>(`/api/projects/${projectId}/shots`));
    } catch { setShots([]); }
  };
  useEffect(() => { load(); }, [projectId]);

  const generate = async () => {
    setBusy(true);
    try {
      await gate.request({
        module: 'shot', projectId, batchCount: count,
        params: { project_id: projectId, shot_count: count },
        onDispatched: async () => { await load(); },
      });
    } finally { setBusy(false); }
  };

  const onDrop = (targetId: number) => {
    if (dragId == null || dragId === targetId) return;
    setShots((prev) => {
      const list = [...prev];
      const from = list.findIndex((s) => s.id === dragId);
      const to = list.findIndex((s) => s.id === targetId);
      const [item] = list.splice(from, 1);
      list.splice(to, 0, item);
      return list;
    });
    setDragId(null);
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-[15px]">分镜时间线</h1>
        <div className="flex items-center gap-2">
          <span className="num text-tertiary text-[12px]">{shots.length} 个镜头</span>
          <input className="input w-20 text-center" type="number" min={1} max={60}
            value={count} onChange={(e) => setCount(Number(e.target.value))} />
          <Button onClick={generate} disabled={busy}>
            {busy ? '生成中…' : `批量生成 ${count} 镜头`}
          </Button>
        </div>
      </div>

      {shots.length === 0 && (
        <EmptyState title="尚无分镜" hint="设置镜头数量后点击「批量生成」；批量 ≥20 镜头将触发闸口批量护栏强制确认" />
      )}

      <div className="flex gap-3 overflow-x-auto pb-4" style={{ minHeight: 200 }}>
        {shots.map((s) => (
          <div
            key={s.id}
            draggable
            onDragStart={() => setDragId(s.id)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => onDrop(s.id)}
            className="card p-3 w-[240px] shrink-0 card-hover cursor-grab"
          >
            <div className="flex items-center justify-between">
              <span className="num text-[11px] text-tertiary">#{s.shot_no}</span>
              <Badge tone={statusTone(s.status)}>{s.status}</Badge>
            </div>
            <div className="mt-2 mb-2 aspect-[9/16] rounded-sm border border-subtle flex items-center justify-center"
              style={{ background: 'var(--bg-elevated)' }}>
              <span className="text-tertiary text-[11px]">
                {TYPE_LABEL[s.shot_type] ?? s.shot_type} · {s.camera_move}
              </span>
            </div>
            <p className="text-[12px] leading-relaxed line-clamp-3">{s.prompt_zh}</p>
            <div className="flex items-center justify-between mt-2 text-[11px] text-tertiary">
              <span className="num">{s.duration}s</span>
              {s.dialogue && <span className="truncate max-w-[120px]">「{s.dialogue}」</span>}
            </div>
            <Link href={`/keyframes/${s.id}`} className="btn-ghost w-full mt-2 text-center block text-[12px]">
              去抽卡
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
