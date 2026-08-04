/* 确认卡（P-11 全局浮层 · 玻璃拟态）——5.0.1 闸口交互：
   意图复述 / 参数摘要 / 成本预估 / 操作（确认/修改/放弃）
   + 60s 超时自动取消、本次会话不再确认开关、高成本护栏警示条 */
'use client';

import { useEffect, useRef, useState } from 'react';
import { api, sessionId } from '@/lib/api';
import { useStudioStore } from '@/store/useStudioStore';
import { Button } from '@/components/ui';

export default function ConfirmCard() {
  const payload = useStudioStore((s) => s.confirmCard);
  const close = useStudioStore((s) => s.closeConfirmCard);
  const [correction, setCorrection] = useState('');
  const [editing, setEditing] = useState(false);
  const [sessionOff, setSessionOff] = useState(false);
  const [left, setLeft] = useState(60);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 60s 未操作自动取消（5.0.1：不产生费用）
  useEffect(() => {
    if (!payload) return;
    setLeft(60);
    setCorrection('');
    setEditing(false);
    setSubmitting(false);
    setError('');
    timerRef.current = setInterval(() => {
      setLeft((t) => {
        if (t <= 1) {
          if (timerRef.current) clearInterval(timerRef.current);
          api.post(`/api/ai/requests/${payload.reqId}/cancel`).catch(() => {});
          close();
          return 0;
        }
        return t - 1;
      });
    }, 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [payload?.reqId, close]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!payload) return null;
  const { high, low, currency } = payload.costEstimate;
  const isHighRisk = payload.highRisk || high >= 50;

  const onCancel = async () => {
    await api.post(`/api/ai/requests/${payload.reqId}/cancel`).catch(() => {});
    close();
  };

  /** 确认执行：防重复点击 + 错误捕获（execute 失败时卡片不关闭，显示错误） */
  const onConfirmClick = async () => {
    if (submitting) return;
    setSubmitting(true);
    setError('');
    try {
      await payload.onConfirm();
      // onConfirm 成功时会 closeConfirmCard → 组件卸载，无需重置 submitting
    } catch (e) {
      setError(e instanceof Error ? e.message : '执行失败，请重试');
      setSubmitting(false);
    }
  };

  const onSessionOff = async (v: boolean) => {
    setSessionOff(v);
    await api.put('/api/ai/settings/gate', { session_disabled: v }, `session_id=${sessionId()}`).catch(() => {});
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" style={{ animation: 'fadeIn 200ms ease' }} onClick={onCancel} />
      <div className="glass relative w-[520px] max-w-[92vw] rounded-lg p-6" style={{ animation: 'springPop 300ms var(--ease-spring)' }}>
        {isHighRisk && (
          <div className="badge badge-warning mb-3">
            大额任务 · 单次预估 {currency} {high.toFixed(2)} 元{payload.batchCount >= 20 && ` · 批量 ${payload.batchCount} 镜头`}，即使关闭闸口仍须确认
          </div>
        )}

        <div className="flex items-center justify-between mb-1">
          <h1 className="text-[15px]">确认 AI 操作</h1>
          <span className="num text-tertiary text-[11px]">{left}s 后自动取消</span>
        </div>

        {/* 意图复述 */}
        <p className="text-[14px] text-primary leading-relaxed">{payload.intent}</p>
        <p className="text-tertiary text-[12px] mt-1">{payload.outputDesc}</p>

        {/* 成本预估 */}
        <div className="card mt-4 p-4 flex items-center justify-between">
          <span className="section-title">预估成本</span>
          <div className="text-right">
            <span className="num text-[20px] font-semibold" style={{ background: 'var(--brand-gradient)', WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' }}>
              {currency} {low.toFixed(2)} ~ {high.toFixed(2)}
            </span>
            <div className="text-tertiary text-[11px] mt-0.5">
              {payload.costEstimate.breakdown
                ? `${String((payload.costEstimate.breakdown as { dimension: string }).dimension)} × ${String((payload.costEstimate.breakdown as { quantity: number }).quantity)} @ ${String((payload.costEstimate.breakdown as { unit_price: number }).unit_price)}`
                : null}
            </div>
          </div>
        </div>

        {/* 修改复述 */}
        {editing ? (
          <div className="mt-4">
            <textarea
              className="input min-h-[72px]"
              placeholder="输入修改意见，AI 将重新复述需求（最多 3 轮）"
              value={correction}
              onChange={(e) => setCorrection(e.target.value)}
            />
            <div className="flex gap-2 mt-2">
              <Button variant="ghost" onClick={() => setEditing(false)}>返回</Button>
              <Button onClick={() => payload.onReject?.(correction)} disabled={!correction.trim()}>
                重新复述
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex gap-2 mt-4">
            <Button variant="ghost" onClick={() => setEditing(true)} disabled={submitting}>修改</Button>
            <Button variant="ghost" onClick={onCancel} disabled={submitting}>放弃</Button>
            <div className="flex-1" />
            <Button onClick={onConfirmClick} disabled={submitting}>
              {submitting ? '执行中…' : '确认执行'}
            </Button>
          </div>
        )}

        {/* 执行错误反馈（execute 失败时卡片不关闭，显示错误供用户重试或放弃） */}
        {error && (
          <div className="mt-3 p-2 rounded-sm text-[12px]" style={{ background: 'rgba(229,72,77,0.1)', color: 'var(--danger, #E5484D)' }}>
            {error}
          </div>
        )}

        {/* 会话级闸口开关（5.0.1） */}
        <div className="divider mt-4 pt-3 flex items-center justify-between">
          <span className="text-tertiary text-[12px]">本次会话不再确认（刷新后恢复）</span>
          <button
            role="switch"
            aria-checked={sessionOff}
            onClick={() => onSessionOff(!sessionOff)}
            className="h-5 w-9 rounded-pill relative transition-colors"
            style={{ background: sessionOff ? 'var(--brand-teal)' : 'var(--bg-elevated)', border: '1px solid var(--border-strong)' }}
          >
            <span
              className="absolute top-0.5 h-3.5 w-3.5 rounded-pill bg-white transition-transform"
              style={{ transform: sessionOff ? 'translateX(16px)' : 'translateX(2px)' }}
            />
          </button>
        </div>
      </div>
    </div>
  );
}
