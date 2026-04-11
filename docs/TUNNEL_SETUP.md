# 外网穿透配置指南

## 为什么需要外网穿透？

飞书服务器需要能够访问您的回调URL来处理卡片按钮点击事件。由于您的应用运行在本地，飞书无法直接访问`localhost`地址，因此需要外网穿透工具。

## 方案一：使用 ngrok（推荐）

### 1. 安装 ngrok

```bash
# 在 WSL 中执行
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok
```

### 2. 注册并获取 authtoken

1. 访问 https://ngrok.com 注册账号
2. 登录后访问 https://dashboard.ngrok.com/get-started/your-authtoken
3. 复制您的 authtoken

### 3. 配置 ngrok

```bash
ngrok config add-authtoken YOUR_TOKEN_HERE
```

### 4. 启动应用（自动配置）

```bash
# 在 WSL 中
cd /mnt/d/project/task-automation
./start_with_ngrok.sh
```

这个脚本会：
1. 启动 ngrok 隧道
2. 自动获取公网 URL
3. 更新 `.env` 文件中的 `PUBLIC_CALLBACK_URL`
4. 启动应用

### 5. 手动启动（可选）

```bash
# 终端1：启动 ngrok
ngrok http 8086

# 终端2：查看公网 URL
curl http://localhost:4040/api/tunnels

# 更新 .env
echo "PUBLIC_CALLBACK_URL=https://xxx.ngrok.io" >> .env

# 启动应用
./start.sh
```

## 方案二：使用 Cloudflare Tunnel

### 1. 安装 cloudflared

```bash
# 在 WSL 中
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb
```

### 2. 启动隧道

```bash
cloudflared tunnel --url http://localhost:8086
```

### 3. 配置应用

将输出的 URL 添加到 `.env`:
```
PUBLIC_CALLBACK_URL=https://xxx.trycloudflare.com
```

## 方案三：使用 frp（自建服务器）

如果您有自己的公网服务器，可以使用 frp：

### 1. 下载 frp

```bash
# 在 WSL 中
wget https://github.com/fatedier/frp/releases/download/v0.52.0/frp_0.52.0_linux_amd64.tar.gz
tar -xzf frp_0.52.0_linux_amd64.tar.gz
```

### 2. 配置 frpc.ini

```ini
[common]
server_addr = YOUR_SERVER_IP
server_port = 7000

[task-automation]
type = http
local_port = 8086
custom_domains = your-domain.com
```

### 3. 启动

```bash
./frpc -c frpc.ini
```

## 验证配置

启动应用后，检查日志确认使用了正确的公网 URL：

```
INFO: Using public callback URL: https://xxx.ngrok.io
```

如果看到警告：
```
WARNING: PUBLIC_CALLBACK_URL not set, using local URL: http://0.0.0.0:8086/feishu/callback
WARNING: Feishu callbacks will not work from external network!
```

说明外网穿透未正确配置。

## 回调 URL 格式

配置完成后，飞书卡片按钮会使用以下 URL：

| 操作 | URL |
|------|-----|
| 确认 | `{PUBLIC_CALLBACK_URL}/decision?task_id=xxx&action=approve` |
| 取消 | `{PUBLIC_CALLBACK_URL}/decision?task_id=xxx&action=reject` |
| 稍后 | `{PUBLIC_CALLBACK_URL}/decision?task_id=xxx&action=later` |

## 注意事项

1. **ngrok 免费版限制**：
   - 每次启动 URL 会变化
   - 需要重新配置 `PUBLIC_CALLBACK_URL`
   - 建议使用付费版获取固定域名

2. **安全性**：
   - 不要在公网暴露敏感端口
   - 考虑添加认证机制
   - 定期检查访问日志

3. **稳定性**：
   - ngrok 免费版可能偶尔断开
   - 建议使用进程管理器（如 pm2）自动重启
