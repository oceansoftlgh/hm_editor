# Git 工作流速查（hm_editor fork 仓库）

> 本仓库是 `huimeicloud/hm_editor`（惠每云上游）的 fork，日常开发与上游同步命令统一记录在此。

## 仓库配置

| 远程 | 地址 | 用途 |
|------|------|------|
| `origin` | https://github.com/oceansoftlgh/hm_editor.git | 自己的线上 fork（推送目标） |
| `upstream` | https://github.com/huimeicloud/hm_editor.git | 第三方上游（同步来源） |

- 默认工作分支：`main`（与线上一致，跟随上游 `main`）
- 已有共同祖先：本地历史 = 上游 23 个提交 + 自己的修改，可正常 merge

## 日常开发提交（自己修改后）

```powershell
# 1. 查看状态与差异
git status
git diff

# 2. 暂存（按需选一种）
git add .                        # 全部修改（含新增文件，受 .gitignore 约束）
git add <具体文件路径>            # 只暂存指定文件

# 3. 提交
git commit -m "fix: 修复xxx问题"

# 4. 推送到自己的线上仓库
git push origin main
```

## 跟随上游更新（惠每云有新版本时）

```powershell
# 1. 拉取上游最新（推荐每次都先 fetch）
git fetch upstream

# 2. 合并上游 main 到本地（方式一：merge，保留合并记录）
git merge upstream/main

# 方式二：rebase，保持线性历史（需要本地无未提交修改）
# git pull --rebase upstream main

# 3. 若有冲突：手动解决后
# git add <冲突文件>
# git merge --continue     （或 git rebase --continue）

# 4. 推送
git push origin main
```

> 冲突只发生在「你和上游都改过」的文件上。解决后务必测试再推送。

## 常见场景

### 提交后忘记推送 / 想改提交说明

```powershell
git commit --amend -m "新提交说明"     # 修改最近一次提交说明
git push origin main                  # 注意：amend 后若已推送过需强推，慎用
```

### 丢弃本地未提交的修改（危险，会丢失改动）

```powershell
git checkout -- <文件路径>      # 丢弃单个文件
git checkout -- .               # 丢弃全部未提交修改
```

### 查看提交历史

```powershell
git log --oneline -10           # 最近 10 条
git log --oneline --graph       # 图形化查看分支结构
```

### 撤销上一次提交（保留修改到工作区）

```powershell
git reset --soft HEAD~1         # 撤销提交，修改保留在暂存区
```

## 注意事项

1. 不要向 `upstream` 直接 push（无权限，也不应该）
2. `.deepseek/`、`task/`、`/.codewhale`、`/.idea` 已在 `.gitignore`，不会入库
3. 线上默认分支是 `main`，`master` 已删除，不要再创建 `master` 分支混淆
4. 推送前确认：`git status` 干净、`git diff` 是自己想要的改动
