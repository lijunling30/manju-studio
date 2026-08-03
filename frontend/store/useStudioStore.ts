/* 全局工作台状态：当前项目 / 流程 / 闸口开关 / 主题 / 确认卡 */
import { create } from 'zustand';
import type { GateResponse } from '@/lib/types';

export type ThemeMode = 'dark' | 'light' | 'system';

/** 确认卡内容（P-11 全局浮层，由 useConfirmGate 弹起） */
export interface ConfirmPayload {
  reqId: number;
  module: string;
  intent: string;
  outputDesc: string;
  costEstimate: { low: number; high: number; currency: string; breakdown?: unknown };
  params: Record<string, unknown>;
  batchCount: number;
  projectId?: number | null;
  highRisk: boolean; // 高成本(≥50元)或批量(≥20)强制确认
  confirmRound: number;
  onConfirm: () => void | Promise<void>;
  onReject?: (correction?: string) => void | Promise<void>;
}

interface StudioState {
  projectId: number | null;
  theme: ThemeMode;
  gateEnabled: boolean;
  confirmCard: ConfirmPayload | null;
  setProject: (id: number | null) => void;
  setTheme: (t: ThemeMode) => void;
  setGateEnabled: (v: boolean) => void;
  openConfirmCard: (p: ConfirmPayload) => void;
  closeConfirmCard: () => void;
}

function applyTheme(mode: ThemeMode) {
  if (typeof window === 'undefined') return;
  const mq = window.matchMedia('(prefers-color-scheme: light)');
  const resolved = mode === 'system' ? (mq.matches ? 'light' : 'dark') : mode;
  document.documentElement.dataset.theme = resolved;
  try {
    localStorage.setItem('manju_theme', mode);
  } catch { /* 隐私模式忽略 */ }
}

const initialTheme: ThemeMode =
  typeof window === 'undefined' ? 'dark' : (localStorage.getItem('manju_theme') as ThemeMode) || 'dark';

export const useStudioStore = create<StudioState>((set) => ({
  projectId: null,
  theme: initialTheme,
  gateEnabled: true,
  confirmCard: null,
  setProject: (id) => set({ projectId: id }),
  setTheme: (t) => {
    applyTheme(t);
    set({ theme: t });
  },
  setGateEnabled: (v) => set({ gateEnabled: v }),
  openConfirmCard: (p) => set({ confirmCard: p }),
  closeConfirmCard: () => set({ confirmCard: null }),
}));

// 初始化主题（SSR 安全）
if (typeof window !== 'undefined') applyTheme(initialTheme);

/** 判断闸口是否需要确认（供各模块发起前调用） */
export function needsConfirm(resp: GateResponse): boolean {
  return resp.execute_now === false;
}
