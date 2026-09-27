# zjmf-v10-epay — 易支付通用支付插件集（智简魔方 V10）

对接 [彩虹易支付](https://www.ezfp.cn/)（及所有同协议平台）的 **智简魔方 V10 `gateway` 接口类插件**，
**一套代码同时支持 V1（MD5）与 V2（SHA256WithRSA）两套协议**，并原生解决
「一个站点挂多个易支付供应商」的问题。

- 作者：空雨不流泪 · 官方网站 <https://www.kybll.cn/>
- 易支付 V2 接口规范 <https://www.ezfp.cn/doc/>
- 开源协议：GPL-3.0

---

## 1. 特性

| 特性 | 说明 |
|---|---|
| V1 / V2 双协议 | 后台一个单选切换，无需换插件。V1 走 `submit.php`/`mapi.php`，V2 走 `/api/pay/*` |
| 多种支付方式 | 微信 / 支付宝 / QQ钱包 / 网银 / 京东 / 抖音 / PayPal / USDT / Stripe，或交给平台收银台选 |
| 原路退款 | 实现 `HandleRefund`，后台可选「原支付路径」退回，V1 / V2 都支持 |
| 多供应商并存 | 每个渠道独立配置 PID / KEY / 密钥对，可同时挂多家易支付分流收款 |
| 一键派生实例 | `python tools/new_channel.py --dir epay_wx3 --name "易支付-微信③"` |
| 免密钥粘贴 | V2 密钥同时吃完整 PEM 与平台只给的**纯 base64 单行**，自动补头折行 |
| 接口返回验签 | V2 下单返回会用平台公钥验签，及时发现「公钥与商户不匹配」这类配置错误 |
| 零素材依赖 | 渠道图标由脚本生成，不需要自己找图 |
| 可离线校验 | `tools/verify.py` 在没有 PHP 运行时的机器上也能核对全部插件契约 |

预置四个渠道：

| 目录 | 插件标识 | 后台显示名 | 预设协议 | 用途 |
|---|---|---|---|---|
| `plugins/epay` | `Epay` | 易支付 | V1 | **母版**，通用通道 |
| `plugins/epay_wx` | `EpayWx` | 易支付-微信 | V1 | 微信易支付 |
| `plugins/epay_wx2` | `EpayWx2` | 易支付-微信② | V1 | 多供应商示例（第二家微信） |
| `plugins/epay_alipay` | `EpayAlipay` | 易支付-支付宝 | V2 | 支付宝通道（默认走 V2） |

> 四个渠道代码**完全同源**，只差目录名 / 类名 / 默认配置，全部由 `tools/new_channel.py` 生成。

---

## 2. 环境要求

| 项目 | 要求 |
|---|---|
| 系统 | 智简魔方 V10（后端 ThinkPHP 6 / PHP 7.4） |
| PHP 扩展 | `curl`（V2 接口下单与退款，以及回调）、`openssl`（**V2 协议必需**，签名验签）、`mbstring`（建议） |
| 网络 | 服务器需能访问你所用的易支付平台域名；站点需有可被外网访问的域名（接收异步回调） |
| 协议 | **强烈建议 HTTPS** |

---

## 3. 目录结构

```
zjmf-v10-epay/                        ← 仓库根
├── README.md
├── CHANGELOG.md
├── LICENSE                           ← GPL-3.0
├── build.py                          ← 发行打包（逐个渠道各打一个 zip）
├── plugins/                          ← 各渠道插件（每个都是一个独立的 V10 插件）
│   ├── epay/                         ← 母版
│   │   ├── Epay.php                  ← 主类：$info / install / uninstall / EpayHandle / EpayHandleRefund
│   │   ├── Epay.png                  ← 支付图标（V10 要求「插件标识.png」）
│   │   ├── config.php                ← 后台配置表单
│   │   ├── controller/
│   │   │   └── IndexController.php   ← 异步回调 notifyHandle / 同步回调 returnHandle
│   │   └── lib/
│   │       └── PayClient.php         ← 协议客户端（V1/V2 签名、下单、验签、退款）
│   ├── epay_wx/                      ← 同构
│   ├── epay_wx2/                     ← 同构
│   └── epay_alipay/                  ← 同构
├── tools/
│   ├── new_channel.py                ← 一键新增渠道
│   ├── make_icon.py                  ← 生成支付图标
│   └── verify.py                     ← 交付前静态校验
└── dist/                             ← 打包产物（不进版本库）
```

---

## 4. 为什么是「多个插件」而不是「一个插件配多个商户」

这不是偷懒，是 V10 的内核结构决定的。

V10 后台「接口管理 → 支付接口」的列表来自 `app/admin/model/PluginModel.php::pluginList()`：

```php
$dirs = array_map('basename', glob(WEB_ROOT . "plugins/{$module}/*", GLOB_ONLYDIR));
...
$plugins[$plugin['name']] = $plugin;   // 以插件标识为键
```

两件事同时成立：

1. 列表是**扫描目录**得到的；
2. 结果数组**以插件标识为键**，同名只能有一条。

而且插件标识还要能反查出类名（`get_plugin_class()` → `gateway\{目录}\{标识}`）。
再看下单链路 `OrderTmpModel::startPay()`，调插件时传入的参数只有
`out_trade_no` / `client` / `product` / `global` / `finance`——**不包含「用哪个商户」**。

所以：

> **一个插件目录 = 后台列表里的一行 = 一套商户配置。**
> 想让用户自己挑供应商，就必须有多个插件目录，没有别的口子。

这也正是官方的做法——`EpayWx.zip`、`EpayAli.zip` 就是**一个支付方式一个插件目录**。

本插件把这件事的成本压到一条命令（见 §8）。

---

## 5. 安装

### 方式一：用 Release 里的安装包（推荐）

1. 到 [Releases](https://github.com/kybll-cn/zjmf-v10-epay/releases) 下载需要的渠道包，例如 `EpayWx-1.0.0.zip`；
2. 解压得到 `epay_wx/` 目录；
3. 把整个目录上传到站点 `public/plugins/gateway/` 下，最终路径为
   `public/plugins/gateway/epay_wx/`；
4. 后台 →「系统 → 接口管理 → 支付接口」→ 点刷新，即可看到「易支付-微信」；
5. 点「安装」，再点「配置」填商户参数，最后「启用」。

> ⚠️ **目录名不要改**。V10 按 `parse_name($目录名, 1)` 推导类名
> （`epay_wx` → `EpayWx`），改名会导致插件加载不到。

### 方式二：clone 仓库

```bash
git clone --depth 1 https://github.com/kybll-cn/zjmf-v10-epay.git epay
cp -r epay/plugins/epay         /path/to/site/public/plugins/gateway/
cp -r epay/plugins/epay_wx      /path/to/site/public/plugins/gateway/
cp -r epay/plugins/epay_wx2     /path/to/site/public/plugins/gateway/
cp -r epay/plugins/epay_alipay  /path/to/site/public/plugins/gateway/
```

注意 `epay_wx` 这些**目录名必须保持原样**，且**只需要复制你要用的那几个**。

### 方式三：从源码自行打包

```bash
cd epay
python build.py            # 生成 dist/EpayWx-1.0.0.zip 等
```

---

## 6. 易支付侧准备

1. 在你的易支付平台注册商户，进入 **商户后台**；
2. 拿到 **商户ID（PID）**；
3. 按平台版本取密钥：
   - **V1 平台**：商户后台 → 商户资料 / API 信息 → **商户密钥（KEY）**；
   - **V2 平台**：商户后台 → 个人资料 → API 信息 → **生成商户 RSA 密钥对**，
     得到 **商户私钥** 与 **平台公钥**（平台公钥即「易支付公钥」，用它对通知验签）。
4. 若要用**原路退款**：V1 平台需先在商户后台**开启「订单退款API接口」开关**，否则平台会拒绝退款请求。

**回调地址无需在平台后台填写**——本插件在下单时把 `notify_url` / `return_url` 直接传给平台，
形如 `https://你的域名/gateway/epay_wx/index/notifyHandle`，每个渠道指向自己的目录。

若平台要求配置「授权域名 / 白名单」，把站点域名加进去即可。

---

## 7. 后台配置项

| 配置项 | 说明 |
|---|---|
| **通道名称** | 后台支付接口列表与前台收银台显示的名字。**多个供应商时务必区分开**，例如「易支付-微信A」「易支付-微信B」 |
| **接口协议** | `V1` 用 MD5 签名走 `submit.php` / `mapi.php`；`V2` 用 RSA 签名走 `/api/pay/*` |
| **接口地址** | 平台地址，**须以 `/` 结尾**，如 `https://pay.example.com/`。写漏结尾斜杠插件会自动补上 |
| **商户ID（PID）** | 商户后台的商户编号 |
| **商户密钥（KEY）** | V1 必填，用于 MD5 签名。V2 可留空 |
| **商户私钥** | V2 必填。支持直接粘贴完整 PEM，也支持平台只给的**纯 base64 单行** |
| **平台公钥** | V2 必填。用于验签异步通知与接口返回 |
| **支付方式** | 决定 `type` 参数。选「由平台收银台选择」则不下发 `type` |
| **自定义通道ID** | 选填，对应平台「进件商户列表」的 ID。未进件请留空 |
| **V1 发起方式** | `页面跳转`：输出 POST 表单，用户点一下跳到平台收银台（**推荐**，不易被劫持）；`接口下单`：后端先请求 `mapi.php` 拿支付地址 |
| **V2 发起方式** | 同上，对应 `/api/pay/submit` 与 `/api/pay/create` |
| **设备类型** | 传给平台的 `device` 参数，接口下单模式下生效。电脑端一般选「电脑浏览器」 |

### 两套协议怎么选

- 平台文档里写「V1 旧版接口 / MD5 签名 / `submit.php`、`mapi.php`」→ 选 **V1**
- 平台文档里写「V2 / RSA 签名 / 时间戳 / `/api/pay/create`」→ 选 **V2**

拿不准就看商户后台的 API 信息页：有「商户密钥」就是 V1，有「商户私钥 / 平台公钥」就是 V2。
两者都有的平台，用 V2 更安全。

---

## 8. 多供应商怎么用

### 场景一：微信、支付宝各走一家易支付

后台装 `epay_wx` + `epay_alipay` 两个渠道，分别填两家的参数即可，互不影响。

### 场景二：两个微信支付，对接两个不同供应商

母版自带派生脚本，一条命令生成第二个微信渠道：

```bash
# 在仓库根目录执行
python tools/new_channel.py --dir epay_wx2 --name "易支付-微信②"
```

生成 `plugins/epay_wx2/`，上传到 `public/plugins/gateway/`，后台刷新即多出一行
「易支付-微信②」，填另一家供应商的 PID / 密钥即可。

### 场景三：还想再加第三个、第四个……

```bash
python tools/new_channel.py --dir epay_wx3                  # 名称按支付方式自动推导
python tools/new_channel.py --dir epay_alipay --pay-type alipay --protocol v2
python tools/new_channel.py --dir epay_ali2 --name-file name.txt   # 中文名走文件，避免 shell 乱码
python tools/new_channel.py --dir epay_wx3 --dry-run        # 先预览会改哪些文件
```

派生脚本会自动完成：复制骨架 → 改目录名 → 改类名与文件名 → 改命名空间与
`$info['name']` → 改支付入口方法名（`EpayHandle` → `EpayWx3Handle`）→ 改配置默认值 → 重新生成图标。
**回调地址里的目录名也会一并替换**，这是手工复制最容易漏、漏了就永远收不到回调的地方。

| 参数 | 说明 |
|---|---|
| `--dir` | 必填，新插件目录名（小写字母+下划线），如 `epay_wx3` |
| `--name` | 通道显示名。**中文在 Git Bash 下可能乱码**，可改用 `--name-file 文件`（UTF-8） |
| `--pay-type` | 默认支付方式：`wxpay`/`alipay`/`qqpay`/`bank`/`jdpay`/`douyinpay`/`paypal`/`usdt`… |
| `--protocol` | 默认协议：`v1` 或 `v2` |
| `--v1-request` / `--v2-request` | 发起方式：`submit` / `mapi`（V1），`submit` / `create`（V2） |
| `--template` | 以哪个目录为母版，默认 `epay` |
| `--dry-run` | 只预览会改哪些文件，不写盘 |
| `--force` | 目标目录已存在时先删除再生成 |

> 通道名称也可以在后台配置里随时改，不必重新派生。

---

## 9. 原路退款

插件实现了 `EpayHandleRefund`，后台退款时可选择「原支付路径」。

- **V1**：走 `api.php?act=refund`。需要先在易支付商户后台**开启「订单退款API接口」开关**，否则平台会拒绝。
- **V2**：走 `/api/pay/refund`。

退款金额、部分退款由系统传入；退款单号会回写成一笔负数流水。
如果平台不支持退款或开关没开，后台会给出平台的原始错误提示。

---

## 10. 工作原理

```
客户下单 → POST /console/v1/pay {gateway: "EpayWx"}
   │
   ├─ OrderTmpModel::pay() 生成临时订单号（毫秒时间戳+8位随机，20+ 位）
   ├─ plugin_reflection() 反射调用入口方法 EpayWxHandle($param)
   │
   ├─ V1：待签名串按 ASCII 升序拼接 → 末尾拼 KEY → md5 小写
   │      页面跳转：输出 POST 表单提交到 {接口地址}submit.php
   │      接口下单：请求 {接口地址}mapi.php 拿支付地址后渲染链接
   │
   ├─ V2：待签名串同上 → 商户私钥 openssl_sign(SHA256) → base64
   │      页面跳转：POST 表单提交到 {接口地址}api/pay/submit
   │      接口下单：请求 {接口地址}api/pay/create 拿支付地址（返回报文用平台公钥验签）
   │
   └─ 渲染支付页 HTML（注入收银台）
          ↓  客户完成支付
易支付 → GET https://你的域名/gateway/epay_wx/index/notifyHandle
   ├─ 校验 pid 归属
   ├─ V1 用 KEY 验签 / V2 用平台公钥验签
   ├─ 判断 trade_status == TRADE_SUCCESS
   ├─ order_pay_handle() 入账（临时订单号 / 金额 / 平台订单号 / 支付时间 / 渠道标识）
   └─ 原样输出 success（否则平台会重复回调）
```

前台同时会轮询 `/console/v1/pay/{id}/status` 感知支付结果，无需插件额外处理页面跳转。

**签名算法**（V1 / V2 一致）：

1. 剔除 `sign`、`sign_type` 与所有空值、非数组参数；
2. 剩余参数按参数名 **ASCII 升序**（PHP 用 `ksort($p, SORT_STRING)`）排序；
3. 拼成 `key1=value1&key2=value2…`；
4. V1：末尾**直接**拼接商户 KEY（无连接符），MD5 取 32 位小写；
   V2：用商户私钥 `openssl_sign(..., OPENSSL_ALGO_SHA256)` 后 base64。

> V2 请求必须携带 `timestamp`（10 位秒级），且**它参与签名**。

---

## 11. 与同类插件对比

| | 本插件 | `EpayWx.zip`（官方易支付微信） | `wx_pay`（微信直连） |
|---|---|---|---|
| 协议 | V1 + V2 双协议可切 | 仅 V1 | 微信官方 APIv3 |
| 支付方式切换 | 配置项切换，含平台收银台 | 固定微信 | 固定微信 |
| 多账号并存 | 母版+衍生脚本，一条命令 | 需手动复制改造 | 需手动复制改造 |
| 原路退款 | V1 / V2 都支持 | 视版本 | 支持 |
| 申请门槛 | 取决于上级易支付平台 | 同 | 需企业资质 |
| 适合场景 | 需灵活切换平台/协议/多供应商 | 单一供应商单一渠道 | 正规企业业务 |

---

## 12. 方法一览

| 方法 | 位置 | 作用 |
|---|---|---|
| `EpayHandle($param)` | 主类 | 支付入口，由内核反射调用；返回支付页 HTML 或错误数组 |
| `EpayHandleRefund($param)` | 主类 | 原路退款入口，由内核反射调用 |
| `install()` / `uninstall()` | 主类 | 安装 / 卸载钩子（本插件无需初始化数据，直接返回 `true`） |
| `notifyHandle()` | IndexController | 异步回调：验签 → 校验状态 → 入账 → 输出 `success` |
| `returnHandle()` | IndexController | 同步回调：入账后把用户送回财务页 |
| `PayClient::buildPayHtml()` | lib | 发起支付，返回注入收银台的 HTML |
| `PayClient::verifyNotify()` | lib | 校验异步 / 同步通知签名 |
| `PayClient::refund()` | lib | 原路退款 |

> 实例目录里的类名与方法名会把 `Epay` 换成对应前缀（如 `EpayWxHandle`）。

---

## 13. 常见报错 FAQ

**Q：后台接口列表里看不到插件？**
确认目录放在了 `public/plugins/gateway/epay_wx/`（不是 `plugins/epay_wx/`），
且目录名没被改过，然后点列表页的刷新。

**Q：前台点支付，弹出「请先在后台配置接口地址与商户ID」？**
插件还没安装，或配置没保存。到后台「支付接口」里安装并填写参数。

**Q：V2 报「服务器未启用 PHP openssl 扩展」？**
宝塔 / 主机面板里给对应 PHP 版本安装 `openssl` 扩展后重启 PHP。

**Q：V2 报「接口返回验签失败」？**
平台公钥填错了，或商户私钥 / 平台公钥不是同一对。请回商户后台重新复制密钥对。

**Q：V1 报签名错误？**
按顺序查：①「接口协议」是否选成了 V2；②商户 KEY 是否填错或有空格；
③接口地址结尾斜杠是否正确；④平台是否为「新版 V2 但文档写 V1」的混装平台。

**Q：支付成功但订单一直不变成已支付？**
说明异步回调没到。排查顺序：
1. 后台「系统 → 网站设置」里的网站地址是否填对（它决定回调地址）；
2. 站点域名能否被外网访问（本地环境收不到回调，用内网穿透）；
3. 站点日志里搜 `epay notify` 看是否有验签失败记录；
4. 协议选错了——V1 平台选 V2 或反之，验签必然失败。

**Q：支付页没有自动跳转？**
V10 的收银台 HTML 是用 jQuery `.html()` 注入的，**内联 `<script>` 不会执行**，
所以插件做不到「自动跳转」，而是渲染成「POST 表单 + 提交按钮」，
这也契合易支付文档「推荐 POST，不易被劫持」的建议。

**Q：能不能一个插件里放两个商户，按订单金额自动分流？**
可以改，但**前台用户无法选择**，只能靠轮询 / 金额等规则自动分配。
如果需要「用户自己选供应商」，就用 §8 的派生方式多装几个实例。

**Q：两个微信通道图标一样，怎么区分？**
后台支付接口列表和前台收银台都会显示你设置的**通道名称**。
如需换图标，把插件目录里**与主类文件同名的那个 png** 替换成自己的图片即可。

---

## 14. 开发与发版

```bash
# 交付前静态校验（无需 PHP 运行时）
python tools/verify.py

# 新增渠道
python tools/new_channel.py --dir epay_wx3 --name "易支付-微信③" --pay-type wxpay

# 单独生成图标
python tools/make_icon.py --out plugins/epay_wx/EpayWx.png --text 易

# 打包
python build.py
```

`tools/verify.py` 会在无 PHP 环境下核对：PHP 括号 / 引号平衡、类名与文件名一致性、
命名空间、`{标识}Handle` 与 `{标识}HandleRefund` 入口方法、回调地址目录、支付图标、
`config.php` 的枚举取值与保留键占用、BOM / CRLF。所有渠道全绿后才建议发版。

发版时同步更新 `CHANGELOG.md` 与各插件主类的 `$info['version']`（`build.py` 会自动读版本号）。

---

## 15. 授权协议

本项目基于 [GNU General Public License v3.0](LICENSE) 开源，
Copyright (C) 2026 空雨不流泪 <https://www.kybll.cn/>。

你可以自由使用、修改、再分发，但**衍生作品必须同样以 GPL-3.0 开源**。

---

## 16. 免责声明

- 本插件为第三方对接实现，与任何易支付平台的官方无隶属关系。
- 易支付平台资质参差不齐，**请自行甄别平台可靠性与资金安全**，作者不对任何平台跑路、冻结、扣量负责。
- 使用前请自行确认你的业务符合所用平台的接入条款与相关法律法规。
- 因使用本插件产生的资金风险、业务损失，作者不承担任何责任。
- 支付通道的费率、结算周期、风控政策以你所用的平台为准。
