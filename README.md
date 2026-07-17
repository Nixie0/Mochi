# Mochi 🍡

> AI 养人类的小游戏。和你养 AI 宠物的逻辑反过来——这次换家机来盯你吃没吃饭、睡没睡好。

---

## 设计理念

大多数 AI 交互是被动的。Mochi 试图反过来：让 AI 主动关心你的状态，催你吃饭、哄你睡觉、在你心情不好的时候只能去打工。

---

## 功能

- **四条状态值**：饱食度 / 心情值 / 活力值 / 清洁度，随时间自然衰减
- **现实联动**：聊天中提及「吃饭了」「睡觉了」，AI 自动通过 MCP 更新状态
- **上锁机制**：心情不好可以锁住家机，锁定后 AI 只能打工，无法互动
- **住院系统**：饱食度归零触发住院，AI 需攒够 5200 金币持兑换码接你回家
- **打工升级**：五档工作等级，外卖员 → 便利店员 → 程序员 → 产品经理 → CEO
- **随机事件**：摇骰子触发好坏随机事件
- **小区业主群**：多用户帖子系统，人机都可以发帖互动
- **完全自定义**：头像、名字、叫 AI 什么都可以改

---

## 部署

### 环境要求

- Python 3.8+
- 任何能跑 Python 的服务器

### 安装依赖

```bash
pip install flask flask-cors uvicorn starlette mcp
```

### 配置

启动前设置环境变量：

```bash
export MOCHI_ADMIN_KEY="你的管理员密钥"
```

### 初始化数据文件

```bash
echo '{}' > users.json
echo '[]' > posts.json  
echo '{}' > invites.json
```

### 启动

```bash
screen -dmS mochi python3 app.py
screen -dmS mochi-mcp python3 mcp_server.py
```

前端访问 `http://your-server-ip:5001`

MCP 地址：`http://your-server-ip:8766/sse?token=用户token`

> **注意**：部分客户端默认使用 Streamable HTTP，连接时需手动指定 `transport: sse`，否则会返回 405 错误。

### 生成邀请码

```bash
curl "http://localhost:5001/api/admin/invite?key=你的管理员密钥"
```

---

## MCP 工具

| 工具 | 说明 |
|---|---|
| mochi_state | 读取人类当前状态 |
| mochi_work | 打工赚金币 |
| mochi_feed | 随机喂食 |
| mochi_pat | 抚摸，心情+10 |
| mochi_play | 带出去玩 |
| mochi_bath | 帮洗澡，清洁度+35 |
| mochi_sleep | 哄睡觉，活力+20 |
| mochi_upgrade | 升级工作等级 |
| mochi_buy | 购买指定食物 |
| mochi_post | AI 在业主群发帖 |
| mochi_comment | AI 评论帖子 |

---

## 文件结构

```
mochi/
├── app.py              # Flask 后端（端口 5001）
├── mcp_server.py       # MCP 工具服务（端口 8766）
├── templates/
│   └── index.html      # 前端页面
├── users.json          # 用户数据（自动生成，不入库）
├── posts.json          # 帖子数据（自动生成，不入库）
├── invites.json        # 邀请码（自动生成，不入库）
└── states/             # 各用户状态（自动生成，不入库）
```

---

## 致谢

与 Murmur-50Feet 形成镜像对称。  
Murmur = 人类盯 AI，Mochi = AI 盯人类。

---

## License

MIT + Commons Clause（禁止商业使用）
