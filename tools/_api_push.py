#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""经 GitHub REST API 推送本地仓库（绕过 git 传输层）。

本机 github.com:443 的 git 传输不通，但 api.github.com 可用，
故用 Git Data API 手工建 blob / tree / commit 并更新 ref。

用法：
    python _api_push.py --repo kybll-cn/zjmf-v10-epay --branch main --src <仓库根> [--message "..."]
"""

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path


def gh_api(method, path, payload=None, jq=None):
    """调用 gh api，返回解析后的 JSON。"""
    cmd = ['gh', 'api', '-X', method, path]
    if payload is not None:
        cmd += ['--input', '-']
    if jq:
        cmd += ['--jq', jq]
    proc = subprocess.run(
        cmd,
        input=(json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else None),
        capture_output=True,
    )
    if proc.returncode != 0:
        raise SystemExit('gh api 失败 %s %s\n%s' % (method, path, proc.stderr.decode('utf-8', 'replace')))
    out = proc.stdout.decode('utf-8', 'replace').strip()
    if jq:
        return out
    return json.loads(out) if out else None


SKIP_DIRS = {'.git', 'dist', '__pycache__', '.idea', '.vscode'}
SKIP_SUFFIX = ('.pyc', '.pyo', '.zip')


def iter_files(root: Path):
    for cur, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for n in sorted(names):
            if n.endswith(SKIP_SUFFIX):
                continue
            yield Path(cur) / n


def ensure_bootstrapped(repo, branch, message):
    """空仓库时用 Contents API 先建一个初始提交，把默认分支撑起来。"""
    try:
        gh_api('GET', '/repos/%s/git/ref/heads/%s' % (repo, branch), jq='.object.sha')
        print('分支已存在，跳过初始化：%s' % branch)
        return
    except SystemExit:
        pass

    print('仓库为空，先用 Contents API 建初始提交……')
    # 找一个真实文件作为初始内容，避免多出一个无意义占位文件
    api = '/repos/%s/contents/.gitattributes' % repo
    try:
        gh_api('PUT', api, {
            'message': 'chore: init',
            'content': base64.b64encode(b'* text=auto eol=lf\n').decode('ascii'),
            'branch': branch,
        })
    except SystemExit as e:
        raise SystemExit('初始化空仓库失败：%s' % e)
    print('初始提交完成')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--branch', default='main')
    ap.add_argument('--src', required=True)
    ap.add_argument('--message', default='feat: 同步本地提交')
    args = ap.parse_args()

    root = Path(args.src).resolve()

    files = list(iter_files(root))
    print('待上传文件：%d 个' % len(files))

    # 0) 空仓库无法直接用 Git Data API（blobs 会报 409 Git Repository is empty），
    #    先用 Contents API 塞一个占位文件把默认分支建起来，后续 tree 会把它覆盖掉。
    ensure_bootstrapped(args.repo, args.branch, args.message)

    # 1) 逐个建 blob，拼 tree
    tree_items = []
    for f in files:
        rel = f.relative_to(root).as_posix()
        data = f.read_bytes()
        blob = gh_api('POST', '/repos/%s/git/blobs' % args.repo, {
            'content': base64.b64encode(data).decode('ascii'),
            'encoding': 'base64',
        })
        tree_items.append({'path': rel, 'mode': '100755' if rel.endswith('.py') else '100644',
                           'type': 'blob', 'sha': blob['sha']})
    print('blob 建完：%d 个' % len(tree_items))

    # 2) 建 tree（不带 base_tree，即为全新树）
    tree = gh_api('POST', '/repos/%s/git/trees' % args.repo, {'tree': tree_items})
    print('tree: %s' % tree['sha'])

    # 3) 建 commit
    commit = gh_api('POST', '/repos/%s/git/commits' % args.repo, {
        'message': args.message,
        'tree': tree['sha'],
        'parents': [],
    })
    print('commit: %s' % commit['sha'])

    # 4) 更新（或创建）分支 ref
    ref_path = '/repos/%s/git/refs/heads/%s' % (args.repo, args.branch)
    try:
        gh_api('PATCH', ref_path, {'sha': commit['sha'], 'force': True})
        print('ref 已更新：%s' % args.branch)
    except SystemExit:
        gh_api('POST', '/repos/%s/git/refs' % args.repo, {
            'ref': 'refs/heads/%s' % args.branch, 'sha': commit['sha'],
        })
        print('ref 已创建：%s' % args.branch)

    print('\n完成：https://github.com/%s' % args.repo)


if __name__ == '__main__':
    main()
