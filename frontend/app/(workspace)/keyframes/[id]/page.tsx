/* 关键帧抽卡（P-06）：候选九宫格 + AI 评分 + 确认 + 再抽一轮 */
'use client';

import { useEffect, useState } from 'react';
import { api, assetUrl } from '@/lib/api';
import { useConfirmGate } from '@/lib/useConfirmGate';
import { useStudioStore } from '@/store/useStudioStore';
import { Badge, Button, Card, EmptyState, Spinner } from '@/components/ui';
import type { Keyframe } from '@/lib/types';

export default function KeyframesPage({ params }: { params: { id: string } }) {
  const shotId = Number(params.id);
  const gate = useConfirmGate();
  const [frames, setFrames] = useState<Keyframe[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [flip, setFlip] = useState(false);

  const load = async () => {
    try {
      const list = await api.get<Keyframe[]>(`/api/shots/${shotId}/keyframes`);
      setFrames(list);
      setSelected(list[0]?.id ?? null);
    } catch { setFrames([]); }
  };
  useEffect(() => { load(); }, [shotId]);

  const generate = async (count = 2) => {
    setBusy(true);
    try {
      setFlip(false);
      await gate.request({
        module: 'keyframe', projectId: null, batchCount: count,
        params: { shot_id: shotId, count },
        onDispatched: async () => {
          await load();
          setFlip(true);
        },
      });
      if (useStudioStore.getState().confirmCard === null) {
        await new Promise((r) => setTimeout(r, 1000));
        await load();
        setFlip(true);
      }
    } finally { setBusy(false); }
  };

  const approve = async (id: number) => {
    await api.post(`/api/keyframes/${id}/approve`);
    await load();
  };

  const big = frames.find((f) => f.id === selected);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-[15px]">关键帧抽卡 · 镜头 #{shotId}</h1>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => generate(2)} disabled={busy}>
            {busy ? <Spinner className="h-3.5 w-3.5 inline mr-1" /> : null}再抽一轮
          </Button>
        </div>
      </div>

      {frames.length === 0 && (
        <EmptyState title="暂无候选帧" hint="点击「再抽一轮」生成 2 张候选帧；连续抽卡可先关闭闸口（5.0.1）" />
      )}

      {big && (
        <Card className="p-4 flex gap-4 items-start">
          <img src={assetUrl(big.image_url)} alt={`候选帧 ${big.id}`}
            className="w-[240px] aspect-[9/16] object-cover rounded-sm border border-subtle" />
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[14px] font-medium">候选帧 #{big.id}</span>
              <Badge tone={big.is_approved ? 'success' : 'default'}>
                {big.is_approved ? '已确认' : '未确认'}
              </Badge>
            </div>
            <div className="space-y-2">
              {Object.entries(big.score).map(([k, v]) => (
                <div key={k} className="flex items-center gap-3">
                  <span className="w-16 text-tertiary text-[12px]">
                    {{ composition: '构图', consistency: '一致性', clarity: '清晰度', overall: '综合' }[k] ?? k}
                  </span>
                  <div className="progress-track flex-1">
                    <div className="progress-bar" style={{ width: `${v * 100}%` }} />
                  </div>
                  <span className="num text-[12px] w-12 text-right">{v.toFixed(2)}</span>
                </div>
              ))}
            </div>
            <div className="mt-4 flex gap-2">
              <Button onClick={() => approve(big.id)} disabled={big.is_approved}>确认此帧</Button>
              <Button variant="ghost" onClick={() => generate(2)} disabled={busy}>不满意，再抽</Button>
            </div>
          </div>
        </Card>
      )}

      {/* 候选九宫格 */}
      <div className="grid grid-cols-3 md:grid-cols-4 xl:grid-cols-6 gap-3">
        {frames.map((f) => (
          <button key={f.id} onClick={() => setSelected(f.id)}
            className={`relative rounded-sm overflow-hidden border ${selected === f.id ? '' : 'border-subtle opacity-80'}`}
            style={selected === f.id ? { borderColor: 'var(--brand-purple)', boxShadow: 'var(--glow-brand)' } : undefined}>
            <img src={assetUrl(f.image_url)} alt={`候选 ${f.id}`} className={`aspect-[9/16] object-cover ${flip ? 'animate-flipIn' : ''}`} />
            <span className="absolute top-1.5 right-1.5 badge badge-brand num text-[10px]">
              {f.score.overall.toFixed(2)}
            </span>
            {f.is_approved && (
              <span className="absolute bottom-1.5 left-1.5 badge badge-success text-[10px]">✓ 已确认</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
