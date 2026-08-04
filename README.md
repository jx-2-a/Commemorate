# Commemorate

浪漫纪念动画窗口：登录后显示全屏无边框动画（星光、爱心、萤火虫），纪念生命中某个珍贵的时刻。

## 更新与数据同步架构

```
GitHub 公开仓库（代码 + 发布包）
├── Code
└── GitHub Releases
       └── v1.1.0 / app.zip  ← 推 v* 标签自动构建发布

GitHub 私有仓库 my-app-data（配置与数据）
├── version.json            ← 版本号 + 下载地址 + SHA-256
├── config.json             ← 远程配置（登录、纪念信息，会叠加到本地）
├── data.csv                ← 业务数据（可推送）
└── rules.txt               ← 规则数据（可推送）
```

更新链路：应用启动 → 读取私有仓库 `version.json` → 有新版则从公开仓库的 GitHub Releases 下载 `app.zip`（地址按版本号寻址，如 `releases/download/v1.1.0/app.zip`）→ 校验 SHA-256 → 解压 → `updater.bat` 替换 exe 并重启。

数据同步链路：应用登录后 → 从私有仓库拉取 4 个文件到本地 `data/` 目录 → `config.json` 作为远程配置叠加生效；`data.csv` / `rules.txt` 可通过 `--sync-push` 推回仓库。

## 首次配置

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

3. 把 [examples/version.json](examples/version.json) 复制到私有仓库根目录。`download_url` 支持 `{version}` 占位符，会自动替换成 `version` 字段的版本号；发布后填上 `app.zip` 的 SHA-256。
4. 私有仓库放好 `config.json`、`data.csv`、`rules.txt`。远程 `config.json` 使用与本地相同的格式，`update` / `sync` 段会被忽略（防止循环依赖）。

## 发布新版本

### 方式一：手动

```bat
pyinstaller --noconfirm Commemorate.spec
```

把 `dist\Commemorate.exe` 压缩为 `Release\app.zip` 提交到公开仓库，然后更新私有仓库的 `version.json`（版本号、下载地址、SHA-256）。

或用 GitHub 网页创建 Release：Tags 填 `v1.1.0`，把 `app.zip` 作为附件上传，再更新私有仓库 `version.json` 的版本号与 SHA-256。

### 方式二：GitHub Actions（推荐）

仓库已内置 [.github/workflows/build.yml](.github/workflows/build.yml)：

1. 推送标签 `v1.1.0` 到公开仓库，自动构建并把 `app.zip` 发布到 GitHub Releases（版本号命名，无分支名）。
2. 如需自动更新私有仓库 `version.json`，在仓库 Settings → Secrets 中添加：
   - `DATA_TOKEN`：对私有仓库有 contents 写权限的 token
   - `DATA_REPO_OWNER`：你的用户名
   - `DATA_REPO_NAME`：私有仓库名（默认 `my-app-data`）

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

## 安全提示

- token 只放在环境变量或 GitHub Secrets 中，不要提交进仓库。
- 私有仓库不勾选可被 fork，`contents` 权限按最小化授予。
- 更新包下载后会校验 SHA-256；`version.json` 中 `sha256` 留空则跳过校验。
