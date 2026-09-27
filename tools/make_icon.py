#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
易支付插件 —— 渠道图标生成

V10 的支付图标约定：plugins/gateway/<插件目录>/<插件标识>.png
（PluginModel::plugins() 会把它转成 base64 交给前台收银台）。

用法
    --out 的相对路径以「插件根目录」（即各渠道目录所在的那一层）为基准，
    而不是当前工作目录，避免从 tools/ 里执行时写错位置。

    # 微信绿
    python make_icon.py --text 微 --out epay_wx/EpayWx.png \
        --top "#07c160" --bottom "#05a04e"

    # 支付宝蓝
    python make_icon.py --text 支 --out epay_alipay/EpayAlipay.png \
        --top "#1677ff" --bottom "#0e5fd8"

    # 重新生成母版图标
    python make_icon.py --text 易 --out epay/Epay.png

@author 空雨不流泪
@link   https://www.kybll.cn/
"""

import argparse
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit('需要 Pillow：pip install Pillow')

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)                # 仓库根

# --out 给相对路径时以此为基准：
#   插件集仓库 -> <仓库根>/plugins ；单插件形态 -> <插件根>（即渠道目录所在那一层）
_nested = os.path.join(REPO_ROOT, 'plugins')
PLUGINS_ROOT = _nested if os.path.isdir(_nested) else REPO_ROOT

FONT_CANDIDATES = (
    r'C:/Windows/Fonts/msyhbd.ttc',
    r'C:/Windows/Fonts/msyh.ttc',
    r'C:/Windows/Fonts/simhei.ttf',
    '/System/Library/Fonts/PingFang.ttc',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
)


def hex_to_rgb(value):
    value = value.strip().lstrip('#')
    if len(value) == 3:
        value = ''.join(c * 2 for c in value)
    if len(value) != 6:
        raise ValueError('颜色格式应为 #RRGGBB：%s' % value)
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def load_font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return None


def main():
    parser = argparse.ArgumentParser(description='生成易支付渠道图标（圆角渐变 + 居中文字）')
    parser.add_argument('--out', required=True, help='输出 png 路径')
    parser.add_argument('--text', default='易', help='图标文字，默认「易」')
    parser.add_argument('--size', type=int, default=120, help='边长像素，默认 120')
    parser.add_argument('--top', default='#00B386', help='渐变起始色（上），默认 #00B386')
    parser.add_argument('--bottom', default='#00A0E9', help='渐变结束色（下），默认 #00A0E9')
    parser.add_argument('--radius', type=float, default=0.22, help='圆角比例，默认 0.22')
    parser.add_argument('--font-size', type=int, default=0, help='文字字号，默认按边长自动')
    args = parser.parse_args()

    size = args.size
    top, bottom = hex_to_rgb(args.top), hex_to_rgb(args.bottom)

    # 竖向渐变
    base = Image.new('RGB', (size, size), top)
    draw = ImageDraw.Draw(base)
    for y in range(size):
        t = y / float(max(size - 1, 1))
        draw.line([(0, y), (size, y)],
                  fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))

    # 圆角遮罩
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=int(size * args.radius), fill=255)

    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    img.paste(base, (0, 0), mask)

    # 居中文字
    font_size = args.font_size or int(size * 0.55)
    font = load_font(font_size)
    draw = ImageDraw.Draw(img)

    if font is not None and args.text:
        text = args.text[0] if len(args.text) == 1 else args.text
        l, t, r, b = draw.textbbox((0, 0), text, font=font)
        draw.text(((size - (r - l)) / 2 - l, (size - (b - t)) / 2 - t),
                  text, font=font, fill=(255, 255, 255, 255))
    elif not args.text:
        pass
    else:
        # 没有可用字体时退化成几何图形，保证脚本不会直接失败
        draw.rectangle([size * 0.3, size * 0.25, size * 0.7, size * 0.75],
                       outline=(255, 255, 255, 255), width=max(2, size // 15))

    # 相对路径以插件根目录为基准，避免从 tools/ 里执行时把文件写到插件内部
    out = args.out if os.path.isabs(args.out) else os.path.join(PLUGINS_ROOT, args.out)
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out, 'PNG')
    print('已生成：%s  (%d×%d, %d 字节)' % (out, size, size, os.path.getsize(out)))


if __name__ == '__main__':
    main()
