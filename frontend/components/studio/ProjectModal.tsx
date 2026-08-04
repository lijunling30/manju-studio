/* 项目新建/编辑弹窗（M1）：名称/题材/风格/平台/预算/描述 */
'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { Button } from '@/components/ui';
import type { Project } from '@/lib/types';

const GENRES = ['都市', '玄幻', '末世', '古言', '悬疑', '科幻', '言情', '仙侠'];
const STYLES = ['漫镜·末世废土风', '赛博朋克', '国漫水墨', '日漫热血', '写实电影感'];
const PLATFORMS = [
  ['douyin_9_16', '抖音竖屏 9:16'],
  ['douyin_4_3', '抖音横屏 4:3'],
  ['bilibili_16_9', 'B站 16:9'],
  ['bilibili_4_3', 'B站 4:3'],
];

const EMPTY = { name: '', genre: '都市', style_name: STYLES[0], target_platform: 'douyin_9_16', budget_limit: 500, description: '' };

export default function ProjectModal({
  open, mode, project, onClose, onSaved,
}: {
  open: boolean;
  mode: 'create' | 'edit';
  project?: Project | null;
  onClose: () => void;
  onSaved: (p: Project) => void;
}) {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setError('');
    setForm(project
      ? {
          name: project.name, genre: project.genre || '都市',
          style_name: project.style_name || STYLES[0],
          target_platform: project.target_platform || 'douyin_9_16',
          budget_limit: project.budget_limit || 0,
          description: project.description || '',
        }
      : EMPTY);
  }, [open, project]);

  if (!open) return null;

  const set = (k: keyof typeof EMPTY, v: string | number) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    if (!form.name.trim()) { setError('项目名称不能为空'); return; }
    setSaving(true);
    setError('');
    try {
      const payload = { ...form, budget_limit: Number(form.budget_limit) || 0 };
      const p = mode === 'create'
        ? await api.post<Project>('/api/projects', payload)
        : await api.put<Project>(`/api/projects/${project!.id}`, payload);
      onSaved(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败');
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div className="card w-[440px] max-w-[92vw] p-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <span className="section-title">{mode === 'create' ? '新建项目' : '编辑项目'}</span>
          <button className="text-tertiary hover:text-primary text-[16px] leading-none" onClick={onClose}>×</button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-[12px] text-tertiary mb-1">项目名称 *</label>
            <input className="input w-full" value={form.name} placeholder="例如：废土求生" maxLength={40}
              onChange={(e) => set('name', e.target.value)} autoFocus />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[12px] text-tertiary mb-1">题材</label>
              <select className="select w-full" value={form.genre} onChange={(e) => set('genre', e.target.value)}>
                {GENRES.map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-[12px] text-tertiary mb-1">美术风格</label>
              <select className="select w-full" value={form.style_name} onChange={(e) => set('style_name', e.target.value)}>
                {STYLES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[12px] text-tertiary mb-1">目标平台</label>
              <select className="select w-full" value={form.target_platform} onChange={(e) => set('target_platform', e.target.value)}>
                {PLATFORMS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-[12px] text-tertiary mb-1">预算上限（元）</label>
              <input className="input w-full" type="number" min={0} value={form.budget_limit}
                onChange={(e) => set('budget_limit', e.target.value)} />
            </div>
          </div>
          <div>
            <label className="block text-[12px] text-tertiary mb-1">项目描述</label>
            <textarea className="input w-full h-16 resize-none" value={form.description} maxLength={200}
              placeholder="一句话剧情梗概…" onChange={(e) => set('description', e.target.value)} />
          </div>
          {error && <p className="text-[12px]" style={{ color: 'var(--danger, #E5484D)' }}>{error}</p>}
        </div>

        <div className="flex justify-end gap-2 mt-5">
          <Button variant="ghost" onClick={onClose} disabled={saving}>取消</Button>
          <Button onClick={save} disabled={saving}>{saving ? '保存中…' : mode === 'create' ? '创建' : '保存'}</Button>
        </div>
      </div>
    </div>
  );
}
