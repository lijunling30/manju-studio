/* 配音与音效面板（P-08）：对白 TTS + BGM + 音效三轨 + 音色卡 */
'use client';

import { useEffect, useState } from 'react';
import { api, assetUrl, waitForTask } from '@/lib/api';
import { useStudioStore } from '@/store/useStudioStore';
import { useConfirmGate } from '@/lib/useConfirmGate';
import { Badge, Button, Card, EmptyState, Spinner } from '@/components/ui';
import type { AudioAsset, Shot } from '@/lib/types';

const VOICES = [
  { id: 'doubao_voice_1', name: '沉稳男声', desc: '男主 · 冷峻' },
  { id: 'doubao_voice_2', name: '清亮女声', desc: '女主 · 灵动' },
  { id: 'doubao_voice_3', name: '温润少年', desc: '配角 · 亲和' },
];

export default function AudioPage({ params }: { params: { id: string } }) {
  const projectId = Number(params.id);
  const setProject = useStudioStore((s) => s.setProject);
  const gate = useConfirmGate();
  const [tracks, setTracks] = useState<AudioAsset[]>([]);
  const [shots, setShots] = useState<Shot[]>([]);
  const [checked, setChecked] = useState<number[]>([]);
  const [withBgm, setWithBgm] = useState(true);
  const [voice, setVoice] = useState('doubao_voice_1');
  const [busy, setBusy] = useState(false);

  useEffect(() => { setProject(projectId); }, [projectId, setProject]);

  const load = async () => {
    try { setTracks(await api.get<AudioAsset[]>(`/api/projects/${projectId}/audio`)); } catch { setTracks([]); }
    try {
      const list = await api.get<Shot[]>(`/api/projects/${projectId}/shots`);
      setShots(list);
      if (!checked.length) setChecked(list.filter((s) => s.dialogue).map((s) => s.id));
    } catch { setShots([]); }
  };
  useEffect(() => { load(); }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = (id: number) =>
    setChecked((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));

  const generate = async () => {
    setBusy(true);
    try {
      await gate.request({
        module: 'audio_tts', projectId, batchCount: Math.max(1, checked.length),
        params: { project_id: projectId, shot_ids: checked, with_bgm: withBgm },
        onDispatched: async () => { await load(); },
        onTaskCreated: async (dispatch) => {
          const taskId = Number(dispatch.task_id ?? 0);
          if (taskId) await waitForTask(taskId, 'audio');
          await load();
        },
      });
    } catch {
      // 任务失败/超时：保留已有音轨
    } finally { setBusy(false); }
  };

  const typeLabel: Record<string, string> = { voice: '对白', bgm: 'BGM', sfx: '音效' };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-[15px]">配音与音效</h1>
        <Badge tone="info">角色绑定固定音色 · 音轨分离</Badge>
      </div>

      <div className="flex gap-4">
        {/* 音色卡 */}
        <Card className="p-4 w-[240px] shrink-0">
          <span className="section-title block mb-3">角色音色</span>
          <div className="space-y-2">
            {VOICES.map((v) => (
              <button key={v.id} onClick={() => setVoice(v.id)}
                className={`w-full text-left card p-3 ${voice === v.id ? '' : 'opacity-70'}`}
                style={voice === v.id ? { borderColor: 'var(--brand-purple)', boxShadow: 'var(--glow-brand)' } : undefined}>
                <div className="flex items-center justify-between">
                  <span className="text-[13px]">{v.name}</span>
                  <span className="text-[11px] text-brand-purple">▶ 试听</span>
                </div>
                <div className="text-tertiary text-[11px] mt-0.5">{v.desc}</div>
              </button>
            ))}
          </div>
          <div className="divider my-3" />
          <label className="flex items-center justify-between text-[12px] text-secondary">
            自动匹配 BGM（按情绪段）
            <input type="checkbox" checked={withBgm} onChange={(e) => setWithBgm(e.target.checked)} className="accent-[var(--brand-teal)]" />
          </label>
        </Card>

        {/* 镜头选择 + 生成 */}
        <div className="flex-1 min-w-0">
          <Card className="p-4 mb-4">
            <div className="flex items-center justify-between mb-3">
              <span className="section-title">选择配音镜头（{checked.length} 个）</span>
              <Button onClick={generate} disabled={busy || checked.length === 0}>
                {busy ? <Spinner className="h-3.5 w-3.5 inline mr-1" /> : null}生成配音
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {shots.map((s) => (
                <button key={s.id} onClick={() => toggle(s.id)}
                  className={`badge ${checked.includes(s.id) ? 'badge-brand' : ''} ${!s.dialogue ? 'opacity-40' : ''}`}>
                  #{s.shot_no} {s.dialogue ? `「${s.dialogue.slice(0, 8)}…」` : '无对白'}
                </button>
              ))}
              {shots.length === 0 && <p className="text-tertiary text-[12px]">暂无分镜</p>}
            </div>
          </Card>

          {/* 音轨 */}
          <Card className="p-4">
            <span className="section-title block mb-3">音轨时间线</span>
            {tracks.length === 0 && <EmptyState title="暂无音轨" hint="选择镜头后点击「生成配音」" />}
            <div className="space-y-2">
              {tracks.map((t) => (
                <div key={t.id} className="card p-3 flex items-center gap-4">
                  <Badge tone={t.type === 'voice' ? 'brand' : t.type === 'bgm' ? 'success' : 'info'}>
                    {typeLabel[t.type]}
                  </Badge>
                  <span className="num text-[12px] text-tertiary w-16">#{t.id}</span>
                  <span className="num text-[12px] text-tertiary">{t.duration.toFixed(1)}s</span>
                  {t.emotion && <span className="text-[12px] text-secondary">情绪：{t.emotion}</span>}
                  <audio src={assetUrl(t.asset_url)} controls className="h-8 flex-1" preload="none" />
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
