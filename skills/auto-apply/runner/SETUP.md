# 一次性设置（在你 Mac 的"终端"里做）

打开"终端"（⌘空格 → 输入 终端 → 回车），按顺序做。

## 1. 安装并自检（约 1 分钟）
```bash
bash ~/Desktop/"job search agent"/skills/auto-apply/runner/setup.sh
```
最后应看到 `== Greenhouse API reachable: True` 和 `== setup check done`。
会打开一个新的 Chrome 窗口（独立配置 `~/.job-agent-chrome`）——这个窗口只用来投递，不用登录你的个人账号。

## 2. Gmail 应用专用密码（用来自动读取验证码，只读）
1. 打开 https://myaccount.google.com/security （用 **alex.rivera@example.com** 登录）。
2. 确认"两步验证"已开启。
3. 打开 https://myaccount.google.com/apppasswords → 名称填 `job agent` → 创建 → 复制那 16 位密码。
4. 回到终端，运行下面这行，按提示粘贴两次（输入时不会显示，这是正常的）：
```bash
security add-generic-password -a alex.rivera@example.com -s job-agent-gmail -w
```
5. 再运行一次第 1 步，应看到 `== Gmail app password: in Keychain`。

密码只存在你 Mac 的钥匙串里，不会出现在任何文件、聊天或日志里。随时可以在 Google 账号里删除这个应用密码。

## 3. 其他网站的密码（以后需要时再做）
Greenhouse / Lever 不需要账号。Workday、iCIMS 等需要账号的网站，等用到时我会告诉你具体命令，格式是：
```bash
security add-generic-password -a alex.rivera@example.com -s job-agent-<网站名> -w
```

## 4. 第一次试跑（只填不交）
做完 1–2 后告诉我。所有命令都用 `~/.job-agent-venv/bin/python`（不是 python3）。我会准备好一个真实职位的 `plan.json`，你在终端里运行一条命令，它会在那个 Chrome 窗口里自动填表、核对，然后停下（不提交）。
