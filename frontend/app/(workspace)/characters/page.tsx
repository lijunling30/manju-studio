/* 角色资产库（P-05）：人物子库导航 + 角色卡片墙 + 三视图/表情集 */
'use client';

import { useEffect, useState } from 'react';
import { api, assetUrl } from '@/lib/api';
import { useStudioStore } from '@/store/useStudioStore';
import { useConfirmGate } from '@/lib/useConfirmGate';
import { Badge, Button, Card, EmptyState, Spinner } from '@/components/ui';
import type { Character, CharacterLibrary } from '@/lib/types';

const EXPRESSIONS = ['喜', '怒', '哀', '乐'];

export default function CharactersPage() {
  const projectId = useStudioStore((s) => s.projectId);
  const setProject = useStudioStore((s) => s.setProject);
  const gate = useConfirmGate();
  const [libs, setLibs] = useState<CharacterLibrary[]>([]);
  const [activeLib, setActiveLib] = useState<number | null>(null);
  const [chars, setChars] = useState<Character[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [appearance, setAppearance] = useState('');
  const [personality, setPersonality] = useState('');
  const [busy, setBusy] = useState(false);

  const loadLibs = async () => {
    try {
      const list = await api.get<CharacterLibrary[]>('/api/character-libraries');
      setLibs(list);
      setActiveLib((cur) => cur ?? list[0]?.id ?? null);
    } catch { setLibs([]); }
  };

  useEffect(() => {
    setProject(projectId);
    loadLibs();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!activeLib) { setChars([]); return; }
    api.get<Character[]>(`/api/character-libraries/${activeLib}/characters`).then(setChars).catch(() => setChars([]));
  }, [activeLib]);

  const createLib = async () => {
    const lib = await api.post<CharacterLibrary>('/api/character-libraries', {
      name: `人物库 ${libs.length + 1}`, project_ids: projectId ? [projectId] : [],
    });
    await loadLibs();
    setActiveLib(lib.id);
  };

  const createChar = async () => {
    if (!activeLib || !name.trim()) return;
    setBusy(true);
    try {
      await gate.request({
        module: 'character', projectId,
        params: { library_id: activeLib, name, appearance, personality, project_id: projectId },
        onDispatched: async () => {
          const list = await api.get<Character[]>(`/api/character-libraries/${activeLib}/characters`);
          setChars(list);
          setShowCreate(false);
          setName(''); setAppearance(''); setPersonality('');
        },
      });
    } finally { setBusy(false); }
  };

  const genImages = async (c: Character) => {
    setBusy(true);
    try {
      await gate.request({
        module: 'character', projectId,
        params: { character_id: c.id, project_id: projectId },
        onDispatched: async () => {
          const list = await api.get<Character[]>(`/api/character-libraries/${activeLib}/characters`);
          setChars(list);
        },
      });
    } finally { setBusy(false); }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-[15px]">角色资产库（人物子库）</h1>
        <Button variant="ghost" onClick={createLib}>+ 新建人物子库</Button>
      </div>

      <div className="flex gap-4">
        {/* 子库导航 */}
        <div className="w-[180px] shrink-0 space-y-1">
          {libs.map((l) => (
            <button key={l.id} onClick={() => setActiveLib(l.id)}
              className={`w-full text-left card px-3 py-2.5 ${activeLib === l.id ? '' : 'opacity-75'}`}
              style={activeLib === l.id ? { boxShadow: 'var(--glow-brand)' } : undefined}>
              <div className="text-[13px] truncate">{l.name}</div>
              <div className="text-tertiary text-[11px] mt-0.5">
                {l.is_shared ? '共享' : '私有'} · {l.status}
              </div>
            </button>
          ))}
          {libs.length === 0 && <p className="text-tertiary text-[12px] px-2">暂无子库</p>}
        </div>

        {/* 角色卡片墙 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-3">
            <span className="section-title">{activeLib ? libs.find((l) => l.id === activeLib)?.name : ''} · {chars.length} 个角色</span>
            <Button onClick={() => setShowCreate(!showCreate)}>+ 创建角色</Button>
          </div>

          {showCreate && (
            <Card className="p-4 mb-4 space-y-3">
              <div className="grid grid-cols-3 gap-3">
                <input className="input" placeholder="角色名（如：陈默）" value={name} onChange={(e) => setName(e.target.value)} />
                <input className="input" placeholder="外貌（如：短发硬朗）" value={appearance} onChange={(e) => setAppearance(e.target.value)} />
                <input className="input" placeholder="性格（如：冷静）" value={personality} onChange={(e) => setPersonality(e.target.value)} />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={() => setShowCreate(false)}>取消</Button>
                <Button onClick={createChar} disabled={busy || !name.trim()}>
                  {busy ? <Spinner className="h-3.5 w-3.5 inline mr-1" /> : null}创建并生成形象
                </Button>
              </div>
            </Card>
          )}

          {chars.length === 0 && !showCreate && (
            <EmptyState title="子库暂无角色" hint="创建角色后自动生成三视图参考图 + 表情集（走确认闸口）" />
          )}

          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {chars.map((c) => (
              <Card key={c.id} className="p-3 card-hover">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[13px] font-medium">{c.name}</span>
                  <Badge tone={c.ref_images?.length ? 'success' : 'warning'}>
                    {c.ref_images?.length ? '形象已生成' : '待生成'}
                  </Badge>
                </div>
                <p className="text-tertiary text-[12px] mb-2 line-clamp-2">{c.appearance} · {c.personality}</p>

                {/* 三视图 */}
                <div className="flex gap-1 mb-2">
                  {(c.ref_images ?? []).map((img, i) => (
                    <img key={i} src={assetUrl(img)} alt={`${c.name} 视图${i + 1}`}
                      className="h-20 flex-1 object-cover rounded-sm border border-subtle" />
                  ))}
                  {!c.ref_images?.length && (
                    <div className="h-20 flex-1 rounded-sm border border-subtle flex items-center justify-center text-tertiary text-[11px]">无参考图</div>
                  )}
                </div>

                {/* 表情集 */}
                <div className="flex gap-1 mb-3">
                  {(c.expression_set ?? []).slice(0, 4).map((img, i) => (
                    <img key={i} src={assetUrl(img)} alt={EXPRESSIONS[i]}
                      className="h-10 flex-1 object-cover rounded-sm border border-subtle" title={EXPRESSIONS[i]} />
                  ))}
                </div>

                <div className="flex items-center justify-between text-[11px] text-tertiary">
                  <span>音色：{c.voice_id || '未绑定'}</span>
                  {c.lora_version && <span>LoRA {c.lora_version}</span>}
                </div>
                {!c.ref_images?.length && (
                  <Button variant="ghost" className="w-full mt-2" onClick={() => genImages(c)} disabled={busy}>
                    生成三视图 + 表情集
                  </Button>
                )}
              </Card>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
