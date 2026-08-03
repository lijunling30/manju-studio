/* 剪辑台 + 合规检验（P-09 / P-10）：
   多镜头合成成片（强制 AI 标识，无开关）→ 导出（M13 合规检验用户可选） */
'use client';

import { useEffect, useState } from 'react';
import { api, assetUrl } from '@/lib/api';
import { useStudioStore } from '@/store/useStudioStore';
import { useConfirmGate } from '@/lib/useConfirmGate';
import { Badge, Button, Card, EmptyState, Spinner, statusTone } from '@/components/ui';
import type { AuditReport, FinalVideo, GateResponse } from '@/lib/types';

const PLATFORMS = ['douyin_9_16', 'bilibili_16_9', 'wechat_9_16'];

export default function ExportPage({ params }: { params: { id: string } }) {
  const projectId = Number(params.id);
  const setProject = useStudioStore((s) => s.setProject);
  const gate = useConfirmGate();
  const [videos, setVideos] = useState<FinalVideo[]>([]);
  const [reports, setReports] = useState<Record<number, AuditReport[]>>({});
  const [episode, setEpisode] = useState(1);
  const [platforms, setPlatforms] = useState<string[]>(['douyin_9_16', 'bilibili_16_9']);
  const [compliance, setCompliance] = useState<'run' | 'skip'>('run');
  const [busy, setBusy] = useState(false);
  const [polling, setPolling] = useState<string | null>(null);

  useEffect(() => { setProject(projectId); }, [projectId, setProject]);

  const loadVideos = async () => {
    try {
      const list = await api.get<FinalVideo[]>(`/api/projects/${projectId}/final-videos`);
      setVideos(list);
      for (const v of list) {
        if (!reports[v.id]) {
          api.get<AuditReport[]>(`/api/final-videos/${v.id}/audit`)
            .then((r) => setReports((prev) => ({ ...prev, [v.id]: r })))
            .catch(() => {});
        }
      }
      // 追踪渲染中的成片
      const running = list.find((v) => v.status === 'rendering' || v.status === 'draft');
      setPolling(running ? String(running.id) : null);
    } catch { setVideos([]); }
  };

  useEffect(() => { loadVideos(); }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  // 渲染任务轮询
  useEffect(() => {
    if (!polling) return;
    const t = setInterval(loadVideos, 2000);
    return () => clearInterval(t);
  }, [polling]); // eslint-disable-line react-hooks/exhaustive-deps

  const render = async () => {
    setBusy(true);
    try {
      await gate.request({
        module: 'render', projectId,
        params: { project_id: projectId, episode_no: episode },
        onDispatched: async () => { await loadVideos(); },
      });
      await new Promise((r) => setTimeout(r, 1000));
      await loadVideos();
    } finally { setBusy(false); }
  };

  const exportVideo = async (fv: FinalVideo) => {
    setBusy(true);
    try {
      // 导出接口自身处理：设置平台版本 + M13 合规检验（用户可选）→ 返回闸口响应或成片
      const resp = await api.post<GateResponse | FinalVideo>(
        `/api/final-videos/${fv.id}/export`, { compliance, platforms });
      if ('ai_request' in resp) {
        await gate.fromGateResponse(resp, {
          module: 'compliance', projectId,
          params: { final_video_id: fv.id, project_id: projectId },
          onDispatched: async () => { await loadVideos(); },
        });
      } else {
        await loadVideos();
      }
    } finally { setBusy(false); }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-[15px]">剪辑合成 · 合规导出</h1>
        <Badge tone="danger" >AI 生成标识强制携带（无开关）</Badge>
      </div>

      {/* 渲染设置 */}
      <Card className="p-4 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-[12px] text-tertiary">
          集数
          <input className="input w-20" type="number" min={1} value={episode}
            onChange={(e) => setEpisode(Number(e.target.value))} />
        </label>
        <Button onClick={render} disabled={busy}>
          {busy ? <Spinner className="h-3.5 w-3.5 inline mr-1" /> : null}合成成片
        </Button>
        <span className="text-tertiary text-[12px]">自动拼接已成功生成的镜头视频，烧录 AI 标识</span>
      </Card>

      {/* 成片列表 */}
      {videos.length === 0 && <EmptyState title="尚未合成成片" hint="先生成镜头视频，再点击「合成成片」（渲染为异步任务）" />}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
        {videos.map((fv) => (
          <Card key={fv.id} className="p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <span className="text-[14px] font-medium">{fv.title}</span>
                <span className="text-tertiary text-[11px] ml-2">第 {fv.episode_no} 集 · {fv.duration}s</span>
              </div>
              <div className="flex items-center gap-2">
                {fv.status === 'rendering' && <Spinner className="h-3.5 w-3.5 text-brand-purple" />}
                <Badge tone={statusTone(fv.status)}>{fv.status}</Badge>
                {fv.ai_label_burned && <Badge tone="success">AI 标识已烧录</Badge>}
              </div>
            </div>

            {fv.preview_url && (
              <video src={assetUrl(fv.preview_url)} controls className="w-full max-h-[220px] rounded-sm border border-subtle mb-3 bg-black" />
            )}

            {/* 导出设置 */}
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                {PLATFORMS.map((p) => (
                  <button key={p} onClick={() => setPlatforms((cur) =>
                      cur.includes(p) ? cur.filter((x) => x !== p) : [...cur, p])}
                    className={`badge ${platforms.includes(p) ? 'badge-brand' : ''}`}>
                    {p.replace('_', ' ')}
                  </button>
                ))}
              </div>

              {/* M13 合规检验：用户可选 */}
              <div className="flex gap-3">
                {(['run', 'skip'] as const).map((c) => (
                  <button key={c} onClick={() => setCompliance(c)}
                    className={`card px-4 py-2 text-[12px] flex-1 ${compliance === c ? '' : 'opacity-60'}`}
                    style={compliance === c ? { borderColor: 'var(--brand-teal)', boxShadow: 'var(--glow-brand)' } : undefined}>
                    {c === 'run' ? '✓ 执行合规检验（推荐）' : '跳过，仅带 AI 标识'}
                  </button>
                ))}
              </div>
              {compliance === 'skip' && (
                <p className="text-warning text-[11px]">跳过将不进行内容安全审核；AI 生成标识不受影响（合规底线）</p>
              )}

              <div className="flex items-center justify-between">
                <div className="text-[12px] text-tertiary">
                  成本合计：<span className="num">¥{fv.cost_total.toFixed(2)}</span>
                  {reports[fv.id]?.length ? ` · 审核报告 ${reports[fv.id].length} 份` : ''}
                </div>
                <Button onClick={() => exportVideo(fv)} disabled={busy || fv.status !== 'completed'}>
                  导出成片
                </Button>
              </div>

              {/* 审核报告 */}
              {reports[fv.id]?.map((r) => (
                <div key={r.id} className="card p-3 bg-elevated">
                  <div className="flex items-center justify-between">
                    <span className="text-[12px]">审核报告 #{r.id} · {r.vendor}</span>
                    <Badge tone={statusTone(r.status)}>{r.status === 'pass' ? '通过' : '驳回'}</Badge>
                  </div>
                  {r.issues?.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {r.issues.map((it, i) => (
                        <li key={i} className="text-[11px] text-danger">
                          「{it.snippet}」→ {it.reason}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
