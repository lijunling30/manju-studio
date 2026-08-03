"""模拟图像厂商（通义万相 / 即梦）：用 Pillow 生成「镜头感」品牌渐变图像。

生成内容：
- 角色三视图参考图（正面/侧面/背面）
- 角色表情集（喜怒哀乐）
- 分镜关键帧（镜头信息 + 中文画面提示词摘要）
"""
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ...config import settings
from ...storage import save_bytes

_WIDTH, _HEIGHT = 720, 960
_BRAND_TOP = (15, 18, 38)       # 深底
_BRAND_MID = (88, 80, 170)      # 镜光紫
_BRAND_BOTTOM = (29, 158, 117)  # 电光青

_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
]
_font_cache: dict[int, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}


def _font(size: int):
    if size not in _font_cache:
        for p in _FONT_CANDIDATES:
            try:
                _font_cache[size] = ImageFont.truetype(p, size)
                return _font_cache[size]
            except Exception:
                continue
        _font_cache[size] = ImageFont.load_default(size)
    return _font_cache[size]


def _gradient(size, palette):
    w, h = size
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    top, mid, bottom = palette
    for y in range(h):
        t = y / h
        if t < 0.5:
            k = t / 0.5
            c = tuple(int(top[i] + (mid[i] - top[i]) * k) for i in range(3))
        else:
            k = (t - 0.5) / 0.5
            c = tuple(int(mid[i] + (bottom[i] - mid[i]) * k) for i in range(3))
        draw.line([(0, y), (w, y)], fill=c)
    return img


def _decorate(img: Image.Image, seed: int):
    """加光晕 + 取景框网格，制造「镜头」质感。"""
    w, h = img.size
    rnd = random.Random(seed)
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = rnd.randint(w // 3, w * 2 // 3), rnd.randint(h // 3, h * 2 // 3)
    gd.ellipse([cx - 240, cy - 240, cx + 240, cy + 240], fill=(150, 140, 255, 26))
    gd.ellipse([cx - 120, cy - 120, cx + 120, cy + 120], fill=(60, 220, 180, 22))
    img.paste(Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB"), (0, 0))

    draw = ImageDraw.Draw(img, "RGBA")
    for x in range(0, w, w // 6):
        draw.line([(x, 0), (x, h)], fill=(242, 244, 255, 10))
    for y in range(0, h, h // 8):
        draw.line([(0, y), (w, y)], fill=(242, 244, 255, 10))
    # 取景框（三分线）
    draw.rectangle([(w // 3, h // 3), (w * 2 // 3, h * 2 // 3)], outline=(242, 244, 255, 36), width=1)
    return img


def _text_block(draw, size, lines, xy, fill, anchor="lm"):
    y = xy[1]
    for line, fsize, bold in lines:
        draw.text((size[0] / 2 if anchor == "mm" else xy[0], y), line,
                  font=_font(fsize), fill=fill, anchor=anchor)
        y += fsize * 1.7


def _frame(title: str, sub: str, tag: str, seed: int) -> bytes:
    palette = (tuple(_BRAND_TOP), tuple(_BRAND_MID), tuple(_BRAND_BOTTOM))
    img = _gradient((_WIDTH, _HEIGHT), palette)
    img = _decorate(img, seed)
    draw = ImageDraw.Draw(img, "RGBA")
    # 顶部品牌条
    draw.rectangle([(0, 0), (_WIDTH, 14)], fill=(255, 255, 255, 60))
    draw.rectangle([(0, 0), (220, 14)], fill=(123, 119, 221, 200))
    draw.text((28, _HEIGHT - 60), tag, font=_font(30), fill=(255, 255, 255, 200))
    # 主体文字
    _text_block(draw, (_WIDTH, 0), [(title, 56, True)], (_WIDTH, _HEIGHT // 2), fill=(242, 244, 255, 255))
    sub_lines = [(sub, 24, False)]
    draw.multiline_text((_WIDTH / 2, _HEIGHT // 2 + 60), sub, font=_font(24),
                        fill=(200, 208, 240, 230), anchor="ma", align="center")
    return img


def _png_bytes(img: Image.Image) -> bytes:
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------- 对外 API ----------
def generate_character_ref(character_name: str, appearance: str, seed: int) -> str:
    img = _frame(character_name, appearance[:28] + ("…" if len(appearance) > 28 else ""),
                 "角色参考图 · 正/侧/背", seed)
    return save_bytes(_png_bytes(img), "images", ".png")


def generate_expression(character_name: str, emotion: str, seed: int) -> str:
    palette = {
        "喜": (29, 158, 117), "怒": (163, 45, 45), "哀": (59, 109, 17),
        "乐": (55, 138, 221), "惊": (123, 119, 221),
    }.get(emotion, (123, 119, 221))
    img = _frame(f"{character_name} · {emotion}", f"表情：{emotion}（情绪强度高）",
                 f"表情集 {emotion}", seed)
    return save_bytes(_png_bytes(img), "images", ".png")


def generate_keyframe(shot_no: int, scene_desc: str, prompt_zh: str, char_names: list[str],
                      seed: int, round_no: int) -> str:
    chars = "、".join(char_names[:3]) or "无角色"
    img = _frame(f"镜头 #{shot_no}", f"角色：{chars}", f"关键帧 · 第{round_no}轮", seed)
    return save_bytes(_png_bytes(img), "images", ".png")


def generate_scene_image(scene_desc: str, seed: int) -> str:
    img = _frame("场景资产", scene_desc[:30], "场景", seed)
    return save_bytes(_png_bytes(img), "images", ".png")
