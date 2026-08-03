"""模拟音频厂商（火山豆包 TTS / 天工 SkyMusic / 音效库）。

用 stdlib wave 生成可播放的 WAV：配音=音色正弦波+颤音；BGM=情绪和弦；
音效=白噪声脉冲。浏览器可直接播放，用于演示「音轨分离/试听」。
"""
import math
import random
import wave

from ...storage import save_bytes

_SAMPLE_RATE = 22050
_VOICE_BASE = {"doubao_voice_1": 220, "doubao_voice_2": 174, "doubao_voice_3": 262, "default": 196}


def _write_wav(samples: list[float], duration: float) -> str:
    import io
    buf = io.BytesIO()
    n = int(_SAMPLE_RATE * duration)
    data = bytearray()
    amp = 0.5
    for s in samples[:n]:
        v = max(-1.0, min(1.0, s))
        data += int(v * amp * 32767).to_bytes(2, "little", signed=True)
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_SAMPLE_RATE)
        w.writeframes(bytes(data))
    return save_bytes(buf.getvalue(), "audio", ".wav")


def generate_voice(text: str, voice_id: str, emotion: str, duration: float, seed: int) -> str:
    rnd = random.Random(seed)
    freq = _VOICE_BASE.get(voice_id, _VOICE_BASE["default"])
    samples = []
    vibrato = 4.0 if emotion in ("怒", "惊") else 2.0
    for t in range(int(_SAMPLE_RATE * duration)):
        envelope = min(1.0, t / (_SAMPLE_RATE * 0.08)) * min(1.0, (duration - t / _SAMPLE_RATE) / 0.08)
        s = math.sin(2 * math.pi * freq * t / _SAMPLE_RATE) * 0.6
        s += math.sin(2 * math.pi * (freq * 1.5) * t / _SAMPLE_RATE) * 0.25
        s *= (0.7 + 0.3 * math.sin(2 * math.pi * vibrato * t / _SAMPLE_RATE))
        samples.append(s * envelope)
    return _write_wav(samples, duration)


def generate_bgm(emotion: str, duration: float, seed: int) -> str:
    rnd = random.Random(seed)
    chords = {"爽点": [196, 247, 294], "虐点": [147, 175, 220], "反转": [174, 196, 262],
              "铺垫": [131, 165, 196], "高潮": [220, 262, 330]}
    freqs = chords.get(emotion, [196, 220, 247])
    samples = []
    beat = _SAMPLE_RATE * 0.5
    for t in range(int(_SAMPLE_RATE * duration)):
        env = min(1.0, t / (_SAMPLE_RATE * 0.05)) * min(1.0, (duration - t / _SAMPLE_RATE) / 0.05)
        idx = int(t / beat) % len(freqs)
        f = freqs[idx]
        s = math.sin(2 * math.pi * f * t / _SAMPLE_RATE) * 0.4
        s += math.sin(2 * math.pi * f * 2 * t / _SAMPLE_RATE) * 0.12
        samples.append(s * env)
    return _write_wav(samples, duration)


def generate_sfx(kind: str, duration: float, seed: int) -> str:
    rnd = random.Random(seed)
    samples = []
    for t in range(int(_SAMPLE_RATE * duration)):
        env = math.exp(-6 * t / _SAMPLE_RATE)
        if kind in ("爆炸", "撞击", "雷声"):
            samples.append(rnd.uniform(-1, 1) * env)
        else:
            freq = rnd.choice([440, 660, 880])
            samples.append(math.sin(2 * math.pi * freq * t / _SAMPLE_RATE) * env * 0.5)
    return _write_wav(samples, duration)
