/* 视频生成面板（P-07）：厂商 Tab（价格实时）+ 镜头选择 + 异步任务进度 */
'use client';

import { useEffect, useState } from 'react';
import { api, assetUrl } from '@/lib/api';
import { useStudioStore } from '@/store/useStudioStore';
import { useConfirmGate } from '@/lib/useConfirmGate';
import { Badge, Button, Card, EmptyState, ProgressBar, Spinner, statusTone } from '@/components/ui';
import type { Keyframe, Shot, VideoTask } from '@/lib/types';

const VENDORS = [
  { key: 'vidu_q3', name: 'Vidu Q3', tag: '一致性主力', price: 1.2 },
  { key: 'seedance_2_0', name: '豆包 Seedance', tag: '性价比', price: 0.8 },
  { key: 'kling_2_0', name: '可灵 Kling', tag: '精品画质', price: 1.5 },
];

export default function VideoPage({ params }: { params: { id: string } }) {
  const projectId = Number(params.id);
  const setProject = useStudioStore((s) => s.setProject);
  const gate = useConfirmGate();
  const [shots, setShots] = useState<Shot[]>([]);
  const [keys, setKeys] = useState<Record<number, Keyframe[]>>({});
  const [tasks, setTasks] = useState<VideoTask[]>([]);
  const [vendor, setVendor] = useState('vidu_q3');
  const [duration, setDuration] = useState(4);
  const [selected, setSelected] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { setProject(projectId); }, [projectId, setProject]);

  const load = async () => {
    const list = await api.get<Shot[]>(`/api/projects/${projectId}/shots`).catch(() => []);
    setShots(list);
    const k: Record<number, Keyframe[]> = {};
    await Promise.all(list.slice(0, 12).map(async (s) => {
      try { k[s.id] = await api.get<Keyframe[]>(`/api/shots/${s.id}/keyframes`); } catch { k[s.id] = []; }
    }));
    setKeys(k);
  };

  const loadTasks = async () => {
    const all: VideoTask[] = [];
    for (const s of shots.slice(0, 12)) {
      try { all.push(...await api.get<VideoTask[]>(`/api/shots/${s.id}/video-tasks`)); } catch { /* 无任务 */ }
    }
    all.sort((a, b) => b.id - a.id);
    setTasks(all.slice(0, 12));
  };

  useEffect(() => { load(); }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  // 任务进度轮询
  useEffect(() => {
    if (!shots.length) return;
    loadTasks();
    const t = setInterval(loadTasks, 2500);
    return () => clearInterval(t);
  }, [shots.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const generate = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      await gate.request({
        module: 'video', projectId: null,
        params: { shot_id: selected, duration, vendor },
        onDispatched: async () => { await loadTasks(); },
      });
      await new Promise((r) => setTimeout(r, 1500));
      await loadTasks();
    } finally { setBusy(false); }
  };

  const vendorPrice = VENDORS.find((v) => v.key === vendor)?.price ?? 1.2;

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-[15px]">多镜头视频生成</h1>
        <Badge tone="info">图生视频 · 首帧=已确认关键帧</Badge>
      </div>

      {/* 厂商 Tab */}
      <Card className="p-4">
        <span className="section-title block mb-3">选择厂商（主失败自动切换备选）</span>
        <div className="flex gap-3">
          {VENDORS.map((v) => (
            <button key={v.key} onClick={() => setVendor(v.key)}
              className={`card p-3 flex-1 text-left ${vendor === v.key ? '' : 'opacity-70'}`}
              style={vendor === v.key ? { borderColor: 'var(--brand-purple)', boxShadow: 'var(--glow-brand)' } : undefined}>
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-medium">{v.name}</span>
                <span className="num text-[12px]" style={{ color: 'var(--brand-teal)' }}>¥{v.price}/秒</span>
              </div>
              <div className="text-tertiary text-[11px] mt-1">{v.tag}</div>
            </button>
          ))}
        </div>
        <div className="mt-4 flex items-center gap-3">
          <span className="text-tertiary text-[12px]">时长</span>
          <input className="input w-24" type="number" min={1} max={10} value={duration}
            onChange={(e) => setDuration(Number(e.target.value))} />
          <span className="text-tertiary text-[12px]">秒</span>
          <span className="num text-[12px] ml-4" style={{ color: 'var(--brand-purple)' }}>
            预估 ¥{(duration * vendorPrice).toFixed(2)}（确认卡展示区间）
          </span>
        </div>
      </Card>

      {/* 镜头选择 */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
        {shots.map((s) => {
          const approved = (keys[s.id] ?? []).find((k) => k.is_approved);
          const hasKeys = (keys[s.id] ?? []).length > 0;
          return (
            <Card key={s.id} className={`p-3 card-hover ${selected === s.id ? '' : 'opacity-80'}`}
              style={selected === s.id ? { borderColor: 'var(--brand-teal)', boxShadow: 'var(--glow-brand)' } : undefined}>
              <button className="w-full text-left" onClick={() => setSelected(s.id)}>
                <div className="flex items-center justify-between mb-1">
                  <span className="num text-[11px] text-tertiary">#{s.shot_no}</span>
                  <Badge tone={approved ? 'success' : hasKeys ? 'warning' : 'default'}>
                    {approved ? '关键帧已确认' : hasKeys ? '有候选未确认' : '无关键帧'}
                  </Badge>
                </div>
                {approved && (
                  <img src={assetUrl(approved.image_url)} alt="已确认关键帧"
                    className="w-full aspect-[9/16] object-cover rounded-sm border border-subtle mb-1" />
                )}
                <p className="text-[11px] text-tertiary line-clamp-2">{s.prompt_zh.slice(0, 30)}…</p>
              </button>
            </Card>
          );
        })}
      </div>

      <div className="flex items-center gap-3">
        <Button onClick={generate} disabled={busy || !selected}>
          {busy ? <Spinner className="h-3.5 w-3.5 inline mr-1" /> : null}
          生成 {selected ? `镜头 #${selected}` : ''} 视频
        </Button>
        {!selected && <span className="text-tertiary text-[12px]">请先选择镜头（需已确认关键帧）</span>}
      </div>

      {/* 任务状态 */}
      <Card className="p-4">
        <span className="section-title block mb-3">生成任务</span>
        {tasks.length === 0 && <EmptyState title="暂无视频任务" />}
        <div className="space-y-2">
          {tasks.map((t) => (
            <div key={t.id} className="card p-3">
              <div className="flex items-center justify-between">
                <span className="text-[13px]">任务 #{t.id} · {t.vendor} · {t.model}</span>
                <div className="flex items-center gap-2">
                  <Badge tone={statusTone(t.status)}>{t.status}</Badge>
                  {t.retry_count > 0 && <span className="num text-[11px] text-tertiary">重试 {t.retry_count}</span>}
                </div>
              </div>
              <div className="mt-2"><ProgressBar percent={t.progress} /></div>
              {t.error && <p className="text-danger text-[11px] mt-1">{t.error}</p>}
              {t.preview_url && (
                <video src={assetUrl(t.preview_url)} controls className="mt-2 h-40 rounded-sm border border-subtle" />
              )}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
