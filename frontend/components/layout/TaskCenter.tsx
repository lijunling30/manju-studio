/* 全局任务中心（P-12）：顶部悬浮，滚动收纳为胶囊 */
'use client';

import { useEffect } from 'react';
import { useTaskStore } from '@/store/useTaskStore';
import { Badge, ProgressBar, Spinner, statusTone } from '@/components/ui';

const KIND_LABEL: Record<string, string> = {
  novel_generate: '小说生成', script: '剧本结构化', shot: '分镜设计', character: '角色资产',
  keyframe_batch: '关键帧抽卡', video: '视频生成', audio: '配音音效', render: '剪辑合成',
  compliance: '合规检验',
};

export default function TaskCenter() {
  const { tasks, refresh } = useTaskStore();

  useEffect(() => {
    const stop = useTaskStore.getState().startPolling();
    return stop;
  }, []);

  const running = tasks.filter((t) => ['queued', 'running', 'retrying'].includes(t.status));
  const failed = tasks.filter((t) => ['failed', 'manual_review'].includes(t.status));

  return (
    <div className="flex items-center gap-2">
      {/* 闸口状态徽章占位：由右侧面板/设置页控制 */}
      {running.length > 0 && (
        <button
          className="glass rounded-pill px-3 py-1.5 flex items-center gap-2 hover:border-strong"
          onClick={refresh}
          title="刷新任务"
        >
          <Spinner className="h-3.5 w-3.5 text-brand-purple" />
          <span className="num text-[12px]">{running.length} 个任务进行中</span>
        </button>
      )}
      {failed.length > 0 && (
        <button className="rounded-pill px-3 py-1.5 flex items-center gap-2 badge badge-warning" onClick={refresh}>
          <span className="num text-[12px]">{failed.length} 个任务需处理</span>
        </button>
      )}
      {running.length === 0 && failed.length === 0 && tasks.length === 0 && (
        <span className="text-tertiary text-[12px]">暂无任务</span>
      )}
    </div>
  );
}

/** 任务抽屉：完整任务列表（可嵌入页面） */
export function TaskList() {
  const tasks = useTaskStore((s) => s.tasks);
  return (
    <div className="space-y-2">
      {tasks.length === 0 && <p className="text-tertiary text-[12px]">暂无任务记录</p>}
      {tasks.map((t) => (
        <div key={`${t.kind}-${t.id}`} className="card p-3">
          <div className="flex items-center justify-between">
            <span className="text-[13px]">{KIND_LABEL[t.kind] ?? t.module}</span>
            <Badge tone={statusTone(t.status)}>{t.status}</Badge>
          </div>
          <div className="mt-2">
            <ProgressBar percent={t.progress} />
          </div>
          <div className="flex items-center justify-between mt-1.5 text-[11px] text-tertiary">
            <span className="num">#{t.id}</span>
            {t.vendor && <span>{t.vendor}</span>}
            {t.error && <span className="text-danger truncate max-w-[180px]">{t.error}</span>}
            {t.retry_count > 0 && <span className="num">重试 {t.retry_count}/{t.max_retries}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}
