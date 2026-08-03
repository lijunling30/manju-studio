/* 登录 / 注册 / 首屏（P-01）：深色品牌墙 + 表单卡片 */
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, setToken } from '@/lib/api';
import { Button } from '@/components/ui';

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setError('');
    setBusy(true);
    try {
      const path = mode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const res = await api.post<{ access_token: string }>(path, { username, password });
      setToken(res.access_token);
      router.push('/dashboard');
    } catch (e) {
      setError((e as Error).message || '操作失败');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="h-full flex">
      {/* 品牌墙 */}
      <div className="flex-1 relative overflow-hidden hidden md:block" style={{ background: 'var(--bg-base)' }}>
        <div className="absolute inset-0 opacity-60" style={{ background: 'radial-gradient(60% 60% at 20% 20%, rgba(127,119,221,0.35) 0%, transparent 60%), radial-gradient(50% 50% at 85% 75%, rgba(29,158,117,0.3) 0%, transparent 60%)' }} />
        <div className="relative h-full flex flex-col items-center justify-center text-center px-12">
          <h1 className="font-serif text-[40px] font-semibold" style={{ background: 'var(--brand-gradient)', WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' }}>
            漫镜工场
          </h1>
          <p className="text-secondary mt-4 text-[15px] leading-relaxed">
            走进一座 AI 漫剧数字工作室<br />
            小说 · 剧本 · 分镜 · 角色 · 视频 · 成片
          </p>
          <p className="text-tertiary text-[12px] mt-8 tracking-[0.3em]">MANJU STUDIO</p>
        </div>
      </div>

      {/* 表单 */}
      <div className="w-[400px] shrink-0 border-l border-subtle bg-surface flex items-center justify-center p-8">
        <div className="w-full max-w-[300px]">
          <div className="mb-6 flex items-center gap-2 md:hidden">
            <span className="h-8 w-8 rounded-sm flex items-center justify-center text-white" style={{ background: 'var(--brand-gradient)' }}>镜</span>
            <span className="font-serif text-[18px] font-semibold">漫镜工场</span>
          </div>

          <div className="flex rounded-sm p-1 mb-6 border border-subtle">
            {(['login', 'register'] as const).map((m) => (
              <button
                key={m}
                onClick={() => { setMode(m); setError(''); }}
                className={`flex-1 py-1.5 text-[13px] rounded-sm transition-colors ${mode === m ? 'text-white' : 'text-tertiary'}`}
                style={mode === m ? { background: 'var(--brand-gradient)' } : undefined}
              >
                {m === 'login' ? '登录' : '注册'}
              </button>
            ))}
          </div>

          <div className="space-y-3">
            <input className="input" placeholder="用户名" value={username}
              onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
            <input className="input" placeholder="密码" type="password" value={password}
              onChange={(e) => setPassword(e.target.value)} autoComplete="current-password"
              onKeyDown={(e) => e.key === 'Enter' && submit()} />
            {error && <p className="text-danger text-[12px]">{error}</p>}
            <Button className="w-full" disabled={busy || !username || !password} onClick={submit}>
              {busy ? '处理中…' : mode === 'login' ? '进入工作台' : '创建账号'}
            </Button>
          </div>

          <p className="text-tertiary text-[11px] mt-6 leading-relaxed">
            AI 调用均经过确认闸口：先复述需求与成本预估，经你确认后才执行
          </p>
        </div>
      </div>
    </div>
  );
}
