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

namespace gateway\epay_alipay;

use app\common\lib\Plugin;
use gateway\epay_alipay\lib\PayClient;

/**
 * 易支付 —— 通用支付接口插件（母版）
 *
 * 一个插件实例 = 后台「支付接口」列表里的一个支付通道。
 * 需要对接多个供应商（例如两家不同的微信易支付）时，不要改这个目录，
 * 而是用包内的 tools/new_channel.py 从本目录派生出独立实例，各自配置互不影响。
 *
 * @title 易支付
 * @desc 彩虹易支付通用接口，支持 V1(MD5) / V2(RSA) 双协议、多种支付方式与原路退款
 * @author 空雨不流泪
 * @version 1.0.0
 * @link https://www.kybll.cn/
 * @namespace gateway\epay_alipay
 * @see https://www.ezfp.cn/doc/ 易支付 V2 接口规范
 */
class EpayAlipay extends Plugin
{
    public $info = [
        # 插件标识，必须与目录名 epay 的大驼峰形式一致（系统按此规则定位类）
        'name'        => 'EpayAlipay',
        'title'       => '易支付',
        'description' => '彩虹易支付通用接口，支持 V1(MD5)/V2(RSA) 双协议、微信/支付宝等支付方式与原路退款',
        'author'      => '空雨不流泪',
        'version'     => '1.0.0',
        'help_url'    => 'https://www.kybll.cn/',
        'author_url'  => 'https://www.kybll.cn/',
        # 留空则使用插件目录下的同名 png 作为支付图标
        'url'         => '',
    ];

    /**
     * 临时订单号生成规则
     * 1 = 毫秒时间戳 + 8 位随机（21-22 位，默认）；2 = 秒时间戳 + 8 位随机（18 位）；3 = 10 位随机
     * 易支付平台对商户订单号一般限制 32 位以内，规则 1 安全可用。
     */
    public $orderRule = 1;

    /**
     * 插件安装
     *
     * @return bool
     */
    public function install()
    {
        return true;
    }

    /**
     * 插件卸载
     *
     * 不要在这里 try/catch 数据库异常，直接抛出由上层回滚。
     *
     * @return bool
     */
    public function uninstall()
    {
        return true;
    }

    /**
     * 发起支付
     *
     * V10 按「插件标识 + Handle」反射调用本方法，返回值作为 HTML 注入前台收银台弹窗。
     *
     * @param array $param 系统传入：out_trade_no / client / product / global / finance
     * @return string
     */
    public function EpayAlipayHandle($param)
    {
        $client = new PayClient($this->getConfig());

        return $client->buildPayHtml(
            is_array($param) ? $param : [],
            $this->callbackUrl('notifyHandle'),
            $this->callbackUrl('returnHandle')
        );
    }

    /**
     * 原路退款
     *
     * V10 通过「插件标识 + HandleRefund」探测本插件是否支持退到原支付渠道。
     *
     * @param array $param transaction_number / amount / out_request_no / total_fee
     * @return array {status:200,data:{trade_no}} 或 {status:400,msg}
     */
    public function EpayAlipayHandleRefund($param)
    {
        $client = new PayClient($this->getConfig());

        return $client->refund(is_array($param) ? $param : []);
    }

    /**
     * 构造外部回调地址：网站地址/gateway/插件目录/控制器/方法
     *
     * 派生新实例后目录名随之变化，这里动态计算，无需手改。
     *
     * @param string $action 回调方法名
     * @return string
     */
    private function callbackUrl($action)
    {
        $domain = rtrim((string)configuration('website_url'), '/');

        return $domain . '/gateway/' . parse_name($this->getName()) . '/index/' . $action;
    }
}
