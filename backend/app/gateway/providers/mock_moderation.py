"""M13 合规检验 · 内容安全审核（模拟阿里云内容安全）。

真实接入时替换为：阿里云内容安全 / 腾讯云天御 / 网易易盾。
返回结构化审核结果：机器审核 → 可疑内容定位。
"""
SENSITIVE_RULES = [
    ("赌博", "涉及赌博/博彩内容"), ("博彩", "涉及赌博/博彩内容"),
    ("毒品", "涉及毒品内容"), ("枪支", "涉及枪支内容"),
    ("血腥", "涉及血腥暴力内容"), ("暴力", "涉及暴力内容"),
    ("色情", "涉及色情内容"), ("自杀", "涉及自杀内容"),
    ("诈骗", "涉及诈骗内容"), ("恐怖袭击", "涉及恐怖袭击内容"),
]


def moderate_texts(texts: list[str], *, vendor: str = "aliyun_sec") -> dict:
    """返回 {status: pass/reject, issues: [{snippet, rule, reason}], checked: n}"""
    issues = []
    for text in texts or []:
        for kw, reason in SENSITIVE_RULES:
            if kw in text:
                idx = text.find(kw)
                snippet = text[max(0, idx - 10): idx + len(kw) + 10]
                issues.append({"snippet": snippet, "rule": kw, "reason": reason})
    status = "reject" if issues else "pass"
    return {"status": status, "issues": issues, "checked": len(texts or []), "vendor": vendor}


def build_report(final_video_id: int, result: dict) -> dict:
    return {
        "final_video_id": final_video_id,
        "status": result["status"],
        "issues": result["issues"],
        "checked": result["checked"],
        "vendor": result["vendor"],
        "conclusion": "全部通过，可公开分发" if result["status"] == "pass"
        else f"发现 {len(result['issues'])} 处可疑内容，需局部重做后重新送审",
    }
