# ThesisMiner v8.0 数据库运维手册

> 本文档详细描述 ThesisMiner v8.0 项目数据库的运维操作、备份恢复、性能调优、故障排查与最佳实践。

## 目录

- [1. 数据库概览](#1-数据库概览)
- [2. 部署与初始化](#2-部署与初始化)
- [3. 日常运维](#3-日常运维)
- [4. 备份与恢复](#4-备份与恢复)
- [5. 性能调优](#5-性能调优)
- [6. 监控与告警](#6-监控与告警)
- [7. 故障排查](#7-故障排查)
- [8. 数据迁移](#8-数据迁移)
- [9. 安全管理](#9-安全管理)
- [10. 容量规划](#10-容量规划)
- [11. 高可用方案](#11-高可用方案)
- [12. 附录](#12-附录)

---

## 1. 数据库概览

### 1.1 数据库选型

ThesisMiner v8.0 使用 SQLite 作为主数据库，原因：

1. **轻量**：无需独立数据库服务，部署简单
2. **可靠**：ACID 事务保证
3. **性能**：WAL 模式下支持并发读写
4. **便携**：单文件存储，便于备份迁移
5. **成熟**：广泛使用，生态完善

### 1.2 数据库文件

```
data/
├── thesisminer.db       # 主数据库
├── thesisminer.db-wal   # WAL 日志
├── thesisminer.db-shm   # 共享内存
└── backups/             # 备份目录
    ├── 2026-06-19.db
    └── 2026-06-18.db
```

### 1.3 表清单

| 表名 | 用途 | 预估行数 |
|------|------|---------|
| sessions | 会话 | < 1000 |
| conversations | 对话 | < 10000 |
| conversation_messages | 消息 | < 100000 |
| search_citations | 引用 | < 50000 |
| budget_ledger | 预算 | < 10000 |
| lineage_nodes | 谱系节点 | < 1000 |
| lineage_edges | 谱系边 | < 5000 |
| theses | 论题 | < 5000 |

---

## 2. 部署与初始化

### 2.1 初始化数据库

```python
# backend/database.py
def init_database(db_path: str = None):
    """初始化数据库"""
    if db_path is None:
        db_path = DB_PATH
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    
    # 创建表
    conn.executescript(SCHEMA_SQL)
    
    # 创建索引
    conn.executescript(INDEX_SQL)
    
    conn.commit()
    conn.close()
```

### 2.2 数据库配置

```sql
-- WAL 模式（Write-Ahead Logging）
PRAGMA journal_mode=WAL;

-- 外键约束
PRAGMA foreign_keys=ON;

-- 同步模式（NORMAL 平衡性能与安全）
PRAGMA synchronous=NORMAL;

-- 缓存大小（负数表示 KB）
PRAGMA cache_size=-64000;  -- 64MB

-- 临时存储
PRAGMA temp_store=MEMORY;

-- 忙等待超时（毫秒）
PRAGMA busy_timeout=5000;
```

---

## 3. 日常运维

### 3.1 日常检查清单

```bash
# 1. 检查数据库大小
ls -lh data/thesisminer.db

# 2. 检查 WAL 文件大小
ls -lh data/thesisminer.db-wal

# 3. 检查完整性
sqlite3 data/thesisminer.db "PRAGMA integrity_check;"

# 4. 检查外键完整性
sqlite3 data/thesisminer.db "PRAGMA foreign_key_check;"

# 5. 检查索引健康
sqlite3 data/thesisminer.db "PRAGMA optimize;"
```

### 3.2 定期维护

```python
def weekly_maintenance():
    """每周维护"""
    conn = get_db_connection()
    
    # 1. ANALYZE 更新统计信息
    conn.execute("ANALYZE")
    
    # 2. 清理碎片
    conn.execute("VACUUM")
    
    # 3. 优化索引
    conn.execute("PRAGMA optimize")
    
    # 4. 检查完整性
    result = conn.execute("PRAGMA integrity_check").fetchone()
    if result[0] != "ok":
        send_alert("数据库完整性检查失败")
    
    conn.commit()
    conn.close()
```

---

## 4. 备份与恢复

### 4.1 备份策略

```python
import shutil
from datetime import datetime

def backup_database():
    """备份数据库"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_path = f"data/backups/thesisminer_{timestamp}.db"
    
    # 使用 SQLite Online Backup API
    conn = get_db_connection()
    backup_conn = sqlite3.connect(backup_path)
    
    conn.backup(backup_conn)
    
    backup_conn.close()
    conn.close()
    
    # 压缩备份
    shutil.make_archive(backup_path, 'zip', root_dir='data/backups', 
                       base_dir=f'thesisminer_{timestamp}.db')
    
    return backup_path + '.zip'
```

### 4.2 恢复流程

```python
def restore_database(backup_path: str):
    """恢复数据库"""
    # 1. 停止应用
    stop_application()
    
    # 2. 备份当前数据库
    shutil.copy("data/thesisminer.db", "data/thesisminer.db.pre_restore")
    
    # 3. 恢复备份
    conn = sqlite3.connect("data/thesisminer.db")
    backup_conn = sqlite3.connect(backup_path)
    backup_conn.backup(conn)
    conn.close()
    backup_conn.close()
    
    # 4. 验证完整性
    conn = get_db_connection()
    result = conn.execute("PRAGMA integrity_check").fetchone()
    if result[0] != "ok":
        # 恢复失败，回滚
        shutil.copy("data/thesisminer.db.pre_restore", "data/thesisminer.db")
        raise Exception("恢复失败，已回滚")
    
    conn.close()
    
    # 5. 启动应用
    start_application()
```

---

## 5. 性能调优

### 5.1 索引优化

```sql
-- 消息表索引
CREATE INDEX idx_messages_conv_created 
    ON conversation_messages(conversation_id, created_at DESC);

CREATE INDEX idx_messages_agent 
    ON conversation_messages(agent_id);

-- 引用表索引
CREATE INDEX idx_citations_message 
    ON search_citations(message_id);

CREATE INDEX idx_citations_domain 
    ON search_citations(source_domain);

-- 会话表索引
CREATE INDEX idx_sessions_created 
    ON sessions(created_at DESC);
```

### 5.2 查询优化

```python
# 差：SELECT *
def get_messages_bad(conv_id):
    return execute_query(
        "SELECT * FROM conversation_messages WHERE conversation_id = ?",
        [conv_id]
    )

# 好：只查需要的列
def get_messages_good(conv_id, limit=50):
    return execute_query(
        """SELECT id, role, content, reasoning, created_at 
           FROM conversation_messages 
           WHERE conversation_id = ? 
           ORDER BY created_at DESC 
           LIMIT ?""",
        [conv_id, limit]
    )
```

### 5.3 批量操作

```python
# 批量插入
def batch_insert_citations(citations: list):
    conn = get_db_connection()
    conn.executemany(
        """INSERT INTO search_citations 
           (id, message_id, url, title, snippet, source_domain, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [(c.id, c.message_id, c.url, c.title, c.snippet, c.source_domain, c.created_at) 
         for c in citations]
    )
    conn.commit()
    conn.close()
```

---

## 6. 监控与告警

### 6.1 监控指标

```python
def get_db_metrics():
    """获取数据库指标"""
    conn = get_db_connection()
    
    # 数据库大小
    db_size = os.path.getsize(DB_PATH)
    
    # WAL 大小
    wal_path = DB_PATH + "-wal"
    wal_size = os.path.getsize(wal_path) if os.path.exists(wal_path) else 0
    
    # 表行数
    table_counts = {}
    for table in ["sessions", "conversations", "conversation_messages", "search_citations"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        table_counts[table] = count
    
    # 慢查询（通过日志）
    slow_queries = get_slow_queries(threshold_ms=100)
    
    conn.close()
    
    return {
        "db_size_mb": db_size / 1024 / 1024,
        "wal_size_mb": wal_size / 1024 / 1024,
        "table_counts": table_counts,
        "slow_queries": slow_queries
    }
```

### 6.2 告警规则

```python
ALERT_RULES = [
    {
        "name": "db_size_too_large",
        "condition": lambda m: m["db_size_mb"] > 1024,
        "message": "数据库大小超过 1GB"
    },
    {
        "name": "wal_size_too_large",
        "condition": lambda m: m["wal_size_mb"] > 100,
        "message": "WAL 文件过大，需要 checkpoint"
    },
    {
        "name": "integrity_check_failed",
        "condition": lambda m: not m["integrity_ok"],
        "message": "数据库完整性检查失败"
    }
]
```

---

## 7. 故障排查

### 7.1 数据库锁定

```python
# 检查锁定状态
def check_locks():
    conn = get_db_connection()
    locks = conn.execute("PRAGMA lock_status").fetchall()
    conn.close()
    return locks

# 解决锁定
def resolve_lock():
    # 1. 检查是否有长事务
    # 2. 终止长事务
    # 3. 设置 busy_timeout
    # 4. 重启应用
    pass
```

### 7.2 性能下降

```python
# 分析查询计划
def explain_query(sql: str, params: list):
    conn = get_db_connection()
    plan = conn.execute(f"EXPLAIN QUERY PLAN {sql}", params).fetchall()
    conn.close()
    return plan

# 示例
plan = explain_query(
    "SELECT * FROM conversation_messages WHERE conversation_id = ?",
    ["conv1"]
)
# 如果看到 "SCAN TABLE" 而非 "SEARCH TABLE USING INDEX"，说明缺少索引
```

---

## 8. 数据迁移

### 8.1 Schema 迁移

```python
def migrate_db():
    """数据库迁移"""
    conn = get_db_connection()
    current_version = get_schema_version(conn)
    
    migrations = [
        (1, "v1_initial", migrate_v1),
        (2, "v2_add_conversations", migrate_v2),
        (3, "v3_add_citations", migrate_v3),
        (8, "v8_multi_agent", migrate_v8)
    ]
    
    for version, name, func in migrations:
        if version > current_version:
            print(f"执行迁移: {name}")
            func(conn)
            update_schema_version(conn, version)
    
    conn.commit()
    conn.close()
```

---

## 9. 安全管理

### 9.1 访问控制

```python
# 数据库文件权限
import os
os.chmod("data/thesisminer.db", 0o600)

# 目录权限
os.chmod("data", 0o700)
```

### 9.2 SQL 注入防护

```python
# 好：参数化查询
def get_session(session_id: str):
    return execute_query(
        "SELECT * FROM sessions WHERE id = ?",
        [session_id]
    )

# 差：字符串拼接（SQL 注入风险）
def get_session_bad(session_id: str):
    return execute_query(
        f"SELECT * FROM sessions WHERE id = '{session_id}'"
    )
```

---

## 10. 容量规划

### 10.1 容量预估

| 数据类型 | 单条大小 | 月增长 | 年增长 |
|---------|---------|--------|--------|
| 会话 | 1KB | 100 | 1.2K |
| 对话 | 1KB | 1000 | 12K |
| 消息 | 5KB | 10000 | 120K |
| 引用 | 2KB | 5000 | 60K |
| **总计** | - | ~80MB | ~1GB |

### 10.2 容量告警

```python
def check_capacity():
    metrics = get_db_metrics()
    
    if metrics["db_size_mb"] > 800:
        alert("数据库容量达 80%，需要清理或扩容")
    
    if metrics["table_counts"]["conversation_messages"] > 800000:
        alert("消息表行数达 80万，考虑归档旧数据")
```

---

## 11. 高可用方案

### 11.1 主从复制（LiteFS）

```yaml
# LiteFS 配置
litefs:
  primary: true
  candidate: true
  
  # 从节点配置
  # proxy:
  #   target: primary:20202
```

### 11.2 故障切换

```python
def failover():
    """故障切换流程"""
    # 1. 检测主节点故障
    if not check_primary_health():
        # 2. 提升从节点为主
        promote_replica()
        # 3. 更新应用配置
        update_db_config(new_primary)
        # 4. 验证服务
        verify_service()
```

---

## 12. 附录

### 12.1 常用 SQL 速查

```sql
-- 查看表结构
.schema sessions

-- 查看索引
.indices conversation_messages

-- 查看表统计
SELECT name, (SELECT COUNT(*) FROM sessions) as count FROM sqlite_master WHERE name='sessions';

-- 查看数据库设置
PRAGMA database_list;
PRAGMA compile_options;

-- 检查完整性
PRAGMA integrity_check;
PRAGMA foreign_key_check;

-- 优化
ANALYZE;
VACUUM;
PRAGMA optimize;
```

### 12.2 运维脚本

```bash
#!/bin/bash
# db_maintenance.sh - 数据库维护脚本

DB_PATH="data/thesisminer.db"
BACKUP_DIR="data/backups"

# 1. 备份
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
sqlite3 "$DB_PATH" ".backup $BACKUP_DIR/thesisminer_$TIMESTAMP.db"

# 2. 完整性检查
RESULT=$(sqlite3 "$DB_PATH" "PRAGMA integrity_check;")
if [ "$RESULT" != "ok" ]; then
    echo "ALERT: 完整性检查失败"
    exit 1
fi

# 3. 优化
sqlite3 "$DB_PATH" "ANALYZE;"

# 4. 清理旧备份（保留30天）
find "$BACKUP_DIR" -name "thesisminer_*.db" -mtime +30 -delete

echo "维护完成"
```

---

## 结语

数据库是 ThesisMiner v8.0 的核心组件，良好的运维实践是系统稳定运行的基础。通过定期备份、性能监控、容量规划，确保数据库的可靠性、性能与可扩展性。
