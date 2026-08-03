/* 与后端 schemas.py 对齐的 TypeScript 类型 */

export interface AiRequest {
  id: number;
  user_id: number;
  project_id: number | null;
  module: string;
  intent: string;
  params_json: Record<string, unknown>;
  output_desc: string;
  cost_estimate: {
    low: number;
    high: number;
    currency: string;
    breakdown: { dimension: string; vendor: string; unit_price: number; quantity: number };
  };
  status: 'draft' | 'confirmed' | 'rejected' | 'bypassed' | 'timeout' | 'cancelled';
  confirm_round: number;
  bypass_reason?: string;
  confirmed_at?: string | null;
  created_at: string;
}

/** 闸口响应：execute_now=true 且含 dispatch；否则为 draft 待确认 */
export interface GateResponse {
  ai_request: AiRequest;
  execute_now: boolean;
  dispatch?: Record<string, unknown>;
}

export interface User {
  id: number;
  username: string;
  role: string;
  plan: string;
  budget_limit: number;
  gate_setting: {
    global_enabled: boolean;
    modules_disabled: string[];
    high_cost_threshold: number;
    batch_threshold: number;
  };
}

export interface Project {
  id: number;
  name: string;
  genre: string;
  description: string;
  style_id: string;
  style_name: string;
  target_platform: string;
  status: string;
  progress: number;
  budget_limit: number;
  ip_license?: string;
  created_at: string;
}

export interface FlowStep {
  key: string;
  label: string;
  status: 'pending' | 'active' | 'done' | 'blocked';
}

export interface ProjectFlow {
  project_id: number;
  steps: FlowStep[];
}

export interface Novel {
  id: number;
  project_id: number;
  title: string;
  genre: string;
  status: string;
  chapters: { no: number; title: string; content: string }[];
  characters: { name: string; role: string; desc: string }[];
  outline: { no: number; title: string; summary: string }[];
  setting: Record<string, unknown>;
  created_at: string;
}

export interface Script {
  id: number;
  project_id: number;
  novel_id: number;
  title: string;
  status: string;
  scenes: { scene_no: number; location: string; time: string; emotion: string; summary: string; beats: unknown[] }[];
  emotion_curve: { scene_no: number; emotion: string; intensity: number }[];
}

export interface Shot {
  id: number;
  project_id: number;
  script_id: number;
  shot_no: number;
  scene_no: number;
  shot_type: string;
  camera_move: string;
  duration: number;
  prompt_zh: string;
  char_ref_ids: number[];
  style_id: string;
  dialogue: string;
  narration: string;
  transition: string;
  status: string;
}

export interface CharacterLibrary {
  id: number;
  user_id: number;
  name: string;
  desc: string;
  project_ids: number[];
  is_shared: boolean;
  status: string;
}

export interface Character {
  id: number;
  library_id: number;
  name: string;
  appearance: string;
  personality: string;
  desc: string;
  ref_images: string[];
  expression_set: string[];
  voice_id: string;
  lora_version: string;
  status: string;
}

export interface Keyframe {
  id: number;
  shot_id: number;
  project_id: number;
  image_url: string;
  vendor: string;
  model: string;
  score: { composition: number; consistency: number; clarity: number; overall: number };
  is_approved: boolean;
  round: number;
  cost: number;
}

export interface VideoTask {
  id: number;
  shot_id: number;
  project_id: number;
  vendor: string;
  model: string;
  status: 'queued' | 'running' | 'success' | 'failed' | 'retrying' | 'manual_review';
  progress: number;
  result_url: string;
  preview_url: string;
  frames: unknown[];
  cost: number;
  retry_count: number;
  error: string;
  created_at: string;
  updated_at: string;
}

export interface AudioAsset {
  id: number;
  shot_id: number | null;
  project_id: number;
  type: 'voice' | 'bgm' | 'sfx';
  character_id?: number | null;
  asset_url: string;
  duration: number;
  emotion?: string;
  status: string;
}

export interface FinalVideo {
  id: number;
  project_id: number;
  episode_no: number;
  title: string;
  url: string;
  preview_url: string;
  platform_versions: { platform: string; spec: string; url: string; exported?: boolean }[];
  duration: number;
  ai_label_burned: boolean;
  compliance_checked: boolean;
  audit_status: string;
  cost_total: number;
  status: string;
  created_at: string;
}

export interface AuditReport {
  id: number;
  final_video_id: number;
  vendor: string;
  status: 'pass' | 'reject';
  issues: { snippet: string; rule: string; reason: string }[];
  report_url: string;
  created_at: string;
}

export interface TaskItem {
  id: number;
  kind: string;
  module: string;
  ref_id: number;
  project_id: number;
  status: string;
  progress: number;
  retry_count: number;
  max_retries: number;
  error: string;
  vendor: string;
  preview_url: string;
  created_at: string;
  updated_at: string;
}

export interface CostLogItem {
  id: number;
  user_id: number;
  project_id: number;
  module: string;
  vendor: string;
  model: string;
  task_id: number;
  tokens: number;
  duration: number;
  count: number;
  amount: number;
  meta?: Record<string, unknown>;
  created_at: string;
}

export interface CostSummary {
  project_id: number;
  total: number;
  budget_limit: number;
  usage_percent: number;
  warn_80: boolean;
  blocked_100: boolean;
  by_module: Record<string, number>;
  logs: CostLogItem[];
}

export interface Bill {
  user_id: number;
  plan: string;
  total: number;
  items: { project_id: number; project_name: string; total: number; calls: number; created_at: string }[];
}

export interface GateSetting {
  global_enabled: boolean;
  modules_disabled: string[];
  high_cost_threshold: number;
  batch_threshold: number;
  session_disabled: boolean;
}
