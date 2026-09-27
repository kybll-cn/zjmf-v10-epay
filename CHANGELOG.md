# 更新日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.0.0] - 2026-09-27

### 新增

- 易支付通用支付接入（智简魔方 V10 `gateway` 接口类插件）
  - `plugins/epay` —— 母版通用通道（标识 `Epay`）
  - `plugins/epay_wx` —— 微信易支付渠道（标识 `EpayWx`）
  - `plugins/epay_wx2` —— 微信易支付②渠道（标识 `EpayWx2`），多供应商并存示例
  - `plugins/epay_alipay` —— 支付宝渠道（标识 `EpayAlipay`），默认走 V2 协议
- **V1 / V2 双协议**：后台单选切换，V1 走 MD5 签名 + `submit.php` / `mapi.php`，
  V2 走 SHA256WithRSA 签名 + `/api/pay/submit` / `/api/pay/create`
- **多支付方式**：微信 / 支付宝 / QQ钱包 / 网银 / 京东 / 抖音 / PayPal / USDT / Stripe，
  另可选「由平台收银台选择」（不下发 `type`）
- **原路退款**：实现 `HandleRefund`，V1 走 `api.php?act=refund`、V2 走 `api/pay/refund`
- **多供应商并存**：每个渠道独立配置 PID / KEY / 密钥对，各走各的商户账号，互不影响
- **V2 密钥免整理**：同时接受完整 PEM 与平台只给的纯 base64 单行，自动补 PEM 头与按 64 字符折行，
  PKCS#8（`PRIVATE KEY`）与 PKCS#1（`RSA PRIVATE KEY`）双头尝试
- **V2 接口返回验签**：下单返回报文用平台公钥验签，可及时发现「公钥与商户不匹配」的配置错误
- 图标随渠道生成（母版绿蓝渐变 / 微信绿 / 支付宝蓝），无需自备素材
- 工具链：
  - `tools/new_channel.py` —— 一条命令新增渠道（复制骨架 + 改目录名/类名/命名空间/入口方法名 + 改默认配置 + 换图标）
  - `tools/make_icon.py` —— 生成 128×128 渠道图标
  - `tools/verify.py` —— 交付前静态校验，在无 PHP 运行时环境下核对全部插件契约
- `build.py` —— 发行打包，一插件一 zip，zip 内保留 V10 要求的安装目录名

### 说明

- 易支付平台不支持「一个商户号下发多种支付方式」的统一收银台语义时，
  「多支付方式」靠 `type` 参数实现；「多供应商」则必须靠多个插件目录，
  这是 V10 内核结构决定的，详见 README §4。
- 收银台 HTML 由内核用 jQuery `.html()` 注入，**内联 `<script>` 不执行**，
  因此支付页采用「POST 表单 + 提交按钮」形态，不做自动跳转。

[1.0.0]: https://github.com/kybll-cn/zjmf-v10-epay/releases/tag/v1.0.0
