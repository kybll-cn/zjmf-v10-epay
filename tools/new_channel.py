#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
易支付插件 —— 实例派生工具

作用
    把 epay 母版派生成多个彼此独立的插件实例，用来接入多个易支付供应商
    （例如两家不同的微信易支付）。每个实例在后台「支付接口」列表里独立占一行、
    独立保存配置，前台收银台由用户自行选择走哪一家。

为什么必须派生而不是在一个插件里配多个商户
    V10 的模型是「一个插件目录 = 数据库一条记录 = 一份配置 = 支付列表里的一行」。
    用户在下单时选中的就是这一行，系统调用插件时只会传订单信息，
    不会告诉插件「用户想用哪个商户」。所以想做到用户可选，只能多实例。

用法
    在仓库根目录执行（脚本在 tools/ 下，会自动找到 plugins/<母版>）：

    python tools/new_channel.py --dir <新目录名> [选项]

示例
    python tools/new_channel.py --dir epay_wx2 --name "易支付-微信②"
    python tools/new_channel.py --dir epay_ali --pay-type alipay --protocol v2
    python tools/new_channel.py --dir epay_wx3 --pay-type wxpay --template epay

选项
    --dir DIR          新插件目录名（小写+下划线），必填
    --name NAME        通道显示名；中文在 Git Bash 下可能乱码，可改用 --name-file
    --name-file FILE   从 UTF-8 文件读取通道显示名，规避 shell 中文编码问题
    --pay-type TYPE    默认支付方式：wxpay/alipay/qqpay/bank/jdpay/douyinpay/paypal/usdt/...
    --protocol VER     默认协议版本：v1 或 v2
    --v1-request MODE  V1 发起方式：submit（页面跳转）或 mapi（接口下单）
    --v2-request MODE  V2 发起方式：submit（页面跳转）或 create（接口下单）
    --template NAME    母版插件目录名，默认 epay
    --out DIR          输出根目录，默认渠道目录所在的那一层（仓库里就是 plugins/）
    --force            目标目录已存在时先删除再生成
    --dry-run          只显示将要改动的文件与替换结果，不写盘

@author 空雨不流泪
@link https://www.kybll.cn/
"""

import argparse
import os
import re
import shutil
import sys

# 需要做文本替换的扩展名；二进制文件（png 等）只复制不改内容
TEXT_EXT = {'.php', '.md', '.txt', '.html', '.htm', '.js', '.css', '.json',
            '.yml', '.yaml', '.tpl', '.ini', '.conf', '.py'}

# 复制时跳过的目录
SKIP_DIRS = {'tools', '.git', '.idea', '.vscode', '__pycache__', 'node_modules', '.svn'}

# 支付方式 -> 中文名（用于自动推导通道名称）
PAY_TYPE_NAMES = {
    'wxpay': '微信',
    'alipay': '支付宝',
    'qqpay': 'QQ钱包',
    'bank': '网银',
    'jdpay': '京东',
    'douyinpay': '抖音',
    'paypal': 'PayPal',
    'usdt': 'USDT',
    'stripepay': 'Stripe',
    'stripealipay': 'Stripe支付宝',
    'stripewxpay': 'Stripe微信',
    'all': '收银台',
}

VALID_PAY_TYPES = set(PAY_TYPE_NAMES.keys())


def v10_studly(dir_name):
    """精确模拟 V10 的 parse_name($dir, 1)：下划线后的字母大写，首字母大写。
    注意 '_2x' 这类不会被转成 '2X'，与 ThinkPHP 正则 /_([a-zA-Z])/ 行为一致。"""
    s = re.sub(r'_([a-zA-Z])', lambda m: m.group(1).upper(), dir_name)
    return s[:1].upper() + s[1:]


def auto_title(new_dir, pay_type):
    """没有显式指定通道名称时，按支付方式 + 目录名末尾数字推导。"""
    name = PAY_TYPE_NAMES.get(pay_type, pay_type or '通用')
    tail = re.search(r'(\d+)$', new_dir)
    return '易支付-' + name + (tail.group(1) if tail else '')


def build_replacer(old_dir, new_dir):
    """构造文本替换规则。

    关键点：类名替换必须带词边界 \\b，否则会把 EpayClient 里的 Epay 也替掉，
    从而生成 EpayWxClient 这种不存在的类，插件直接白屏。
    """
    old_class = v10_studly(old_dir)
    new_class = v10_studly(new_dir)

    return [
        # 1) 支付入口方法：EpayHandle -> EpayWxHandle，EpayHandleRefund 同理
        (re.compile(r'\b' + re.escape(old_class) + r'Handle'), new_class + 'Handle'),
        # 2) 命名空间前缀：gateway\epay -> gateway\epay_wx
        (re.compile(re.escape('gateway\\' + old_dir)), 'gateway\\' + new_dir),
        # 3) 独立的类名 / 插件标识 / 文件名：Epay -> EpayWx（不碰 EpayClient）
        (re.compile(r'\b' + re.escape(old_class) + r'\b'), new_class),
    ], old_class, new_class


def rename_file(filename, old_class, new_class):
    """Epay.php -> EpayWx.php，Epay.png -> EpayWx.png，其余保持原名。"""
    stem, ext = os.path.splitext(filename)
    if stem == old_class:
        return new_class + ext
    return filename


def set_config_value(text, key, value):
    """设置 config.php 中某个配置项的 'value'（只改该键块内的第一个 value）。"""
    pattern = re.compile(
        r"('" + re.escape(key) + r"'\s*=>\s*\[.*?'value'\s*=>\s*')([^']*)(')",
        re.S,
    )
    new_text, count = pattern.subn(lambda m: m.group(1) + value + m.group(3), text, count=1)
    if count != 1:
        raise RuntimeError("未能定位 config.php 中的配置项 '%s'" % key)
    return new_text


def apply_text_replacement(content, rules):
    # 用 lambda 返回字面量：替换串含反斜杠（如 gateway\epay_wx），
    # 直接传给 re.sub 会被当成转义序列而报 bad escape。
    for pattern, replacement in rules:
        content = pattern.sub(lambda _m, r=replacement: r, content)
    return content


def collect_files(source):
    """遍历母版目录，返回 [(绝对路径, 相对路径)]，跳过 SKIP_DIRS。"""
    items = []
    for root, dirs, files in os.walk(source):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, source)
            items.append((full, rel))
    return items


def main():
    parser = argparse.ArgumentParser(
        description='从 epay 母版派生一个新的易支付插件实例',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--dir', required=True, help='新插件目录名（小写+下划线），例如 epay_wx2')
    parser.add_argument('--name', default=None, help='通道显示名，写入 config.php 的 module_name')
    parser.add_argument('--name-file', default=None, help='从 UTF-8 文件读取通道显示名')
    parser.add_argument('--pay-type', default=None, help='默认支付方式')
    parser.add_argument('--protocol', default=None, choices=['v1', 'v2'], help='默认协议版本')
    parser.add_argument('--v1-request', default=None, choices=['submit', 'mapi'])
    parser.add_argument('--v2-request', default=None, choices=['submit', 'create'])
    parser.add_argument('--template', default=None, help='母版插件目录名，默认 epay')
    parser.add_argument('--out', default=None, help='输出根目录，默认母版所在的目录')
    parser.add_argument('--force', action='store_true', help='目标目录已存在时先删除再生成')
    parser.add_argument('--dry-run', action='store_true', help='只预览，不写盘')
    args = parser.parse_args()

    new_dir = args.dir.strip()

    # ---- 参数校验 ----
    if not re.match(r'^[a-z][a-z0-9_]*$', new_dir):
        print('[错误] 目录名只能是小写字母、数字与下划线，且以字母开头：%s' % new_dir)
        return 1

    # 插件集仓库里脚本位于 <仓库根>/tools/，各渠道位于 <仓库根>/plugins/<目录>/
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    nested = os.path.join(repo_root, 'plugins')
    plugins_root = nested if os.path.isdir(nested) else repo_root

    template_name = (args.template or 'epay').strip()
    source = os.path.abspath(os.path.join(plugins_root, template_name))

    # --out 的相对路径同样以渠道目录所在的那一层为基准
    if args.out:
        out_root = args.out if os.path.isabs(args.out) else os.path.join(plugins_root, args.out)
        out_root = os.path.abspath(out_root)
    else:
        out_root = plugins_root

    if not os.path.isdir(source):
        print('[错误] 母版目录不存在：%s' % source)
        return 1

    old_dir = os.path.basename(source)
    if new_dir == old_dir:
        print('[错误] 新目录名不能与母版相同：%s' % new_dir)
        return 1

    target = os.path.join(out_root, new_dir)
    if os.path.exists(target):
        if args.dry_run:
            # 预览不写盘，所以目录已存在也照常演示
            print('[预览] 目标目录已存在，实际执行时会先删除重建：%s' % target)
        elif not args.force:
            print('[错误] 目标目录已存在：%s\n       如需覆盖请加 --force' % target)
            return 1
        else:
            shutil.rmtree(target)

    if args.pay_type and args.pay_type not in VALID_PAY_TYPES:
        print('[错误] 不支持的支付方式：%s\n       可选：%s'
              % (args.pay_type, ', '.join(sorted(VALID_PAY_TYPES))))
        return 1

    rules, old_class, new_class = build_replacer(old_dir, new_dir)

    base_dir = source
    pay_type = args.pay_type
    if pay_type is None:
        # 从母版 config.php 读出默认支付方式
        with open(os.path.join(source, 'config.php'), encoding='utf-8') as fp:
            m = re.search(r"'pay_type'\s*=>\s*\[.*?'value'\s*=>\s*'([^']*)'", fp.read(), re.S)
            pay_type = m.group(1) if m else 'wxpay'

    if args.name_file:
        with open(args.name_file, encoding='utf-8') as fp:
            title = fp.read().strip()
    elif args.name:
        title = args.name.strip()
    else:
        title = auto_title(new_dir, pay_type)

    print('母版目录 : %s' % source)
    print('新实例   : %s' % target)
    print('类名映射 : %s -> %s' % (old_class, new_class))
    print('通道名称 : %s' % title)
    print('支付方式 : %s' % pay_type)
    print('-' * 66)

    # ---- 复制 + 替换 ----
    entries = collect_files(source)
    if not entries:
        print('[错误] 母版目录为空：%s' % source)
        return 1

    for full, rel in entries:
        rel_dir = os.path.dirname(rel)
        new_name = rename_file(os.path.basename(rel), old_class, new_class)
        rel_new = os.path.join(rel_dir, new_name) if rel_dir else new_name

        dest = os.path.join(target, rel_new)
        ext = os.path.splitext(rel)[1].lower()
        changed = []

        if ext in TEXT_EXT:
            with open(full, encoding='utf-8') as fp:
                content = fp.read()
            content = apply_text_replacement(content, rules)

            # config.php 额外写入默认值
            if new_name == 'config.php':
                content = set_config_value(content, 'module_name', title)
                if args.pay_type:
                    content = set_config_value(content, 'pay_type', args.pay_type)
                if args.protocol:
                    content = set_config_value(content, 'protocol', args.protocol)
                if args.v1_request:
                    content = set_config_value(content, 'v1_request', args.v1_request)
                if args.v2_request:
                    content = set_config_value(content, 'v2_request', args.v2_request)
                changed.append('默认值已写入')

            if not args.dry_run:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, 'w', encoding='utf-8', newline='') as fp:
                    fp.write(content)
        else:
            if not args.dry_run:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(full, dest)

        tag = ' (改名)' if new_name != os.path.basename(rel) else ''
        extra = ('  [' + '; '.join(changed) + ']') if changed else ''
        print('  %s%s%s' % (rel_new, tag, extra))

    print('-' * 66)
    if args.dry_run:
        print('预览完成，未写入任何文件（去掉 --dry-run 才会真正生成）')
    else:
        print('生成完成：%s' % target)
        print()
        print('接下来：')
        print('  1. 把 %s 整个目录上传到网站的 plugins/gateway/ 下' % new_dir)
        print('  2. 后台「系统 - 支付接口」刷新，安装 %s 并填写商户参数' % title)
        print('  3. 需要第三个供应商？把上面的命令换个目录名再跑一次即可')

    return 0


if __name__ == '__main__':
    sys.exit(main())
