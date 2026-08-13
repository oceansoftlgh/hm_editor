# HmEditor 离线部署文档

> 适用于服务器无法连接外网的部署场景。

---

## 目录

- [前置条件](#前置条件)
- [方案概述](#方案概述)
- [第 1 步：在开发机上准备项目](#第-1-步在开发机上准备项目)
- [第 2 步：传输到离线服务器](#第-2-步传输到离线服务器)
- [第 3 步：在服务器上安装 Node.js](#第-3-步在服务器上安装-nodejs)
- [第 4 步：启动服务](#第-4-步启动服务)
- [第 5 步：进程守护方案](#第-5-步进程守护方案)
- [第 6 步：防火墙配置](#第-6-步防火墙配置)
- [常见问题](#常见问题)
- [附录：最小文件清单](#附录最小文件清单)

---

## 前置条件

| 条件 | 说明 |
|------|------|
| 开发机 | Windows 系统，可联网，已安装 Node.js 14.x |
| 目标服务器 | Windows Server 2016/2019/2022，x64 架构 |
| 传输方式 | U 盘 / 内网共享 / 移动硬盘 |

---

## 方案概述

```
开发机（有网）                   离线 Windows Server
─────────────────                ─────────────────────
① npm install 安装依赖
② npx grunt release 编译
③ 打包项目目录 ── U盘/内网 ──▶   ④ 复制到目标路径
                                  ⑤ 安装 Node.js (离线 MSI)
                                  ⑥ node index.js 启动
                                  ⑦ 防火墙放行 3071 端口
                                  ⑧ 浏览器访问
```

核心原则：**所有需要联网和编译的工作在开发机上完成，产物整体搬运。**

---

## 第 1 步：在开发机上准备项目

### 1.1 拉取代码

```bash
git clone <仓库地址> hm-editor
cd hm-editor
```

### 1.2 安装依赖

```bash
npm install
```

关键依赖安装确认：

| 依赖 | 验证方式 |
|------|---------|
| express | `dir node_modules\express` |
| canvas（原生模块） | `dir node_modules\canvas\build` 有 `Release\canvas.node` |
| puppeteer（Chromium） | `dir node_modules\puppeteer\.local-chromium` |

### 1.3 编译前端资源

```bash
npx grunt release
```

确认产物：

```bash
dir editorDist\
```

应有 `all.min.css`、`all.min.js`、`base.min.js`、`css\`、`js\`。

### 1.4 打包

**方法 A：压缩包（推荐，U 盘传输）**

```powershell
powershell Compress-Archive -Path "C:\hm-editor\*" -DestinationPath "C:\hm-editor.zip" `
  -Exclude @(".git\*", "logs\*", ".idea\*", "node_modules\.chromium-browser-snapshot\*")
```

**方法 B：直接复制（内网共享）**

```powershell
robocopy C:\hm-editor \\192.168.x.x\共享目录\hm-editor /E /XD .git logs .idea
```

---

## 第 2 步：传输到离线服务器

将打包好的 `hm-editor.zip` 通过 U 盘或内网拷贝到服务器，解压到目标路径，例如 `D:\hm-editor`。

解压后目录结构应包含（关键目录）：

```
D:\hm-editor\
├── index.js              ← 服务入口
├── package.json          ← 项目配置
├── config.js             ← CKEditor 配置
├── node_modules\         ← 全部依赖（已安装）
├── editorDist\           ← 编译产物
├── hmEditor\             ← 编辑器 SDK 源码
├── src\                  ← 后端逻辑
├── plugins\              ← 编辑器插件
├── vendor\               ← 第三方库
├── core\                 ← CKEditor 核心
├── start.bat             ← 启动脚本
└── ...其他目录
```

---

## 第 3 步：在服务器上安装 Node.js

### 3.1 下载离线安装包

在有网电脑上下载 Node.js 14.x LTS MSI 安装包：

| 架构 | 下载链接 |
|------|---------|
| x64 | https://nodejs.org/dist/v14.21.3/node-v14.21.3-x64.msi |
| x86 | https://nodejs.org/dist/v14.21.3/node-v14.21.3-x86.msi |

> 如需其他版本，访问 https://nodejs.org/dist/latest-v14.x/ 浏览下载。

### 3.2 安装

将 MSI 拷贝到服务器，双击安装：

- 安装路径保持默认（`C:\Program Files\nodejs\`）
- 勾选 **Add to PATH**
- 一路 Next 完成

### 3.3 验证

```cmd
node -v
npm -v
```

输出应分别为 `v14.21.3` 和 `6.x`。

---

## 第 4 步：启动服务

### 方式一：双击 start.bat（前台窗口）

`start.bat` 内容：

```batch
@echo off
chcp 65001 >nul
title 惠每电子病历编辑器 HmEditor

cd /d %~dp0

set PORT=3071
set NODE_ENV=production

echo ========================================
echo  惠每电子病历编辑器 HmEditor
echo  启动中...
echo ========================================
echo.
echo 端口: %PORT%
echo 模式: %NODE_ENV%
echo 目录: %CD%
echo.

node index.js

echo.
echo 服务已停止。
pause
```

直接双击 `start.bat` 即可启动，关闭窗口即停止。

### 方式二：命令行直接启动

```cmd
cd /d D:\hm-editor
node index.js
```

如需自定义端口：

```cmd
set PORT=8080 && node index.js
```

### 启动成功标志

控制台输出：

```
========================================
欢迎使用 惠每智能电子病历编辑器
官网地址：https://editor.huimei.com/
========================================

📄 Demo 页面地址（本地）：
   http://127.0.0.1:3071/hmEditor/demo/index.html
```

### 访问验证

在服务器本机或局域网其他机器浏览器打开：

```
http://服务器IP:3071/hmEditor/demo/index.html
```

---

## 第 5 步：进程守护方案

### 方案 A：Windows 任务计划程序（推荐，无需额外安装）

**创建任务步骤：**

1. 打开 **任务计划程序**（`taskschd.msc`）
2. 右侧点击 **创建任务**
3. **常规** 标签：
   - 名称：`HmEditor`
   - 勾选 **不管用户是否登录都要运行**
   - 勾选 **使用最高权限运行**
4. **触发器** 标签 → **新建**：
   - 开始任务：**启动时**
5. **操作** 标签 → **新建**：
   - 操作：**启动程序**
   - 程序或脚本：`D:\hm-editor\start.bat`
   - 起始于：`D:\hm-editor`
6. 确定保存，输入管理员密码

**其他操作：**

- 手动启动：在任务列表右键 → **运行**
- 查看状态：查看任务历史记录或检查端口 `netstat -ano | findstr :3071`

### 方案 B：NSSM（Windows 服务注册）

在有网电脑下载 [NSSM](https://nssm.cc/download) 带到服务器：

```cmd
nssm install HmEditor "C:\Program Files\nodejs\node.exe" "D:\hm-editor\index.js"
nssm set HmEditor AppDirectory D:\hm-editor
nssm set HmEditor AppEnvironmentExtra PORT=3071 NODE_ENV=production
nssm start HmEditor
```

### 方案 C：PM2（需提前下载全局包）

在有网电脑上：

```cmd
npm install -g pm2
```

将 `%APPDATA%\npm\node_modules\pm2` 目录和 `%APPDATA%\npm\pm2.cmd` 拷贝到服务器相同相对路径。然后：

```cmd
pm2 start D:\hm-editor\bin\pm2.json --env production
pm2 save
pm2 startup
```

---

## 第 6 步：防火墙配置

放行服务端口，允许局域网其他机器访问：

```cmd
netsh advfirewall firewall add rule name="HmEditor" dir=in action=allow protocol=TCP localport=3071
```

如需删除规则：

```cmd
netsh advfirewall firewall delete rule name="HmEditor"
```

---

## 常见问题

### Q1：启动报错 `Cannot find module 'express'`

依赖未完整复制。检查 `node_modules\express` 是否存在。如果缺失，需在开发机上重新打包。

### Q2：启动报错 `The specified module could not be found`（canvas 相关）

`canvas` 原生模块 (.node 文件) 在传输过程中损坏或架构不匹配。确保开发机和服务器都是 **Windows x64**，重新拷贝 `node_modules\canvas\build\` 目录。

### Q3：页面能打开但无法打印 / 导出 PDF

打印功能依赖 `puppeteer`（Chromium）。检查：

```cmd
dir node_modules\puppeteer\.local-chromium
```

如果此目录为空，说明 Chromium 未随项目打包。在有网电脑上进入项目目录执行：

```cmd
npx puppeteer browsers install chrome
```

然后重新打包传输。

### Q4：中文字体显示异常

Windows Server 通常缺少中文字体。将开发机上的 `C:\Windows\Fonts\simsun.ttc`、`msyh.ttc` 等中文字体拷贝到服务器的 `C:\Windows\Fonts\`，或使用项目自带字体（`fontPackage\` 目录）。

### Q5：端口被占用

```cmd
netstat -ano | findstr :3071
```

找到占用进程的 PID，再通过任务管理器结束，或更换端口启动：

```cmd
set PORT=8080 && node index.js
```

### Q6：后台运行而不占用命令行窗口

```cmd
start /B node index.js
```

或使用任务计划程序方案（详见第 5 章）。

---

## 附录：最小文件清单

如果磁盘空间有限，以下为服务运行所必需的目录和文件，其他可酌情删除：

```
hm-editor/
├── index.js                  ← 必需：服务入口
├── package.json              ← 必需：依赖清单
├── node_modules/             ← 必需：全部依赖
├── editorDist/               ← 必需：前端编译产物
├── hmEditor/                 ← 必需：SDK 前端文件
│   ├── iframe/               ←   必需：编辑器加载器
│   ├── extensions/           ←   必需：扩展功能
│   └── demo/                 ←   可选：演示页面
├── src/                      ← 必需：后端逻辑
│   ├── editor.js
│   ├── print.js
│   ├── mock/
│   └── mcp-server.js
├── plugins/                  ← 必需：编辑器插件
├── vendor/                   ← 必需：第三方前端库
├── core/                     ← 必需：CKEditor 核心
├── skins/                    ← 必需：编辑器皮肤
├── lang/                     ← 必需：多语言文件
├── config.js                 ← 必需：编辑器配置
├── styles/                   ← 必需：样式表
├── fonts/                    ← 必需：字体图标
├── fontPackage/              ← 可选：系统字体
├── album/                    ← 可选：图库资源
├── adapters/                 ← 可选：适配器
├── print.css                 ← 可选：打印样式
├── contents.css              ← 可选：内容样式
└── start.bat                 ← 推荐：启动脚本
```

---

> 文档版本：v1.0 | 最后更新：2026-07-08
