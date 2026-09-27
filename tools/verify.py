#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
易支付插件 —— 交付前静态校验

本机没有 PHP 运行时，用 Python 复刻 ThinkPHP 的 parse_name 规则与 V10 的插件契约，
对每个渠道目录做结构体检：

  1. PHP 词法粗检：括号 / 引号平衡（跳过注释与字符串，避免误报）
  2. 目录名 -> 标识 -> 类名 -> 文件名 -> namespace -> $info['name'] -> Handle 方法名 的全链一致
  3. config.php 合规：每项都有 value；radio 的 value 必须落在 options 的键里；不得占用系统保留键
  4. 契约完整性：notifyHandle / returnHandle / HandleRefund / order_pay_handle / 图标文件

用法
    python verify.py                     # 校验仓库 plugins/ 下所有 epay* 渠道
    python verify.py --prefix epay       # 指定渠道目录前缀
    python verify.py --dirs epay epay_wx2
    python verify.py --plugins ../epay   # 指到单插件形态的插件目录

@author 空雨不流泪
@link   https://www.kybll.cn/
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)                    # 仓库根（或单插件形态下的插件根）

DEFAULT_PREFIX = 'epay'


def default_plugins_dir():
    """兼容两种布局：
    - 插件集仓库：<仓库根>/plugins/<渠道>/   -> 返回 <仓库根>/plugins
    - 单插件目录：<插件根>/<渠道>/，且 tools/ 就在 <插件根>/ 里 -> 返回 <插件根>
    """
    nested = os.path.join(REPO_ROOT, 'plugins')
    if os.path.isdir(nested):
        return nested
    return REPO_ROOT


PLUGIN_ROOT = REPO_ROOT

OK = '  [OK]   '
FAIL = '  [FAIL] '
WARN = '  [WARN] '

PAIRS = {'(': ')', '[': ']', '{': '}'}
CLOSING = {')': '(', ']': '[', '}': '{'}

errors = []
warnings = []


def report(level, msg):
    print(level + msg)
    if level == FAIL:
        errors.append(msg)
    elif level == WARN:
        warnings.append(msg)


# ---------------------------------------------------------------- 内核规则复刻

def parse_name_studly(name):
    """等价 PHP: parse_name($name, 1) —— 下划线后首字母大写 + ucfirst"""
    name = re.sub(r'_([a-zA-Z])', lambda m: m.group(1).upper(), name)
    if not name:
        return name
    return name[0].upper() + name[1:]


def scan_php(source):
    """逐字符扫描，跳过注释与字符串，返回配对错误列表。"""
    found = []
    stack = []
    i, n, line = 0, len(source), 1

    while i < n:
        c = source[i]

        if c == '\n':
            line += 1
            i += 1
            continue

        # 字符串必须最先判断，否则 'https://x' 里的 // 会被当成注释
        if c in ("'", '"'):
            quote, start_line = c, line
            i += 1
            closed = False
            while i < n:
                if source[i] == '\\':
                    i += 2
                    continue
                if source[i] == quote:
                    closed = True
                    i += 1
                    break
                if source[i] == '\n':
                    line += 1
                i += 1
            if not closed:
                found.append('第 %d 行：字符串未闭合' % start_line)
            continue

        if c == '/' and i + 1 < n and source[i + 1] == '/':
            while i < n and source[i] != '\n':
                i += 1
            continue
        if c == '#':
            while i < n and source[i] != '\n':
                i += 1
            continue
        if c == '/' and i + 1 < n and source[i + 1] == '*':
            i += 2
            while i < n and not (source[i] == '*' and i + 1 < n and source[i + 1] == '/'):
                if source[i] == '\n':
                    line += 1
                i += 1
            i += 2
            continue

        if c in PAIRS:
            stack.append((c, line))
        elif c in CLOSING:
            if not stack:
                found.append('第 %d 行：多余的 %s' % (line, c))
            elif stack[-1][0] != CLOSING[c]:
                found.append('第 %d 行：%s 与第 %d 行的 %s 不匹配'
                             % (line, c, stack[-1][1], stack[-1][0]))
                stack.pop()
            else:
                stack.pop()
        i += 1

    for ch, ln in stack:
        found.append('第 %d 行：%s 未闭合' % (ln, ch))

    return found


# ---------------------------------------------------------------- 单项检查

def check_config(path):
    with open(path, encoding='utf-8') as fp:
        text = fp.read()

    if 'return [' not in text:
        report(FAIL, 'config.php 缺少 return [...] 返回数组')
        return

    chunks = re.split(r"\n    '", text)
    items = [(ch.split("'", 1)[0], ch) for ch in chunks[1:]]

    if not items:
        report(FAIL, 'config.php 未解析到任何配置项')
        return

    keys = [k for k, _ in items]

    for key, body in items:
        if not re.match(r'^[a-z][a-z0-9_]*$', key):
            report(FAIL, "配置项键名 %r 不是小写+下划线" % key)

        m_type = re.search(r"'type'\s*=>\s*'(\w+)'", body)
        if not m_type:
            report(FAIL, "配置项 '%s' 缺少 type" % key)
            continue
        ctype = m_type.group(1)

        m_val = re.search(r"'value'\s*=>\s*'([^']*)'", body)
        if m_val is None:
            # Plugin::getDefaultConfig() 会读每一项的 value，缺失会在未安装时报错
            report(FAIL, "配置项 '%s' 缺少 value（Plugin::getDefaultConfig 会读取它）" % key)
            continue
        value = m_val.group(1)

        if key in ('return_url', 'notify_url'):
            report(FAIL, "配置项 '%s' 是系统保留键，settingPost 会 unset 它" % key)

        if ctype in ('radio', 'checkbox', 'select'):
            m_opt = re.search(r"'options'\s*=>\s*\[(.*)", body, re.S)
            if not m_opt:
                report(FAIL, "配置项 '%s' 是 %s 却没有 options" % (key, ctype))
                continue
            opt_keys = re.findall(r"'([^']+)'\s*=>", m_opt.group(1))
            if value not in opt_keys:
                report(FAIL, "配置项 '%s' 的 value=%r 不在 options 的键 %s 里（后台保存会被拒）"
                             % (key, value, opt_keys))
            if ctype == 'select':
                report(WARN, "配置项 '%s' 用了 select：admin 模板取 ele.value/ele.label，"
                             "与 PHP 关联数组 JSON 后的对象结构不匹配，实际不可用，建议改 radio" % key)
            if '' in opt_keys:
                report(WARN, "配置项 '%s' 的 options 含空字符串键，radio 选中态可能异常" % key)

    if 'module_name' not in keys:
        report(FAIL, 'config.php 缺少 module_name：系统按它显示通道名称')


def check_plugin(name):
    path = os.path.join(PLUGINS_DIR, name)
    studly = parse_name_studly(name)

    print('')
    print('─' * 62)
    print('渠道：%s   （标识 %s）' % (name, studly))
    print('─' * 62)

    if not os.path.isdir(path):
        report(FAIL, '目录不存在：%s' % path)
        return

    # ---- 主类 ----
    main = os.path.join(path, studly + '.php')
    if not os.path.isfile(main):
        report(FAIL, '缺少主类文件 %s.php' % studly)
    else:
        with open(main, encoding='utf-8') as fp:
            src = fp.read()

        for e in scan_php(src):
            report(FAIL, '%s.php：%s' % (studly, e))

        if not re.search(r'^namespace\s+gateway\\%s\s*;' % re.escape(name), src, re.M):
            report(FAIL, '%s.php 的 namespace 不是 gateway\\%s' % (studly, name))
        if not re.search(r'^class\s+%s\s+extends\s+Plugin' % re.escape(studly), src, re.M):
            report(FAIL, '%s.php 未定义 class %s extends Plugin' % (studly, studly))
        if not re.search(r"'name'\s*=>\s*'%s'" % re.escape(studly), src):
            report(FAIL, "$info['name'] 不等于 %s（类名匹配会直接断）" % studly)
        if 'public function %sHandle(' % studly not in src:
            report(FAIL, '缺少支付入口方法 %sHandle()' % studly)
        if 'public function %sHandleRefund(' % studly not in src:
            report(WARN, '未实现 %sHandleRefund()，后台退款将没有「原支付路径」选项' % studly)

    # ---- 配置 ----
    conf = os.path.join(path, 'config.php')
    if not os.path.isfile(conf):
        report(FAIL, '缺少 config.php')
    else:
        check_config(conf)

    # ---- 协议客户端 ----
    client = os.path.join(path, 'lib', 'PayClient.php')
    if not os.path.isfile(client):
        report(FAIL, '缺少 lib/PayClient.php')
    else:
        with open(client, encoding='utf-8') as fp:
            src = fp.read()
        for e in scan_php(src):
            report(FAIL, 'lib/PayClient.php：%s' % e)
        if not re.search(r'^namespace\s+gateway\\%s\\lib\s*;' % re.escape(name), src, re.M):
            report(FAIL, 'lib/PayClient.php 的 namespace 不正确')
        for method in ('buildPayHtml', 'verifyNotify', 'refund'):
            if 'function %s(' % method not in src:
                report(FAIL, 'lib/PayClient.php 缺少 %s()' % method)

    # ---- 回调控制器 ----
    ctrl = os.path.join(path, 'controller', 'IndexController.php')
    if not os.path.isfile(ctrl):
        report(FAIL, '缺少 controller/IndexController.php')
    else:
        with open(ctrl, encoding='utf-8') as fp:
            src = fp.read()
        for e in scan_php(src):
            report(FAIL, 'controller/IndexController.php：%s' % e)
        for method in ('notifyHandle', 'returnHandle'):
            if 'function %s(' % method not in src:
                report(FAIL, '控制器缺少 %s()' % method)
        if 'order_pay_handle(' not in src:
            report(FAIL, '控制器未调用 order_pay_handle()，支付成功不会入账')
        if 'verifyNotify' not in src:
            report(FAIL, '控制器未调用 verifyNotify()，回调没有验签')

    # ---- 图标 ----
    if not os.path.isfile(os.path.join(path, studly + '.png')):
        report(WARN, '缺少 %s.png，收银台会没有支付图标' % studly)


# ---------------------------------------------------------------- 入口

def discover(prefix):
    """找出插件根下所有以 prefix 开头、且确实是插件（存在同名主类）的目录"""
    result = []
    for name in sorted(os.listdir(PLUGINS_DIR)):
        full = os.path.join(PLUGINS_DIR, name)
        if not os.path.isdir(full) or not name.startswith(prefix):
            continue
        if os.path.isfile(os.path.join(full, parse_name_studly(name) + '.php')):
            result.append(name)
    return result


def main():
    global PLUGINS_DIR

    parser = argparse.ArgumentParser(description='易支付插件交付前静态校验')
    parser.add_argument('--prefix', default=DEFAULT_PREFIX, help='渠道目录前缀，默认 %s' % DEFAULT_PREFIX)
    parser.add_argument('--dirs', nargs='*', default=None, help='显式指定要校验的目录名')
    parser.add_argument('--plugins', default=None, help='渠道所在的目录，默认自动探测 <仓库根>/plugins')
    args = parser.parse_args()

    PLUGINS_DIR = os.path.abspath(args.plugins) if args.plugins else default_plugins_dir()

    names = args.dirs if args.dirs else discover(args.prefix)

    print('插件根目录：%s' % PLUGINS_DIR)
    print('待校验渠道：%s' % (', '.join(names) if names else '（无）'))

    if not names:
        print('')
        print('没有找到任何渠道目录，请用 --prefix 或 --dirs 指定')
        return 1

    for name in names:
        check_plugin(name)

    print('')
    print('=' * 62)
    if not errors and not warnings:
        print('全部通过：%d 个渠道，0 错误 0 警告' % len(names))
    else:
        print('共 %d 个渠道，%d 处错误，%d 处警告' % (len(names), len(errors), len(warnings)))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
