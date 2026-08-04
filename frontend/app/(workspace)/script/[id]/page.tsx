/* 剧本编辑器（P-03）：小说生成 + 剧本结构化 + 情绪曲线 */
'use client';

import { useCallback, useEffect, useState } from 'react';
import { api, waitForTask } from '@/lib/api';
import { useStudioStore } from '@/store/useStudioStore';
import { useConfirmGate } from '@/lib/useConfirmGate';
import { Badge, Button, Card, EmptyState, Spinner, statusTone } from '@/components/ui';
import type { Novel, Script, ScriptScene } from '@/lib/types';

const EMOTION_TONE: Record<string, string> = {
  '爽点': 'success', '虐点': 'danger', '反转': 'brand', '高潮': 'warning',
  '铺垫': 'default',
};

function EmotionCurve({ curve }: { curve: Script['emotion_curve'] }) {
  if (!curve.length) return null;
  const w = 600, h = 120, pad = 16;
  const max = Math.max(...curve.map((c) => c.intensity));
  const step = (w - pad * 2) / Math.max(1, curve.length - 1);
  const pts = curve.map((c, i) => `${(pad + i * step).toFixed(1)},${(h - pad - (c.intensity / max) * (h - pad * 2)).toFixed(1)}`);
  const COLOR: Record<string, string> = { '爽点': '#1D9E75', '虐点': '#A32D2D', '反转': '#378ADD' };
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ maxHeight: 160 }}>
      {curve.map((c, i) => (
        <circle key={i} cx={pad + i * step} cy={h - pad - (c.intensity / max) * (h - pad * 2)} r="3"
          fill={COLOR[c.emotion] ?? 'var(--brand-purple)'} />
      ))}
      <polyline points={pts.join(' ')} fill="none" stroke="var(--brand-purple)" strokeWidth="1.5" opacity="0.8" />
      {curve.map((c, i) => (
        <text key={i} x={pad + i * step} y={h - 4} fontSize="9" fill="var(--text-tertiary)" textAnchor="middle">
          {c.scene_no}
        </text>
      ))}
    </svg>
  );
}

export default function ScriptPage({ params }: { params: { id: string } }) {
  const projectId = Number(params.id);
  const setProject = useStudioStore((s) => s.setProject);
  const gate = useConfirmGate();
  const [novel, setNovel] = useState<Novel | null>(null);
  const [script, setScript] = useState<Script | null>(null);
  const [selected, setSelected] = useState<number>(0);
  const [form, setForm] = useState({ genre: '都市', setting: '', protagonist: '陈默', chapter_count: 6 });
  const [busy, setBusy] = useState(false);

  useEffect(() => { setProject(projectId); }, [projectId, setProject]);

  const load = useCallback(async () => {
    try {
      const n = await api.get<Novel | null>(`/api/projects/${projectId}/novel`);
      setNovel(n);
      if (n?.chapters?.length) setSelected(0);
    } catch { setNovel(null); }
    try {
      const s = await api.get<Script | null>(`/api/projects/${projectId}/script`);
      setScript(s);
    } catch { setScript(null); }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const generateNovel = async () => {
    setBusy(true);
    try {
      await gate.request({
        module: 'novel', projectId,
        params: { ...form, project_id: projectId },
        onDispatched: async () => { await load(); },
        // 小说生成异步执行（真实模式每章 2500 字需数分钟）：轮询任务完成再加载
        onTaskCreated: async (dispatch) => {
          const taskId = Number(dispatch.task_id ?? 0);
          if (taskId) await waitForTask(taskId, 'novel_generate');
          await load();
        },
      });
    } catch {
      // 任务失败/超时：保留现有内容
    } finally { setBusy(false); }
  };

  const convertScript = async () => {
    setBusy(true);
    try {
      await gate.request({
        module: 'script', projectId,
        params: { project_id: projectId },
        onDispatched: async () => { await load(); },
      });
      await load();
    } finally { setBusy(false); }
  };

  const ch = novel?.chapters?.[selected];

  return (
    <div className="p-6 space-y-4">
      {/* 工具栏 */}
      <div className="flex items-center justify-between">
        <h1 className="text-[15px]">剧本编辑器</h1>
        <div className="flex items-center gap-2">
          <Badge tone={novel?.status === 'completed' ? 'success' : 'default'}>
            {novel?.status === 'completed' ? '小说已生成' : '未生成'}
          </Badge>
          {script?.status === 'completed' && <Badge tone="success">剧本已结构化</Badge>}
        </div>
      </div>

      {/* 生成表单 */}
      <Card className="p-4 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-[12px] text-tertiary">
          题材
          <input className="input w-24" value={form.genre} onChange={(e) => setForm({ ...form, genre: e.target.value })} />
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-tertiary">
          世界观
          <input className="input w-40" placeholder="如：废土、现代都市" value={form.setting} onChange={(e) => setForm({ ...form, setting: e.target.value })} />
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-tertiary">
          主角
          <input className="input w-28" value={form.protagonist} onChange={(e) => setForm({ ...form, protagonist: e.target.value })} />
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-tertiary">
          章数
          <input className="input w-20" type="number" min={1} max={20} value={form.chapter_count}
            onChange={(e) => setForm({ ...form, chapter_count: Number(e.target.value) })} />
        </label>
        <Button onClick={generateNovel} disabled={busy}>
          {busy ? <Spinner className="h-3.5 w-3.5 inline mr-1" /> : null}AI 生成小说
        </Button>
        <Button variant="ghost" onClick={convertScript} disabled={busy || novel?.status !== 'completed'}>
          结构化为剧本
        </Button>
      </Card>

      {!novel && <EmptyState title="尚未生成小说" hint="填写题材与主角后点击「AI 生成小说」，请求将先进入确认闸口" />}

      {novel && (
        <div className="grid grid-cols-[220px_1fr] gap-4 h-[calc(100vh-260px)] min-h-[380px]">
          {/* 大纲树 */}
          <Card className="p-3 overflow-y-auto">
            <span className="section-title block mb-2">章节大纲</span>
            <div className="space-y-1">
              {novel.outline.map((o, i) => (
                <button key={o.no} onClick={() => setSelected(i)}
                  className={`w-full text-left px-3 py-2 rounded-sm text-[12px] ${selected === i ? '' : 'text-tertiary'}`}
                  style={selected === i ? { background: 'rgba(127,119,221,0.15)', color: 'var(--brand-purple)' } : undefined}>
                  <span className="num mr-1">#{o.no}</span>{o.title}
                </button>
              ))}
            </div>
          </Card>

          {/* 正文编辑（Monaco 同源风格：深色 + 等宽） */}
          <Card className="flex flex-col min-w-0">
            <div className="px-4 py-2 border-b border-subtle flex items-center justify-between">
              <span className="text-[13px]">{ch?.title ?? '（无内容）'}</span>
              <span className="text-tertiary text-[11px]">Ctrl+S 保存</span>
            </div>
            <textarea
              className="flex-1 w-full bg-transparent p-4 outline-none resize-none font-mono text-[13px] leading-relaxed text-primary"
              value={ch?.content ?? ''}
              onChange={() => {}}
              placeholder="章节正文（演示环境只读，生产接入 Monaco Editor 支持续写/改写）"
              spellCheck={false}
            />
          </Card>
        </div>
      )}

      {/* 结构化剧本场景列表 */}
      {script?.status === 'completed' && script.scenes?.length > 0 && (
        <Card className="p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="section-title">剧本分场（{script.scenes.length} 场）</span>
            <span className="text-tertiary text-[11px]">{script.title}</span>
          </div>
          <div className="space-y-3">
            {script.scenes.map((sc) => (
              <SceneCard key={sc.scene_no} scene={sc} />
            ))}
          </div>
        </Card>
      )}
      {script && script.status !== 'completed' && (
        <Card className="p-4">
          <EmptyState title="剧本尚未结构化" hint="先生成小说，再点击「结构化为剧本」按钮" />
        </Card>
      )}

      {/* 情绪曲线 */}
      {script?.emotion_curve && (
        <Card className="p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="section-title">情绪曲线（爽点/虐点/反转）</span>
            <div className="flex gap-3 text-[11px] text-tertiary">
              <span>● 爽点 #1D9E75</span><span>● 虐点 #A32D2D</span><span>● 反转 #378ADD</span>
            </div>
          </div>
          <EmotionCurve curve={script.emotion_curve} />
        </Card>
      )}
    </div>
  );
}

/** 场景卡片：场景号 / 地点·时间 / 情绪标签 / 概要 / 节拍列表（角色·对白·旁白·动作·情绪） */
function SceneCard({ scene }: { scene: ScriptScene }) {
  const [expanded, setExpanded] = useState(true);
  const tone = EMOTION_TONE[scene.emotion] ?? 'default';
  return (
    <div className="rounded-sm border border-subtle bg-elevated/30 overflow-hidden">
      {/* 场景头部 */}
      <div
        className="px-3 py-2 flex items-center gap-2 cursor-pointer hover:bg-elevated/60 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <span className="num text-[11px] text-tertiary shrink-0">#{scene.scene_no}</span>
        <span className="text-[13px] flex-1 truncate">
          📍 {scene.location || '未知地点'} · 🕐 {scene.time || '未知时间'}
        </span>
        <Badge tone={tone as 'success'}>{scene.emotion || '铺垫'}</Badge>
        <span className="text-tertiary text-[11px] shrink-0">{expanded ? '▾' : '▸'}</span>
      </div>

      {/* 场景概要 */}
      {expanded && (
        <div className="px-3 pb-3 pt-1">
          <p className="text-[12px] text-secondary leading-relaxed mb-2">{scene.summary}</p>

          {/* 节拍列表 */}
          {scene.beats?.length > 0 && (
            <div className="space-y-1.5 mt-2">
              <span className="text-tertiary text-[10px] tracking-wider">节拍</span>
              {scene.beats.map((b, i) => (
                <div key={i} className="pl-3 border-l-2 border-brand-purple/30 text-[12px] leading-relaxed">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-primary font-medium">{b.character || '旁白'}</span>
                    {b.emotion && <span className="text-tertiary text-[10px]">[{b.emotion}]</span>}
                  </div>
                  {b.dialogue && <p className="text-secondary mt-0.5">「{b.dialogue}」</p>}
                  {b.narration && <p className="text-tertiary italic mt-0.5">（{b.narration}）</p>}
                  {b.action && <p className="text-tertiary text-[11px] mt-0.5">动作：{b.action}</p>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
