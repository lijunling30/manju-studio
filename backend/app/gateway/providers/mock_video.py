"""模拟视频厂商（Vidu Q3 / 豆包 Seedance / 可灵）。

- 若系统存在 ffmpeg：由关键帧渲染真实 mp4（zoompan 运镜），输出 H.264 竖屏。
- 否则：生成 8 帧关键帧变体（帧序列模式），前端以 Ken Burns 动效预览。

图生视频、首尾帧控制、异步任务语义均由任务编排层模拟（见 tasks/jobs.py）。
"""
import random
import shutil
import subprocess
from pathlib import Path

from ...config import settings
from ...storage import abs_path, save_bytes

FFMPEG = shutil.which("ffmpeg")
_IMAGE_VARIANTS = 8


class VideoGenerationError(Exception):
    pass


def _variant(image: Path, frame_idx: int, total: int, seed: int) -> bytes:
    """对关键帧做亮度/色相/位置微调，生成镜头「运动感」的帧序列。"""
    from PIL import Image, ImageEnhance, ImageFilter
    img = Image.open(image).convert("RGB")
    rnd = random.Random(seed + frame_idx)
    brightness = 0.85 + 0.3 * (frame_idx / max(1, total))
    img = ImageEnhance.Brightness(img).enhance(brightness)
    dx, dy = int(8 * (frame_idx / max(1, total)) - 4), 0
    img = img.transform(img.size, Image.AFFINE, (1, 0, -dx, 0, 1, -dy), resample=Image.BILINEAR)
    img = img.filter(ImageFilter.GaussianBlur(0.3))
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_video(keyframe_rel: str, duration: float, vendor: str, seed: int,
                   fail_times: int = 0, attempt: int = 1) -> dict:
    """返回 {video_url, preview_url, frames, duration, mock}。"""
    if fail_times >= attempt:
        raise VideoGenerationError(f"{vendor} 任务翻车（模拟失败，用于验证重试/降级）")

    src = abs_path(keyframe_rel)
    frames: list[str] = []

    if FFMPEG:
        out_rel = _render_mp4(src, duration, seed)
        return {"video_url": out_rel, "preview_url": keyframe_rel, "frames": [],
                "duration": duration, "mock": False}

    # 帧序列模式（无 ffmpeg）
    for i in range(_IMAGE_VARIANTS):
        frames.append(save_bytes(_variant(src, i, _IMAGE_VARIANTS, seed), "frames", ".png"))
    return {"video_url": "", "preview_url": frames[0], "frames": frames,
            "duration": duration, "mock": True}


def _render_mp4(src: Path, duration: float, seed: int) -> str:
    fps = 25
    d = int(duration)
    out = settings.STORAGE_DIR / "videos" / f"v_{seed}_{int(duration * 10)}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = (f"zoompan=z='min(zoom+0.0012,1.25)':d={fps * d}:s=1080x1920:fps={fps}"
          f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'")
    cmd = [FFMPEG, "-y", "-loop", "1", "-i", str(src), "-vf", vf,
           "-t", str(d), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps), str(out)]
    subprocess.run(cmd, capture_output=True, timeout=120)
    if not out.exists():
        raise VideoGenerationError("ffmpeg 渲染失败")
    return f"/storage/videos/{out.name}"
