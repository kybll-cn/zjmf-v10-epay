#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
易支付插件集 —— 发行打包

遍历 plugins/ 下的每个渠道插件，各自打成 dist/<插件标识>-<版本>.zip，
zip 内所有条目带一层 <目录名>/ 前缀（即 V10 要求的安装目录名），解压到
public/plugins/gateway/ 即可直接使用。

用法：
    python build.py                       # 打包全部渠道
    python build.py --plugin epay_wx      # 只打包指定渠道
    python build.py --out D:/tmp          # 指定输出目录

为什么入包范围是「全量 - 黑名单」而不是白名单：
    插件子目录形态差异很大（gateway 插件常带 controller/ + lib/，captcha 插件带
    logic/ + vendor/）。白名单一旦漏项，会静默打出缺文件的坏包且不易察觉，
    因此这里只排除 VCS / 打包脚本 / 产物 / 缓存。

@author 空雨不流泪
@link   https://www.kybll.cn/
"""

import argparse
import os
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent   # 仓库根
PLUGINS_DIR = HERE / 'plugins'
DIST_DIR = HERE / 'dist'

# ---- 黑名单：不进 zip ----
EXCLUDE_DIRS = {'.git', '.svn', '.github', '.idea', '.vscode', 'dist', '__pycache__', 'node_modules'}
EXCLUDE_FILES = {'.gitignore', '.gitattributes', '.gitmodules', 'build.py', 'build.bat',
                 '.DS_Store', 'Thumbs.db', 'desktop.ini'}
EXCLUDE_SUFFIX = ('.pyc', '.pyo', '.zip', '.tmp', '.bak', '.log', '.swp', '.swo')


def read_info(plugin_dir):
    """从主类（含 `public $info =` 的 PHP 文件）读出 name / version"""
    for p in sorted(plugin_dir.glob('*.php')):
        src = p.read_text(encoding='utf-8')
        if not re.search(r'public\s+\$info\s*=', src):
            continue

        def field(key):
            m = re.search(r"'%s'\s*=>\s*'([^']*)'" % key, src)
            return m.group(1) if m else ''

        return p, field('name'), field('version')

    raise SystemExit('%s：未找到含 `public $info` 的主类' % plugin_dir.name)


def collect(plugin_dir):
    """全量收集，按黑名单排除"""
    items = []
    for cur, dirs, names in os.walk(plugin_dir):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
        for n in sorted(names):
            if n in EXCLUDE_FILES or n.endswith(EXCLUDE_SUFFIX):
                continue
            items.append(Path(cur) / n)
    return items


def build_one(plugin_dir, out_dir):
    main_file, class_name, version = read_info(plugin_dir)
    if not version:
        raise SystemExit('%s：主类里没读到 $info[\'version\']' % plugin_dir.name)

    base = class_name or plugin_dir.name
    zip_path = out_dir / ('%s-%s.zip' % (base, version))
    if zip_path.exists():
        zip_path.unlink()

    files = collect(plugin_dir)
    rels = [f.relative_to(plugin_dir).as_posix() for f in files]

    # 自检：主类必须进包，否则说明黑名单误伤
    if main_file.relative_to(plugin_dir).as_posix() not in rels:
        raise SystemExit('%s：主类未进包，请检查黑名单' % plugin_dir.name)

    prefix = plugin_dir.name   # V10: 目录名 = 安装目录名，不可改
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for f, rel in zip(files, rels):
            z.write(f, '%s/%s' % (prefix, rel))

    total = sum(f.stat().st_size for f in files)
    print('  [OK] %-24s %-12s v%-8s %2d 文件  %7d B  ->  %6.1f KB'
          % (prefix + '/', base, version, len(files), total, zip_path.stat().st_size / 1024))
    return zip_path


def main():
    parser = argparse.ArgumentParser(description='易支付插件集 - 打包')
    parser.add_argument('--plugin', help='只打包指定插件目录名')
    parser.add_argument('--out', help='输出目录，默认 <仓库根>/dist')
    args = parser.parse_args()

    out_dir = Path(args.out).resolve() if args.out else DIST_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.plugin:
        targets = [PLUGINS_DIR / args.plugin]
        if not targets[0].is_dir():
            sys.exit('插件目录不存在：%s' % targets[0])
    else:
        targets = sorted(d for d in PLUGINS_DIR.iterdir() if d.is_dir())

    if not targets:
        sys.exit('plugins/ 下没有任何插件目录')

    print('仓库根  : %s' % HERE)
    print('输出目录: %s\n' % out_dir)

    built = [build_one(d, out_dir) for d in targets]

    print('\n共生成 %d 个安装包。' % len(built))
    print('安装：解压后把 <目录名>/ 整个放入站点 public/plugins/gateway/ ，')
    print('      再到后台「系统 - 接口管理 - 支付接口」刷新并安装。')


if __name__ == '__main__':
    main()
