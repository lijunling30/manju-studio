/* 全局确认闸口 hook（5.0.1 ★）：任何 AI 操作统一入口。
   - 发起请求 → 后端生成「结构化复述 + 成本预估」；
   - 闸口放行（bypassed）→ 直接执行；
   - 闸口拦截（draft）→ 弹全局确认卡；确认→执行；修改→重新复述(≤3轮)；放弃→取消(零费用)。 */
import { api, sessionId } from '@/lib/api';
import { useStudioStore } from '@/store/useStudioStore';
import type { AiRequest, GateResponse } from '@/lib/types';

export interface ConfirmGateOptions {
  module: string;
  projectId?: number | null;
  params: Record<string, unknown>;
  batchCount?: number;
  /** 闸口放行或用户确认后的回调（派发任务） */
  onDispatched?: (req: AiRequest) => Promise<void> | void;
  /** 派发响应回调（含 task_id，用于前端轮询任务完成后再刷新） */
  onTaskCreated?: (dispatch: Record<string, unknown>) => Promise<void> | void;
}

function highRisk(req: AiRequest): boolean {
  return req.bypass_reason === 'high_cost_guardrail' || req.bypass_reason === 'batch_guardrail';
}

export function useConfirmGate() {
  const openConfirmCard = useStudioStore((s) => s.openConfirmCard);
  const closeConfirmCard = useStudioStore((s) => s.closeConfirmCard);

  async function openForRequest(req: AiRequest, opts: ConfirmGateOptions) {
    openConfirmCard({
      reqId: req.id,
      module: opts.module,
      intent: req.intent,
      outputDesc: req.output_desc,
      costEstimate: req.cost_estimate,
      params: opts.params,
      batchCount: opts.batchCount ?? 1,
      projectId: opts.projectId,
      highRisk: highRisk(req),
      confirmRound: req.confirm_round,
      onConfirm: async () => {
        await api.post(`/api/ai/requests/${req.id}/confirm`);
        const dispatch = await api.post<Record<string, unknown>>(`/api/ai/requests/${req.id}/execute`);
        await opts.onDispatched?.(req);
        await opts.onTaskCreated?.(dispatch);
        closeConfirmCard();
      },
      onReject: async (correction?: string) => {
        await api.post(`/api/ai/requests/${req.id}/reject?correction=${encodeURIComponent(correction ?? '')}`);
        const updated = await api.get<AiRequest>(`/api/ai/requests/${req.id}`);
        if (updated.status === 'cancelled') {
          closeConfirmCard(); // 修改复述达上限 → 转人工
          return;
        }
        openForRequest(updated, opts); // 重新复述后再次弹出
      },
    });
  }

  async function request(opts: ConfirmGateOptions): Promise<AiRequest> {
    const resp = await api.post<GateResponse>('/api/ai/requests', {
      module: opts.module,
      project_id: opts.projectId ?? null,
      params: opts.params,
      batch_count: opts.batchCount ?? 1,
      session_id: sessionId(),
    });
    return fromGateResponse(resp, opts);
  }

  /** 直接处理已返回的闸口响应（如导出接口自带闸口的场景） */
  async function fromGateResponse(resp: GateResponse, opts: ConfirmGateOptions): Promise<AiRequest> {
    if (resp.execute_now) {
      await opts.onDispatched?.(resp.ai_request);
      await opts.onTaskCreated?.(resp.dispatch ?? {});
      return resp.ai_request;
    }
    openForRequest(resp.ai_request, opts);
    return resp.ai_request;
  }

  /** 直接执行（业务模块内已完成闸口确认时） */
  async function execute(reqId: number): Promise<unknown> {
    return api.post(`/api/ai/requests/${reqId}/execute`);
  }

  return { request, fromGateResponse, execute };
}
