# Commemorate

浪漫纪念动画窗口：登录后显示全屏无边框动画（星光、爱心、萤火虫），纪念生命中某个珍贵的时刻。

## 更新与数据同步架构

```
GitHub 公开仓库（代码 + 发布包）
├── Code
├── version.json            ← 版本号 + 下载地址 + SHA-256（发布时 CI 自动更新）
└── GitHub Releases
       └── v1.1.0 / app.zip  ← 推 v* 标签自动构建发布

GitHub 私有仓库 my-app-data（配置与数据）
├── config.json             ← 远程配置（登录、纪念信息，会叠加到本地）
├── data.csv                ← 业务数据（可推送）
└── rules.txt               ← 规则数据（可推送）
```

更新链路：应用启动 → 读取公开仓库 `version.json`（无需 token）→ 有新版则从 GitHub Releases 下载 `app.zip`（地址按版本号寻址，如 `releases/download/v1.1.0/app.zip`）→ 校验 SHA-256 → 解压 → 独立的 `updater.bat` 等待旧程序退出后替换 exe 并重启。

启动流程：立即显示登录窗口，同时在后台线程同步用户信息与其他数据（拉取到本地 `data/`，`config.json` 作为远程配置叠加生效）并静默完成版本检查，不阻塞界面；登录必须等待同步成功（同步期间按钮禁用，失败则阻止登录，右上角出现刷新按钮可一键重试同步）→ 登录成功 → 如需更新则切换为更新界面，更新完成后自动重启并自动登录进入主窗口；`data.csv` / `rules.txt` 可通过 `--sync-push` 推回仓库。

同步采用哈希对比：拉取时先通过一次 GitHub API 获取远程文件哈希清单（git blob SHA），与本地逐一对比，仅下载有变化的文件；推送时本地与远程哈希一致也会直接跳过，避免浪费网络。

## 首次配置

根目录的 [config.json](config.json) 是**引导配置**，只保留网络引导信息：私有仓库位置、同步文件列表、应用名称/版本。账号与纪念信息一律来自远程，不写在这里。

1. 创建公开仓库（代码 + Release 文件夹）和私有仓库 `my-app-data`。
2. 编辑 [config.json](config.json)：

   | 字段 | 说明 |
   | --- | --- |
   | `sync.repo_owner` | 你的 GitHub 用户名 |
   | `sync.repo_name` | 私有仓库名，默认 `my-app-data` |
   | `sync.branch` | 私有仓库分支，默认 `main` |
   | `sync.use_api` | 私有仓库用 `true`（走 GitHub Contents API，需 token）；公开仓库可设 `false` 走 raw 地址 |
   | `sync.files` | 需要同步的文件列表 |
   | `sync.push_files` | 允许推回仓库的文件（避免远程配置被覆盖） |
   | `sync.push_token_env` | 读取 GitHub token 的环境变量名，默认 `GITHUB_TOKEN` |

3. 把 [examples/version.json](examples/version.json) 提交到公开仓库根目录（作为版本检查入口）。`download_url` 支持 `{version}` 占位符，会自动替换成 `version` 字段的版本号；发布后填上 `app.zip` 的 SHA-256，或直接交给 CI 自动更新。
4. 私有仓库放好 `config.json`、`data.csv`、`rules.txt`。远程 `config.json` 使用与本地相同的格式，`update` / `sync` 段会被忽略（防止循环依赖）。
5. 远程 `config.json` 的 `auth` 段可配置注册策略：`allow_register`（是否开放注册）、`max_users`（用户数量上限）、`local_users`（管理账户与密码）。**账号信息一律来自远程**：登录校验、注册（写入 `auth.local_users`）都以远程配置为准，注册需要网络，远程写入成功才算注册成功；本地不保存任何账号。

本地 `local_state.json` 只保留两类数据：GitHub 令牌（`github_token`）和"记住我"勾选状态（`remembered`，含用户名），均不参与远程同步。

## 打包目录结构

打包后 exe 单独放在顶层，运行时产生的文件统一收进旁边的 `appdata` 文件夹，保持目录整洁：

```
Commemorate.exe
└── appdata/
    ├── config.json          ← 引导配置（首次运行从内置副本自动生成）
    ├── remote/              ← 远程同步数据（config.json / data.csv / rules.txt）
    └── local/               ← 本地数据（local_state.json 令牌与记住状态 / commemorate.log / updater.bat）
```

数据读取位置：远程同步数据放在 `appdata/remote/`（打包后）或项目根 `remote/`（开发模式），本地个人数据放在 `appdata/local/`（打包后）或项目根 `local/`（开发模式），引导配置为 `appdata/config.json`。

## 发布新版本

### 方式一：手动

```bat
pyinstaller --noconfirm Commemorate.spec
```

把 `dist\Commemorate.exe` 压缩为 `Release\app.zip` 上传到 GitHub Releases，然后更新公开仓库根目录的 `version.json`（版本号、下载地址、SHA-256）。

或用 GitHub 网页创建 Release：Tags 填 `v1.1.0`，把 `app.zip` 作为附件上传，再更新公开仓库 `version.json` 的版本号与 SHA-256。

### 方式二：GitHub Actions（推荐）

仓库已内置 [.github/workflows/build.yml](.github/workflows/build.yml)：

1. 推送标签 `v1.1.0` 到公开仓库，自动构建并把 `app.zip` 发布到 GitHub Releases（版本号命名，无分支名）。
2. CI 会自动用内置 token 更新公开仓库根目录的 `version.json`（版本号、下载地址、SHA-256），无需配置任何 Secrets。

## 数据同步用法

```bat
:: 启动（登录后自动拉取私有仓库数据）
python main.py

:: 把本地 data\data.csv、rules.txt 推回私有仓库
python main.py --sync-push

:: 只推送指定文件
python main.py --sync-push data.csv

:: 跳过启动时的自动拉取
python main.py --skip-sync
```

推送前需要设置环境变量（对私有仓库有 `repo` 或 `contents` 写权限）：

```bat
set GITHUB_TOKEN=ghp_xxx
```

令牌读取优先级：环境变量 `GITHUB_TOKEN` 优先，其次本地 `local_state.json`（不依赖环境变量，重启/双击启动都可用）。本地保存用：

```bat
python main.py --set-token ghp_xxx
```

如果同步失败，登录窗口会显示具体原因（如 `Not Found` 通常是令牌缺失/失效/未授权该仓库，`Operation canceled` 通常是网络超时）。

## 安全提示

- token 只放在环境变量或 GitHub Secrets 中，不要提交进仓库。
- 私有仓库不勾选可被 fork，`contents` 权限按最小化授予。
- 更新包下载后会校验 SHA-256；`version.json` 中 `sha256` 留空则跳过校验。
