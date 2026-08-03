/* 全局任务中心（P-12）：轮询后端 /api/tasks，驱动进度条与状态徽章 */
import { create } from 'zustand';
import { api } from '@/lib/api';
import type { TaskItem } from '@/lib/types';

interface TaskState {
  tasks: TaskItem[];
  loading: boolean;
  refresh: () => Promise<void>;
  startPolling: () => void;
  stopPolling: () => void;
}

export const useTaskStore = create<TaskState>((set, get) => ({
  tasks: [],
  loading: false,
  refresh: async () => {
    try {
      const tasks = await api.get<TaskItem[]>('/api/tasks?limit=20');
      set({ tasks, loading: false });
    } catch {
      set({ loading: false });
    }
  },
  startPolling: () => {
    // 5s 轮询（WebSocket 生产可替换）
    const timer = setInterval(() => get().refresh(), 5000);
    get().refresh();
    return () => clearInterval(timer);
  },
  stopPolling: () => { /* no-op，轮询 timer 由 startPolling 返回的清理函数管理 */ },
}));
