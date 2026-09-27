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

namespace gateway\epay_wx\lib;

/**
 * 易支付协议客户端
 *
 * 统一封装两套协议，对上层（插件主类 / 回调控制器）只暴露三个方法：
 *   buildPayHtml()  发起支付，返回注入收银台的 HTML
 *   verifyNotify()  校验异步 / 同步通知签名
 *   refund()        原路退款
 *
 * ── 协议差异 ────────────────────────────────────────────────
 * V1（MD5）
 *   下单：{apiurl}submit.php（页面跳转，GET/POST）或 {apiurl}mapi.php（接口下单，返回JSON）
 *   退款：POST {apiurl}api.php  act=refund
 *   验签：非空参数（剔除 sign/sign_type）按参数名 ASCII 升序拼 a=b&c=d，末尾直接拼 KEY，取 md5 小写
 * V2（SHA256WithRSA）
 *   下单：{apiurl}api/pay/submit（页面跳转）或 {apiurl}api/pay/create（接口下单，返回JSON）
 *   退款：POST {apiurl}api/pay/refund
 *   验签：同样的待签名串，用商户私钥 openssl_sign(OPENSSL_ALGO_SHA256) 后 base64；
 *         验签用平台公钥 openssl_verify；请求须带 timestamp
 *   成功码：V1 code==1，V2 code==0（两套协议约定不同，注意区分）
 *
 * @author 空雨不流泪
 * @link https://www.kybll.cn/
 * @version 1.0.0
 */
class PayClient
{
    /** @var array 完整插件配置 */
    private $config = [];

    /** @var string v1|v2 */
    private $protocol = 'v1';

    /** @var string 接口地址，恒以 / 结尾 */
    private $apiurl = '';

    /** @var string 商户ID */
    private $pid = '';

    /** @var string 商户密钥（V1） */
    private $key = '';

    /** @var string 商户私钥（V2） */
    private $privateKey = '';

    /** @var string 平台公钥（V2） */
    private $publicKey = '';

    /** @var string 支付方式 */
    private $payType = '';

    /** @var string 自定义通道ID */
    private $channelId = '';

    /** @var string 设备类型 */
    private $device = 'pc';

    public function __construct(array $config)
    {
        $this->config = $config;

        $protocol = strtolower(trim((string)($config['protocol'] ?? 'v1')));
        $this->protocol = in_array($protocol, ['v1', 'v2'], true) ? $protocol : 'v1';

        $apiurl = trim((string)($config['apiurl'] ?? ''));
        if ($apiurl !== '') {
            # 容错：商户常忘记写结尾斜杠
            $apiurl = rtrim($apiurl, '/') . '/';
        }
        $this->apiurl = $apiurl;

        $this->pid        = trim((string)($config['pid'] ?? ''));
        $this->key        = trim((string)($config['key'] ?? ''));
        $this->privateKey = trim((string)($config['merchant_private_key'] ?? ''));
        $this->publicKey  = trim((string)($config['platform_public_key'] ?? ''));
        $this->payType    = trim((string)($config['pay_type'] ?? ''));
        $this->channelId  = trim((string)($config['channel_id'] ?? ''));
        $this->device     = trim((string)($config['device'] ?? 'pc')) ?: 'pc';
    }

    /* =====================================================================
     * 对外接口
     * ===================================================================*/

    /**
     * 发起支付
     *
     * @param array  $param     V10 传入的支付参数
     * @param string $notifyUrl 异步通知地址
     * @param string $returnUrl 同步跳转地址
     * @return string 注入到收银台的 HTML
     */
    public function buildPayHtml(array $param, $notifyUrl, $returnUrl)
    {
        try {
            if ($this->apiurl === '' || $this->pid === '') {
                return $this->errorHtml('请先在后台配置接口地址与商户ID');
            }

            $order = $this->buildOrder($param, $notifyUrl, $returnUrl);

            if ($this->protocol === 'v1') {
                if ($this->mode('v1_request', 'submit') === 'mapi') {
                    # clientip / device 也是请求参数，必须一并参与签名后再提交
                    $order['clientip'] = $this->clientIp();
                    $order['device']   = $this->device;
                    $url = $this->apiCreate($this->apiurl . 'mapi.php', $this->signParams($order, 'v1'), 'v1');

                    return is_array($url) ? $this->errorHtml($url['msg']) : $this->linkHtml($url);
                }

                return $this->formHtml($this->apiurl . 'submit.php', $this->signParams($order, 'v1'));
            }

            if ($this->mode('v2_request', 'submit') === 'create') {
                # method / clientip 同样要参与签名
                $order['method']   = 'jump';
                $order['clientip'] = $this->clientIp();
                $url = $this->apiCreate($this->apiurl . 'api/pay/create', $this->signParams($order, 'v2'), 'v2');

                return is_array($url) ? $this->errorHtml($url['msg']) : $this->linkHtml($url);
            }

            return $this->formHtml($this->apiurl . 'api/pay/submit', $this->signParams($order, 'v2'));
        } catch (\Exception $e) {
            return $this->errorHtml($e->getMessage());
        }
    }

    /**
     * 校验异步 / 同步通知的签名
     *
     * @param array $data 通知的 GET 参数
     * @return bool
     */
    public function verifyNotify(array $data)
    {
        try {
            if (empty($data['sign'])) {
                return false;
            }

            if ($this->protocol === 'v2') {
                return $this->verifyV2($data);
            }

            return $this->verifyV1($data);
        } catch (\Exception $e) {
            return false;
        }
    }

    /**
     * 原路退款
     *
     * @param array $param V10 传入：transaction_number / amount / out_request_no / total_fee
     * @return array {status:200,data:{trade_no}} 或 {status:400,msg}
     */
    public function refund(array $param)
    {
        try {
            if ($this->apiurl === '' || $this->pid === '') {
                return ['status' => 400, 'msg' => '接口地址或商户ID未配置'];
            }

            $tradeNo = trim((string)($param['transaction_number'] ?? ''));
            if ($tradeNo === '') {
                return ['status' => 400, 'msg' => '缺少原交易流水号，无法原路退款'];
            }

            $money = number_format((float)($param['amount'] ?? 0), 2, '.', '');
            if ((float)$money <= 0) {
                return ['status' => 400, 'msg' => '退款金额不正确'];
            }

            # 退款请求号：用于部分退款时标识本次请求，保证同一交易号下唯一
            $requestNo = trim((string)($param['out_request_no'] ?? ''));

            if ($this->protocol === 'v1') {
                # V1 退款接口用商户密钥明文校验，不走 sign（需商户后台先开启退款API开关）
                # 文档把 act 挂在 URL 上，这里 URL 与 body 各带一份，兼容不同平台实现
                $resp = $this->httpPost($this->apiurl . 'api.php?act=refund', [
                    'act'      => 'refund',
                    'pid'      => $this->pid,
                    'key'      => $this->key,
                    'trade_no' => $tradeNo,
                    'money'    => $money,
                ]);

                $json = json_decode($resp, true);
                # V1 退款成功 code == 0
                if (is_array($json) && isset($json['code']) && (int)$json['code'] === 0) {
                    return [
                        'status' => 200,
                        'data'   => ['trade_no' => $json['trade_no'] ?? $requestNo],
                    ];
                }

                return [
                    'status' => 400,
                    'msg'    => is_array($json) ? (string)($json['msg'] ?? '退款失败') : '退款接口返回异常',
                ];
            }

            $signed = $this->signParams([
                'pid'      => $this->pid,
                'trade_no' => $tradeNo,
                'money'    => $money,
            ], 'v2');

            $resp = $this->httpPost($this->apiurl . 'api/pay/refund', $signed);
            $json = json_decode($resp, true);

            # V2 成功 code == 0
            if (is_array($json) && isset($json['code']) && (int)$json['code'] === 0) {
                return [
                    'status' => 200,
                    'data'   => ['trade_no' => $json['trade_no'] ?? $requestNo],
                ];
            }

            return [
                'status' => 400,
                'msg'    => is_array($json) ? (string)($json['msg'] ?? '退款失败') : '退款接口返回异常',
            ];
        } catch (\Exception $e) {
            return ['status' => 400, 'msg' => $e->getMessage()];
        }
    }

    /* =====================================================================
     * 下单参数拼装
     * ===================================================================*/

    /**
     * 组装公共下单参数
     */
    private function buildOrder(array $param, $notifyUrl, $returnUrl)
    {
        $outTradeNo = trim((string)($param['out_trade_no'] ?? ''));
        if ($outTradeNo === '') {
            throw new \Exception('缺少商户订单号');
        }

        $money = number_format((float)($param['finance']['total'] ?? 0), 2, '.', '');
        if ((float)$money <= 0) {
            throw new \Exception('支付金额必须大于 0');
        }

        $subject = '';
        if (!empty($param['product']) && is_array($param['product'])) {
            $subject = (string)reset($param['product']);
        }
        if ($subject === '') {
            $subject = (string)($param['global']['website_name'] ?? '商品');
        }
        # 易支付限制商品名 127 字节，超出部分自动截断
        $subject = $this->cutStr($subject, 127);

        $order = [
            'pid'          => $this->pid,
            'out_trade_no' => $outTradeNo,
            'notify_url'   => $notifyUrl,
            'return_url'   => $returnUrl,
            'name'         => $subject,
            'money'        => $money,
        ];

        # pay_type 为 all 表示不带 type，由平台收银台自行选择
        if ($this->payType !== '' && $this->payType !== 'all') {
            $order['type'] = $this->payType;
        }

        if ($this->channelId !== '') {
            $order['channel_id'] = $this->channelId;
        }

        return $order;
    }

    /**
     * 追加签名（及 V2 的 timestamp）
     */
    private function signParams(array $params, $protocol)
    {
        if ($protocol === 'v2') {
            # timestamp 必须参与签名
            $params['timestamp'] = time();
            $params['sign']      = $this->signV2($params);
            $params['sign_type'] = 'RSA';

            return $params;
        }

        $params['sign']      = $this->signV1($params);
        $params['sign_type'] = 'MD5';

        return $params;
    }

    /* =====================================================================
     * 接口下单（mapi.php / api/pay/create）
     * ===================================================================*/

    /**
     * @return string|array 成功返回支付地址，失败返回 ['msg'=>...]
     */
    private function apiCreate($url, array $params, $protocol)
    {
        $resp = $this->httpPost($url, $params);
        $json = json_decode($resp, true);

        if (!is_array($json)) {
            return ['msg' => '接口返回异常：' . $this->cutStr((string)$resp, 200)];
        }

        # V1 成功 code==1，V2 成功 code==0
        $okCode = $protocol === 'v1' ? 1 : 0;
        if (!isset($json['code']) || (int)$json['code'] !== $okCode) {
            return ['msg' => '接口返回失败：' . (string)($json['msg'] ?? '未知错误')];
        }

        if ($protocol === 'v2') {
            # 配了平台公钥就按规范验签；失败直接报错，避免公钥配错却静默跑下去
            if ($this->publicKey !== '' && !$this->verifyV2($json)) {
                return ['msg' => '接口返回验签失败，请核对平台公钥是否与当前商户匹配'];
            }

            return (string)($json['pay_info'] ?? '');
        }

        # V1：payurl / qrcode / urlscheme 三选一返回
        foreach (['payurl', 'qrcode', 'urlscheme'] as $field) {
            if (!empty($json[$field])) {
                return (string)$json[$field];
            }
        }

        return '';
    }

    /* =====================================================================
     * 签名 / 验签
     * ===================================================================*/

    /**
     * V1：MD5 签名（小写）
     */
    private function signV1(array $params)
    {
        return md5($this->buildSignString($params) . $this->key);
    }

    private function verifyV1(array $data)
    {
        if ($this->key === '') {
            return false;
        }

        return hash_equals($this->signV1($data), strtolower((string)$data['sign']));
    }

    /**
     * V2：SHA256WithRSA 签名（base64）
     */
    private function signV2(array $params)
    {
        $this->assertOpenssl();

        $pem = $this->normalizePrivateKey();

        $signature = '';
        $ok = @openssl_sign($this->buildSignString($params), $signature, $pem, OPENSSL_ALGO_SHA256);
        if (!$ok) {
            throw new \Exception('商户私钥签名失败，请检查私钥内容是否为平台生成的密钥对');
        }

        return base64_encode($signature);
    }

    private function verifyV2(array $data)
    {
        $this->assertOpenssl();

        if ($this->publicKey === '') {
            return false;
        }

        $signature = base64_decode((string)$data['sign'], true);
        if ($signature === false) {
            return false;
        }

        $pem = $this->normalizePublicKey();

        # openssl_verify 返回 1=通过，0=不通过，-1/其它=出错
        return @openssl_verify($this->buildSignString($data), $signature, $pem, OPENSSL_ALGO_SHA256) === 1;
    }

    /**
     * 构造待签名串：非空参数（剔除 sign/sign_type），按参数名 ASCII 升序，拼 a=b&c=d
     */
    private function buildSignString(array $params)
    {
        unset($params['sign'], $params['sign_type']);

        $pairs = [];
        foreach ($params as $key => $value) {
            # 数组与空值不参与签名
            if (is_array($value) || $value === '' || $value === null) {
                continue;
            }
            $pairs[(string)$key] = (string)$value;
        }

        # SORT_STRING 才是真正的 ASCII 码升序，默认 SORT_REGULAR 会把纯数字键当数字比较
        ksort($pairs, SORT_STRING);

        $list = [];
        foreach ($pairs as $key => $value) {
            $list[] = $key . '=' . $value;
        }

        return implode('&', $list);
    }

    /* =====================================================================
     * 密钥规整
     * ===================================================================*/

    private function assertOpenssl()
    {
        if (!function_exists('openssl_sign') || !extension_loaded('openssl')) {
            throw new \Exception('服务器未启用 PHP openssl 扩展，无法使用 V2（RSA）协议');
        }
    }

    /**
     * 商户私钥归整：支持完整 PEM，也支持平台只给的纯 base64 单行
     */
    private function normalizePrivateKey()
    {
        if ($this->privateKey === '') {
            throw new \Exception('V2 协议需要配置商户私钥');
        }

        if (strpos($this->privateKey, '-----BEGIN') !== false) {
            return $this->privateKey;
        }

        $body = $this->wrapBase64($this->privateKey);

        # 依次尝试 PKCS#8 / PKCS#1 头，哪个能被解析就用哪个
        foreach (['PRIVATE KEY', 'RSA PRIVATE KEY'] as $header) {
            $pem = "-----BEGIN {$header}-----\n{$body}-----END {$header}-----\n";
            if (@openssl_pkey_get_private($pem) !== false) {
                return $pem;
            }
        }

        throw new \Exception('商户私钥格式无法识别，请确认复制的是平台生成的商户私钥');
    }

    /**
     * 平台公钥归整
     */
    private function normalizePublicKey()
    {
        if (strpos($this->publicKey, '-----BEGIN') !== false) {
            return $this->publicKey;
        }

        $body = $this->wrapBase64($this->publicKey);

        foreach (['PUBLIC KEY', 'RSA PUBLIC KEY'] as $header) {
            $pem = "-----BEGIN {$header}-----\n{$body}-----END {$header}-----\n";
            if (@openssl_pkey_get_public($pem) !== false) {
                return $pem;
            }
        }

        throw new \Exception('平台公钥格式无法识别，请确认复制的是平台提供的公钥');
    }

    /**
     * 纯 base64 按 64 字符折行，便于包上 PEM 头尾
     */
    private function wrapBase64($key)
    {
        $key = preg_replace('/\s+/', '', (string)$key);

        return chunk_split($key, 64, "\n");
    }

    /* =====================================================================
     * 输出 HTML（注入收银台弹窗，经 jQuery .html() 插入，内联 script 不会执行）
     * ===================================================================*/

    /**
     * 页面跳转模式：输出 POST 表单，由用户点击提交（官方推荐 POST，不易被劫持）
     */
    private function formHtml($action, array $params)
    {
        $html = '<form action="' . $this->esc($action) . '" method="post" target="_blank" '
            . 'style="text-align:center;padding:24px 0;">';

        foreach ($params as $key => $value) {
            $html .= '<input type="hidden" name="' . $this->esc($key) . '" value="' . $this->esc((string)$value) . '">';
        }

        $html .= '<button type="submit" style="display:inline-block;padding:10px 32px;font-size:15px;'
            . 'line-height:1.5;color:#fff;background:#07c160;border:none;border-radius:4px;cursor:pointer;">'
            . '立即前往支付</button></form>';

        return $html;
    }

    /**
     * 接口下单模式：输出跳转链接
     */
    private function linkHtml($url)
    {
        if ($url === '') {
            return $this->errorHtml('接口未返回支付地址，请检查商户参数或改用页面跳转方式');
        }

        $safe = $this->esc($url);
        $tip = '';

        # 手机端可被 weixin:// 、alipays:// 等 scheme 直接唤起，PC 端需扫码，故给出提示
        if (stripos($url, 'http://') !== 0 && stripos($url, 'https://') !== 0) {
            $tip = '<p style="margin:12px 0 0;font-size:12px;color:#909399;line-height:1.7;">'
                . '该地址为支付唤起链接，请在<b>手机浏览器</b>中打开，或复制后发送到手机打开。</p>';
        }

        return '<div style="text-align:center;padding:24px 0;">'
            . '<a href="' . $safe . '" target="_blank" rel="noopener noreferrer" '
            . 'style="display:inline-block;padding:10px 32px;font-size:15px;line-height:1.5;color:#fff;'
            . 'background:#07c160;border-radius:4px;text-decoration:none;">立即前往支付</a>'
            . $tip
            . '</div>';
    }

    /**
     * 错误提示
     */
    private function errorHtml($message)
    {
        return '<div style="padding:20px 0;text-align:center;color:#f56c6c;font-size:14px;line-height:1.7;">'
            . $this->esc($message) . '</div>';
    }

    private function esc($string)
    {
        return htmlspecialchars((string)$string, ENT_QUOTES, 'UTF-8');
    }

    /* =====================================================================
     * 工具
     * ===================================================================*/

    /**
     * 读取配置里的二选一枚举值
     */
    private function mode($key, $default)
    {
        $value = trim((string)($this->config[$key] ?? ''));

        return $value === '' ? $default : $value;
    }

    /**
     * 取发起支付的客户端 IP
     */
    private function clientIp()
    {
        if (function_exists('request')) {
            try {
                $ip = request()->ip();
                if (!empty($ip)) {
                    return $ip;
                }
            } catch (\Exception $e) {
                # 忽略，走兜底
            }
        }

        return $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0';
    }

    /**
     * 按字节数安全截断（不切坏多字节字符）
     */
    private function cutStr($string, $maxBytes)
    {
        $string = trim(preg_replace('/\s+/u', ' ', (string)$string));
        if ($string === '' || strlen($string) <= $maxBytes) {
            return $string;
        }

        $result = '';
        $length = 0;
        $chars = preg_split('//u', $string, -1, PREG_SPLIT_NO_EMPTY) ?: [];

        foreach ($chars as $char) {
            $size = strlen($char);
            if ($length + $size > $maxBytes) {
                break;
            }
            $result .= $char;
            $length += $size;
        }

        return $result;
    }

    /**
     * POST 请求（form-urlencoded），返回原始响应体
     */
    private function httpPost($url, array $data, $timeout = 15)
    {
        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_TIMEOUT, $timeout);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 10);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($data));
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            'Accept: */*',
            'Accept-Language: zh-CN,zh;q=0.8',
            'Content-Type: application/x-www-form-urlencoded; charset=UTF-8',
            'Connection: close',
        ]);
        curl_setopt($ch, CURLOPT_HEADER, false);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_FOLLOWLOCATION, false);

        $response = curl_exec($ch);
        $error    = curl_error($ch);
        curl_close($ch);

        if ($response === false) {
            throw new \Exception('请求支付接口失败：' . $error);
        }

        return $response;
    }
}
