# Budget Mate / 经费审批与记账助手

一个基于 AI 的个人经费审批与记账工具。通过 AI 智能判断支出合理性，结合预算上限进行双重把关，帮助你在日常生活中守住钱包。

## 核心功能

- **AI 智能审批** — 接入 DeepSeek / 通义千问 / 智谱 GLM 等模型，AI 全权判断支出合理性，规则引擎兜底
- **每日预算感知** — 自动计算「剩余预算 ÷ 剩余天数」作为日均参考红线，AI 审批更智能
- **智能出行合并** — 自动聚合 30 分钟内同类支出（如午饭 + 奶茶 + 小吃），按「一次外出」整体审批
- **批量出行审批** — 支持一次提交多笔消费，AI 自动重新分类（关键词未识别的项由 AI 补充分类）
- **分类预算管控** — 餐饮、交通、购物、娱乐、其他五大类，分别设置月度上限
- **短时高频限制** — 1 小时内同分类累计超过月预算 5%（单笔）或 15%（批量）自动拒绝
- **每日预算分配** — 根据剩余预算和天数，自动推荐当日各类别可支配金额
- **用餐时段推荐** — 午餐/晚餐时段自动弹出预算建议，AI 推荐符合预算和忌口的食物
- **月度自动重置** — 每月 1 号自动生成上月账单并归档，清空记录开启新月
- **账单导出** — 支持生成今日账单、周账单、月账单，纯文本格式方便分享

## 技术栈

- **后端**: Python + Flask
- **前端**: 原生 HTML / CSS / JavaScript（单页面应用）
- **桌面端**: pywebview（本地窗口，PyInstaller 打包为 `BudgetMate.exe`）
- **移动端**: Capacitor v8 → Android APK（IndexedDB 离线存储）
- **存储**: JSON 文件（桌面端 `%LOCALAPPDATA%/budget-mate/`）/ IndexedDB（移动端/PWA）
- **AI**: DeepSeek API（兼容 OpenAI 格式，可选通义千问、智谱 GLM 等）

## 快速开始

### 1. 克隆项目

```bash
git clone git@github.com:Niuyeye1688/budget-mate.git
cd budget-mate
```

### 2. 安装依赖

```bash
pip install flask pywebview pyinstaller
```

### 3. 启动服务

**Web 模式**（浏览器访问）:
```bash
python app.py
```
访问 `http://localhost:5000`

**桌面模式**（原生窗口）:
```bash
python desktop.py
```

**命令行模式**（终端交互）:
```bash
python main.py
```

**Android APK**:
```bash
npm install
npx cap sync android
# 在 Android Studio 中打开 android/ 目录并构建
```

### 4. 首次配置

进入「设置」页面：
1. 设置**每月总预算**
2. 设置各**分类预算上限**
3. （可选）启用 AI 审批，填入你的 API Key 和模型
4. （可选）填写**饮食偏好/忌口**，AI 推荐食物时会自动避开

> API Key 仅存储在本地 `budget_data.json` 中，不会上传到任何服务器。

## 项目结构

```
budget-mate/
├── app.py              # Flask 主入口，API 路由
├── desktop.py          # 桌面应用启动器（pywebview）
├── main.py             # 命令行交互入口
├── approver.py         # AI 审批逻辑 + 规则引擎 + 消费分类
├── budget.py           # 预算查询与设置
├── ledger.py           # 支出记录增删查
├── bills.py            # 账单生成 + 用餐推荐 + 月度重置
├── storage.py          # JSON 数据读写
├── build.spec          # PyInstaller 打包配置
├── PRD.md              # 产品需求文档
├── capacitor.config.json  # Capacitor 移动端配置
├── templates/
│   └── index.html      # 前端单页面
├── static/
│   ├── style.css       # 样式文件
│   ├── app-logic.js    # 前端业务逻辑（与后端对称，支持离线）
│   ├── db.js           # 客户端存储抽象（IndexedDB → localStorage → 内存）
│   ├── custom-select.js # 自定义选择组件
│   ├── manifest.json   # PWA 配置
│   └── sw.js           # Service Worker（离线缓存）
├── www/                # Capacitor 静态资源副本
├── android/            # Android 项目（Gradle/Android Studio）
├── budget_data.json    # 本地数据（%LOCALAPPDATA%/budget-mate/，已忽略）
└── bills/              # 月度账单归档（已忽略）
```

## 审批逻辑

Budget Mate 采用 **AI 优先 + 规则兜底** 的双层架构：

1. **AI 模式（默认开启时）**：AI 直接判断支出合理性，参考日均预算、分类使用情况、近期消费等上下文
2. **规则兜底（AI 关闭或调用失败时）**：
   - 月总预算检查
   - 分类上限检查（不超过月预算）
   - 短时高频限制（1 小时内同分类累计 ≤ 5%/15% 月预算）
   - 大额预警（单笔 > 1000 元）

## 使用流程示例

1. **设置预算**: 月初或首次使用时，在「设置」页配置本月总预算和分类上限。
2. **提交支出**: 在「审批/记账」页填写金额和用途（如"午饭 25 元"），点击提交。
3. **查看结果**: AI 结合日均预算、近期同类支出、分类上限综合判断，给出通过/拒绝及理由。
4. **批量出行**: 在「出行」页一次输入多笔消费，系统自动合并分类、AI 整体判断。
5. **查看记录**: 「记录」页展示所有历史支出，可按时间、分类、状态回溯。
6. **生成账单**: 「账单」页可生成今日、本周或上月账单，复制分享或导出。
7. **月度归档**: 每月 1 号系统自动生成上月账单文件存入 `bills/` 目录，并清空记录。

## 注意事项

- 桌面端数据存储在 `%LOCALAPPDATA%\budget-mate\budget_data.json`，换设备时需手动迁移。
- `budget_data.json` 和 `bills/` 目录已加入 `.gitignore`，不会进入版本控制。
- AI 审批受**规则引擎**兜底：AI 不可用时自动降级为纯规则判断。
- 月度重置基于 `current_month` 字段检测，首次启动时会自动设置当前月份。

## License

MIT
