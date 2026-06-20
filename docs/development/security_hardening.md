# ThesisMiner v8.0 安全加固文档

> **文档版本**：v8.0.0
> **最后更新**：2026-06-20
> **文档负责**：ThesisMiner Security Team
> **审阅状态**：Approved
> **适用范围**：ThesisMiner v8.0 全部生产环境、预发环境、开发环境
> **机密级别**：内部机密（Confidential）

---

## 目录

- [1. 概述](#1-概述)
  - [1.1 文档目的](#11-文档目的)
  - [1.2 安全理念](#12-安全理念)
  - [1.3 设计原则](#13-设计原则)
  - [1.4 术语表](#14-术语表)
- [2. 操作系统加固](#2-操作系统加固)
  - [2.1 系统更新](#21-系统更新)
  - [2.2 内核参数加固](#22-内核参数加固)
  - [2.3 服务最小化](#23-服务最小化)
  - [2.4 用户与组管理](#24-用户与组管理)
  - [2.5 sudo 配置](#25-sudo-配置)
  - [2.6 SSH 加固](#26-ssh-加固)
- [3. 网络加固](#3-网络加固)
  - [3.1 防火墙配置](#31-防火墙配置)
  - [3.2 端口管理](#32-端口管理)
  - [3.3 网络分段](#33-网络分段)
  - [3.4 DDoS 防护](#34-ddos-防护)
  - [3.5 WAF 配置](#35-waf-配置)
- [4. 应用加固](#4-应用加固)
  - [4.1 FastAPI 加固](#41-fastapi-加固)
  - [4.2 输入验证](#42-输入验证)
  - [4.3 输出编码](#43-输出编码)
  - [4.4 会话安全](#44-会话安全)
  - [4.5 CSRF 防护](#45-csrf-防护)
  - [4.6 XSS 防护](#46-xss-防护)
  - [4.7 SQL 注入防护](#47-sql-注入防护)
  - [4.8 文件上传安全](#48-文件上传安全)
- [5. 文件与目录权限](#5-文件与目录权限)
  - [5.1 权限模型](#51-权限模型)
  - [5.2 关键文件权限](#52-关键文件权限)
  - [5.3 敏感文件保护](#53-敏感文件保护)
  - [5.4 临时文件安全](#54-临时文件安全)
- [6. 日志审计](#6-日志审计)
  - [6.1 审计日志](#61-审计日志)
  - [6.2 系统日志](#62-系统日志)
  - [6.3 应用日志](#63-应用日志)
  - [6.4 日志保护](#64-日志保护)
- [7. 入侵检测](#7-入侵检测)
  - [7.1 HIDS](#71-hids)
  - [7.2 NIDS](#72-nids)
  - [7.3 文件完整性监控](#73-文件完整性监控)
  - [7.4 异常检测](#74-异常检测)
- [8. 漏洞扫描](#8-漏洞扫描)
  - [8.1 扫描类型](#81-扫描类型)
  - [8.2 镜像扫描](#82-镜像扫描)
  - [8.3 代码扫描](#83-代码扫描)
  - [8.4 依赖扫描](#84-依赖扫描)
  - [8.5 渗透测试](#85-渗透测试)
- [9. 安全基线](#9-安全基线)
  - [9.1 CIS Benchmark](#91-cis-benchmark)
  - [9.2 合规检查](#92-合规检查)
  - [9.3 基线扫描](#93-基线扫描)
- [10. 密钥与凭证管理](#10-密钥与凭证管理)
  - [10.1 密钥管理](#101-密钥管理)
  - [10.2 凭证管理](#102-凭证管理)
  - [10.3 证书管理](#103-证书管理)
  - [10.4 密钥轮换](#104-密钥轮换)
- [11. 安全加固案例](#11-安全加固案例)
  - [11.1 案例一：服务器加固](#111-案例一服务器加固)
  - [11.2 案例二：应用安全加固](#112-案例二应用安全加固)
  - [11.3 案例三：网络加固](#113-案例三网络加固)
  - [11.4 案例四：应急响应](#114-案例四应急响应)
- [12. 检查清单](#12-检查清单)
  - [12.1 操作系统检查清单](#121-操作系统检查清单)
  - [12.2 网络检查清单](#122-网络检查清单)
  - [12.3 应用检查清单](#123-应用检查清单)
  - [12.4 综合检查清单](#124-综合检查清单)
- [13. 附录](#13-附录)
  - [13.1 配置示例](#131-配置示例)
  - [13.2 工具列表](#132-工具列表)
  - [13.3 参考资料](#133-参考资料)
  - [13.4 变更记录](#134-变更记录)

---

## 1. 概述

### 1.1 文档目的

本文档定义 ThesisMiner v8.0 系统的安全加固规范，覆盖操作系统加固、网络加固、应用加固、文件权限、日志审计、入侵检测、漏洞扫描、安全基线、密钥管理等主题。文档面向以下读者：

- **安全工程师**：负责安全加固方案制定与实施
- **SRE 与运维工程师**：负责服务器、网络、应用的安全配置
- **后端开发工程师**：负责在 ThesisMiner 各模块（`backend/agents`、`backend/sessions`、`backend/orchestration`、`backend/ai`、`backend/analytics`、`backend/ml`、`backend/export`、`backend/knowledge`、`backend/validation`、`backend/routing`、`backend/integrity`、`backend/optimization`、`backend/nlp`、`backend/monitoring`、`backend/planning`、`backend/reasoning` 等）中实现安全编码
- **DBA**：负责 SQLite 数据库安全配置
- **架构师**：评审安全架构合理性

文档目标是让任何一名工程师在阅读后能够：

1. 理解 ThesisMiner v8.0 安全加固整体方案
2. 知道如何加固操作系统、网络、应用
3. 能够执行安全检查与漏洞扫描
4. 能够处理安全事件
5. 能够基于 CIS Benchmark 制定安全基线

### 1.2 安全理念

ThesisMiner v8.0 安全理念：

- **纵深防御**：多层防护，单层失效不影响整体
- **最小权限**：任何实体只授予最小必要权限
- **默认安全**：默认配置即安全配置
- **假设失陷**：假设系统已被入侵，设计检测与响应
- **安全左移**：在开发阶段就考虑安全，而非事后补救
- **零信任**：不信任任何请求，全部验证

### 1.3 设计原则

| 编号 | 原则 | 说明 |
|------|------|------|
| P1 | **纵深防御** | 多层防护，避免单点失效 |
| P2 | **最小权限** | 最小必要权限 |
| P3 | **默认安全** | 默认配置即安全 |
| P4 | **假设失陷** | 设计检测与响应 |
| P5 | **安全左移** | 开发阶段考虑安全 |
| P6 | **零信任** | 不信任，全验证 |
| P7 | **可审计** | 所有操作可审计 |
| P8 | **持续监控** | 7x24 安全监控 |

### 1.4 术语表

| 术语 | 英文 | 说明 |
|------|------|------|
| HIDS | Host-based IDS | 主机入侵检测 |
| NIDS | Network IDS | 网络入侵检测 |
| WAF | Web Application Firewall | Web 应用防火墙 |
| DDoS | Distributed Denial of Service | 分布式拒绝服务 |
| CSRF | Cross-Site Request Forgery | 跨站请求伪造 |
| XSS | Cross-Site Scripting | 跨站脚本 |
| SQLi | SQL Injection | SQL 注入 |
| RCE | Remote Code Execution | 远程代码执行 |
| LFI | Local File Inclusion | 本地文件包含 |
| RFI | Remote File Inclusion | 远程文件包含 |
| CIS | Center for Internet Security | 互联网安全中心 |
| CVE | Common Vulnerabilities and Exposures | 通用漏洞披露 |
| CVSS | Common Vulnerability Scoring System | 通用漏洞评分 |
| SBOM | Software Bill of Materials | 软件物料清单 |
| MFA | Multi-Factor Authentication | 多因素认证 |
| RBAC | Role-Based Access Control | 基于角色的访问控制 |
| ABAC | Attribute-Based Access Control | 基于属性的访问控制 |
| IAM | Identity and Access Management | 身份与访问管理 |
| KMS | Key Management Service | 密钥管理服务 |
| HSM | Hardware Security Module | 硬件安全模块 |
| SIEM | Security Information and Event Management | 安全信息与事件管理 |
| SOAR | Security Orchestration, Automation and Response | 安全编排自动化响应 |

---

## 2. 操作系统加固

### 2.1 系统更新

#### 2.1.1 更新策略

- **安全补丁**：发布后 7 天内安装
- **重要更新**：发布后 30 天内安装
- **一般更新**：每月维护窗口安装
- **内核更新**：在维护窗口重启安装

#### 2.1.2 自动更新配置

```bash
# Ubuntu/Debian
apt-get install unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades

# /etc/apt/apt.conf.d/50unattended-upgrades
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
};
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
```

```bash
# RHEL/CentOS
yum install yum-cron
systemctl enable yum-cron
systemctl start yum-cron

# /etc/yum/yum-cron.conf
update_cmd = security
update_messages = yes
download_updates = yes
apply_updates = yes
```

#### 2.1.3 更新验证

```bash
#!/bin/bash
# scripts/security/check_updates.sh

set -euo pipefail

echo "Checking for security updates..."

# Ubuntu/Debian
if command -v apt-get &> /dev/null; then
    apt-get update -qq
    UPDATES=$(apt list --upgradable 2>/dev/null | grep -i security | wc -l)
    if [ "${UPDATES}" -gt 0 ]; then
        echo "WARNING: ${UPDATES} security updates available"
        apt list --upgradable 2>/dev/null | grep -i security
    else
        echo "OK: No security updates pending"
    fi
fi

# RHEL/CentOS
if command -v yum &> /dev/null; then
    UPDATES=$(yum check-update --security --quiet | wc -l)
    if [ "${UPDATES}" -gt 0 ]; then
        echo "WARNING: ${UPDATES} security updates available"
        yum check-update --security
    else
        echo "OK: No security updates pending"
    fi
fi

# 检查是否需要重启
if [ -f /var/run/reboot-required ]; then
    echo "WARNING: System reboot required"
fi
```

### 2.2 内核参数加固

#### 2.2.1 sysctl 加固

```bash
# /etc/sysctl.d/99-thesisminer-security.conf

# 网络加固
# 禁用 IP 转发（非路由器）
net.ipv4.ip_forward = 0

# 禁用源路由
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0

# 禁用重定向
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0

# 启用反向路径过滤
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1

# 禁用 ICMP 广播
net.ipv4.icmp_echo_ignore_broadcasts = 1

# 启用 SYN Cookies（防 SYN Flood）
net.ipv4.tcp_syncookies = 1

# 增加 SYN 队列
net.ipv4.tcp_max_syn_backlog = 4096

# 减少 SYN-ACK 重试
net.ipv4.tcp_synack_retries = 2

# 禁用 IPv6（如不使用）
net.ipv6.conf.all.disable_ipv6 = 1
net.ipv6.conf.default.disable_ipv6 = 1

# 内存保护
# 启用 ASLR
kernel.randomize_va_space = 2

# 禁用核心转储（生产环境）
fs.suid_dumpable = 0

# 进程加固
# 限制 dmesg 访问
kernel.dmesg_restrict = 1

# 限制内核指针
kernel.kptr_restrict = 2

# 限制 perf 事件
kernel.perf_event_paranoid = 3

# 文件系统加固
# 启用硬链接保护
fs.protected_hardlinks = 1

# 启用符号链接保护
fs.protected_symlinks = 1

# 限制 FIFO
fs.protected_fifos = 2

# 限制普通文件
fs.protected_regular = 2
```

应用配置：

```bash
sysctl --system
```

#### 2.2.2 验证

```bash
#!/bin/bash
# scripts/security/verify_sysctl.sh

check_param() {
    local param=$1
    local expected=$2
    local actual=$(sysctl -n ${param} 2>/dev/null)

    if [ "${actual}" = "${expected}" ]; then
        echo "✓ ${param} = ${actual}"
    else
        echo "✗ ${param} = ${actual} (expected: ${expected})"
    fi
}

check_param "net.ipv4.ip_forward" "0"
check_param "net.ipv4.conf.all.accept_source_route" "0"
check_param "net.ipv4.conf.all.accept_redirects" "0"
check_param "net.ipv4.conf.all.rp_filter" "1"
check_param "net.ipv4.tcp_syncookies" "1"
check_param "kernel.randomize_va_space" "2"
check_param "fs.suid_dumpable" "0"
check_param "kernel.dmesg_restrict" "1"
check_param "kernel.kptr_restrict" "2"
check_param "fs.protected_hardlinks" "1"
check_param "fs.protected_symlinks" "1"
```

### 2.3 服务最小化

#### 2.3.1 禁用不必要服务

```bash
#!/bin/bash
# scripts/security/disable_services.sh

# 禁用不必要的服务
SERVICES_TO_DISABLE=(
    "avahi-daemon"      # mDNS 服务
    "cups"              # 打印服务
    "dhcpd"             # DHCP 服务
    "nfs-server"        # NFS 服务
    "rpcbind"           # RPC 服务
    "smb"               # Samba 服务
    "vsftpd"            # FTP 服务
    "telnetd"           # Telnet 服务
    "rsh-server"        # RSH 服务
    "ypbind"            # NIS 服务
)

for service in "${SERVICES_TO_DISABLE[@]}"; do
    if systemctl is-active --quiet ${service} 2>/dev/null; then
        systemctl stop ${service}
        systemctl disable ${service}
        echo "Disabled: ${service}"
    fi
done

# 删除不必要的软件包
PACKAGES_TO_REMOVE=(
    "telnet"
    "rsh-client"
    "rsh-server"
    "nis"
    "nfs-kernel-server"
    "samba"
    "vsftpd"
)

for pkg in "${PACKAGES_TO_REMOVE[@]}"; do
    if dpkg -l ${pkg} &> /dev/null; then
        apt-get purge -y ${pkg}
        echo "Removed: ${pkg}"
    fi
done
```

#### 2.3.2 检查运行服务

```bash
#!/bin/bash
# scripts/security/check_services.sh

echo "Listening services:"
ss -tulpn | grep LISTEN

echo ""
echo "Enabled services:"
systemctl list-unit-files --type=service --state=enabled

echo ""
echo "Running services:"
systemctl list-units --type=service --state=running
```

### 2.4 用户与组管理

#### 2.4.1 用户管理原则

- **最小用户数**：只保留必要用户
- **唯一用户**：每个用户有唯一账号
- **无共享账号**：禁止共享账号
- **禁用默认账号**：禁用 root、guest 等默认账号
- **定期审查**：每季度审查用户列表

#### 2.4.2 密码策略

```bash
# /etc/pam.d/common-password (Debian/Ubuntu)
password requisite pam_pwquality.so \
    try_first_pass \
    retry=3 \
    minlen=12 \
    dcredit=-1 \
    ucredit=-1 \
    ocredit=-1 \
    lcredit=-1 \
    difok=3 \
    enforce_for_root

password [success=1 default=ignore] pam_unix.so \
    obscure \
    sha512 \
    remember=12

# /etc/login.defs
PASS_MAX_DAYS 90
PASS_MIN_DAYS 1
PASS_WARN_AGE 7
PASS_MIN_LEN 12
ENCRYPT_METHOD SHA512
```

#### 2.4.3 账户锁定策略

```bash
# /etc/pam.d/common-auth (Debian/Ubuntu)
auth required pam_tally2.so \
    file=/var/log/tallylog \
    onerr=fail \
    deny=5 \
    unlock_time=900 \
    even_deny_root \
    root_unlock_time=900

auth [success=1 default=ignore] pam_unix.so nullok_secure
auth requisite pam_deny.so
auth required pam_permit.so
```

#### 2.4.4 用户审查脚本

```bash
#!/bin/bash
# scripts/security/audit_users.sh

echo "=== User Audit Report ==="
echo "Date: $(date)"
echo ""

echo "Users with UID 0 (root privileges):"
awk -F: '($3 == 0) { print $1 }' /etc/passwd

echo ""
echo "Users with empty passwords:"
awk -F: '($2 == "") { print $1 }' /etc/shadow

echo ""
echo "Users with login shell:"
grep -v "/nologin\|/false" /etc/passwd | awk -F: '{ print $1, $7 }'

echo ""
echo "Users with sudo access:"
getent group sudo wheel

echo ""
echo "Users not logged in for 90 days:"
lastlog -b 90 | grep -v "Never logged in"
```

### 2.5 sudo 配置

#### 2.5.1 sudo 加固

```bash
# /etc/sudoers.d/thesisminer

# 默认设置
Defaults    requiretty
Defaults    !visiblepw
Defaults    always_set_home
Defaults    env_reset
Defaults    mail_badpass
Defaults    secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Defaults    use_pty
Defaults    logfile="/var/log/sudo.log"
Defaults    log_input, log_output
Defaults    iolog_dir="/var/log/sudo-io/%{user}"
Defaults    passwd_timeout=2
Defaults    timestamp_timeout=5
Defaults    badpass_message="Incorrect password. Access denied."
Defaults    insults=off

# 用户权限
# thesisminer 用户只能重启服务
thesisminer ALL=(root) NOPASSWD: /bin/systemctl restart thesisminer
thesisminer ALL=(root) NOPASSWD: /bin/systemctl status thesisminer
thesisminer ALL=(root) NOPASSWD: /bin/journalctl -u thesisminer

# SRE 组权限
%sre ALL=(ALL) ALL
%sre ALL=(root) NOPASSWD: /bin/systemctl restart *
%sre ALL=(root) NOPASSWD: /bin/systemctl status *

# 禁止的命令
Cmnd_Alias DANGER = /bin/su, /bin/bash, /bin/sh, /usr/bin/passwd, /usr/sbin/visudo
%sre ALL=(ALL) ALL, !DANGER
```

#### 2.5.2 sudo 审计

```bash
# 所有 sudo 操作记录到日志
# /var/log/sudo.log
# /var/log/sudo-io/ (输入输出记录)

# 定期审查
grep -i "incorrect" /var/log/sudo.log
grep -i "command not allowed" /var/log/sudo.log
```

### 2.6 SSH 加固

#### 2.6.1 SSH 服务端配置

```bash
# /etc/ssh/sshd_config

# 基础设置
Port 2222                          # 修改默认端口
Protocol 2                         # 仅使用 SSH 2
AddressFamily inet                 # 仅 IPv4
ListenAddress 0.0.0.0              # 监听地址

# 认证设置
PermitRootLogin no                 # 禁止 root 登录
PermitEmptyPasswords no            # 禁止空密码
PasswordAuthentication no          # 禁止密码登录（仅密钥）
ChallengeResponseAuthentication no # 禁用挑战响应
KbdInteractiveAuthentication no    # 禁用键盘交互
UsePAM yes                         # 启用 PAM

# 密钥设置
PubkeyAuthentication yes           # 启用密钥认证
AuthorizedKeysFile .ssh/authorized_keys
HostKey /etc/ssh/ssh_host_ed25519_key
HostKey /etc/ssh/ssh_host_rsa_key

# 加密算法（仅使用强算法）
KexAlgorithms curve25519-sha256@libssh.org,diffie-hellman-group16-sha512,diffie-hellman-group18-sha512
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com,aes128-gcm@openssh.com,aes256-ctr,aes192-ctr,aes128-ctr
MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com,umac-128-etm@openssh.com

# 限制设置
MaxAuthTries 3                     # 最大认证尝试
MaxSessions 10                     # 最大会话数
MaxStartups 10:30:100              # 最大并发未认证连接
LoginGraceTime 30                  # 登录宽限时间

# 超时设置
ClientAliveInterval 300            # 客户端存活检查间隔
ClientAliveCountMax 2              # 客户端存活检查次数

# 用户限制
AllowUsers thesisminer @sre        # 允许的用户
AllowGroups sre thesisminer        # 允许的组
DenyUsers root guest               # 禁止的用户

# 日志设置
SyslogFacility AUTH
LogLevel VERBOSE                   # 详细日志

# 转发设置
AllowTcpForwarding no              # 禁止 TCP 转发
X11Forwarding no                   # 禁止 X11 转发
AllowAgentForwarding no            # 禁止 Agent 转发
PermitTunnel no                    # 禁止隧道

# 其他
Banner /etc/ssh/banner             # 登录 banner
PrintMotd no                       # 不打印 MOTD
PrintLastLog yes                   # 打印最后登录
Compression yes                    # 启用压缩
```

#### 2.6.2 SSH Banner

```bash
# /etc/ssh/banner
**********************************************************************
*                                                                    *
*  WARNING: Authorized access only                                  *
*                                                                    *
*  This system is the property of ThesisMiner.                      *
*  Unauthorized access is strictly prohibited.                      *
*  All activities are monitored and logged.                         *
*                                                                    *
**********************************************************************
```

#### 2.6.3 fail2ban 配置

```ini
# /etc/fail2ban/jail.local

[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3
banaction = iptables-multiport
backend = systemd

[sshd]
enabled = true
port = 2222
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
findtime = 600

[sshd-ddos]
enabled = true
port = 2222
filter = sshd-ddos
logpath = /var/log/auth.log
maxretry = 2
bantime = 7200
```

#### 2.6.4 SSH 密钥管理

```bash
# 生成强密钥
ssh-keygen -t ed25519 -a 100 -f ~/.ssh/id_ed25519 -C "user@thesisminer.io"

# 或 RSA 4096
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -C "user@thesisminer.io"

# 密钥权限
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
chmod 600 ~/.ssh/id_ed25519
chmod 644 ~/.ssh/id_ed25519.pub
```

---

## 3. 网络加固

### 3.1 防火墙配置

#### 3.1.1 iptables 配置

```bash
#!/bin/bash
# scripts/security/setup_firewall.sh

set -euo pipefail

# 清除现有规则
iptables -F
iptables -X
iptables -Z

# 默认策略
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# 回环接口
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# 已建立连接
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# 防 SYN Flood
iptables -A INPUT -p tcp --syn -m limit --limit 20/s --limit-burst 40 -j ACCEPT
iptables -A INPUT -p tcp --syn -j DROP

# 防端口扫描
iptables -A INPUT -p tcp --tcp-flags ALL NONE -j DROP
iptables -A INPUT -p tcp --tcp-flags SYN,FIN SYN,FIN -j DROP
iptables -A INPUT -p tcp --tcp-flags SYN,RST SYN,RST -j DROP
iptables -A INPUT -p tcp --tcp-flags FIN,RST FIN,RST -j DROP
iptables -A INPUT -p tcp --tcp-flags ALL ALL -j DROP

# 防 Ping of Death
iptables -A INPUT -p icmp --icmp-type echo-request -m limit --limit 1/s -j ACCEPT

# 允许 SSH（限制源 IP）
iptables -A INPUT -p tcp --dport 2222 -s 10.0.0.0/8 -j ACCEPT
iptables -A INPUT -p tcp --dport 2222 -j DROP

# 允许 HTTP/HTTPS
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# 允许监控（限制源 IP）
iptables -A INPUT -p tcp --dport 9090 -s 10.0.1.100/32 -j ACCEPT  # Prometheus
iptables -A INPUT -p tcp --dport 9100 -s 10.0.1.100/32 -j ACCEPT  # Node Exporter

# 允许内部通信
iptables -A INPUT -s 10.0.0.0/8 -j ACCEPT

# 记录被拒绝的连接
iptables -A INPUT -m limit --limit 5/min -j LOG --log-prefix "iptables-dropped: " --log-level 4

# 保存规则
iptables-save > /etc/iptables/rules.v4
```

#### 3.1.2 ip6tables 配置

```bash
#!/bin/bash
# scripts/security/setup_ip6tables.sh

ip6tables -F
ip6tables -X
ip6tables -Z

ip6tables -P INPUT DROP
ip6tables -P FORWARD DROP
ip6tables -P OUTPUT ACCEPT

ip6tables -A INPUT -i lo -j ACCEPT
ip6tables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# ICMPv6 必要类型
ip6tables -A INPUT -p ipv6-icmp -m icmp6 --icmpv6-type 1 -j ACCEPT   # Destination Unreachable
ip6tables -A INPUT -p ipv6-icmp -m icmp6 --icmpv6-type 2 -j ACCEPT   # Packet Too Big
ip6tables -A INPUT -p ipv6-icmp -m icmp6 --icmpv6-type 3 -j ACCEPT   # Time Exceeded
ip6tables -A INPUT -p ipv6-icmp -m icmp6 --icmpv6-type 128 -j ACCEPT # Echo Request
ip6tables -A INPUT -p ipv6-icmp -m icmp6 --icmpv6-type 129 -j ACCEPT # Echo Reply

ip6tables-save > /etc/iptables/rules.v6
```

### 3.2 端口管理

#### 3.2.1 端口扫描检测

```bash
#!/bin/bash
# scripts/security/scan_ports.sh

echo "=== Port Scan Report ==="
echo "Date: $(date)"
echo ""

echo "Listening TCP ports:"
ss -tlnp | grep LISTEN

echo ""
echo "Listening UDP ports:"
ss -ulnp

echo ""
echo "External accessible ports:"
ss -tlnp | grep -v "127.0.0.1\|::1"

echo ""
echo "Suspicious ports (non-standard):"
ss -tlnp | grep -vE ":(80|443|2222|9090|9100|8000) " | grep LISTEN
```

#### 3.2.2 端口规范

| 端口 | 服务 | 访问范围 | 说明 |
|------|------|----------|------|
| 80 | HTTP | 公网 | 重定向到 443 |
| 443 | HTTPS | 公网 | 主入口 |
| 2222 | SSH | 内网 | 管理 |
| 8000 | FastAPI | 内网 | 应用 |
| 9090 | Prometheus | 内网 | 监控 |
| 9100 | Node Exporter | 内网 | 监控 |
| 6379 | Redis | 内网 | 缓存 |
| 5432 | PostgreSQL | 内网 | 数据库（如使用） |

### 3.3 网络分段

#### 3.3.1 VLAN 划分

```
+------------------------------------------------------------------+
|                        网络拓扑                                   |
+------------------------------------------------------------------+
|                                                                  |
|  +-------------------+        +-------------------+              |
|  | VLAN 10 (DMZ)     |        | VLAN 20 (App)     |              |
|  | - 负载均衡        | -----> | - ThesisMiner App |              |
|  | - WAF             |        | - FastAPI         |              |
|  | - 反向代理        |        | - Agent 服务      |              |
|  +-------------------+        +-------------------+              |
|         |                              |                         |
|         |         +-------------------+|                         |
|         |         | VLAN 30 (Data)    ||                         |
|         +-------> | - SQLite          |<                         |
|                   | - Redis           |                          |
|                   | - 对象存储        |                          |
|                   +-------------------+                          |
|         |                              |                         |
|         |         +-------------------+|                         |
|         |         | VLAN 40 (Mgmt)    ||                         |
|         +-------> | - 监控            |<                         |
|                   | - 日志            |                          |
|                   | - 跳板机          |                          |
|                   +-------------------+                          |
+------------------------------------------------------------------+
```

#### 3.3.2 网络策略（Kubernetes）

```yaml
# deploy/k8s/networkpolicy-default-deny.yml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: thesisminer
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

```yaml
# deploy/k8s/networkpolicy-thesisminer.yml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: thesisminer-allow
  namespace: thesisminer
spec:
  podSelector:
    matchLabels:
      app: thesisminer
  policyTypes:
  - Ingress
  - Egress
  ingress:
  # 允许来自 Ingress 的流量
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
  # 允许来自监控的流量
  - from:
    - namespaceSelector:
        matchLabels:
          name: monitoring
    ports:
    - protocol: TCP
      port: 9090
  egress:
  # 允许访问 DNS
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system
    ports:
    - protocol: UDP
      port: 53
  # 允许访问 DeepSeek API
  - to:
    - ipBlock:
        cidr: 0.0.0.0/0
    ports:
    - protocol: TCP
      port: 443
  # 允许访问数据库
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    ports:
    - protocol: TCP
      port: 5432
```

### 3.4 DDoS 防护

#### 3.4.1 流量清洗

```
用户请求 --> CDN/CDN --> 流量清洗 --> WAF --> 负载均衡 --> 应用
                |            |          |          |
                v            v          v          v
            缓存静态     识别攻击    应用层防护   分发流量
            抗 L3/L4    SYN Flood   SQLi/XSS    健康检查
```

#### 3.4.2 限流配置

```python
# backend/monitoring/rate_limiter.py
from fastapi import Request, Response
from fastapi.middleware import Middleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware


limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


@limiter.limit("10/minute")
async def generate_thesis(request: Request):
    """论文生成 API，严格限流。"""
    pass


@limiter.limit("100/minute")
async def get_thesis(request: Request, thesis_id: str):
    """获取论文 API，宽松限流。"""
    pass


# 异常处理
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return Response(
        content='{"error": "Rate limit exceeded"}',
        status_code=429,
        media_type="application/json",
        headers={
            "Retry-After": str(exc.retry_after),
            "X-RateLimit-Limit": str(exc.limit),
            "X-RateLimit-Remaining": "0",
        }
    )
```

### 3.5 WAF 配置

#### 3.5.1 ModSecurity 规则

```apache
# /etc/modsecurity/modsecurity.conf

SecRuleEngine On
SecRequestBodyAccess On
SecResponseBodyAccess On
SecResponseBodyLimit 1048576
SecTmpDir /tmp/
SecDataDir /var/cache/modsecurity/

# 日志
SecAuditEngine RelevantOnly
SecAuditLog /var/log/modsecurity/audit.log
SecAuditLogParts ABIJDEFHZ
SecAuditLogType Serial

# 默认动作
SecDefaultAction "phase:1,pass,log,auditlog"

# 包含 OWASP CRS
Include /usr/share/modsecurity-crs/*.load
```

#### 3.5.2 OWASP CRS 规则

```apache
# /usr/share/modsecurity-crs/rules/REQUEST-942-APPLICATION-ATTACK-SQLI.conf

# SQL 注入检测
SecRule REQUEST_COOKIES|REQUEST_COOKIES_NAMES|REQUEST_FILENAME|REQUEST_HEADERS|REQUEST_HEADERS_NAMES|REQUEST_METHOD|REQUEST_URI|REQUEST_URI|ARGS|ARGS_NAMES|XML:/* "@rx (?i)(?:union\s+select|select\s+.*\s+from|insert\s+into|delete\s+from|update\s+.*\s+set)" \
    "id:942100,\
    phase:2,\
    block,\
    capture,\
    t:none,t:urlDecodeUni,t:removeComments,t:replaceComments,t:compressWhitespace,t:lowercase,\
    msg:'SQL Injection Attack Detected',\
    logdata:'Matched Data: %{TX.0} found within %{MATCHED_VAR_NAME}: %{MATCHED_VAR}',\
    tag:'application-multi',\
    tag:'language-multi',\
    tag:'platform-multi',\
    tag:'attack-sqli',\
    tag:'OWASP_CRS',\
    tag:'capec/1000/152/248/66',\
    tag:'PCI/6.5.2',\
    ver:'OWASP_CRS/3.3.0',\
    severity:'CRITICAL',\
    setvar:'tx.sql_injection_score=+%{tx.critical_anomaly_score}',\
    setvar:'tx.anomaly_score_pl1=+%{tx.critical_anomaly_score}'"
```

---

## 4. 应用加固

### 4.1 FastAPI 加固

#### 4.1.1 安全头

```python
# backend/monitoring/security_headers.py
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """安全响应头中间件。"""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # 防止 MIME 类型嗅探
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 防 XSS（现代浏览器用 CSP，此头为兼容）
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # 防点击劫持
        response.headers["X-Frame-Options"] = "DENY"

        # HSTS（仅 HTTPS）
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # 内容安全策略
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "connect-src 'self' https://api.deepseek.com; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        # Referrer 策略
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 权限策略
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=()"
        )

        # 缓存控制（敏感接口）
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response


# 使用
app.add_middleware(SecurityHeadersMiddleware)
```

#### 4.1.2 CORS 配置

```python
# backend/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://thesisminer.example.com",
        "https://app.thesisminer.io",
    ],  # 严格白名单，禁止 "*"
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Trace-Id",
        "X-Request-Id",
    ],
    max_age=3600,
)
```

### 4.2 输入验证

#### 4.2.1 Pydantic 模型验证

```python
# backend/api/models.py
from pydantic import BaseModel, Field, validator, constr
from typing import Optional, List
from datetime import datetime
import re


class ThesisGenerateRequest(BaseModel):
    """论文生成请求模型。"""

    topic: constr(min_length=1, max_length=500) = Field(
        ..., description="论文主题"
    )
    session_id: constr(pattern=r"^sess-[a-zA-Z0-9-]+$") = Field(
        ..., description="会话 ID"
    )
    stage: constr(pattern=r"^(topic_clarification|literature_mapping|method_design|writing|refinement)$") = Field(
        default="topic_clarification", description="阶段"
    )
    max_iterations: int = Field(default=3, ge=1, le=10)
    user_id: Optional[constr(pattern=r"^user-[a-zA-Z0-9-]+$")] = None

    @validator("topic")
    def validate_topic(cls, v):
        """验证主题不含恶意内容。"""
        # 检测 SQL 注入特征
        sql_patterns = [
            r"(?i)union\s+select",
            r"(?i)drop\s+table",
            r"(?i)insert\s+into",
            r"(?i)delete\s+from",
        ]
        for pattern in sql_patterns:
            if re.search(pattern, v):
                raise ValueError("Invalid topic content")

        # 检测 XSS 特征
        xss_patterns = [
            r"<script[^>]*>",
            r"javascript:",
            r"on\w+\s*=",
        ]
        for pattern in xss_patterns:
            if re.search(pattern, v):
                raise ValueError("Invalid topic content")

        return v.strip()


class UserCreateRequest(BaseModel):
    """用户创建请求模型。"""

    username: constr(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$")
    email: constr(pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    password: constr(min_length=12, max_length=128)

    @validator("password")
    def validate_password(cls, v):
        """密码强度验证。"""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain uppercase")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain lowercase")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain special character")
        return v
```

#### 4.2.2 文件上传验证

```python
# backend/api/uploads.py
import os
import magic
from fastapi import UploadFile, HTTPException
from typing import Set

ALLOWED_MIME_TYPES: Set[str] = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/markdown",
    "text/plain",
}

ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".docx", ".md", ".txt"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


async def validate_upload(file: UploadFile) -> bytes:
    """验证上传文件。"""
    # 1. 检查文件名
    filename = file.filename or ""
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")

    # 2. 检查扩展名
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type {ext} not allowed")

    # 3. 读取文件内容
    content = await file.read()

    # 4. 检查文件大小
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large")

    # 5. 检查真实 MIME 类型（基于内容，非扩展名）
    mime = magic.from_buffer(content, mime=True)
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, f"File type {mime} not allowed")

    # 6. 检查文件头魔数
    if not _validate_magic_bytes(content, ext):
        raise HTTPException(400, "File content does not match extension")

    return content


def _validate_magic_bytes(content: bytes, ext: str) -> bool:
    """验证文件头魔数。"""
    magic_numbers = {
        ".pdf": b"%PDF",
        ".docx": b"PK\x03\x04",  # ZIP
        ".md": None,  # 文本，无固定头
        ".txt": None,
    }
    expected = magic_numbers.get(ext)
    if expected is None:
        return True
    return content.startswith(expected)
```

### 4.3 输出编码

```python
# backend/monitoring/output_encoding.py
import html
import json
import re
from typing import Any


def encode_html(value: str) -> str:
    """HTML 编码。"""
    return html.escape(value, quote=True)


def encode_js(value: str) -> str:
    """JavaScript 编码。"""
    return json.dumps(value)[1:-1]  # 去掉引号


def encode_url(value: str) -> str:
    """URL 编码。"""
    from urllib.parse import quote
    return quote(value, safe="")


def encode_attr(value: str) -> str:
    """HTML 属性编码。"""
    value = html.escape(value, quote=True)
    # 额外处理
    value = value.replace("'", "&#x27;")
    return value


def sanitize_html(value: str) -> str:
    """HTML 清理（使用白名单）。"""
    import bleach
    allowed_tags = ["p", "br", "strong", "em", "ul", "ol", "li", "h1", "h2", "h3"]
    allowed_attrs = {}
    return bleach.clean(value, tags=allowed_tags, attributes=allowed_attrs, strip=True)
```

### 4.4 会话安全

```python
# backend/sessions/security.py
import secrets
import hashlib
import time
from typing import Optional
from dataclasses import dataclass


@dataclass
class SessionConfig:
    """会话安全配置。"""
    session_cookie_name: str = "thesisminer_session"
    session_timeout: int = 1800  # 30 分钟
    session_max_age: int = 86400  # 24 小时
    cookie_secure: bool = True
    cookie_httponly: bool = True
    cookie_samesite: str = "strict"
    session_id_length: int = 32


class SessionManager:
    """安全的会话管理器。"""

    def __init__(self, config: SessionConfig):
        self.config = config

    def create_session(self, user_id: str) -> str:
        """创建会话。"""
        # 生成安全的会话 ID
        session_id = secrets.token_urlsafe(self.config.session_id_length)

        # 存储会话（含创建时间、最后访问时间、用户 ID）
        session_data = {
            "session_id": self._hash_session_id(session_id),
            "user_id": user_id,
            "created_at": time.time(),
            "last_accessed": time.time(),
            "ip_address": None,  # 由中间件填充
            "user_agent": None,
        }

        # 存储到 Redis（带过期）
        # redis.setex(f"session:{session_data['session_id']}",
        #             self.config.session_timeout, json.dumps(session_data))

        return session_id

    def validate_session(self, session_id: str, ip_address: str,
                         user_agent: str) -> bool:
        """验证会话。"""
        hashed_id = self._hash_session_id(session_id)

        # 从 Redis 获取
        # session_data = redis.get(f"session:{hashed_id}")
        session_data = {}  # 模拟

        if not session_data:
            return False

        # 检查超时
        if time.time() - session_data["last_accessed"] > self.config.session_timeout:
            return False

        # 检查 IP 绑定（可选）
        if session_data.get("ip_address") and \
           session_data["ip_address"] != ip_address:
            return False

        # 检查 User-Agent 绑定（可选）
        if session_data.get("user_agent") and \
           session_data["user_agent"] != user_agent:
            return False

        # 更新最后访问时间
        session_data["last_accessed"] = time.time()
        # redis.setex(...)

        return True

    def destroy_session(self, session_id: str):
        """销毁会话。"""
        hashed_id = self._hash_session_id(session_id)
        # redis.delete(f"session:{hashed_id}")

    def _hash_session_id(self, session_id: str) -> str:
        """哈希会话 ID（存储哈希值，防止 Redis 泄露后可重放）。"""
        return hashlib.sha256(session_id.encode()).hexdigest()

    def regenerate_session(self, old_session_id: str, user_id: str) -> str:
        """重新生成会话 ID（防会话固定攻击）。"""
        self.destroy_session(old_session_id)
        return self.create_session(user_id)
```

### 4.5 CSRF 防护

```python
# backend/monitoring/csrf.py
import secrets
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF 防护中间件。"""

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
    TOKEN_HEADER = "X-CSRF-Token"
    TOKEN_COOKIE = "csrf_token"

    async def dispatch(self, request: Request, call_next):
        # 安全方法跳过
        if request.method in self.SAFE_METHODS:
            response = await call_next(request)
            # 为 GET 请求设置 CSRF cookie
            if request.method == "GET":
                csrf_token = secrets.token_urlsafe(32)
                response.set_cookie(
                    self.TOKEN_COOKIE,
                    csrf_token,
                    httponly=False,  # 前端需读取
                    secure=True,
                    samesite="strict"
                )
            return response

        # 非 GET 请求验证 CSRF token
        cookie_token = request.cookies.get(self.TOKEN_COOKIE)
        header_token = request.headers.get(self.TOKEN_HEADER)

        if not cookie_token or not header_token:
            raise HTTPException(403, "CSRF token missing")

        if not secrets.compare_digest(cookie_token, header_token):
            raise HTTPException(403, "CSRF token invalid")

        return await call_next(request)
```

### 4.6 XSS 防护

```python
# backend/monitoring/xss_protection.py
import re
from typing import List

XSS_PATTERNS: List[str] = [
    r"<script[^>]*>.*?</script>",
    r"javascript:",
    r"on\w+\s*=",
    r"<iframe[^>]*>",
    r"<object[^>]*>",
    r"<embed[^>]*>",
    r"expression\s*\(",
    r"<meta[^>]*>",
    r"<link[^>]*>",
    r"data:text/html",
    r"vbscript:",
]


def detect_xss(input_string: str) -> bool:
    """检测 XSS 攻击。"""
    for pattern in XSS_PATTERNS:
        if re.search(pattern, input_string, re.IGNORECASE):
            return True
    return False


def sanitize_xss(input_string: str) -> str:
    """清理 XSS 攻击。"""
    import html
    return html.escape(input_string, quote=True)
```

### 4.7 SQL 注入防护

```python
# backend/sessions/database.py
import sqlite3
from typing import Any, List, Optional, Tuple


class SecureDatabase:
    """安全的数据库访问层。"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def execute(self, sql: str, params: Tuple = ()) -> Any:
        """执行参数化查询。"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor
        finally:
            conn.close()

    def query_one(self, sql: str, params: Tuple = ()) -> Optional[Tuple]:
        """查询单条记录。"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(sql, params)
            return cursor.fetchone()
        finally:
            conn.close()

    def query_all(self, sql: str, params: Tuple = ()) -> List[Tuple]:
        """查询多条记录。"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(sql, params)
            return cursor.fetchall()
        finally:
            conn.close()


# 正确用法（参数化查询）
db = SecureDatabase("/data/thesisminer.db")

# ✓ 正确：使用参数化查询
user = db.query_one(
    "SELECT * FROM users WHERE id = ? AND status = ?",
    (user_id, "active")
)

# ✗ 错误：字符串拼接（SQL 注入风险）
# user = db.query_one(f"SELECT * FROM users WHERE id = '{user_id}'")


# 表名/列名白名单验证
ALLOWED_TABLES = {"users", "theses", "sessions", "conversations"}
ALLOWED_COLUMNS = {"id", "name", "email", "created_at", "status"}


def validate_identifier(identifier: str, allowed: set) -> str:
    """验证 SQL 标识符（表名、列名）。"""
    if identifier not in allowed:
        raise ValueError(f"Invalid identifier: {identifier}")
    return identifier


def safe_order_by(column: str, allowed: set) -> str:
    """安全的 ORDER BY。"""
    column = validate_identifier(column, allowed)
    return f"ORDER BY {column}"
```

### 4.8 文件上传安全

```python
# backend/api/uploads.py
import os
import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile, HTTPException

UPLOAD_DIR = Path("/data/uploads")
QUARANTINE_DIR = Path("/data/quarantine")
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


async def safe_upload(file: UploadFile, user_id: str) -> Path:
    """安全的文件上传。"""
    # 1. 验证文件名
    original_name = file.filename or ""
    if not original_name or ".." in original_name or "/" in original_name:
        raise HTTPException(400, "Invalid filename")

    # 2. 验证扩展名
    ext = Path(original_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Extension {ext} not allowed")

    # 3. 生成安全文件名（不使用原始文件名）
    safe_name = f"{user_id}_{uuid.uuid4().hex}{ext}"
    upload_path = UPLOAD_DIR / safe_name

    # 4. 限制上传目录（防路径穿越）
    upload_path = upload_path.resolve()
    if not str(upload_path).startswith(str(UPLOAD_DIR.resolve())):
        raise HTTPException(400, "Path traversal detected")

    # 5. 写入文件（限制大小）
    total_size = 0
    with open(upload_path, "wb") as f:
        while chunk := await file.read(65536):
            total_size += len(chunk)
            if total_size > MAX_FILE_SIZE:
                f.close()
                upload_path.unlink()
                raise HTTPException(400, "File too large")
            f.write(chunk)

    # 6. 病毒扫描（如有）
    if not await virus_scan(upload_path):
        shutil.move(str(upload_path), str(QUARANTINE_DIR / safe_name))
        raise HTTPException(400, "File infected")

    return upload_path


async def virus_scan(file_path: Path) -> bool:
    """病毒扫描。"""
    # 集成 ClamAV
    import subprocess
    result = subprocess.run(
        ["clamscan", "--no-summary", str(file_path)],
        capture_output=True
    )
    return result.returncode == 0
```

---

## 5. 文件与目录权限

### 5.1 权限模型

ThesisMiner v8.0 采用最小权限原则：

| 权限 | 说明 | 示例 |
|------|------|------|
| 读 (4) | 可读 | 配置文件 |
| 写 (2) | 可写 | 日志文件 |
| 执行 (1) | 可执行 | 脚本、二进制 |

权限表示：`owner|group|other`，如 `750` = `rwxr-x---`。

### 5.2 关键文件权限

```bash
#!/bin/bash
# scripts/security/set_permissions.sh

set -euo pipefail

# 应用目录
APP_DIR="/opt/thesisminer"
chown -R thesisminer:thesisminer ${APP_DIR}
chmod 750 ${APP_DIR}
find ${APP_DIR} -type d -exec chmod 750 {} \;
find ${APP_DIR} -type f -exec chmod 640 {} \;
find ${APP_DIR} -name "*.sh" -exec chmod 750 {} \;
find ${APP_DIR} -name "*.py" -exec chmod 640 {} \;

# 配置文件（含敏感信息）
CONFIG_DIR="/etc/thesisminer"
chown -R root:thesisminer ${CONFIG_DIR}
chmod 750 ${CONFIG_DIR}
find ${CONFIG_DIR} -type f -exec chmod 640 {} \;

# 密钥文件
chmod 600 ${CONFIG_DIR}/*.key
chmod 600 ${CONFIG_DIR}/*.pem
chmod 600 ${CONFIG_DIR}/.env

# 数据目录
DATA_DIR="/data/thesisminer"
chown -R thesisminer:thesisminer ${DATA_DIR}
chmod 700 ${DATA_DIR}
find ${DATA_DIR} -type d -exec chmod 700 {} \;
find ${DATA_DIR} -type f -exec chmod 600 {} \;

# 日志目录
LOG_DIR="/var/log/thesisminer"
chown -R thesisminer:adm ${LOG_DIR}
chmod 750 ${LOG_DIR}
find ${LOG_DIR} -type f -exec chmod 640 {} \;

# 数据库文件
DB_FILE="${DATA_DIR}/thesisminer.db"
chmod 600 ${DB_FILE}

# 备份目录
BACKUP_DIR="/data/backups"
chown -R root:backup ${BACKUP_DIR}
chmod 700 ${BACKUP_DIR}

# 临时目录
TMP_DIR="/tmp/thesisminer"
mkdir -p ${TMP_DIR}
chown thesisminer:thesisminer ${TMP_DIR}
chmod 700 ${TMP_DIR}

# 二进制文件
chmod 755 ${APP_DIR}/bin/*
chmod 755 ${APP_DIR}/venv/bin/*

# 系统服务
chmod 644 /etc/systemd/system/thesisminer.service

echo "Permissions set successfully"
```

### 5.3 敏感文件保护

#### 5.3.1 敏感文件清单

| 文件 | 权限 | 所有者 | 说明 |
|------|------|--------|------|
| `/etc/thesisminer/.env` | 600 | root:thesisminer | 环境变量 |
| `/etc/thesisminer/api_key.pem` | 600 | root:thesisminer | API Key |
| `/etc/thesisminer/db_password` | 600 | root:thesisminer | 数据库密码 |
| `/etc/thesisminer/ssl/` | 700 | root:root | SSL 证书 |
| `/etc/thesisminer/ssl/private.key` | 600 | root:root | 私钥 |
| `/etc/thesisminer/ssl/cert.pem` | 644 | root:root | 证书 |
| `/data/thesisminer/thesisminer.db` | 600 | thesisminer:thesisminer | 数据库 |
| `/root/.ssh/` | 700 | root:root | SSH 密钥 |
| `/root/.ssh/authorized_keys` | 600 | root:root | 授权密钥 |

#### 5.3.2 文件完整性监控

```bash
#!/bin/bash
# scripts/security/fim_check.sh

# 关键文件清单
CRITICAL_FILES=(
    "/etc/passwd"
    "/etc/shadow"
    "/etc/group"
    "/etc/sudoers"
    "/etc/ssh/sshd_config"
    "/etc/thesisminer/.env"
    "/etc/thesisminer/api_key.pem"
    "/opt/thesisminer/bin/thesisminer"
)

BASELINE_FILE="/var/lib/thesisminer/fim_baseline"

if [ ! -f "${BASELINE_FILE}" ]; then
    echo "Creating baseline..."
    for file in "${CRITICAL_FILES[@]}"; do
        if [ -f "${file}" ]; then
            sha256sum "${file}" >> "${BASELINE_FILE}"
        fi
    done
    chmod 600 "${BASELINE_FILE}"
    exit 0
fi

echo "Checking file integrity..."
TEMP_FILE=$(mktemp)
for file in "${CRITICAL_FILES[@]}"; do
    if [ -f "${file}" ]; then
        sha256sum "${file}" >> "${TEMP_FILE}"
    fi
done

DIFF=$(diff "${BASELINE_FILE}" "${TEMP_FILE}")
if [ -n "${DIFF}" ]; then
    echo "WARNING: File integrity changed!"
    echo "${DIFF}"
    # 发送告警
    # ./scripts/notify/alert.sh "File integrity violation"
fi

rm "${TEMP_FILE}"
```

### 5.4 临时文件安全

```python
# backend/monitoring/tempfile_secure.py
import os
import tempfile
from pathlib import Path


def secure_temp_file(prefix: str = "thesisminer_",
                     suffix: str = ".tmp") -> Path:
    """创建安全的临时文件。"""
    # 使用 mkstemp 而非 mktemp（避免竞态条件）
    fd, path = tempfile.mkstemp(
        prefix=prefix,
        suffix=suffix,
        dir="/tmp/thesisminer"  # 限制目录
    )
    os.close(fd)

    # 设置权限（仅 owner 可读写）
    os.chmod(path, 0o600)

    return Path(path)


def secure_temp_dir(prefix: str = "thesisminer_") -> Path:
    """创建安全的临时目录。"""
    path = tempfile.mkdtemp(
        prefix=prefix,
        dir="/tmp/thesisminer"
    )
    os.chmod(path, 0o700)
    return Path(path)


class SecureTempFile:
    """安全临时文件上下文管理器。"""

    def __init__(self, prefix: str = "thesisminer_"):
        self.prefix = prefix
        self.path: Path = None

    def __enter__(self) -> Path:
        self.path = secure_temp_file(self.prefix)
        return self.path

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.path and self.path.exists():
            # 安全删除（覆盖后删除）
            self.path.write_bytes(b"\x00" * self.path.stat().st_size)
            self.path.unlink()
```

---

## 6. 日志审计

### 6.1 审计日志

#### 6.1.1 审计日志内容

| 事件类型 | 记录内容 |
|----------|----------|
| 用户登录 | 用户 ID、IP、时间、成功/失败、方式 |
| 用户登出 | 用户 ID、IP、时间 |
| 权限变更 | 操作者、目标用户、旧权限、新权限 |
| 配置变更 | 操作者、变更内容、时间 |
| 数据访问 | 用户 ID、数据 ID、操作、时间 |
| 数据导出 | 用户 ID、数据 ID、格式、时间 |
| 管理操作 | 操作者、操作内容、时间 |
| API Key 操作 | 操作者、操作、Key ID、时间 |

#### 6.1.2 审计日志格式

```json
{
  "timestamp": "2026-06-20T10:30:45.123Z",
  "event_type": "user_login",
  "actor": {
    "user_id": "user-001",
    "username": "zhangsan",
    "ip_address": "192.168.1.100",
    "user_agent": "Mozilla/5.0..."
  },
  "action": "login",
  "target": {
    "type": "user",
    "id": "user-001"
  },
  "result": "success",
  "details": {
    "auth_method": "password",
    "mfa_used": true
  },
  "trace_id": "abc123"
}
```

#### 6.1.3 auditd 配置

```bash
# /etc/audit/auditd.conf
log_file = /var/log/audit/audit.log
log_format = ENRICHED
log_group = root
priority_boost = 4
flush = INCREMENTAL_ASYNC
freq = 50
max_log_file = 100
num_logs = 10
max_log_file_action = ROTATE
space_left = 500
space_left_action = EMAIL
action_mail_acct = security@thesisminer.io
admin_space_left = 100
admin_space_left_action = HALT
disk_full_action = HALT
disk_error_action = HALT
```

```bash
# /etc/audit/rules.d/thesisminer.rules

# 监控关键文件
-w /etc/passwd -p wa -k identity
-w /etc/shadow -p wa -k identity
-w /etc/group -p wa -k identity
-w /etc/sudoers -p wa -k sudoers
-w /etc/ssh/sshd_config -p wa -k ssh_config

# 监控 ThesisMiner 配置
-w /etc/thesisminer/ -p wa -k thesisminer_config

# 监控二进制文件
-w /opt/thesisminer/bin/ -p wa -k thesisminer_binary

# 监控数据库文件
-w /data/thesisminer/thesisminer.db -p ra -k database_access

# 系统调用监控
-a always,exit -F arch=b64 -S unlink -S unlinkat -S rmdir -k delete
-a always,exit -F arch=b64 -S chmod -S fchmod -S fchmodat -k perm_mod
-a always,exit -F arch=b64 -S chown -S fchown -S fchownat -S lchown -k perm_mod

# 登录监控
-w /var/log/faillog -p wa -k logins
-w /var/log/lastlog -p wa -k logins

# 进程监控
-a always,exit -F arch=b64 -S execve -k exec
```

### 6.2 系统日志

#### 6.2.1 rsyslog 配置

```bash
# /etc/rsyslog.d/49-thesisminer.conf

# ThesisMiner 应用日志
:programname, isequal, "thesisminer" /var/log/thesisminer/app.log
& stop

# 认证日志
auth,authpriv.* /var/log/auth.log

# sudo 日志
local2.* /var/log/sudo.log

# 审计日志
local6.* /var/log/audit/thesisminer-audit.log

# 远程日志（发送到 SIEM）
*.* @@siem.thesisminer.io:6514;RSYSLOG_SyslogTLSProtocol
```

### 6.3 应用日志

```python
# backend/monitoring/audit_logger.py
import logging
import json
from datetime import datetime, timezone
from typing import Any, Optional


class AuditLogger:
    """审计日志记录器。"""

    def __init__(self):
        self.logger = logging.getLogger("thesisminer.audit")
        self.logger.setLevel(logging.INFO)
        # 不输出到控制台，仅文件
        handler = logging.FileHandler("/var/log/thesisminer/audit.log")
        handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(handler)
        self.logger.propagate = False

    def log(self, event_type: str, actor: dict, action: str,
            target: dict, result: str, details: Optional[dict] = None,
            trace_id: Optional[str] = None):
        """记录审计日志。"""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "actor": actor,
            "action": action,
            "target": target,
            "result": result,
            "details": details or {},
            "trace_id": trace_id
        }
        self.logger.info(json.dumps(entry, ensure_ascii=False, default=str))


# 全局实例
audit_logger = AuditLogger()


# 使用示例
audit_logger.log(
    event_type="user_login",
    actor={
        "user_id": "user-001",
        "username": "zhangsan",
        "ip_address": "192.168.1.100",
        "user_agent": "Mozilla/5.0..."
    },
    action="login",
    target={"type": "user", "id": "user-001"},
    result="success",
    details={"auth_method": "password", "mfa_used": True}
)
```

### 6.4 日志保护

#### 6.4.1 日志不可篡改

```bash
# 设置日志文件追加属性（仅追加，不可修改）
chattr +a /var/log/thesisminer/audit.log
chattr +a /var/log/auth.log

# 验证
lsattr /var/log/thesisminer/audit.log
# 输出：-----a------- /var/log/thesisminer/audit.log
```

#### 6.4.2 日志远程传输

```bash
# 实时传输到远程 SIEM
# /etc/rsyslog.d/50-remote-siem.conf
*.* action(type="omfwd"
    target="siem.thesisminer.io"
    port="6514"
    protocol="tcp"
    StreamDriver="gtls"
    StreamDriverMode="1"
    StreamDriverAuthMode="x509/name"
    StreamDriverPermittedPeers="siem.thesisminer.io"
    queue.type="LinkedList"
    queue.size="10000"
    queue.filename="siem_queue"
    queue.maxdiskspace="1g"
    queue.saveonshutdown="on"
    action.resumeRetryCount="-1")
```

#### 6.4.3 日志加密

```python
# backend/monitoring/log_encryption.py
from cryptography.fernet import Fernet
import json
import base64


class EncryptedLogHandler(logging.Handler):
    """加密日志处理器。"""

    def __init__(self, filename: str, key: bytes):
        super().__init__()
        self.filename = filename
        self.cipher = Fernet(key)

    def emit(self, record):
        try:
            log_entry = self.format(record)
            encrypted = self.cipher.encrypt(log_entry.encode())
            with open(self.filename, "ab") as f:
                f.write(encrypted + b"\n")
        except Exception:
            self.handleError(record)
```

---

## 7. 入侵检测

### 7.1 HIDS

#### 7.1.1 Wazuh 配置

```xml
<!-- /var/ossec/etc/ossec.conf -->
<ossec_config>

  <global>
    <jsonout_output>yes</jsonout_output>
    <alerts_log>yes</alerts_log>
    <logall>no</logall>
    <logall_json>no</logall_json>
    <email_notification>yes</email_notification>
    <email_to>security@thesisminer.io</email_to>
    <smtp_server>smtp.thesisminer.io</smtp_server>
    <email_from>wazuh@thesisminer.io</email_from>
    <email_maxperhour>12</email_maxperhour>
  </global>

  <!-- 文件完整性监控 -->
  <syscheck>
    <disabled>no</disabled>
    <frequency>43200</frequency>
    <scan_on_start>yes</scan_on_start>

    <directories>/etc/thesisminer</directories>
    <directories>/opt/thesisminer/bin</directories>
    <directories>/data/thesisminer</directories>

    <ignore>/etc/thesisminer/logs</ignore>
    <ignore>/data/thesisminer/logs</ignore>

    <nodiff>/etc/thesisminer/.env</nodiff>
    <nodiff>/etc/thesisminer/api_key.pem</nodiff>
  </syscheck>

  <!-- Rootkit 检测 -->
  <rootcheck>
    <disabled>no</disabled>
    <check_files>yes</check_files>
    <check_trojans>yes</check_trojans>
    <check_dev>yes</check_dev>
    <check_sys>yes</check_sys>
    <check_pids>yes</check_pids>
    <check_ports>yes</check_ports>
    <check_if>yes</check_if>
    <frequency>36000</frequency>
  </rootcheck>

  <!-- 日志监控 -->
  <localfile>
    <log_format>syslog</log_format>
    <location>/var/log/auth.log</location>
  </localfile>

  <localfile>
    <log_format>json</log_format>
    <location>/var/log/thesisminer/audit.log</location>
  </localfile>

  <localfile>
    <log_format>syslog</log_format>
    <location>/var/log/sudo.log</location>
  </localfile>

  <!-- 活动响应 -->
  <active-response>
    <disabled>no</disabled>
    <command>firewall-drop</command>
    <location>local</location>
    <rules_id>5712,5713</rules_id>
    <timeout>600</timeout>
  </active-response>

</ossec_config>
```

### 7.2 NIDS

#### 7.2.1 Suricata 配置

```yaml
# /etc/suricata/suricata.yaml

vars:
  address-groups:
    HOME_NET: "[10.0.0.0/8]"
    EXTERNAL_NET: "!$HOME_NET"
    HTTP_SERVERS: "$HOME_NET"
    SQL_SERVERS: "$HOME_NET"

default-log-dir: /var/log/suricata/

outputs:
  - eve-log:
      enabled: yes
      filetype: regular
      filename: eve.json
      types:
        - alert
        - http
        - dns
        - tls
        - files
        - flow
        - anomaly

app-layer:
  protocols:
    http:
      enabled: yes
    tls:
      enabled: yes
    dns:
      enabled: yes

# 规则
default-rule-path: /var/lib/suricata/rules
rule-files:
  - emerging-all.rules
  - thesisminer.rules
```

```
# /var/lib/suricata/rules/thesisminer.rules

# 检测 SQL 注入
alert http any any -> $HOME_NET any (msg:"SQL Injection Attempt"; \
    content:"UNION"; nocase; content:"SELECT"; nocase; distance:0; within:50; \
    sid:1000001; rev:1;)

# 检测 XSS
alert http any any -> $HOME_NET any (msg:"XSS Attempt"; \
    content:"<script"; nocase; \
    sid:1000002; rev:1;)

# 检测路径穿越
alert http any any -> $HOME_NET any (msg:"Path Traversal Attempt"; \
    content:"../"; \
    sid:1000003; rev:1;)

# 检测异常 User-Agent
alert http any any -> $HOME_NET any (msg:"Suspicious User-Agent"; \
    pcre:"/User-Agent\:.*(?:sqlmap|nikto|nmap|masscan)/Hi"; \
    sid:1000004; rev:1;)
```

### 7.3 文件完整性监控

#### 7.3.1 AIDE 配置

```bash
# /etc/aide/aide.conf

database_in=file:/var/lib/aide/aide.db
database_out=file:/var/lib/aide/aide.db.new

# 规则
ThesisMiner_Config = p+i+n+u+g+s+m+c+sha512
ThesisMiner_Binary = p+i+n+u+g+s+m+c+sha512
ThesisMiner_Data = p+i+n+u+g+s+m+c+sha512

# 监控路径
/etc/thesisminer ThesisMiner_Config
/opt/thesisminer/bin ThesisMiner_Binary
/data/thesisminer ThesisMiner_Data

# 忽略
!/etc/thesisminer/logs
!/data/thesisminer/logs
!/data/thesisminer/tmp
```

```bash
# 初始化基线
aide --init
mv /var/lib/aide/aide.db.new /var/lib/aide/aide.db

# 检查
aide --check

# 更新基线（变更后）
aide --update
mv /var/lib/aide/aide.db.new /var/lib/aide/aide.db
```

### 7.4 异常检测

#### 7.4.1 异常行为检测

```python
# backend/monitoring/anomaly_detection.py
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List
import statistics


class AnomalyDetector:
    """异常行为检测器。"""

    def __init__(self, window_minutes: int = 60):
        self.window = timedelta(minutes=window_minutes)
        self.events: Dict[str, deque] = defaultdict(lambda: deque())

    def record(self, user_id: str, event: str, timestamp: datetime = None):
        """记录事件。"""
        timestamp = timestamp or datetime.now()
        self.events[f"{user_id}:{event}"].append(timestamp)
        self._cleanup(f"{user_id}:{event}", timestamp)

    def _cleanup(self, key: str, now: datetime):
        """清理过期事件。"""
        events = self.events[key]
        while events and events[0] < now - self.window:
            events.popleft()

    def detect_brute_force(self, user_id: str, threshold: int = 10) -> bool:
        """检测暴力破解。"""
        key = f"{user_id}:login_failed"
        self._cleanup(key, datetime.now())
        return len(self.events[key]) >= threshold

    def detect_unusual_access(self, user_id: str,
                              usual_hours: range = range(9, 18)) -> bool:
        """检测异常时间访问。"""
        now = datetime.now()
        return now.hour not in usual_hours

    def detect_mass_export(self, user_id: str, threshold: int = 100) -> bool:
        """检测批量导出。"""
        key = f"{user_id}:export"
        self._cleanup(key, datetime.now())
        return len(self.events[key]) >= threshold

    def detect_privilege_escalation(self, user_id: str) -> bool:
        """检测权限提升。"""
        key = f"{user_id}:sudo"
        self._cleanup(key, datetime.now())
        return len(self.events[key]) >= 5
```

---

## 8. 漏洞扫描

### 8.1 扫描类型

| 类型 | 频率 | 工具 | 说明 |
|------|------|------|------|
| 镜像扫描 | 每次构建 | Trivy | 容器镜像漏洞 |
| 代码扫描 | 每次提交 | Semgrep | 代码漏洞 |
| 依赖扫描 | 每天 | Dependabot | 依赖漏洞 |
| 基础设施扫描 | 每周 | Nessus | 服务器漏洞 |
| 渗透测试 | 每年 | 第三方 | 深度安全测试 |

### 8.2 镜像扫描

#### 8.2.1 Trivy 配置

```yaml
# .trivy.yaml
scan:
  scanners:
    - vuln
    - misconfig
    - secret
    - license

vulnerability:
  severity:
    - CRITICAL
    - HIGH
    - MEDIUM
  ignore-unfixed: true
  ignore-policy: .trivyignore.yaml

misconfig:
  severity:
    - CRITICAL
    - HIGH

secret:
  severity:
    - CRITICAL
    - HIGH
```

```bash
# 扫描镜像
trivy image ghcr.io/thesisminer/thesisminer:8.0.0

# 扫描并生成报告
trivy image --format json --output report.json \
    ghcr.io/thesisminer/thesisminer:8.0.0

# 扫描文件系统
trivy fs --security-checks vuln,secret .

# CI 中集成
trivy image --exit-code 1 --severity CRITICAL,HIGH \
    ghcr.io/thesisminer/thesisminer:8.0.0
```

### 8.3 代码扫描

#### 8.3.1 Semgrep 配置

```yaml
# .semgrep.yml
rules:
  # 检测 SQL 注入
  - id: sql-injection
    patterns:
      - pattern: |
          $DB.execute(f"...{$VAR}...")
      - pattern-not: |
          $DB.execute("...?", ($VAR,))
    message: "Possible SQL injection. Use parameterized queries."
    languages: [python]
    severity: ERROR

  # 检测硬编码密码
  - id: hardcoded-password
    patterns:
      - pattern: |
          $VAR = "..."
      - metavariable-regex:
          metavariable: $VAR
          regex: ".*password.*|.*secret.*|.*api_key.*"
    message: "Hardcoded password/secret detected."
    languages: [python]
    severity: ERROR

  # 检测不安全的 pickle
  - id: unsafe-pickle
    pattern: pickle.loads($DATA)
    message: "Unsafe pickle deserialization."
    languages: [python]
    severity: WARNING

  # 检测不安全的 eval
  - id: unsafe-eval
    pattern: eval($EXPR)
    message: "Unsafe eval."
    languages: [python]
    severity: ERROR

  # 检测不安全的 subprocess
  - id: unsafe-subprocess-shell
    pattern: subprocess.call($CMD, shell=True)
    message: "Unsafe subprocess with shell=True."
    languages: [python]
    severity: ERROR
```

```bash
# 运行扫描
semgrep --config .semgrep.yml backend/

# CI 集成
semgrep --config .semgrep.yml --error backend/
```

### 8.4 依赖扫描

#### 8.4.1 Dependabot 配置

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "daily"
    open-pull-requests-limit: 10
    reviewers:
      - "thesisminer/security"
    assignees:
      - "thesisminer/security-lead"
    labels:
      - "security"
      - "dependencies"

  - package-ecosystem: "docker"
    directory: "/"
    schedule:
      interval: "weekly"
```

#### 8.4.2 pip-audit

```bash
# 安装
pip install pip-audit

# 扫描
pip-audit -r requirements.txt

# CI 集成
pip-audit -r requirements.txt --strict
```

### 8.5 渗透测试

#### 8.5.1 渗透测试范围

- **Web 应用**：API、前端
- **网络**：防火墙、IDS
- **主机**：服务器、容器
- **数据库**：SQLite
- **第三方**：DeepSeek API 集成

#### 8.5.2 渗透测试报告

```markdown
# 渗透测试报告

## 基本信息
- **测试时间**：2026-06-01 至 2026-06-05
- **测试团队**：[第三方安全公司]
- **测试范围**：ThesisMiner v8.0 生产环境

## 发现漏洞

### 漏洞 1：SQL 注入（严重）
- **位置**：/api/v1/thesis/search
- **描述**：搜索接口存在 SQL 注入
- **PoC**：`?keyword=' OR '1'='1`
- **修复**：使用参数化查询
- **状态**：已修复

### 漏洞 2：XSS（高）
- **位置**：/api/v1/thesis/{id}
- **描述**：论文标题未转义
- **修复**：HTML 编码输出
- **状态**：已修复

### 漏洞 3：CSRF（中）
- **位置**：/api/v1/thesis/generate
- **描述**：缺少 CSRF token
- **修复**：添加 CSRF 中间件
- **状态**：已修复

## 结论
共发现 3 个漏洞，全部已修复。建议定期复查。
```

---

## 9. 安全基线

### 9.1 CIS Benchmark

#### 9.1.1 CIS Benchmark 概述

CIS Benchmark 是互联网安全中心发布的安全配置基线，覆盖操作系统、数据库、中间件、云平台等。

#### 9.1.2 CIS Ubuntu Linux Benchmark

| 编号 | 检查项 | 建议 | ThesisMiner 状态 |
|------|--------|------|------------------|
| 1.1.1 | 禁用不必要的文件系统 | 禁用 cramfs、freevxfs、jffs2、hfs、hfsplus、squashfs、udf | ✓ 已禁用 |
| 1.4.1 | 单用户模式需要密码 | 设置 root 密码 | ✓ 已设置 |
| 1.4.2 | 引导加载程序密码 | 设置 GRUB 密码 | ✓ 已设置 |
| 1.5.1 | 内核模块签名验证 | 启用 | ✓ 已启用 |
| 2.1.1 | 时间同步 | 安装 chrony 或 ntp | ✓ 已安装 |
| 3.1.1 | 禁用 IPv6 | 如不使用则禁用 | ✓ 已禁用 |
| 3.2.1 | 禁用 IP 转发 | net.ipv4.ip_forward=0 | ✓ 已设置 |
| 3.2.2 | 禁用源路由 | accept_source_route=0 | ✓ 已设置 |
| 4.1.1 | 安装 auditd | 安装 auditd | ✓ 已安装 |
| 4.2.1 | 安装 rsyslog | 安装 rsyslog | ✓ 已安装 |
| 5.1.1 | 确保 cron 已安装 | 安装 cron | ✓ 已安装 |
| 5.2.1 | sudo 已安装 | 安装 sudo | ✓ 已安装 |
| 5.2.6 | sudo 日志 | 配置 sudo 日志 | ✓ 已配置 |
| 5.3.1 | SSH 协议版本 | Protocol 2 | ✓ 已设置 |
| 5.3.2 | 禁止 root SSH 登录 | PermitRootLogin no | ✓ 已设置 |
| 5.3.3 | 禁止空密码 | PermitEmptyPasswords no | ✓ 已设置 |
| 5.3.4 | 禁止密码认证 | PasswordAuthentication no | ✓ 已设置 |
| 5.4.1 | 密码最大天数 | PASS_MAX_DAYS 90 | ✓ 已设置 |
| 5.4.2 | 密码最小天数 | PASS_MIN_DAYS 1 | ✓ 已设置 |
| 5.4.3 | 密码警告天数 | PASS_WARN_AGE 7 | ✓ 已设置 |
| 5.5.1 | 禁用空密码账户 | 无空密码账户 | ✓ 已确认 |
| 5.5.2 | root 唯一 UID 0 | 仅 root UID=0 | ✓ 已确认 |
| 6.1.1 | 文件权限 | /etc/passwd 644 | ✓ 已设置 |
| 6.1.2 | 文件权限 | /etc/shadow 640 | ✓ 已设置 |
| 6.1.3 | 文件权限 | /etc/group 644 | ✓ 已设置 |

### 9.2 合规检查

#### 9.2.1 合规框架

| 框架 | 适用 | 说明 |
|------|------|------|
| ISO 27001 | 全球 | 信息安全管理 |
| SOC 2 | 全球 | 服务组织控制 |
| GDPR | 欧盟 | 通用数据保护条例 |
| CCPA | 加州 | 消费者隐私法 |
| PIPL | 中国 | 个人信息保护法 |
| 等保 2.0 | 中国 | 网络安全等级保护 |

#### 9.2.2 等保 2.0 检查项

| 类别 | 检查项 | 状态 |
|------|--------|------|
| 安全物理环境 | 机房物理安全 | ✓ 云服务商负责 |
| 安全通信网络 | 网络分段 | ✓ VLAN 隔离 |
| 安全区域边界 | 防火墙 | ✓ iptables + WAF |
| 安全计算环境 | 身份鉴别 | ✓ MFA |
| 安全计算环境 | 访问控制 | ✓ RBAC |
| 安全计算环境 | 安全审计 | ✓ auditd + 应用审计 |
| 安全计算环境 | 入侵防范 | ✓ HIDS + NIDS |
| 安全计算环境 | 恶意代码防范 | ✓ ClamAV |
| 安全管理中心 | 集中管控 | ✓ SIEM |
| 安全管理中心 | 安全审计 | ✓ 集中审计 |

### 9.3 基线扫描

#### 9.3.1 Lynis 扫描

```bash
# 安装
apt-get install lynis

# 扫描
lynis audit system --quick

# 详细扫描
lynis audit system

# 生成报告
lynis audit system --pentest
```

#### 9.3.2 OpenSCAP 扫描

```bash
# 安装
apt-get install openscap-scanner ssg-noble

# 扫描
oscap xccdf eval --profile xccdf_org.ssgproject.content_profile_cis_server_l2 \
    --results scan-results.xml --report scan-report.html \
    /usr/share/xml/scap/ssg/content/ssg-ubuntu2204-ds.xml
```

---

## 10. 密钥与凭证管理

### 10.1 密钥管理

#### 10.1.1 HashiCorp Vault

```python
# backend/monitoring/vault_client.py
import hvac
from typing import Optional


class VaultClient:
    """Vault 密钥管理客户端。"""

    def __init__(self, url: str, token: str):
        self.client = hvac.Client(url=url, token=token)

    def get_secret(self, path: str, key: str) -> Optional[str]:
        """获取密钥。"""
        try:
            response = self.client.secrets.kv.read_secret_version(path=path)
            return response["data"]["data"].get(key)
        except Exception:
            return None

    def put_secret(self, path: str, **secrets):
        """存储密钥。"""
        self.client.secrets.kv.create_or_update_secret(
            path=path, secret=secrets
        )

    def rotate_secret(self, path: str, key: str, new_value: str):
        """轮换密钥。"""
        self.put_secret(path, **{key: new_value})


# 使用
vault = VaultClient("https://vault.thesisminer.io", os.environ["VAULT_TOKEN"])

# 获取 DeepSeek API Key
deepseek_key = vault.get_secret("thesisminer/ai", "deepseek_api_key")

# 获取数据库密码
db_password = vault.get_secret("thesisminer/db", "password")
```

#### 10.1.2 Kubernetes Secrets

```yaml
# deploy/k8s/secrets.yml
apiVersion: v1
kind: Secret
metadata:
  name: thesisminer-secrets
  namespace: thesisminer
type: Opaque
stringData:
  DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY}
  DATABASE_URL: ${DATABASE_URL}
  REDIS_PASSWORD: ${REDIS_PASSWORD}
  JWT_SECRET: ${JWT_SECRET}
```

```yaml
# 使用 External Secrets 从 Vault 拉取
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: thesisminer-secrets
  namespace: thesisminer
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: thesisminer-secrets
    creationPolicy: Owner
  data:
  - secretKey: DEEPSEEK_API_KEY
    remoteRef:
      key: thesisminer/ai
      property: deepseek_api_key
  - secretKey: DATABASE_URL
    remoteRef:
      key: thesisminer/db
      property: url
```

### 10.2 凭证管理

#### 10.2.1 凭证存储原则

- **不硬编码**：禁止在代码中硬编码凭证
- **不提交 Git**：禁止将凭证提交到版本控制
- **环境变量**：通过环境变量传递
- **密钥管理服务**：使用 Vault/KMS 集中管理
- **最小权限**：凭证仅授予最小必要权限

#### 10.2.2 .env 文件管理

```bash
# .env.example（提交到 Git，作为模板）
DEEPSEEK_API_KEY=your-api-key-here
DATABASE_URL=sqlite:///data/thesisminer.db
REDIS_URL=redis://redis:6379
JWT_SECRET=your-jwt-secret
LOG_LEVEL=INFO

# .env（不提交到 Git，实际值）
# .gitignore 中添加 .env
```

```python
# .gitignore
.env
.env.local
.env.production
*.key
*.pem
secrets/
```

#### 10.2.3 凭证审计

```python
# scripts/security/credential_audit.py
import re
from pathlib import Path
from typing import List


class CredentialAuditor:
    """凭证审计器。"""

    PATTERNS = {
        "AWS Access Key": r"AKIA[0-9A-Z]{16}",
        "AWS Secret Key": r"[0-9a-zA-Z/+]{40}",
        "GitHub Token": r"gh[pousr]_[A-Za-z0-9_]{36}",
        "Slack Token": r"xox[baprs]-[A-Za-z0-9-]+",
        "Google API Key": r"AIza[0-9A-Za-z\-_]{35}",
        "Private Key": r"-----BEGIN (RSA |EC )?PRIVATE KEY-----",
        "Generic Password": r"(?i)password\s*[=:]\s*\S+",
        "Generic API Key": r"(?i)api[_-]?key\s*[=:]\s*\S+",
    }

    def scan_file(self, file_path: Path) -> List[dict]:
        """扫描文件中的凭证。"""
        findings = []
        content = file_path.read_text(errors="ignore")

        for name, pattern in self.PATTERNS.items():
            matches = re.finditer(pattern, content)
            for match in matches:
                findings.append({
                    "file": str(file_path),
                    "type": name,
                    "line": content[:match.start()].count("\n") + 1,
                    "match": match.group()[:20] + "..."  # 截断
                })

        return findings

    def scan_directory(self, dir_path: Path) -> List[dict]:
        """扫描目录。"""
        all_findings = []
        for file_path in dir_path.rglob("*"):
            if file_path.is_file() and file_path.suffix in (
                ".py", ".yml", ".yaml", ".json", ".env", ".conf", ".txt"
            ):
                all_findings.extend(self.scan_file(file_path))
        return all_findings


if __name__ == "__main__":
    auditor = CredentialAuditor()
    findings = auditor.scan_directory(Path("backend/"))
    for f in findings:
        print(f"⚠ {f['type']} in {f['file']}:{f['line']}")
```

### 10.3 证书管理

#### 10.3.1 TLS 证书

```bash
# 生成 CSR
openssl req -new -newkey rsa:2048 -nodes \
    -keyout thesisminer.key -out thesisminer.csr \
    -subj "/C=CN/ST=Beijing/L=Beijing/O=ThesisMiner/CN=thesisminer.example.com"

# 自签名证书（开发环境）
openssl x509 -req -days 365 -in thesisminer.csr \
    -signkey thesisminer.key -out thesisminer.crt

# Let's Encrypt（生产环境）
certbot certonly --webroot -w /var/www/html \
    -d thesisminer.example.com \
    --email admin@thesisminer.io --agree-tos
```

#### 10.3.2 证书监控

```python
# scripts/security/cert_monitor.py
import ssl
import socket
from datetime import datetime
from typing import List


class CertificateMonitor:
    """证书监控器。"""

    def check_cert(self, hostname: str, port: int = 443) -> dict:
        """检查证书。"""
        context = ssl.create_default_context()
        with socket.create_connection((hostname, port)) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()

        not_after = datetime.strptime(
            cert["notAfter"], "%b %d %H:%M:%S %Y %Z"
        )
        days_left = (not_after - datetime.now()).days

        return {
            "hostname": hostname,
            "issuer": dict(x[0] for x in cert["issuer"]),
            "subject": dict(x[0] for x in cert["subject"]),
            "not_before": cert["notBefore"],
            "not_after": cert["notAfter"],
            "days_left": days_left,
            "expired": days_left < 0,
            "expiring_soon": 0 <= days_left <= 30
        }


if __name__ == "__main__":
    monitor = CertificateMonitor()
    result = monitor.check_cert("thesisminer.example.com")
    if result["expiring_soon"]:
        print(f"⚠ Certificate expiring in {result['days_left']} days")
    elif result["expired"]:
        print("✗ Certificate expired!")
    else:
        print(f"✓ Certificate valid, {result['days_left']} days left")
```

### 10.4 密钥轮换

#### 10.4.1 轮换策略

| 密钥类型 | 轮换频率 | 方式 |
|----------|----------|------|
| API Key | 90 天 | 双 Key 平滑切换 |
| 数据库密码 | 90 天 | 双密码平滑切换 |
| JWT Secret | 180 天 | 双 Secret 平滑切换 |
| TLS 证书 | 365 天 | 自动续期 |
| SSH 密钥 | 180 天 | 手动轮换 |
| 加密密钥 | 365 天 | 双密钥重新加密 |

#### 10.4.2 轮换脚本

```python
# scripts/security/rotate_keys.py
import os
import time
from backend.monitoring.vault_client import VaultClient


class KeyRotator:
    """密钥轮换器。"""

    def __init__(self, vault: VaultClient):
        self.vault = vault

    def rotate_api_key(self, service: str) -> str:
        """轮换 API Key（双 Key 平滑切换）。"""
        # 1. 生成新 Key
        new_key = self._generate_api_key()

        # 2. 存储新 Key（保留旧 Key）
        old_key = self.vault.get_secret(f"thesisminer/{service}", "api_key")
        self.vault.put_secret(
            f"thesisminer/{service}",
            api_key=new_key,
            api_key_previous=old_key,
            rotation_time=int(time.time())
        )

        # 3. 更新应用配置（使用新 Key）
        # 应用支持双 Key，优先用新 Key，旧 Key 作为备用

        # 4. 等待应用刷新（5 分钟）
        time.sleep(300)

        # 5. 删除旧 Key
        self.vault.put_secret(
            f"thesisminer/{service}",
            api_key=new_key,
            api_key_previous=None
        )

        return new_key

    def _generate_api_key(self) -> str:
        """生成 API Key。"""
        import secrets
        return secrets.token_urlsafe(32)
```

---

## 11. 安全加固案例

### 11.1 案例一：服务器加固

#### 11.1.1 背景

新部署 10 台生产服务器，需进行安全加固。

#### 11.1.2 加固步骤

1. **系统更新**：安装所有安全补丁
2. **禁用服务**：禁用 23 个不必要服务
3. **配置防火墙**：iptables 规则
4. **SSH 加固**：修改端口、禁用密码登录
5. **用户管理**：删除多余用户、配置 sudo
6. **内核加固**：sysctl 参数
7. **审计配置**：auditd 规则
8. **HIDS 部署**：Wazuh 安装
9. **文件权限**：关键文件权限
10. **基线扫描**：Lynis 扫描

#### 11.1.3 结果

加固后 Lynis 评分从 65 提升到 92。

### 11.2 案例二：应用安全加固

#### 11.2.1 背景

ThesisMiner v8.0 应用层安全加固。

#### 11.2.2 加固内容

1. **安全头**：添加 7 个安全响应头
2. **CORS**：严格白名单
3. **输入验证**：Pydantic 模型
4. **SQL 注入防护**：参数化查询
5. **XSS 防护**：输出编码
6. **CSRF 防护**：Token 验证
7. **文件上传**：类型、大小、病毒扫描
8. **会话安全**：安全 Cookie、会话固定防护
9. **限流**：API 限流
10. **审计日志**：全操作审计

#### 11.2.3 结果

渗透测试发现漏洞从 8 个降到 0 个。

### 11.3 案例三：网络加固

#### 11.3.1 背景

生产网络架构加固。

#### 11.3.2 加固内容

1. **VLAN 划分**：4 个 VLAN 隔离
2. **防火墙**：iptables + WAF
3. **网络策略**：Kubernetes NetworkPolicy
4. **DDoS 防护**：CDN + 流量清洗
5. **入侵检测**：Suricata NIDS
6. **VPN**：管理访问通过 VPN
7. **跳板机**：所有管理通过跳板机

#### 11.3.3 结果

网络攻击拦截率提升到 99%。

### 11.4 案例四：应急响应

#### 11.4.1 事件

2026-04-20 发现勒索软件攻击（详见灾备文档案例三）。

#### 11.4.2 响应

1. **检测**：HIDS 告警异常文件变更
2. **隔离**：断开受影响主机网络
3. **取证**：保留磁盘镜像
4. **清除**：重装系统
5. **恢复**：从离线备份恢复
6. **加固**：修复入侵路径（SSH 弱密码）
7. **复盘**：撰写 Postmortem

#### 11.4.3 改进

1. 强制 SSH 密钥认证
2. 部署文件完整性监控
3. 备份离线存储
4. 网络分段隔离
5. 定期安全审计

---

## 12. 检查清单

### 12.1 操作系统检查清单

- [ ] 系统已更新到最新补丁
- [ ] 不必要服务已禁用
- [ ] 不必要软件包已删除
- [ ] 内核参数已加固（sysctl）
- [ ] 防火墙已配置
- [ ] SSH 已加固（端口、密钥、禁用 root）
- [ ] fail2ban 已安装
- [ ] 用户密码策略已配置
- [ ] 账户锁定策略已配置
- [ ] sudo 已配置最小权限
- [ ] auditd 已配置
- [ ] rsyslog 已配置
- [ ] HIDS 已部署
- [ ] 文件完整性监控已配置
- [ ] 定期重启（内核更新）

### 12.2 网络检查清单

- [ ] 防火墙默认策略为 DROP
- [ ] 仅开放必要端口
- [ ] 网络已分段（VLAN）
- [ ] Kubernetes NetworkPolicy 已配置
- [ ] WAF 已部署
- [ ] DDoS 防护已配置
- [ ] 限流已配置
- [ ] NIDS 已部署
- [ ] VPN 已配置（管理访问）
- [ ] 跳板机已部署
- [ ] TLS 全站启用
- [ ] 证书自动续期

### 12.3 应用检查清单

- [ ] 安全响应头已配置
- [ ] CORS 严格白名单
- [ ] 输入验证（Pydantic）
- [ ] 输出编码
- [ ] SQL 注入防护（参数化查询）
- [ ] XSS 防护
- [ ] CSRF 防护
- [ ] 文件上传安全
- [ ] 会话安全（安全 Cookie）
- [ ] 认证与授权
- [ ] MFA 已启用
- [ ] API 限流
- [ ] 审计日志
- [ ] 错误处理不泄露信息
- [ ] 敏感数据加密

### 12.4 综合检查清单

- [ ] 安全基线扫描通过（CIS Benchmark）
- [ ] 漏洞扫描无严重漏洞
- [ ] 渗透测试通过
- [ ] 密钥管理（Vault）
- [ ] 凭证无硬编码
- [ ] 密钥轮换策略
- [ ] 日志审计
- [ ] 入侵检测
- [ ] 应急响应预案
- [ ] 安全培训
- [ ] 合规检查通过

---

## 13. 附录

### 13.1 配置示例

#### 13.1.1 完整加固脚本

```bash
#!/bin/bash
# scripts/security/harden_system.sh

set -euo pipefail

echo "=========================================="
echo "ThesisMiner System Hardening"
echo "Time: $(date)"
echo "=========================================="

# 1. 系统更新
echo "[1/10] System update..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get dist-upgrade -y -qq

# 2. 安装安全工具
echo "[2/10] Install security tools..."
apt-get install -y -qq \
    fail2ban \
    auditd \
    aide \
    clamav \
    lynis \
    unattended-upgrades

# 3. 禁用不必要服务
echo "[3/10] Disable unnecessary services..."
./scripts/security/disable_services.sh

# 4. 内核加固
echo "[4/10] Kernel hardening..."
cp config/sysctl/99-thesisminer-security.conf /etc/sysctl.d/
sysctl --system

# 5. 防火墙配置
echo "[5/10] Firewall configuration..."
./scripts/security/setup_firewall.sh
./scripts/security/setup_ip6tables.sh

# 6. SSH 加固
echo "[6/10] SSH hardening..."
cp config/ssh/sshd_config /etc/ssh/sshd_config
systemctl restart sshd

# 7. 用户与权限
echo "[7/10] User and permissions..."
./scripts/security/set_permissions.sh

# 8. 审计配置
echo "[8/10] Audit configuration..."
cp config/audit/thesisminer.rules /etc/audit/rules.d/
augenrules --load
systemctl enable auditd
systemctl start auditd

# 9. HIDS 部署
echo "[9/10] HIDS deployment..."
# Wazuh agent 安装
curl -sO https://packages.wazuh.com/4.x/apt/pool/main/w/wazuh-agent/wazuh-agent_4.5.0-1_amd64.deb
dpkg -i wazuh-agent_4.5.0-1_amd64.deb
sed -i 's/MANAGER_IP/wazuh.thesisminer.io/' /var/ossec/etc/ossec.conf
systemctl daemon-reload
systemctl enable wazuh-agent
systemctl start wazuh-agent

# 10. 基线扫描
echo "[10/10] Baseline scan..."
lynis audit system --quick

echo "=========================================="
echo "Hardening completed"
echo "=========================================="
```

### 13.2 工具列表

| 工具 | 用途 | 类型 |
|------|------|------|
| Lynis | 系统基线扫描 | 开源 |
| OpenSCAP | 合规扫描 | 开源 |
| Trivy | 镜像/文件系统扫描 | 开源 |
| Semgrep | 代码扫描 | 开源 |
| pip-audit | 依赖扫描 | 开源 |
| Wazuh | HIDS | 开源 |
| Suricata | NIDS | 开源 |
| AIDE | 文件完整性监控 | 开源 |
| ClamAV | 病毒扫描 | 开源 |
| fail2ban | 入侵防护 | 开源 |
| ModSecurity | WAF | 开源 |
| HashiCorp Vault | 密钥管理 | 开源/商业 |
| Nessus | 漏洞扫描 | 商业 |

### 13.3 参考资料

- CIS Benchmarks: https://www.cisecurity.org/cis-benchmarks
- NIST Cybersecurity Framework: https://www.nist.gov/cyberframework
- OWASP Top 10: https://owasp.org/Top10
- OWASP Cheat Sheet: https://cheatsheetseries.owasp.org
- MITRE ATT&CK: https://attack.mitre.org
- CVE Database: https://cve.mitre.org
- NVD: https://nvd.nist.gov

### 13.4 变更记录

| 版本 | 日期 | 变更 | 作者 |
|------|------|------|------|
| v1.0 | 2026-01-15 | 初始版本 | Security Team |
| v2.0 | 2026-03-20 | 增加应用加固 | Security Team |
| v3.0 | 2026-05-10 | 增加入侵检测 | Security Team |
| v8.0 | 2026-06-20 | 适配 v8.0，增加案例 | Security Team |

---

## 14. FAQ

### Q1: 安全加固会影响性能吗？

**A**: 合理的加固对性能影响极小（< 5%）。防火墙、加密、审计会有轻微开销，但现代硬件可轻松承受。安全与性能需平衡，不建议为性能牺牲安全。

### Q2: 多久做一次安全扫描？

**A**: 镜像扫描每次构建；代码扫描每次提交；依赖扫描每天；基础设施扫描每周；渗透测试每年。持续扫描优于一次性扫描。

### Q3: 发现漏洞怎么处理？

**A**: 严重漏洞（CVSS ≥ 9）24 小时内修复；高危漏洞（7-8.9）7 天内修复；中危漏洞（4-6.9）30 天内修复；低危漏洞（< 4）下次发布修复。

### Q4: SSH 必须用密钥吗？

**A**: 强烈建议。密码登录易被暴力破解，密钥登录安全性高得多。ThesisMiner v8.0 强制密钥登录，禁止密码登录。

### Q5: WAF 会误报吗？

**A**: 会。WAF 规则需调优，初期建议仅观察模式，收集误报后调整规则，再切换到阻断模式。

### Q6: 如何防止内部威胁？

**A**: 1) 最小权限原则；2) 操作审计；3) 职责分离；4) 定期权限审查；5) 离职及时收回权限；6) 敏感操作多人审批。

### Q7: 密钥轮换会影响业务吗？

**A**: 合理设计不会。采用双密钥平滑切换：新密钥生效后保留旧密钥一段时间，确认无误后删除旧密钥。ThesisMiner v8.0 所有密钥轮换都采用此方式。

### Q8: 容器需要加固吗？

**A**: 需要。1) 使用最小基础镜像；2) 非 root 用户运行；3) 只读文件系统；4) 禁用特权模式；5) 镜像扫描；6) 资源限制。

### Q9: 如何检测是否被入侵？

**A**: 1) HIDS 告警；2) 文件完整性监控；3) 异常日志；4) 网络流量异常；5) 系统资源异常；6) 用户行为异常。多层检测，单一手段不够。

### Q10: 安全事件如何响应？

**A**: 1) 检测确认；2) 隔离遏制；3) 取证分析；4) 清除威胁；5) 恢复服务；6) 加固改进；7) 复盘总结。详见应急响应预案。

---

## 15. 结语

安全是一个持续的过程，而非一次性的项目。ThesisMiner v8.0 通过操作系统加固、网络加固、应用加固、文件权限、日志审计、入侵检测、漏洞扫描、安全基线、密钥管理等全方位措施，构建了纵深防御体系。随着威胁演进，安全措施应持续更新，确保系统始终处于安全状态。

**核心要点回顾**：

1. **纵深防御**：多层防护，避免单点失效
2. **最小权限**：最小必要权限
3. **默认安全**：默认配置即安全
4. **假设失陷**：设计检测与响应
5. **安全左移**：开发阶段考虑安全
6. **零信任**：不信任，全验证
7. **可审计**：所有操作可审计
8. **持续监控**：7x24 安全监控

---

**文档结束**

> 本文档由 ThesisMiner Security Team 维护，最后更新于 2026-06-20。
> 如有疑问或建议，请联系 `security@thesisminer.io` 或在内部 Wiki 提交 Issue。
> 本文档为内部机密，未经授权不得外传。
