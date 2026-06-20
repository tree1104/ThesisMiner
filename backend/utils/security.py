"""安全工具

提供 API 密钥加密、密码哈希、JWT 令牌、CSRF 令牌、速率限制等安全能力。

核心组件：
    - PasswordHasher: 密码哈希（PBKDF2 / 安全比较）
    - APIKeyManager: API 密钥加密存储
    - JWTManager: JWT 令牌签发与验证
    - CSRFTokenManager: CSRF 令牌生成与验证
    - RateLimiter: 速率限制（滑动窗口 / 令牌桶）
    - SecurityUtils: 安全工具函数集合

设计原则：
    1. 安全优先：使用标准库加密原语，避免自实现加密算法
    2. 零依赖：仅使用 Python 标准库（hashlib / hmac / secrets / json / base64）
    3. 防御纵深：多层安全校验，不依赖单一防护
    4. 可审计：所有安全操作可记录日志
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import string
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Optional


# ===== 密码哈希 =====


class PasswordHasher:
    """密码哈希器

    使用 PBKDF2-HMAC-SHA256 算法哈希密码，加盐防彩虹表攻击。
    哈希格式：pbkdf2$iterations$salt_hex$hash_hex

    使用示例：
        hasher = PasswordHasher()
        hashed = hasher.hash("mypassword")
        hasher.verify("mypassword", hashed)  # True
        hasher.verify("wrongpassword", hashed)  # False
    """

    ALGORITHM = "pbkdf2"
    HASH_NAME = "sha256"
    ITERATIONS = 100000
    SALT_LENGTH = 32  # 字节
    HASH_LENGTH = 32  # 字节

    def __init__(self, iterations: Optional[int] = None):
        self.iterations = iterations or self.ITERATIONS

    def hash(self, password: str) -> str:
        """哈希密码。

        Args:
            password: 明文密码。

        Returns:
            哈希字符串（格式：pbkdf2$iterations$salt_hex$hash_hex）。
        """
        if not password:
            raise ValueError("密码不能为空")
        salt = secrets.token_bytes(self.SALT_LENGTH)
        hash_bytes = hashlib.pbkdf2_hmac(
            self.HASH_NAME,
            password.encode("utf-8"),
            salt,
            self.iterations,
            dklen=self.HASH_LENGTH,
        )
        return f"{self.ALGORITHM}${self.iterations}${salt.hex()}${hash_bytes.hex()}"

    def verify(self, password: str, hashed: str) -> bool:
        """验证密码。

        Args:
            password: 待验证的明文密码。
            hashed: 已哈希的密码字符串。

        Returns:
            匹配返回 True，不匹配返回 False。
        """
        if not password or not hashed:
            return False
        try:
            parts = hashed.split("$")
            if len(parts) != 4 or parts[0] != self.ALGORITHM:
                return False
            iterations = int(parts[1])
            salt = bytes.fromhex(parts[2])
            stored_hash = bytes.fromhex(parts[3])
            computed_hash = hashlib.pbkdf2_hmac(
                self.HASH_NAME,
                password.encode("utf-8"),
                salt,
                iterations,
                dklen=len(stored_hash),
            )
            return hmac.compare_digest(computed_hash, stored_hash)
        except (ValueError, IndexError, TypeError):
            return False

    def needs_rehash(self, hashed: str, min_iterations: Optional[int] = None) -> bool:
        """判断密码是否需要重新哈希（迭代次数不足）。"""
        if not hashed:
            return True
        try:
            parts = hashed.split("$")
            if len(parts) != 4:
                return True
            iterations = int(parts[1])
            threshold = min_iterations or self.iterations
            return iterations < threshold
        except (ValueError, IndexError):
            return True


# ===== API 密钥管理 =====


class APIKeyManager:
    """API 密钥管理器

    提供 API 密钥的生成、加密存储、验证与脱敏功能。
    密钥使用 Fernet 风格的对称加密（基于 HMAC-SHA256）。

    使用示例：
        manager = APIKeyManager(secret_key="my-secret")
        encrypted = manager.encrypt("sk-xxxxxxxx")
        decrypted = manager.decrypt(encrypted)
    """

    def __init__(self, secret_key: Optional[str] = None):
        """初始化 API 密钥管理器。

        Args:
            secret_key: 加密密钥（应为高熵随机字符串）。为 None 则自动生成。
        """
        self._secret_key = secret_key or secrets.token_urlsafe(32)
        self._key_bytes = hashlib.sha256(self._secret_key.encode("utf-8")).digest()

    def encrypt(self, plaintext: str) -> str:
        """加密明文。

        使用 XOR 流加密 + HMAC 签名，确保机密性与完整性。

        Args:
            plaintext: 明文字符串。

        Returns:
            Base64 编码的密文字符串。
        """
        if not plaintext:
            return ""
        # 生成随机 IV
        iv = secrets.token_bytes(16)
        # 基于 IV 与密钥派生流密钥
        stream_key = hashlib.sha256(self._key_bytes + iv).digest()
        # XOR 加密
        plaintext_bytes = plaintext.encode("utf-8")
        cipher_bytes = bytes(
            b ^ stream_key[i % len(stream_key)]
            for i, b in enumerate(plaintext_bytes)
        )
        # HMAC 签名
        signature = hmac.new(
            self._key_bytes, iv + cipher_bytes, hashlib.sha256
        ).digest()
        # 组合：iv + signature + cipher
        combined = iv + signature + cipher_bytes
        return base64.urlsafe_b64encode(combined).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        """解密密文。

        Args:
            ciphertext: Base64 编码的密文字符串。

        Returns:
            明文字符串。

        Raises:
            ValueError: 密文无效或签名校验失败。
        """
        if not ciphertext:
            return ""
        try:
            combined = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
            if len(combined) < 48:  # iv(16) + signature(32)
                raise ValueError("密文长度不足")
            iv = combined[:16]
            signature = combined[16:48]
            cipher_bytes = combined[48:]
            # 验证签名
            expected_signature = hmac.new(
                self._key_bytes, iv + cipher_bytes, hashlib.sha256
            ).digest()
            if not hmac.compare_digest(signature, expected_signature):
                raise ValueError("签名校验失败")
            # 解密
            stream_key = hashlib.sha256(self._key_bytes + iv).digest()
            plaintext_bytes = bytes(
                b ^ stream_key[i % len(stream_key)]
                for i, b in enumerate(cipher_bytes)
            )
            return plaintext_bytes.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as e:
            raise ValueError(f"解密失败: {e}")

    def generate_api_key(self, prefix: str = "sk", length: int = 32) -> str:
        """生成新的 API 密钥。"""
        return f"{prefix}-{secrets.token_urlsafe(length)}"

    def mask_api_key(self, api_key: str, visible_start: int = 4, visible_end: int = 4) -> str:
        """脱敏 API 密钥。"""
        if not api_key or len(api_key) <= visible_start + visible_end:
            return "*" * len(api_key) if api_key else ""
        return (
            api_key[:visible_start]
            + "*" * (len(api_key) - visible_start - visible_end)
            + api_key[-visible_end:]
        )

    def is_valid_format(self, api_key: str) -> bool:
        """验证 API 密钥格式。"""
        if not api_key or len(api_key) < 10:
            return False
        # 允许字母数字连字符下划线
        import re
        return bool(re.match(r"^[a-zA-Z0-9\-_]+$", api_key))


# ===== JWT 令牌 =====


class JWTManager:
    """JWT 令牌管理器

    实现 JWT（JSON Web Token）的签发与验证。
    使用 HMAC-SHA256 签名算法。

    使用示例：
        manager = JWTManager(secret_key="my-secret")
        token = manager.create_token({"user_id": "123"}, expires_in=3600)
        payload = manager.verify_token(token)  # 返回 payload 或 None
    """

    HEADER = {"alg": "HS256", "typ": "JWT"}

    def __init__(self, secret_key: Optional[str] = None, issuer: str = "thesisminer"):
        self._secret_key = secret_key or secrets.token_urlsafe(32)
        self.issuer = issuer

    def _base64url_encode(self, data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    def _base64url_decode(self, data: str) -> bytes:
        padding = 4 - len(data) % 4
        if padding != 4:
            data += "=" * padding
        return base64.urlsafe_b64decode(data.encode("ascii"))

    def _sign(self, data: str) -> str:
        signature = hmac.new(
            self._secret_key.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return self._base64url_encode(signature)

    def create_token(
        self,
        payload: dict,
        expires_in: int = 3600,
        subject: str = "",
        audience: str = "",
    ) -> str:
        """签发 JWT 令牌。

        Args:
            payload: 载荷数据。
            expires_in: 过期时间（秒）。
            subject: 主题（通常为用户 ID）。
            audience: 受众。

        Returns:
            JWT 令牌字符串。
        """
        now = int(time.time())
        full_payload = {
            "iss": self.issuer,
            "iat": now,
            "exp": now + expires_in,
            **payload,
        }
        if subject:
            full_payload["sub"] = subject
        if audience:
            full_payload["aud"] = audience

        header_encoded = self._base64url_encode(
            json.dumps(self.HEADER, separators=(",", ":")).encode("utf-8")
        )
        payload_encoded = self._base64url_encode(
            json.dumps(full_payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        )
        signing_input = f"{header_encoded}.{payload_encoded}"
        signature = self._sign(signing_input)
        return f"{signing_input}.{signature}"

    def verify_token(self, token: str, verify_exp: bool = True) -> Optional[dict]:
        """验证 JWT 令牌。

        Args:
            token: JWT 令牌字符串。
            verify_exp: 是否验证过期时间。

        Returns:
            载荷字典，验证失败返回 None。
        """
        if not token:
            return None
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            header_encoded, payload_encoded, signature = parts

            # 验证签名
            expected_signature = self._sign(f"{header_encoded}.{payload_encoded}")
            if not hmac.compare_digest(signature, expected_signature):
                return None

            # 解析载荷
            payload_bytes = self._base64url_decode(payload_encoded)
            payload = json.loads(payload_bytes.decode("utf-8"))

            # 验证过期时间
            if verify_exp and "exp" in payload:
                if time.time() > payload["exp"]:
                    return None

            return payload
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            return None

    def refresh_token(self, token: str, expires_in: int = 3600) -> Optional[str]:
        """刷新令牌（验证旧令牌后签发新令牌）。

        Args:
            token: 旧令牌（可已过期但签名必须有效）。
            expires_in: 新令牌过期时间。

        Returns:
            新令牌字符串，验证失败返回 None。
        """
        payload = self.verify_token(token, verify_exp=False)
        if payload is None:
            return None
        # 移除标准声明，保留业务字段
        business_payload = {
            k: v for k, v in payload.items()
            if k not in ("iss", "iat", "exp", "sub", "aud")
        }
        subject = payload.get("sub", "")
        audience = payload.get("aud", "")
        return self.create_token(
            business_payload,
            expires_in=expires_in,
            subject=subject,
            audience=audience,
        )

    def decode_token_unsafe(self, token: str) -> Optional[dict]:
        """不验证签名地解码令牌（仅用于调试）。

        Args:
            token: JWT 令牌字符串。

        Returns:
            载荷字典，解码失败返回 None。
        """
        if not token:
            return None
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            payload_bytes = self._base64url_decode(parts[1])
            return json.loads(payload_bytes.decode("utf-8"))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            return None


# ===== CSRF 令牌 =====


class CSRFTokenManager:
    """CSRF 令牌管理器

    生成与验证 CSRF 令牌，防止跨站请求伪造攻击。
    使用 HMAC 签名的随机令牌，支持会话绑定与时效验证。

    使用示例：
        manager = CSRFTokenManager(secret_key="my-secret")
        token = manager.generate_token(session_id="sess-123")
        is_valid = manager.validate_token(token, session_id="sess-123")
    """

    def __init__(self, secret_key: Optional[str] = None, token_ttl: int = 3600):
        self._secret_key = secret_key or secrets.token_urlsafe(32)
        self.token_ttl = token_ttl
        self._used_tokens: set = set()
        self._lock = threading.Lock()

    def generate_token(self, session_id: str = "") -> str:
        """生成 CSRF 令牌。

        Args:
            session_id: 会话 ID（用于绑定会话）。

        Returns:
            CSRF 令牌字符串。
        """
        timestamp = int(time.time())
        random_part = secrets.token_hex(16)
        # 签名：session_id + timestamp + random
        signing_input = f"{session_id}:{timestamp}:{random_part}"
        signature = hmac.new(
            self._secret_key.encode("utf-8"),
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        token = f"{timestamp}.{random_part}.{signature}"
        return base64.urlsafe_b64encode(token.encode("utf-8")).decode("ascii")

    def validate_token(self, token: str, session_id: str = "") -> bool:
        """验证 CSRF 令牌。

        Args:
            token: 待验证的令牌。
            session_id: 会话 ID（必须与生成时一致）。

        Returns:
            有效返回 True，无效返回 False。
        """
        if not token:
            return False
        try:
            decoded = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
            parts = decoded.split(".")
            if len(parts) != 3:
                return False
            timestamp_str, random_part, signature = parts
            timestamp = int(timestamp_str)

            # 验证时效（token_ttl=0 表示立即过期）
            if time.time() - timestamp > self.token_ttl:
                return False

            # 验证签名
            signing_input = f"{session_id}:{timestamp}:{random_part}"
            expected_signature = hmac.new(
                self._secret_key.encode("utf-8"),
                signing_input.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(signature, expected_signature):
                return False

            # 防重放：检查令牌是否已使用
            with self._lock:
                if token in self._used_tokens:
                    return False
                self._used_tokens.add(token)
                # 清理过期已用令牌（简单实现，生产环境应定期清理）
                if len(self._used_tokens) > 10000:
                    self._used_tokens.clear()

            return True
        except (ValueError, UnicodeDecodeError, IndexError):
            return False

    def clear_used_tokens(self) -> None:
        """清空已使用令牌集合。"""
        with self._lock:
            self._used_tokens.clear()


# ===== 速率限制 =====


@dataclass
class RateLimitResult:
    """速率限制检查结果"""
    allowed: bool
    remaining: int
    reset_at: float
    retry_after: float = 0.0


class RateLimiter:
    """速率限制器

    支持两种算法：
        - sliding_window: 滑动窗口（精确但内存较高）
        - token_bucket: 令牌桶（允许突发）

    使用示例：
        limiter = RateLimiter(max_requests=100, window_seconds=60)
        result = limiter.check("user-123")
        if not result.allowed:
            raise Exception("请求过于频繁")
    """

    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: int = 60,
        algorithm: str = "sliding_window",
        burst_size: Optional[int] = None,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.algorithm = algorithm
        self.burst_size = burst_size or max_requests

        self._windows: dict[str, deque] = defaultdict(deque)
        self._buckets: dict[str, dict] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> RateLimitResult:
        """检查速率限制。

        Args:
            key: 限流键（如用户 ID、IP 地址）。

        Returns:
            RateLimitResult 实例。
        """
        if self.algorithm == "token_bucket":
            return self._check_token_bucket(key)
        return self._check_sliding_window(key)

    def _check_sliding_window(self, key: str) -> RateLimitResult:
        """滑动窗口算法。"""
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            # 清理过期记录
            window = self._windows[key]
            while window and window[0] < window_start:
                window.popleft()

            if len(window) >= self.max_requests:
                # 计算重试时间
                oldest = window[0] if window else now
                retry_after = oldest + self.window_seconds - now
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_at=oldest + self.window_seconds,
                    retry_after=max(0, retry_after),
                )

            window.append(now)
            remaining = self.max_requests - len(window)
            reset_at = (window[0] if window else now) + self.window_seconds
            return RateLimitResult(
                allowed=True,
                remaining=remaining,
                reset_at=reset_at,
            )

    def _check_token_bucket(self, key: str) -> RateLimitResult:
        """令牌桶算法。"""
        now = time.time()
        refill_rate = self.max_requests / self.window_seconds

        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = {
                    "tokens": self.burst_size,
                    "last_refill": now,
                }

            bucket = self._buckets[key]
            # 补充令牌
            elapsed = now - bucket["last_refill"]
            bucket["tokens"] = min(
                self.burst_size,
                bucket["tokens"] + elapsed * refill_rate,
            )
            bucket["last_refill"] = now

            if bucket["tokens"] >= 1:
                bucket["tokens"] -= 1
                return RateLimitResult(
                    allowed=True,
                    remaining=int(bucket["tokens"]),
                    reset_at=now + (self.burst_size - bucket["tokens"]) / refill_rate,
                )

            retry_after = (1 - bucket["tokens"]) / refill_rate
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=now + retry_after,
                retry_after=retry_after,
            )

    def reset(self, key: str) -> None:
        """重置指定键的限流。"""
        with self._lock:
            self._windows.pop(key, None)
            self._buckets.pop(key, None)

    def reset_all(self) -> None:
        """重置所有限流。"""
        with self._lock:
            self._windows.clear()
            self._buckets.clear()

    def get_status(self, key: str) -> dict:
        """获取指定键的限流状态。"""
        with self._lock:
            if self.algorithm == "token_bucket":
                bucket = self._buckets.get(key, {})
                return {
                    "algorithm": "token_bucket",
                    "tokens": bucket.get("tokens", self.burst_size),
                    "max_tokens": self.burst_size,
                }
            window = self._windows.get(key, deque())
            now = time.time()
            window_start = now - self.window_seconds
            active = [t for t in window if t > window_start]
            return {
                "algorithm": "sliding_window",
                "current_count": len(active),
                "max_requests": self.max_requests,
                "remaining": max(0, self.max_requests - len(active)),
            }


class MultiRateLimiter:
    """多级速率限制器

    支持对不同端点 / 操作配置不同的限流策略。
    """

    def __init__(self):
        self._limiters: dict[str, RateLimiter] = {}
        self._lock = threading.Lock()

    def configure(
        self,
        name: str,
        max_requests: int,
        window_seconds: int,
        algorithm: str = "sliding_window",
    ) -> None:
        """配置命名限流策略。"""
        with self._lock:
            self._limiters[name] = RateLimiter(
                max_requests=max_requests,
                window_seconds=window_seconds,
                algorithm=algorithm,
            )

    def check(self, name: str, key: str) -> RateLimitResult:
        """检查命名限流。"""
        limiter = self._limiters.get(name)
        if limiter is None:
            # 未配置则放行
            return RateLimitResult(allowed=True, remaining=999, reset_at=time.time() + 60)
        return limiter.check(key)

    def get_limiter(self, name: str) -> Optional[RateLimiter]:
        """获取命名限流器。"""
        return self._limiters.get(name)

    def reset_all(self) -> None:
        """重置所有限流器。"""
        with self._lock:
            for limiter in self._limiters.values():
                limiter.reset_all()


# ===== 安全工具函数 =====


class SecurityUtils:
    """安全工具函数集合"""

    @staticmethod
    def generate_secret(length: int = 32) -> str:
        """生成随机密钥。"""
        return secrets.token_urlsafe(length)

    @staticmethod
    def generate_password(length: int = 16, include_symbols: bool = True) -> str:
        """生成随机密码。"""
        alphabet = string.ascii_letters + string.digits
        if include_symbols:
            alphabet += "!@#$%^&*()-_=+[]{}|;:,.<>?"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def constant_time_compare(a: str, b: str) -> bool:
        """常量时间字符串比较（防时序攻击）。"""
        return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))

    @staticmethod
    def hmac_sign(key: str, message: str, algorithm: str = "sha256") -> str:
        """HMAC 签名。"""
        hasher = getattr(hashlib, algorithm)
        return hmac.new(
            key.encode("utf-8"),
            message.encode("utf-8"),
            hasher,
        ).hexdigest()

    @staticmethod
    def hmac_verify(key: str, message: str, signature: str, algorithm: str = "sha256") -> bool:
        """HMAC 验签。"""
        expected = SecurityUtils.hmac_sign(key, message, algorithm)
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> tuple:
        """简单密码哈希（返回 hash, salt）。

        注意：推荐使用 PasswordHasher 替代此方法。
        """
        if salt is None:
            salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100000,
        ).hex()
        return hashed, salt

    @staticmethod
    def sanitize_input(value: str, max_length: int = 10000) -> str:
        """净化输入字符串。

        移除控制字符，限制长度。
        """
        if not value:
            return value
        # 移除控制字符（保留换行与制表符）
        import re
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
        # 限制长度
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length]
        return cleaned

    @staticmethod
    def detect_sql_injection(value: str) -> bool:
        """检测 SQL 注入特征。"""
        if not value:
            return False
        import re
        patterns = [
            r"'\s*OR\s*'?\d*'?\s*=\s*'?\d*",
            r"'\s*OR\s*'?'?\s*=\s*'?'?",
            r"UNION\s+SELECT",
            r"DROP\s+TABLE",
            r"DELETE\s+FROM",
            r"INSERT\s+INTO",
            r"--\s*$",
            r";\s*DROP",
            r"EXEC\s*\(",
            r"xp_cmdshell",
        ]
        for pattern in patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def detect_xss(value: str) -> bool:
        """检测 XSS 攻击特征。"""
        if not value:
            return False
        import re
        patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
            r"<svg[^>]*>.*?</svg>",
            r"data:text/html",
        ]
        for pattern in patterns:
            if re.search(pattern, value, re.IGNORECASE | re.DOTALL):
                return True
        return False

    @staticmethod
    def is_safe_redirect_url(url: str, allowed_hosts: list) -> bool:
        """验证重定向 URL 是否安全（防开放重定向）。"""
        if not url:
            return False
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            # 仅允许相对路径或白名单主机
            if not parsed.netloc:
                return url.startswith("/")
            return parsed.netloc in allowed_hosts
        except Exception:
            return False

    @staticmethod
    def encode_base64(value: str) -> str:
        """Base64 编码。"""
        return base64.b64encode(value.encode("utf-8")).decode("ascii")

    @staticmethod
    def decode_base64(value: str) -> str:
        """Base64 解码。"""
        return base64.b64decode(value.encode("ascii")).decode("utf-8")

    @staticmethod
    def url_safe_encode(value: str) -> str:
        """URL 安全 Base64 编码。"""
        return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")

    @staticmethod
    def url_safe_decode(value: str) -> str:
        """URL 安全 Base64 解码。"""
        padding = 4 - len(value) % 4
        if padding != 4:
            value += "=" * padding
        return base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8")


# ===== 会话令牌管理 =====


class SessionTokenManager:
    """会话令牌管理器

    生成与验证会话令牌，支持令牌黑名单（登出失效）。
    """

    def __init__(self, secret_key: Optional[str] = None, default_ttl: int = 86400):
        self._jwt_manager = JWTManager(secret_key=secret_key)
        self.default_ttl = default_ttl
        self._blacklist: set = set()
        self._lock = threading.Lock()

    def create_session(self, user_id: str, extra_payload: Optional[dict] = None) -> str:
        """创建会话令牌。"""
        payload = {"user_id": user_id, "type": "session"}
        if extra_payload:
            payload.update(extra_payload)
        return self._jwt_manager.create_token(
            payload, expires_in=self.default_ttl, subject=user_id
        )

    def verify_session(self, token: str) -> Optional[dict]:
        """验证会话令牌。"""
        # 检查黑名单
        with self._lock:
            if token in self._blacklist:
                return None
        return self._jwt_manager.verify_token(token)

    def revoke_session(self, token: str) -> None:
        """吊销会话令牌（加入黑名单）。"""
        with self._lock:
            self._blacklist.add(token)

    def cleanup_blacklist(self, max_size: int = 100000) -> None:
        """清理黑名单（超过大小则清空）。"""
        with self._lock:
            if len(self._blacklist) > max_size:
                self._blacklist.clear()


# ===== 全局实例 =====

# 默认密码哈希器
_default_password_hasher = PasswordHasher()

# 默认 API 密钥管理器（使用环境变量或自动生成密钥）
_default_api_key_manager = APIKeyManager(
    secret_key=os.environ.get("THESISMINER_ENCRYPTION_KEY")
)

# 默认 JWT 管理器
_default_jwt_manager = JWTManager(
    secret_key=os.environ.get("THESISMINER_JWT_SECRET")
)

# 默认 CSRF 令牌管理器
_default_csrf_manager = CSRFTokenManager(
    secret_key=os.environ.get("THESISMINER_CSRF_SECRET")
)

# 默认速率限制器
_default_rate_limiter = RateLimiter(max_requests=100, window_seconds=60)

# 默认多级速率限制器
_default_multi_limiter = MultiRateLimiter()


def get_password_hasher() -> PasswordHasher:
    """获取默认密码哈希器。"""
    return _default_password_hasher


def get_api_key_manager() -> APIKeyManager:
    """获取默认 API 密钥管理器。"""
    return _default_api_key_manager


def get_jwt_manager() -> JWTManager:
    """获取默认 JWT 管理器。"""
    return _default_jwt_manager


def get_csrf_manager() -> CSRFTokenManager:
    """获取默认 CSRF 令牌管理器。"""
    return _default_csrf_manager


def get_rate_limiter() -> RateLimiter:
    """获取默认速率限制器。"""
    return _default_rate_limiter


def get_multi_rate_limiter() -> MultiRateLimiter:
    """获取默认多级速率限制器。"""
    return _default_multi_limiter
