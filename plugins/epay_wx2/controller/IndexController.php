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

namespace gateway\epay_wx2\controller;

use app\home\controller\BaseController;
use gateway\epay_wx2\EpayWx2;
use gateway\epay_wx2\lib\PayClient;

/**
 * 易支付回调处理
 *
 * 外部地址（由 AppInit 的 gateway 路由转发到本控制器）：
 *   异步通知  网站地址/gateway/epay/index/notifyHandle
 *   同步跳转  网站地址/gateway/epay/index/returnHandle
 *
 * 易支付的异步通知与同步跳转都是 GET 方式携带参数，字段一致。
 *
 * @title 易支付回调
 * @desc 接收易支付的支付结果通知并完成入账
 * @author 空雨不流泪
 * @version 1.0.0
 * @link https://www.kybll.cn/
 */
class IndexController extends BaseController
{
    /**
     * 异步通知
     *
     * 处理成功必须原样输出 success，否则易支付平台会按失败重试。
     */
    public function notifyHandle()
    {
        echo $this->handleNotify($_GET) ? 'success' : 'fail';
    }

    /**
     * 同步跳转
     *
     * 无论验签结果如何都跳回订单页，实际入账以异步通知为准；
     * 这里同样执行一次入账，是为了应对部分平台异步通知延迟的场景。
     */
    public function returnHandle()
    {
        $this->handleNotify($_GET);

        $tmpOrderId = (string)($_GET['out_trade_no'] ?? '');

        if ($tmpOrderId === '') {
            return redirect((string)configuration('website_url'));
        }

        # 系统内置：优先跳到订单自身的 return_url，否则回首页
        return get_gateway_return_url($tmpOrderId);
    }

    /**
     * 统一回调处理：校验商户 → 验签 → 校验交易状态 → 入账
     *
     * @param array $data 回调的 GET 参数
     * @return bool 是否处理成功
     */
    private function handleNotify(array $data)
    {
        if (empty($data)) {
            return false;
        }

        $plugin = new EpayWx2();
        $config = $plugin->getConfig();

        # 快速挡掉与本商户无关的请求
        if (trim((string)($data['pid'] ?? '')) !== trim((string)($config['pid'] ?? ''))) {
            return false;
        }

        # 必须先验签，否则任何人都能伪造一条“支付成功”通知把订单改成已支付
        $client = new PayClient($config);
        if (!$client->verifyNotify($data)) {
            return false;
        }

        if ((string)($data['trade_status'] ?? '') !== 'TRADE_SUCCESS') {
            return false;
        }

        try {
            # 异步与本地的同步跳转都会走到这里，order_pay_handle 内部对已支付订单已做幂等处理
            order_pay_handle([
                'tmp_order_id' => (string)($data['out_trade_no'] ?? ''),
                'amount'       => (string)($data['money'] ?? ''),
                # 存易支付订单号，原路退款时作为 trade_no 使用
                'trans_id'     => (string)($data['trade_no'] ?? ''),
                'currency'     => 'CNY',
                'paid_time'    => date('Y-m-d H:i:s'),
                'gateway'      => $plugin->info['name'],
            ]);
        } catch (\Exception $e) {
            return false;
        }

        return true;
    }
}
