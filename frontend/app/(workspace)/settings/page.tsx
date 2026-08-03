/* 设置页（P-14）：主题 / 确认闸口三级开关 / 快捷键 / 账号 */
'use client';

import { useEffect, useState } from 'react';
import { api, clearToken, sessionId } from '@/lib/api';
import { useStudioStore, type ThemeMode } from '@/store/useStudioStore';
import { Badge, Button, Card } from '@/components/ui';
import type { GateSetting, User } from '@/lib/types';

const MODULES = [
  { key: 'novel', label: '小说生成' },
  { key: 'script', label: '剧本结构化' },
  { key: 'shot', label: '分镜设计' },
  { key: 'character', label: '角色形象' },
  { key: 'keyframe', label: '关键帧抽卡' },
  { key: 'video', label: '视频生成' },
  { key: 'audio_tts', label: '配音音效' },
  { key: 'render', label: '剪辑合成' },
  { key: 'compliance', label: '合规检验' },
];

export default function SettingsPage() {
  const theme = useStudioStore((s) => s.theme);
  const setTheme = useStudioStore((s) => s.setTheme);
  const [gate, setGate] = useState<GateSetting | null>(null);
  const [me, setMe] = useState<User | null>(null);

  useEffect(() => {
    api.get<GateSetting>(`/api/ai/settings/gate?session_id=${sessionId()}`).then(setGate).catch(() => {});
    api.get<User>('/api/auth/me').then(setMe).catch(() => {});
  }, []);

  const saveGate = async (patch: Partial<GateSetting>) => {
    const g = await api.put<GateSetting>('/api/ai/settings/gate', patch, `session_id=${sessionId()}`);
    setGate(g);
  };

  const toggleModule = async (key: string) => {
    if (!gate) return;
    const cur = gate.modules_disabled ?? [];
    const next = cur.includes(key) ? cur.filter((m) => m !== key) : [...cur, key];
    await saveGate({ modules_disabled: next });
  };

  const themes: { key: ThemeMode; label: string; desc: string }[] = [
    { key: 'dark', label: '影院级深色', desc: '默认 · 深邃太空蓝黑' },
    { key: 'light', label: '亮色', desc: '纸面清爽 · 跟随设计 Token' },
    { key: 'system', label: '跟随系统', desc: '自动适配系统偏好' },
  ];

  const logout = () => {
    clearToken();
    window.location.href = '/login';
  };

  return (
    <div className="p-6 space-y-4 max-w-[760px]">
      <h1 className="text-[15px]">设置</h1>

      {/* 主题 */}
      <Card className="p-4">
        <span className="section-title block mb-3">主题</span>
        <div className="flex gap-3">
          {themes.map((t) => (
            <button key={t.key} onClick={() => setTheme(t.key)}
              className={`card p-3 flex-1 text-left ${theme === t.key ? '' : 'opacity-70'}`}
              style={theme === t.key ? { borderColor: 'var(--brand-purple)', boxShadow: 'var(--glow-brand)' } : undefined}>
              <div className="text-[13px] font-medium">{t.label}</div>
              <div className="text-tertiary text-[11px] mt-1">{t.desc}</div>
            </button>
          ))}
        </div>
      </Card>

      {/* 确认闸口（5.0.1 三级开关） */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <span className="section-title block">确认闸口（5.0.1）</span>
            <p className="text-tertiary text-[11px] mt-1">AI 请求先复述需求与成本预估，经你确认后才执行；未确认零计费</p>
          </div>
          <button role="switch" aria-checked={gate?.global_enabled ?? true}
            onClick={() => saveGate({ global_enabled: !(gate?.global_enabled ?? true) })}
            className="h-6 w-11 rounded-pill relative transition-colors"
            style={{ background: gate?.global_enabled ? 'var(--brand-teal)' : 'var(--bg-elevated)', border: '1px solid var(--border-strong)' }}>
            <span className="absolute top-0.5 h-4.5 w-4.5 rounded-pill bg-white transition-transform"
              style={{ width: 18, height: 18, transform: gate?.global_enabled ? 'translateX(22px)' : 'translateX(2px)' }} />
          </button>
        </div>

        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="card p-3">
            <div className="text-[13px]">{gate?.session_disabled ? '已关闭' : '已开启'}</div>
            <div className="text-tertiary text-[11px] mt-0.5">会话级（当前浏览器）</div>
          </div>
          <div className="card p-3">
            <div className="text-[13px]">{(gate?.modules_disabled ?? []).length ? `${gate!.modules_disabled.length} 个模块关闭` : '全部开启'}</div>
            <div className="text-tertiary text-[11px] mt-0.5">模块级</div>
          </div>
          <div className="card p-3">
            <div className="text-[13px]">{gate?.global_enabled ? '已开启' : '已关闭'}</div>
            <div className="text-tertiary text-[11px] mt-0.5">全局</div>
          </div>
        </div>

        <span className="section-title block mb-2">模块级关闭</span>
        <div className="flex flex-wrap gap-2">
          {MODULES.map((m) => {
            const off = gate?.modules_disabled?.includes(m.key) ?? false;
            return (
              <button key={m.key} onClick={() => toggleModule(m.key)}
                className={`badge ${off ? 'badge-danger' : 'badge-success'}`}>
                {m.label} {off ? '已关' : '开'}
              </button>
            );
          })}
        </div>

        <div className="divider my-4" />
        <div className="flex items-center gap-4 text-[12px] text-secondary">
          <span>高成本护栏：≥ {gate?.high_cost_threshold ?? 50} 元强制确认</span>
          <span>批量护栏：≥ {gate?.batch_threshold ?? 20} 镜头强制确认</span>
        </div>
      </Card>

      {/* 快捷键 */}
      <Card className="p-4">
        <span className="section-title block mb-3">快捷键</span>
        <div className="grid grid-cols-2 gap-2 text-[12px]">
          {[
            ['Ctrl + S', '保存当前工作'],
            ['Ctrl + Enter', '触发 AI 生成（过闸口）'],
            ['Ctrl + Z', '撤销'],
            ['G', '闸口开关（当前会话）'],
          ].map(([k, d]) => (
            <div key={k} className="card p-2.5 flex items-center justify-between">
              <span className="num">{k}</span><span className="text-tertiary">{d}</span>
            </div>
          ))}
        </div>
      </Card>

      {/* 账号 */}
      <Card className="p-4 flex items-center justify-between">
        <div>
          <div className="text-[13px]">账号：{me?.username ?? '—'}</div>
          <div className="text-tertiary text-[11px] mt-0.5">套餐 {me?.plan ?? 'free'} · 个人预算 ¥{me?.budget_limit ?? 0}</div>
        </div>
        <Button variant="danger" onClick={logout}>退出登录</Button>
      </Card>

      <Badge tone="info">所有导出成片强制携带 AI 生成标识（合规底线，无开关）</Badge>
    </div>
  );
}
