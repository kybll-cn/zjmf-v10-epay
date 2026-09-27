<?php
/*
 * Copyright (C) 2026 空雨不流泪 <https://www.kybll.cn/>
 *
 * This program is free software: you can redistribute it and/or modify it under
 * the terms of the GNU General Public License as published by the Free Software
 * Foundation, either version 3 of the License, or (at your option) any later
 * version.
 *
 * This program is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along with
 * this program. If not, see <https://www.gnu.org/licenses/>.
 */

/**
 * 易支付插件 —— 后台配置表单
 *
 * 规则说明（V10 约定，勿随意改动）：
 * 1. 键名统一 小写 + 下划线，表单里以 config[键名] 提交。
 * 2. 枚举类控件必须用 radio：模板会把 options 的「键」当作提交值、「值」当作显示文案
 *    （主题/admin/template/default/js/gateway.js 的 computedRadio），
 *    因此 options 一律写成 [提交值 => 显示文案]。select 模板取 ele.value/ele.label，
 *    与 PHP 关联数组 JSON 化后的对象结构不匹配，实际不可用，故本插件不使用 select。
 * 3. 每一项都必须有 value 键（Plugin::getDefaultConfig 会读取它）。
 * 4. return_url / notify_url 是系统保留键（PluginModel::settingPost 会 unset），不可用作配置项名。
 * 5. module_name 是系统识别「通道显示名」的固定键，不可改名。
 *
 * @author 空雨不流泪
 * @link https://www.kybll.cn/
 */

return [
    'module_name' => [
        'title' => '通道名称',
        'type'  => 'text',
        'value' => '易支付',
        'tip'   => '显示在后台支付接口列表与前台收银台，建议写清供应商与支付方式，例如「易支付-微信A」',
        'size'  => 200,
    ],
    'protocol' => [
        'title'   => '接口协议',
        'type'    => 'radio',
        'value'   => 'v1',
        'options' => [
            'v1' => 'V1（MD5 签名 / submit.php、mapi.php）',
            'v2' => 'V2（RSA 签名 / /api/pay/*）',
        ],
    ],
    'apiurl' => [
        'title' => '接口地址',
        'type'  => 'text',
        'value' => '',
        'tip'   => '易支付平台地址，须以 / 结尾，例如 https://pay.example.com/',
        'size'  => 200,
    ],
    'pid' => [
        'title' => '商户ID（PID）',
        'type'  => 'text',
        'value' => '',
        'tip'   => '商户后台的商户编号',
        'size'  => 200,
    ],
    'key' => [
        'title' => '商户密钥（KEY）',
        'type'  => 'password',
        'value' => '',
        'tip'   => 'V1 协议必填，用于 MD5 签名；V2 协议可留空',
        'size'  => 200,
    ],
    'merchant_private_key' => [
        'title' => '商户私钥',
        'type'  => 'textarea',
        'value' => '',
        'tip'   => 'V2 协议必填，用于请求签名。可粘贴完整 PEM（含 BEGIN/END 行）或纯 base64 单行',
    ],
    'platform_public_key' => [
        'title' => '平台公钥',
        'type'  => 'textarea',
        'value' => '',
        'tip'   => 'V2 协议必填，用于验签异步通知。可粘贴完整 PEM（含 BEGIN/END 行）或纯 base64 单行',
    ],
    'pay_type' => [
        'title'   => '支付方式',
        'type'    => 'radio',
        'value'   => 'wxpay',
        'options' => [
            'wxpay'        => '微信支付',
            'alipay'       => '支付宝',
            'qqpay'        => 'QQ钱包',
            'bank'         => '网银支付',
            'jdpay'        => '京东支付',
            'douyinpay'    => '抖音支付',
            'paypal'       => 'PayPal',
            'usdt'         => 'USDT',
            'stripepay'    => 'Stripe',
            'stripealipay' => 'Stripe支付宝',
            'stripewxpay'  => 'Stripe微信',
            'all'          => '由平台收银台选择',
        ],
    ],
    'channel_id' => [
        'title' => '自定义通道ID',
        'type'  => 'text',
        'value' => '',
        'tip'   => '选填，对应平台「进件商户列表」的ID；未进件请留空',
        'size'  => 200,
    ],
    'v1_request' => [
        'title'   => 'V1 发起方式',
        'type'    => 'radio',
        'value'   => 'submit',
        'options' => [
            'submit' => '页面跳转（submit.php）',
            'mapi'   => '接口下单（mapi.php）',
        ],
    ],
    'v2_request' => [
        'title'   => 'V2 发起方式',
        'type'    => 'radio',
        'value'   => 'submit',
        'options' => [
            'submit' => '页面跳转（/api/pay/submit）',
            'create' => '接口下单（/api/pay/create）',
        ],
    ],
    'device' => [
        'title'   => '设备类型',
        'type'    => 'radio',
        'value'   => 'pc',
        'options' => [
            'pc'     => '电脑浏览器',
            'mobile' => '手机浏览器',
            'wechat' => '微信内浏览器',
            'alipay' => '支付宝客户端',
            'qq'     => '手机QQ内浏览器',
        ],
    ],
];
