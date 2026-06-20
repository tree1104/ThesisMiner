# ThesisMiner v8.0 常见问题解答（FAQ）

> 本文档收集 ThesisMiner v8.0 项目使用过程中的常见问题与解答。

## 目录

- [1. 安装与配置](#1-安装与配置)
- [2. 功能使用](#2-功能使用)
- [3. 性能问题](#3-性能问题)
- [4. 错误排查](#4-错误排查)
- [5. 开发相关](#5-开发相关)
- [6. 部署运维](#6-部署运维)

---

## 1. 安装与配置

### Q1: 系统要求是什么？

**A**: 
- Python 3.11+
- SQLite 3.40+
- 至少 2GB 内存
- 至少 10GB 磁盘空间

### Q2: 如何获取 API 密钥？

**A**: 
- OpenAI: https://platform.openai.com/api-keys
- DeepSeek: https://platform.deepseek.com/
- Anthropic: https://console.anthropic.com/
- 阿里云（通义千问）: https://dashscope.console.aliyun.com/
- Google（Gemini）: https://aistudio.google.com/
- 智谱（GLM）: https://open.bigmodel.cn/
- 字节（豆包）: https://volcengine.com/

### Q3: 配置文件在哪里？

**A**: 
- 环境变量: `.env` 文件
- 用户配置: `data/config.json`
- 默认配置: `backend/config.py`

优先级：环境变量 > config.json > 默认值

### Q4: 如何切换默认模型？

**A**: 修改 `data/config.json`:
```json
{
    "ai_model": "deepseek-v3.2",
    "step_models": {
        "orchestrator": "claude-sonnet-4.5",
        "reasoner": "deepseek-r2"
    }
}
```

---

## 2. 功能使用

### Q5: 如何创建多个对话？

**A**: 在会话管理页面，点击"新建对话"按钮，选择 Agent 类型，输入标题即可。每个会话支持多个对话并存，上下文完全隔离。

### Q6: 五阶段流程是什么？

**A**: 
1. **信息确权**：联网检索近 2 年文献，等待用户确认
2. **创意**：基于四维创意引擎生成候选论题
3. **校验**：评估新颖性与可行性，评分 < 60 回退
4. **生成**：多粒度生成（标题/摘要/大纲/全文）
5. **深度辅助**：文献精读/实验预研/答辩模拟

### Q7: 谱系图谱如何交互？

**A**: 
- **拖拽节点**：鼠标按住节点拖动
- **缩放画布**：鼠标滚轮
- **悬停高亮**：鼠标悬停节点高亮关联
- **点击详情**：点击节点查看详情
- **类型过滤**：顶部工具栏勾选

### Q8: 如何导出论题？

**A**: 在生成阶段完成后，点击"导出"按钮，支持 Markdown、HTML、PDF 格式。

---

## 3. 性能问题

### Q9: 响应慢怎么办？

**A**: 
1. 检查网络连接
2. 确认 LLM API 可用
3. 查看缓存命中率（`/api/cache-stats`）
4. 检查数据库是否需要优化（`VACUUM; ANALYZE;`）
5. 增加 Uvicorn workers

### Q10: 内存占用高？

**A**: 
1. 检查活跃对话数量
2. 清理历史消息
3. 调整缓存大小
4. 重启服务释放内存

### Q11: 谱系图渲染卡顿？

**A**: 
1. 减少节点数量（过滤）
2. 降低节点大小
3. 使用现代浏览器
4. 关闭动画效果

---

## 4. 错误排查

### Q12: 启动报错 "ModuleNotFoundError"？

**A**: 
```bash
# 确保虚拟环境已激活
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate  # Windows

# 重新安装依赖
pip install -r requirements.txt
```

### Q13: 数据库锁定 "database is locked"？

**A**: 
```bash
# 检查锁定状态
sqlite3 data/thesisminer.db "PRAGMA lock_status"

# 执行 checkpoint
sqlite3 data/thesisminer.db "PRAGMA wal_checkpoint(TRUNCATE)"

# 重启服务
sudo systemctl restart thesisminer
```

### Q14: LLM 调用失败？

**A**: 
1. 检查 API 密钥是否正确
2. 检查账户余额
3. 检查网络连接
4. 查看错误日志
5. 尝试切换模型

### Q15: 缓存命中率低？

**A**: 
1. 确认使用 DeepSeek 模型
2. 检查 Prompt 前缀是否一致
3. 查看缓存监控日志
4. 重启服务重置缓存

---

## 5. 开发相关

### Q16: 如何运行测试？

**A**: 
```bash
# 全部测试
pytest

# 单元测试
pytest tests/unit/

# 特定测试
pytest tests/unit/test_orchestrator.py

# 带覆盖率
pytest --cov=backend --cov-report=html
```

### Q17: 如何添加新 Agent？

**A**: 
1. 创建 `backend/agents/my_agent.py`
2. 继承 `BaseAgent`
3. 实现 `run` 方法
4. 使用 `@register_agent("my_agent")` 注册
5. 编写测试

### Q18: 如何添加约束规则？

**A**: 
1. 在 `backend/constraints/` 添加规则模块
2. 定义规则函数
3. 注册到规则引擎
4. 编写测试

---

## 6. 部署运维

### Q19: 如何备份？

**A**: 
```bash
# 手动备份
sqlite3 data/thesisminer.db ".backup data/backups/backup.db"

# 自动备份（crontab）
0 2 * * * /opt/thesisminer/backup.sh
```

### Q20: 如何升级？

**A**: 
```bash
# 1. 备份
./backup.sh

# 2. 停止服务
sudo systemctl stop thesisminer

# 3. 拉取代码
git pull origin main

# 4. 更新依赖
pip install -r requirements.txt

# 5. 数据库迁移
python -c "from backend.database import migrate_db; migrate_db()"

# 6. 启动服务
sudo systemctl start thesisminer
```

### Q21: 如何监控？

**A**: 
- 健康检查: `GET /api/health`
- 缓存统计: `GET /api/cache-stats`
- 日志: `logs/thesisminer.log`
- 系统指标: `htop`, `df -h`

---

## 结语

如有未覆盖的问题，请在 GitHub Issues 提问。
