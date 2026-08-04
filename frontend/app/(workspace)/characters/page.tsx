/* 角色资产库（P-05）：两阶段候选抽卡
 * 阶段1：AI 生成 4 张三视图候选 → 用户选择
 * 阶段2：基于选中三视图生成 8 张表情候选 → 用户选 4 张
 * 所有 AI 生成通过 prompt_builder 确保角色/风格一致性
 */
'use client';

import { useEffect, useState } from 'react';
import { api, assetUrl, waitForTask } from '@/lib/api';
import { useStudioStore } from '@/store/useStudioStore';
import { useConfirmGate } from '@/lib/useConfirmGate';
import { Badge, Button, Card, EmptyState, Spinner } from '@/components/ui';
import type { Character, CharacterLibrary, Novel } from '@/lib/types';

const EMOTIONS = ['喜', '怒', '哀', '乐'];

export default function CharactersPage() {
  const projectId = useStudioStore((s) => s.projectId);
  const setProject = useStudioStore((s) => s.setProject);
  const gate = useConfirmGate();
  const [libs, setLibs] = useState<CharacterLibrary[]>([]);
  const [activeLib, setActiveLib] = useState<number | null>(null);
  const [chars, setChars] = useState<Character[]>([]);
  const [novel, setNovel] = useState<Novel | null>(null);
  const [busy, setBusy] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [selected, setSelected] = useState<Character | null>(null);
  const [approving, setApproving] = useState(false);
  const [selectedExprs, setSelectedExprs] = useState<number[]>([]); // 表情抽卡选中索引

  const loadLibs = async () => {
    try {
      const list = await api.get<CharacterLibrary[]>('/api/character-libraries');
      setLibs(list);
      const projLib = list.find((l) => projectId && (l.project_ids || []).includes(projectId));
      setActiveLib((cur) => cur ?? projLib?.id ?? list[0]?.id ?? null);
    } catch { setLibs([]); }
  };

  const loadChars = async () => {
    if (!activeLib) { setChars([]); return; }
    try {
      const list = await api.get<Character[]>(`/api/character-libraries/${activeLib}/characters`);
      setChars(list);
      setSelected((cur) => cur ? list.find((c) => c.id === cur.id) ?? null : null);
    } catch { setChars([]); }
  };

  const loadNovel = async () => {
    if (!projectId) return;
    try {
      const n = await api.get<Novel | null>(`/api/projects/${projectId}/novel`);
      setNovel(n);
    } catch { setNovel(null); }
  };

  useEffect(() => { setProject(projectId); loadLibs(); loadNovel(); }, []); // eslint-disable-line
  useEffect(() => { loadChars(); }, [activeLib]); // eslint-disable-line

  // 打开详情弹窗时初始化已选表情
  useEffect(() => {
    if (selected?.expression_set?.length && selected.expression_candidates?.length) {
      // 从 expression_set 反推选中索引
      const indices: number[] = [];
      selected.expression_set.forEach((url) => {
        const idx = selected.expression_candidates.indexOf(url);
        if (idx >= 0) indices.push(idx);
      });
      setSelectedExprs(indices);
    } else {
      setSelectedExprs([]);
    }
  }, [selected?.id]); // eslint-disable-line

  /** AI 自动生成：从小说提取角色 + 生成三视图候选 */
  const autoGenerate = async () => {
    if (!projectId) return;
    setBusy(true);
    try {
      await gate.request({
        module: 'character', projectId,
        batchCount: novel?.characters?.length || 1,
        params: { auto_generate: true, project_id: projectId, candidate_count: 4 },
        onDispatched: async () => { await loadLibs(); },
        onTaskCreated: async (dispatch) => {
          const libId = Number(dispatch.library_id);
          if (libId) { await loadLibs(); setActiveLib(libId); await loadChars(); }
          const taskIds = (dispatch.task_ids as number[]) || [];
          if (taskIds.length) {
            await Promise.all(taskIds.map((id) => waitForTask(id, 'character').catch(() => {})));
            await loadChars();
          }
        },
      });
    } catch { /* 失败保留 */ } finally { setBusy(false); }
  };

  /** 阶段1：选择三视图 → 触发表情候选生成 */
  const approveRef = async (c: Character, refIndex: number) => {
    setApproving(true);
    try {
      const resp = await api.post<{ task_id: number }>(`/api/characters/${c.id}/approve`,
        { ref_index: refIndex });
      await waitForTask(resp.task_id, 'character_expression').catch(() => {});
      await loadChars();
    } catch { /* 失败保留 */ } finally { setApproving(false); }
  };

  /** 阶段2：确认表情集（从 8 张候选中选 4 张） */
  const approveExpressions = async (c: Character) => {
    if (selectedExprs.length !== 4) return;
    try {
      await api.post(`/api/characters/${c.id}/approve-expressions`, { indices: selectedExprs });
      await loadChars();
    } catch { /* 失败保留 */ }
  };

  /** 切换表情选中状态（最多 4 张，每种情绪建议选 1 张） */
  const toggleExpr = (idx: number) => {
    setSelectedExprs((cur) => {
      if (cur.includes(idx)) return cur.filter((i) => i !== idx);
      if (cur.length >= 4) return cur; // 最多 4 张
      return [...cur, idx];
    });
  };

  /** 重新生成三视图候选 */
  const regenCandidates = async (c: Character) => {
    setBusy(true); setSelected(null);
    try {
      await gate.request({
        module: 'character', projectId,
        params: { character_id: c.id, project_id: projectId, candidate_count: 4 },
        onDispatched: async () => { await loadChars(); },
        onTaskCreated: async (dispatch) => {
          const taskId = Number(dispatch.task_id ?? 0);
          if (taskId) await waitForTask(taskId, 'character');
          await loadChars();
        },
      });
    } catch { /* 失败 */ } finally { setBusy(false); }
  };

  const deleteChar = async (c: Character) => {
    await api.delete(`/api/characters/${c.id}`);
    setDeletingId(null); setSelected(null); await loadChars();
  };

  const hasNovel = novel?.status === 'completed' && (novel.characters?.length ?? 0) > 0;
  const generating = chars.some((c) => !c.ref_images?.length);

  /** 角色状态 */
  const charStatus = (c: Character): { label: string; tone: string } => {
    if (!c.ref_images?.length) return { label: '生成中', tone: 'warning' };
    if (c.approved_ref === null || c.approved_ref === undefined) return { label: '待选三视图', tone: 'info' };
    if (!c.expression_candidates?.length) return { label: '表情生成中', tone: 'brand' };
    if (!c.expression_set?.length) return { label: '待选表情', tone: 'info' };
    return { label: '已完成', tone: 'success' };
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-[15px]">角色资产库</h1>
        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={() => { loadLibs(); loadChars(); }}>刷新</Button>
          <Button onClick={autoGenerate} disabled={busy || !hasNovel}>
            {busy ? <Spinner className="h-3.5 w-3.5 inline mr-1" /> : null}
            AI 自动生成角色
          </Button>
        </div>
      </div>

      {!hasNovel && (
        <Card className="p-3 text-[13px] text-tertiary">
          {novel?.status === 'completed' ? '小说角色表为空' : '请先完成小说生成，AI 将自动从小说角色表提取并生成全部角色资产'}
        </Card>
      )}
      {hasNovel && (
        <Card className="p-3 text-[13px] text-secondary">
          小说《{novel?.title}》包含 {novel?.characters?.length} 个角色：
          {(novel?.characters ?? []).map((c) => c.name).join('、')}。点击「AI 自动生成角色」生成三视图候选，再抽卡选择。
        </Card>
      )}

      <div className="flex gap-4">
        <div className="w-[180px] shrink-0 space-y-1">
          {libs.map((l) => (
            <button key={l.id} onClick={() => setActiveLib(l.id)}
              className={`w-full text-left card px-3 py-2.5 ${activeLib === l.id ? '' : 'opacity-75'}`}
              style={activeLib === l.id ? { boxShadow: 'var(--glow-brand)' } : undefined}>
              <div className="text-[13px] truncate">{l.name}</div>
              <div className="text-tertiary text-[11px] mt-0.5">{l.is_shared ? '共享' : '私有'} · {l.status}</div>
            </button>
          ))}
          {libs.length === 0 && <p className="text-tertiary text-[12px] px-2">暂无子库</p>}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-3">
            <span className="section-title">
              {activeLib ? libs.find((l) => l.id === activeLib)?.name : ''} · {chars.length} 个角色
              {generating && <span className="text-brand-purple ml-2">（生成中…）</span>}
            </span>
          </div>

          {chars.length === 0 && (
            <EmptyState title="暂无角色资产"
              hint={hasNovel ? '点击「AI 自动生成角色」，AI 将生成三视图候选供你选择' : '请先生成小说'} />
          )}

          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {chars.map((c) => {
              const st = charStatus(c);
              const displayImg = c.ref_images?.[c.approved_ref ?? 0] || c.ref_images?.[0];
              return (
                <Card key={c.id} className="p-3 card-hover group relative cursor-pointer" onClick={() => setSelected(c)}>
                  <button className="absolute top-2 right-2 text-tertiary hover:text-danger text-[12px] opacity-0 group-hover:opacity-100 z-10"
                    onClick={(e) => { e.stopPropagation(); if (deletingId === c.id) deleteChar(c); else setDeletingId(c.id); }}>
                    {deletingId === c.id ? '确认?' : '🗑'}
                  </button>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[13px] font-medium">{c.name}</span>
                    <Badge tone={st.tone as 'success'}>{st.label}</Badge>
                  </div>
                  <p className="text-tertiary text-[11px] mb-2 line-clamp-1">{c.appearance || '—'}</p>
                  <div className="aspect-[4/3] rounded-sm border border-subtle overflow-hidden mb-2 bg-elevated/30">
                    {displayImg ? (
                      <img src={assetUrl(displayImg)} alt={c.name} className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center"><Spinner className="h-5 w-5 text-tertiary" /></div>
                    )}
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-tertiary">
                    <span>三视图 {c.ref_images?.length || 0}</span>
                    <span>表情 {c.expression_set?.length || 0}/4</span>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      </div>

      {/* 详情弹窗：两阶段抽卡 */}
      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: 'rgba(0,0,0,0.6)' }}
          onClick={() => { setSelected(null); setDeletingId(null); }}>
          <div className="bg-elevated rounded-sm border border-subtle max-w-3xl w-full max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}>
            {/* 顶部栏 */}
            <div className="flex items-center justify-between p-4 border-b border-subtle sticky top-0 bg-elevated z-10">
              <div className="flex items-center gap-3">
                <span className="text-[16px] font-medium">{selected.name}</span>
                <Badge tone={charStatus(selected).tone as 'success'}>{charStatus(selected).label}</Badge>
              </div>
              <button onClick={() => { setSelected(null); setDeletingId(null); }}
                className="text-tertiary hover:text-primary text-[18px] leading-none">✕</button>
            </div>

            <div className="p-4 space-y-5">
              {/* ===== 阶段1：三视图候选抽卡 ===== */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-tertiary text-[11px] tracking-wider">
                    ① 候选三视图（点击选择最满意的）
                  </span>
                  {selected.approved_ref !== null && selected.approved_ref !== undefined && (
                    <span className="text-brand-purple text-[11px]">✓ 已选择第 {selected.approved_ref + 1} 张</span>
                  )}
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {(selected.ref_images ?? []).length === 0 && (
                    <div className="col-span-4 aspect-square rounded-sm border border-subtle flex items-center justify-center text-tertiary text-[12px]">
                      <Spinner className="h-5 w-5 inline mr-2" /> 三视图生成中…
                    </div>
                  )}
                  {(selected.ref_images ?? []).map((img, i) => {
                    const isApproved = selected.approved_ref === i;
                    return (
                      <button key={i}
                        className={`relative rounded-sm overflow-hidden border-2 transition-all ${
                          isApproved ? 'border-brand-purple' : 'border-subtle hover:border-brand-purple/50'
                        }`}
                        style={isApproved ? { boxShadow: 'var(--glow-brand)' } : undefined}
                        onClick={() => { if (!approving && !isApproved) approveRef(selected, i); }}
                        disabled={approving}>
                        <img src={assetUrl(img)} alt={`三视图 ${i + 1}`} className="w-full aspect-square object-cover" />
                        {isApproved && <span className="absolute top-1 left-1 badge badge-success text-[10px]">✓ 选中</span>}
                        <span className="absolute bottom-1 right-1 badge text-[10px] bg-black/50">#{i + 1}</span>
                      </button>
                    );
                  })}
                </div>
                {approving && (
                  <div className="mt-2 text-center text-[12px] text-brand-purple">
                    <Spinner className="h-3.5 w-3.5 inline mr-1" />正在生成表情候选…
                  </div>
                )}
              </div>

              {/* ===== 阶段2：表情候选抽卡 ===== */}
              {selected.expression_candidates?.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-tertiary text-[11px] tracking-wider">
                      ② 候选表情（选 4 张，{selectedExprs.length}/4 已选）
                    </span>
                    {selectedExprs.length === 4 && !selected.expression_set?.length && (
                      <Button onClick={() => approveExpressions(selected)}>确认表情集</Button>
                    )}
                  </div>
                  <div className="grid grid-cols-4 gap-2">
                    {selected.expression_candidates.map((img, i) => {
                      const isSel = selectedExprs.includes(i);
                      const emotionIdx = Math.floor(i / 2);
                      const variantIdx = i % 2;
                      const isConfirmed = selected.expression_set?.includes(img);
                      return (
                        <button key={i}
                          className={`relative rounded-sm overflow-hidden border-2 transition-all ${
                            isSel || isConfirmed ? 'border-brand-purple' : 'border-subtle hover:border-brand-purple/50'
                          }`}
                          style={isSel || isConfirmed ? { boxShadow: 'var(--glow-brand)' } : undefined}
                          onClick={() => toggleExpr(i)}>
                          <img src={assetUrl(img)} alt={`${EMOTIONS[emotionIdx]} 变体${variantIdx + 1}`}
                            className="w-full aspect-square object-cover" />
                          <span className="absolute bottom-1 left-1 badge text-[10px] bg-black/50">
                            {EMOTIONS[emotionIdx]}·{variantIdx + 1}
                          </span>
                          {isSel && <span className="absolute top-1 left-1 badge badge-success text-[10px]">✓</span>}
                        </button>
                      );
                    })}
                  </div>
                  {selected.expression_set?.length === 4 && (
                    <div className="mt-2 text-[12px] text-brand-purple">✓ 表情集已确认</div>
                  )}
                </div>
              )}

              {/* 角色信息 */}
              <div className="grid grid-cols-2 gap-4 pt-3 border-t border-subtle">
                <div>
                  <div className="text-tertiary text-[11px] tracking-wider mb-1">外貌描述</div>
                  <p className="text-[13px] text-secondary leading-relaxed">{selected.appearance || '—'}</p>
                </div>
                <div>
                  <div className="text-tertiary text-[11px] tracking-wider mb-1">角色定位</div>
                  <p className="text-[13px] text-secondary">{selected.personality || '—'}</p>
                </div>
              </div>

              <div className="flex gap-2 pt-3 border-t border-subtle">
                <Button onClick={() => regenCandidates(selected)} disabled={busy || approving}>
                  {busy ? <Spinner className="h-3.5 w-3.5 inline mr-1" /> : null}重新生成三视图
                </Button>
                <Button variant="ghost"
                  onClick={() => { if (deletingId === selected.id) deleteChar(selected); else setDeletingId(selected.id); }}>
                  {deletingId === selected.id ? '确认删除?' : '删除角色'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
