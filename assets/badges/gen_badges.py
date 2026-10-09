#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成本地 SVG 徽章（flat-square 风格，模仿 shields.io），确保 README 离线可显示。

用法: python gen_badges.py  （在 assets/badges 目录下执行，覆盖生成 *.svg）
"""
from __future__ import annotations

import os

# ---------------------------------------------------------------- 宽度估算
def text_width(text: str, size: int = 11) -> float:
    """粗略估算 Verdana 字体宽度（px）。"""
    factor = size / 11
    width = 0.0
    for ch in text:
        if ch in " .:il|![]()'":
            width += 3.6
        elif ch.isupper() or ch.isdigit():
            width += 7.6
        elif ch == "-":
            width += 4.5
        else:
            width += 6.6
    return width * factor


def flat_square(label: str, value: str, color: str) -> str:
    """生成 shields.io flat-square 风格徽章 SVG。"""
    pad = 5
    lw = round(text_width(label) + 10)
    vw = round(text_width(value) + 10)
    lx = lw / 2
    vx = lw + vw / 2
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{lw + vw}" height="20" role="img" aria-label="{label}: {value}">
  <title>{label}: {value}</title>
  <g shape-rendering="crispEdges">
    <rect width="{lw}" height="20" fill="#555"/>
    <rect x="{lw}" width="{vw}" height="20" fill="{color}"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="{lx}" y="14">{label}</text>
    <text x="{vx}" y="14">{value}</text>
  </g>
</svg>
'''


def for_the_badge(label: str, value: str, color: str, value_color: str) -> str:
    """生成 shields.io for-the-badge 风格（大号）徽章 SVG。"""
    size = 12
    pad = 9
    lw = round(text_width(label, size) + 2 * pad)
    vw = round(text_width(value, size) + 2 * pad)
    lx = lw / 2
    vx = lw + vw / 2
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{lw + vw}" height="28" role="img" aria-label="{label}: {value}">
  <title>{label}: {value}</title>
  <g shape-rendering="crispEdges">
    <rect width="{lw}" height="28" fill="{color}"/>
    <rect x="{lw}" width="{vw}" height="28" fill="{value_color}"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="{size}" font-weight="bold">
    <text x="{lx}" y="19">{label}</text>
    <text x="{vx}" y="19">{value}</text>
  </g>
</svg>
'''


# ---------------------------------------------------------------- 徽章定义
BADGES: dict[str, str] = {
    # 主徽章（for-the-badge 大号风格）
    "flow-llmops.svg": for_the_badge("Flow-LLMOps", "v1.0", "#555", "#6366F1"),
    # 技术栈徽章（flat-square 风格）
    "python.svg": flat_square("Python", "3.12", "#3776AB"),
    "fastapi.svg": flat_square("FastAPI", "0.139", "#009688"),
    "vue.svg": flat_square("Vue", "3.4", "#4FC08D"),
    "typescript.svg": flat_square("TypeScript", "5.4", "#3178C6"),
    "langchain.svg": flat_square("LangChain", "1.x", "#1C3C3C"),
    "docker.svg": flat_square("Docker", "Compose", "#2496ED"),
    "license.svg": flat_square("License", "MIT", "#FF6B6B"),
}


def main() -> None:
    base = os.path.dirname(os.path.abspath(__file__))
    for name, svg in BADGES.items():
        path = os.path.join(base, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(svg)
        print(f"生成 {name}")


if __name__ == "__main__":
    main()