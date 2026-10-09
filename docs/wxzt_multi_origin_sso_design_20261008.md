# wxzt 多来源地址 SSO 设计方案_20261008

## 0. 执行基线

本文基于当前 Octop、wxzt 代码和生产数据库检查，目标是支持 wxzt 使用内网域名、外网域名和 IP 地址并存。用户于 2026-10-08 明确要求按清单一次性实施并完成后打钩，本文及同日任务清单为执行基线。各接入实例沿用同一业务 userid 体系；不同独立身份库不在本轮合并范围。

## 1. 结论先行

推荐采用“wxzt 主动接入 Octop，来源绑定到本次登录”的链路，不要求统一 wxzt 域名，也不维护 wxzt IP 列表：

```text
浏览器访问任意 wxzt 地址
        |
        +--> Octop iframe / 新窗口：准备本窗口的登录状态
        |
        +--> 当前 wxzt 后端：校验 wxzt 会话
                  |
                  | 共享密钥 + 用户身份 + 本次 wxzt origin
                  v
             Octop 后端签发一次性登录码
                  |
                  v
        Octop iframe / 新窗口：兑换本窗口绑定的登录码
                  |
                  v
             Octop JWT + 本次 wxzt 导航上下文
```

该方案不要求 Octop 配置任何 wxzt IP、域名或端口。任意受信任的 wxzt 实例都可以接入，只要它具备同一份 SSO 共享密钥并能访问 Octop。该密钥仅用于本登录协议，不能复用 Octop JWT 签名密钥。

wxzt 仍需要知道 Octop 的入口。浏览器入口与后端调用入口分别配置，避免外网浏览器得到内网地址；这不要求 wxzt 自身地址统一。Octop 不向 wxzt 发起服务端请求，不依赖多个 wxzt 共用 Redis。

## 2. 已确认的现状

- 当前 wxzt `/api/octop/sso/start` 在 wxzt Redis DB 11 写入票据；Octop 再用固定 `OCTOP_WXZT_SSO_EXCHANGE_URL` 反向请求 wxzt 兑换。
- 当前 Octop 的 `allowed_return_url`、`allowed_logout_url` 都要求来源等于 `OCTOP_WXZT_ORIGIN`，因此无法同时接受不同域名和 IP。
- 当前 Octop 使用 PostgreSQL `octop_prod`，schema version 为 20；`sso_providers` 中已有一个 `kind=wxzt` 提供方，`user_sso_identities` 通过 `provider_id + subject` 绑定身份，不依赖 IP。
- 当前 `sso_login_states` 有一次性、过期和原子消费能力；本次只读核对有 0 条状态记录。它可以承载新登录流程，但缺少动态来源、打开方式和本窗口校验字段，需要小幅增列，不能仅复用方法而忽略这些数据。
- 当前 wxzt 用户身份来自 MySQL `user_detail.userid`，生产数据中非空 `userid` 没有重复；已检查到的 Octop wxzt subject 可以和 wxzt `userid` 对应。
- 当前 wxzt 已连接远端 MySQL、Redis；其他服务器是否共享同一用户体系尚未确认。方案默认同一业务身份体系，保留已有 subject，不按服务器新增身份。

### 权威来源与约束继承

当前权威来源是用户本次“内网、外网、IP 入口并存，wxzt 域名无法统一”的要求；当前权威方案为本文草案，主任务清单为同目录 `wxzt_multi_origin_sso_tasks_20261008.md`。`Octop/AGENTS.md` 的模块边界、SQLite/PostgreSQL 对等迁移和验证要求继续适用。

旧方案处理：根目录 `Octop从零接入wxzt设计方案_20260929.md` 和 wxzt 的 20260930 内嵌文档作为历史/参考文档；本轮替换固定 wxzt 地址、反向兑换和 referrer 兜底口径，继承原生 Dashboard、用户映射、JWT 不交给父页以及内嵌返回/退出的行为。历史文档不覆盖本轮需求。

## 3. 目标

- 支持任意受信任 wxzt 实例通过域名、IP、内网地址或外网地址接入。
- Octop 不维护 wxzt 地址白名单，不反向请求固定 wxzt 地址。
- 保持一次性登录码、短时有效、服务端共享密钥和用户身份映射。
- 返回主页和退出地址跟随本次登录来源，不把某个实例写死为全局默认地址。
- 保持现有 iframe 内嵌、顶层打开、返回主页和退出行为。

## 4. 非目标

- 不取消服务间身份认证；“任何 wxzt 地址可接入”不等于匿名程序可伪造 wxzt 用户。
- 不把长期 JWT、wxzt Cookie 或共享密钥放进 URL 或 `postMessage`。
- 不按服务器 IP 创建 Octop 用户或身份；IP 只是本次导航来源。
- 不处理不同 wxzt 用户库之间相同 `userid` 的全局合并。若多个系统的 `userid` 可能相同，必须先定义稳定的租户/系统标识。
- 不改变 wxzt AI Router 的地址配置。模型调用地址是独立的运行时依赖，不能随 SSO 来源地址一起删除。

## 5. 核心设计

### 5.1 Octop 窗口先准备登录状态

HTTP 路由保持薄层，状态编排归现有 `infra/auth/sso/service.py` 的 wxzt 方法，SQL 归 `infra/db/repos/sso.py`；不在 router 中复制用户创建或数据库事务逻辑。协议扩展只为本流程服务，不建立通用登录平台。

wxzt 页面把公开的 Octop 浏览器入口注入当前运行配置，在 iframe 中打开 `/login/wxzt?embedded=1&parent_origin=<window.location.origin>&request_id=<本次请求标识>`。参数只是启动提示，不能证明来源可信。

Octop 窗口向自己的 `/api/auth/wxzt/prepare` POST `{wxzt_origin, mode}`。Octop 生成随机 `state`、随机 `verifier`，保存 verifier 的 SHA-256 challenge，返回 `{state, verifier, expires_in:120}`。verifier 只保留在 Octop 窗口内存，不交给 wxzt。复用已有服务端 PKCE 随机/哈希工具，避免 HTTP IP 页面依赖只在安全上下文可用的浏览器 `crypto.subtle`。

Octop 向当前父窗口发送 `OCTOP_EMBED_PREPARED {state, request_id}`。wxzt 校验来自当前 iframe、origin 等于实际 Octop 入口、request_id 等于当前尝试后，才发起本地 SSO 请求。

### 5.2 wxzt 后端确认身份和来源

wxzt 页面 POST 自己的 `/api/octop/sso/start`，输入仅为 `{state, mode}`。wxzt 后端继续校验本地会话和当前 AI Hub 访问权限，用户字段取自该会话，前端不得提交 userid 或 role。

wxzt 后端从本次请求的有效 scheme、host、port 解析外部 origin，完成同源请求校验后向配置好的 Octop 后端地址 POST `/api/auth/wxzt/issue`：

```json
{
  "state": "<prepared-state>",
  "wxzt_origin": "https://本次实际访问的wxzt",
  "mode": "embedded",
  "userid": "<会话中的userid>",
  "username": "<会话中的username>",
  "display_name": "<会话中的显示名>",
  "role": "<会话中的角色>"
}
```

请求头复用 `X-Octop-SSO-Secret`，密钥必须在服务端比较。代理后的外部 scheme/host 仅从部署已信任的代理头还原；禁止无条件信任客户端的 `X-Forwarded-*`。Origin/Referer 用于与当前有效请求来源核对，不用于自动识别身份或向外发请求。

Octop 要求 state 尚未使用、提供方是启用的 wxzt、来源和 mode 与 prepare 一致，再原子认领状态。随后解析或创建已有 wxzt 身份，绑定 user_id，签发 60 秒一次性 code，保存 code 哈希。issue 响应为 `{state, code, expires_in:60}`，不返回 JWT。

### 5.3 本窗口兑换，导航只认登录上下文

wxzt 将 issue 结果交给对应 Octop 窗口：`OCTOP_EMBED_CODE {state, code, request_id}`，使用精确 targetOrigin。该码短时有效且绑定 Octop 窗口的 verifier；JWT、密钥和身份字段不进入消息。Octop 必须校验消息 source、实际 origin、state 和 request_id。

Octop 窗口 POST 自己的 `/api/auth/wxzt/exchange`，输入 `{state, code, verifier}`。服务端在校验 code 哈希、verifier challenge、有效期和 wxzt 提供方后原子消费，只允许一次成功。返回普通 JWT、`auth_source=wxzt` 和由状态推导的导航上下文。

`return_url = 已确认的 wxzt_origin + /ai_hub_layout`，`logout_url = 同一 origin + /logout`。exchange 不接受浏览器覆盖来源、返回 URL、角色或用户 ID。

### 5.4 动态来源与消息校验

- 启动时 parent_origin 是未验证提示；issue 成功后只使用与本次状态匹配、由持有密钥的 wxzt 后端确认的 origin。删除成功态的 referrer 优先兜底。
- wxzt 页面持续校验当前 iframe 或新窗口的 WindowProxy、实际 Octop origin、请求标识和消息类型；不使用 `postMessage(..., '*')`。
- 增加 PREPARED、CODE 两种握手消息；READY、ERROR、GO_HOME、LOGOUT 的业务动作保持原行为。后四种消息不携带导航 URL。
- iframe 成功后留在 `/chat`；返回由当前父页 `goHome()` 处理，退出由当前父页访问自己的 `/logout`。
- 新窗口复用相同流程，通过 `window.opener` 与发起 wxzt 页面握手；成功后留在 Octop `/chat`，返回/退出使用本次登录上下文。无父窗口也无 opener 的直接访问走正常登录，不降级到旧的 URL code 兑换。

### 5.5 配置边界

Octop 侧保留：

```env
OCTOP_WXZT_SSO_SHARED_SECRET=<shared-secret>
```

Octop 侧移除登录用途的以下配置：

```env
OCTOP_WXZT_ORIGIN
OCTOP_WXZT_SSO_EXCHANGE_URL
OCTOP_WXZT_DEFAULT_RETURN_URL
```

wxzt 侧保留或新增：

```env
OCTOP_ORIGIN=<浏览器可达的Octop入口>
OCTOP_WXZT_SSO_SHARED_SECRET=<same-secret>
# 可选：后端有独立内网通道时填写，空则使用 OCTOP_ORIGIN
OCTOP_SSO_BASE_URL=<wxzt后端可达的Octop根地址>
```

每个 wxzt 部署选择适合其用户网络的 Octop 浏览器入口；同一 wxzt 实例服务内外网时，该入口需要对两类用户均可达，或在 wxzt 侧使用明确的部署路由规则选择入口。不能从 wxzt Host 猜测 Octop Host。

两个配置指向同一个逻辑 Octop 和同一控制数据库，浏览器 API 始终调用它当前 Octop origin 的相对路径，无需把 wxzt 域名加入 Octop CORS。后端 issue 地址不是浏览器传入参数。

若当前使用 `OCTOP_WXZT_ORIGIN` 推导模型 Router base URL，先设置独立 `OCTOP_WXZT_AI_ROUTER_BASE_URL`，再移除登录地址依赖。模型 Router 仍按自己的启用开关运行，本次只清理 origin 默认推导，不重写模型调用链路。

## 6. 地址校验规则

不登记来源白名单；来源先由 wxzt 后端确认，再进行 URL 结构校验，最后作为单次状态字段保存：

| 地址 | 允许 | 拒绝 |
| --- | --- | --- |
| wxzt origin | 任意合法 HTTP(S) 域名、IPv4、带方括号 IPv6、有效端口 | userinfo、非法端口、path、query、fragment、反斜杠、控制字符 |
| 返回/退出地址 | 服务端从单次 origin 推导固定路径 | 浏览器另传的地址、`next=` 等跳转参数 |

协议允许持有共享密钥的 wxzt 后端声明任意合法来源。固定路径本身不能证明某个域名可信，可信依据是服务间密钥和绑定的登录状态；来源不能成为 Octop 的服务端 HTTP 请求目标。

同一用户从内网 IP、内网域名、外网域名进入，映射到同一个 Octop 用户，但每个窗口有自己的导航上下文，不能改写全局 provider 的 `dashboard_origin`。

## 7. 用户、权限与审计

- wxzt `userid` 继续作为外部 subject；Octop 用户绑定仍使用已有 `provider_id + subject` 唯一约束。
- wxzt 角色只在服务端共享密钥验证通过后使用；浏览器提交的角色字段必须被忽略。
- 现有管理员角色映射逻辑继续保留，不能因为取消地址限制而取消角色校验。
- 复用现有 `audit_log`，用结构化 actor/action/target 表达签发、登录、失败；来源和已知失败原因仅作为脱敏审计快照。未完成匿名 prepare 的自然过期不逐条写日志。禁止记录共享密钥、verifier 和完整登录码。
- 不使用 IP 作为用户主键、身份 subject、权限条件或持久化租户标识。

## 8. 数据模型与复杂度审计

复用 `sso_login_states`，新增三个同一登录生命周期字段：

| 字段 | 类型/默认 | 用途 |
| --- | --- | --- |
| `wxzt_origin` | nullable TEXT，默认 NULL | 预备来源，issue 必须由 wxzt 后端确认一致 |
| `wxzt_mode` | nullable TEXT，默认 NULL | `embedded` 或 `standalone`，由服务端校验 |
| `wxzt_browser_challenge` | nullable TEXT，默认 NULL | SHA-256 base64url challenge，不存 verifier 明文 |

旧 OIDC/OAuth 状态新列为 NULL，无需回填；新 wxzt 状态必须三个字段齐全。原字段 `nonce`、`code_verifier` 属于 OIDC 交换语义，wxzt 创建状态时填空字符串，不能冒充第三方 OIDC 授权过程。

继续使用 state 主键、login_code 唯一索引、user_id/provider_id 关联和 expires_at/consumed_at 生命周期。wxzt 的 `login_code` 存码哈希，OIDC/OAuth 维持现有表示；各消费方法必须限定 provider.kind，防止相互消费。

状态流转：PREPARED(120 秒) -> CLAIMED -> ISSUED(60 秒) -> CONSUMED；失败或到期不允许重新使用同一个 state，前端重试生成新状态。CLAIMED 用现有 consumed_at 标记；只有同一次签发认领成功才能附加 code 并重置 consumed_at。重复 issue 返回 409，不重复绑定或签发；响应丢失后重新准备，不从数据库回传旧 code。复用到期删除机制，在新流程准备/签发时清理到期记录，不增加定时任务。

启用初始化：共享密钥已配置且 wxzt provider 不存在时，在服务启动阶段创建唯一 wxzt provider，`dashboard_origin=NULL`；已有显式禁用行不能被启动或登录重新启用。prepare 只允许启用的 wxzt 提供方，并对匿名状态创建做有界频率控制；共享密钥未配置时不开放流程。禁用用户在 issue 和 exchange 都必须拒绝。

| 对象 | 决策 | 理由 | 更轻替代方案 | 是否新增 |
| --- | --- | --- | --- | --- |
| `sso_providers` | 复用 | 已有 `wxzt` provider | 新建 wxzt provider 表 | 否 |
| `user_sso_identities` | 复用 | 已有 `provider_id + subject` 绑定 | 按 IP 建身份表 | 否 |
| `sso_login_states` | 复用并增三列 | 来源和窗口 challenge 必须随单次状态存储，现有字段无法表达 | 新表或独立 Redis 票据存储 | 不新增表 |
| wxzt 来源地址 | 存于状态列 | 兑换、消息和导航需要同一事实源 | 来源配置表或全局 provider 地址 | 不新增表 |

现有 identity/provider/audit 和 SSO 状态存储足够，不新增服务或数据库。更轻的“取消 return URL 校验”仍留下固定回调；“动态回调”又会把密钥交给任意回调目标。推荐方案增加两边握手和三个状态字段，换来无回调地址、无共享 Redis 要求和有明确来源的登录上下文；无需新增统一域名或负载均衡服务。

### JSON 字段登记表与核心查询验证

| 位置 | 允许用途 | 禁止用途 | 核心查询 |
| --- | --- | --- | --- |
| 现有 `sso_providers.extra` | 保持现有 managed 展示元数据 | 不存来源列表或活动登录事实 | 登录不解析该字段取得 origin |
| 现有 `audit_log.payload` | 来源、mode、已知失败原因的脱敏快照；限制 2 KB | 密钥、code、verifier、JWT、权限事实源 | actor/action/target 查询，payload 不用于鉴权 |
| 新流程 HTTP JSON |  typed 请求/响应数据 | 直接把整个请求塞入数据库 | state/provider/code/challenge 用列查询 |

核心登录条件、身份关联、到期清理、一次性消费均使用结构化列；来源没有列表索引需求，不使用 JSON/EAV/多值字符串。

## 9. 安全风险与取舍

### 9.1 共享密钥泄露

共享密钥是唯一的 wxzt 来源准入凭证。泄露后，持有者可以向 Octop 申请登录码并伪造用户身份。因此密钥必须只放在 wxzt 服务端环境变量/密封配置，不能放前端、HTML、URL 或日志。

服务间 issue 请求跨公网时必须使用有有效证书的 HTTPS；HTTP 仅限明确受信任的内网通道。HTTP 无法抵抗链路监听或篡改，窗口 challenge 也不能替代传输加密。外网浏览器的 Octop 入口应提供 HTTPS。密钥轮换在同批部署中更新所有实例，不引入永久多密钥兼容。

### 9.2 开放来源与开放重定向

取消静态 origin 后，来源必须由持有密钥的 wxzt 后端确认。prepare 的提示、浏览器 query、document.referrer 都不能独立成为可信导航依据。兑换仅接受绑定状态及本窗口 verifier，不能把攻击者预先取得的 code 直接塞进另一浏览器自动登录。

### 9.3 HTTP、HTTPS 和内嵌限制

本方案不依赖 wxzt 与 Octop 共享 Cookie，也不使用第三方 state Cookie。浏览器仍有以下实际限制：

| wxzt 浏览器入口 | Octop 浏览器入口 | 本轮行为 |
| --- | --- | --- |
| HTTP 内网域名/IP | HTTP 内网域名/IP | 通常可内嵌，按实际浏览器规则验收 |
| HTTP 内网域名/IP | HTTPS 可达地址 | 通常可内嵌，必须有有效证书 |
| HTTPS 外网/内网地址 | HTTPS 可达地址 | 推荐内嵌路径；公网页面访问私网目标仍受浏览器网络规则影响 |
| HTTPS 地址 | HTTP 地址 | HTTPS iframe 会被混合内容拦截；提供用户点击“在新窗口打开”，不承诺静默内嵌 |
| 外网浏览器 | 仅内网可达的地址 | 不可用；需提供外网可达的 Octop 浏览器入口，代码无法补足路由 |

框架/代理的 frame-ancestors、X-Frame-Options、COOP 和第三方存储策略可能影响 iframe 或 opener 握手，作为部署验收检查。JWT 仍只存 Octop 自己的 origin；不通过父页转存来绕过限制。新窗口使用同一 prepare/issue/exchange 流程，从用户点击直接打开以避免弹窗拦截；iframe 握手/存储失败使用现有错误区域显示该命令。

### 9.4 用户身份冲突

如果不同 wxzt 系统使用相同的 `userid` 表示不同的人，当前 `provider_id + subject` 会把他们视为同一人。此时需要把稳定的系统/租户标识纳入 subject 规范，例如 `system_id:userid`；不能用来源 IP 代替系统标识。

## 10. 接口、状态与失败处理

| 接口 | 调用方/输入 | 成功输出 | 主要失败 |
| --- | --- | --- | --- |
| Octop `/api/auth/wxzt/prepare` | Octop 窗口；origin、mode | state、verifier、120 秒 | 400 格式错误；403 提供方禁用；429 频率超限；503 未配置/未初始化 |
| wxzt `/api/octop/sso/start` | 已登录 wxzt 同源页面；state、mode | state、code、60 秒 | 401 未登录；403 无权限/非同源；502/503 Octop 不可用 |
| Octop `/api/auth/wxzt/issue` | wxzt 后端；密钥、state、origin、mode、会话身份 | state、code、60 秒 | 403 错密钥/禁用；400 格式错误；409 状态已认领；401 状态到期；503 数据库不可用 |
| Octop `/api/auth/wxzt/exchange` | Octop 窗口；state、code、verifier | JWT、用户、动态 return/logout（来源和 mode 保留在状态及窗口上下文） | 401 过期/重放/校验失败；403 用户或提供方禁用；503 数据库不可用 |

prepare、issue 纳入精确 JWT 豁免列表，但 issue 自己强制服务间鉴权；禁止宽泛豁免整个 wxzt 路由前缀。所有新错误沿用 Octop 错误封装与中英文文案，400/401/403 分别测试到业务条件。

1. wxzt 会话无效：`/api/octop/sso/start` 返回 401，不调用 Octop。
2. 共享密钥错误：Octop `/issue` 返回 403，不创建登录码。
3. 身份字段缺失：返回 400，不创建登录码。
4. Octop 数据库不可用：返回 503，wxzt 展示可重试错误。
5. 登录码重复消费或过期：Octop `/exchange` 返回 401，不能重复签发 JWT。
6. origin 或 mode 不匹配：拒绝 issue，不使用配置默认地址兜底；exchange 中额外 return_url/role 字段拒绝。
7. iframe 消息来源不匹配：父页面丢弃消息，保留现有超时和重试入口。

### 页面/交互 ASCII 原型

保留现有布局，仅补握手与新窗口状态，不做视觉重设计或 mock HTML。

```text
+---------------------------------------------------------+
| wxzt AI Hub                       当前访问地址保持不变    |
| [Octop 卡片]                                            |
|                                                         |
|  正常: Octop iframe -> /chat                             |
|  等待: preparing -> issuing -> exchanging -> ready       |
|  失败: 现有错误区域                                      |
|        [重新加载] [在新窗口打开] [返回 AI 主页]            |
+---------------------------------------------------------+
```

多标签页、快速重复点击、返回后再进入和取消旧请求必须按请求标识隔离。用户确认点是接受浏览器禁止 iframe 的组合使用显式新窗口入口；如果要求所有组合均内嵌，需要先提供可用的 HTTPS Octop 地址。

## 11. 兼容、迁移与退场

本次建议一次性切换登录协议：

- wxzt 取消 Redis `octop:sso:ticket:*` 的生成和兑换接口。
- Octop 删除 `redeem_ticket()` 对固定 wxzt exchange URL 的依赖。
- 保留 `/api/auth/wxzt/exchange` 作为浏览器兑换入口，但它只消费 Octop 本地一次性码。
- 现有 PostgreSQL SSO 用户和 `user_sso_identities` 保留，ID、绑定和资源归属不变；不按域名/IP 拆分账号。
- 现有配置中的旧 wxzt 地址在切换前保留备份，验收后从运行环境和文档清理。
- provider 的旧 `dashboard_origin` 只清理 `kind=wxzt` 行并置 NULL，禁止每次登录写入新来源；其他 provider 不变。到期的旧 wxzt Redis 票据自然失效，不扫描删除无关 Redis 会话。
- 旧 query code/return_url 自动登录分支和成功态 referrer 兜底同轮删除，现有 `/login/wxzt` 路径保留但只接受新握手。

数据库已实际应用 v20，增列需新增下一编号 SQLite/PostgreSQL 成对迁移，当前预计为 `021_wxzt_login_context.sql` 和 `.pg.sql`，不能修改 v20 让现有数据库漏应用。实施时检查是否出现新迁移编号，再确定最终编号。新增列默认 NULL，迁移事务清理 wxzt provider 地址，保留用户数据。

执行前备份/快照数据库并记录 schema、provider/identity/user 计数。先在数据库副本验证迁移、新建库和重复启动，再进行受控切换；迁移前后用户绑定数量一致。普通代码/配置采用 Git 版本依据与前向修复；增列一般无需删列 down migration，数据误改从明确快照恢复，不把 Git revert 当数据库恢复。

迁移及构建准备完成后，停止旧登录签发，等待 60 秒旧票据失效，按 Octop -> wxzt 顺序发布本轮修改；未升级实例停止旧 SSO 路径，不自动回退。M5 完成前清理全部旧链路，不设永久兼容开关。

## 12. 验收门禁

- 一个 wxzt 内网 IP、一个内网域名和一个外网域名分别发起登录，合法且可达的协议组合均能创建并消费一次性登录码；不要求三个来源统一。
- 任意来源登录后，返回和退出地址跟随当前来源；Octop 不再因 `OCTOP_WXZT_ORIGIN` 不匹配而回退到固定地址。
- 登录码只能消费一次，过期后不能换取 JWT。
- 共享密钥错误、身份缺失、浏览器伪造角色、非法 origin、未确认来源、错 verifier、其他窗口 code、已禁用提供方或用户均被拒绝；不降级到固定地址或匿名身份。
- iframe 场景下地址栏仍停留在 wxzt，Octop 最终进入 `/chat`；返回和退出作用于当前 wxzt 顶层页面。
- 现有 wxzt 身份映射、Octop 管理员权限和本地登录回归通过。
- Octop 不再发起到任意 wxzt 地址的服务端 HTTP 请求。
- OIDC/OAuth 既有流程不受影响且不能消费 wxzt 状态；SQLite/PostgreSQL 迁移与并发消费行为一致。
- 根因是固定兑换目标与全局固定 origin 校验；同机制扫描覆盖 auth、导航工具、Header/Sidebar/AvatarDropdown、iframe 消息、provider dashboard_origin 和模型 Router origin 推导。修复层级为服务端状态事实源与前端共享导航工具；回归防复发覆盖不同域名/IP/端口和多窗口串扰，不扩大到全站认证重构。

完成证据与回填位置：在任务清单记录后端测试、Vitest/TypeScript/构建结果、数据库副本迁移校验，以及 `reports/wxzt-multi-origin-sso/` 浏览器验收截图与请求结果摘要，不保存真实密钥、code 或 JWT。

浏览器验收拉起方式：使用项目现有 wxzt 和 Octop 启动命令，在独立测试配置与数据库副本下打开对应 `/ai_hub_layout?site=octop`。用 Playwright/MCP 实际点击卡片 -> 等待 `/chat` -> 返回主页 -> 再进入 -> 退出；按域名/IP 与协议矩阵记录桌面 `1440x900`、窄屏 `390x844` 截图。无法提供外网路由或证书时记录该组合未验收，不能用本机 HTTP 测试代替。

自动验收包括 Octop `uv run pytest` 的相关认证/DB 测试、dashboard Vitest/TypeScript/构建、wxzt Node 行为测试和隔离 Flask 路由测试；提交交付前按 AGENTS.md 跑 `make all`，不将无结果的命令写成通过。

## 13. 需要用户确认

本方案按同一业务身份体系、共享接入密钥设计；无需确认或登记每个 wxzt 地址。实施前核对其他 wxzt 是否也使用同一用户身份：若不是，需给出稳定系统/租户标识，另补身份隔离设计，不能把同名 userid 自动合并。

浏览器不允许 iframe 的组合默认提供“在新窗口打开”。本设计已进入代码实施：本机 SQLite、应用测试和浏览器行为已有证据；生产配置、数据库迁移、服务发布及真实公网/证书矩阵仍未执行或验收，详见配套任务清单。

## 14. 最终执行口径

已按“窗口 prepare、wxzt 主动 issue、Octop 本地一次性码、登录上下文来源、无静态 wxzt origin”完成代码实现和本机验收；余下生产切换、PostgreSQL 专用测试及真实公网矩阵按配套任务清单保持未完成，不增加身份中心、实例登记服务或全站代理。
