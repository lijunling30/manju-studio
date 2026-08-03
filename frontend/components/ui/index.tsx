/* 基础 UI 原语（基于设计 Token，深色默认） */
import React from 'react';

export function Button({
  variant = 'brand',
  className = '',
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'brand' | 'ghost' | 'danger' }) {
  const cls =
    variant === 'brand' ? 'btn-brand' : variant === 'danger' ? 'btn-danger' : 'btn-ghost';
  return <button className={`${cls} ${className}`} {...props} />;
}

export function Card({
  className = '',
  style,
  children,
}: {
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
}) {
  return (
    <div className={`card ${className}`} style={style}>
      {children}
    </div>
  );
}

export type BadgeTone = 'success' | 'warning' | 'danger' | 'info' | 'brand' | 'default';

export function Badge({ tone = 'default', children }: { tone?: BadgeTone; children: React.ReactNode }) {
  const cls = tone === 'default' ? '' : `badge-${tone}`;
  return <span className={`badge ${cls}`}>{children}</span>;
}

/** 状态 → 徽章色调（任务/成片状态机 6.2） */
export function statusTone(status: string): BadgeTone {
  switch (status) {
    case 'success': case 'completed': case 'done': case 'pass': case 'bypassed': case 'confirmed':
      return 'success';
    case 'running': case 'queued': case 'retrying': case 'rendering': case 'generating':
      return 'info';
    case 'failed': case 'reject': case 'rejected': case 'cancelled': case 'timeout':
      return 'danger';
    case 'manual_review': case 'draft':
      return 'warning';
    default:
      return 'default';
  }
}

export function Spinner({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function ProgressBar({ percent }: { percent: number }) {
  return (
    <div className="progress-track">
      <div className="progress-bar" style={{ width: `${Math.min(100, Math.max(0, percent))}%` }} />
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="h-16 w-16 rounded-lg mb-4 bg-elevated border border-subtle flex items-center justify-center text-2xl">
        🎬
      </div>
      <p className="text-secondary">{title}</p>
      {hint && <p className="text-tertiary text-[11px] mt-1">{hint}</p>}
    </div>
  );
}
