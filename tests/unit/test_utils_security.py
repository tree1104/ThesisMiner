"""security 模块单元测试

覆盖 backend/utils/security.py 中的所有组件：
- PasswordHasher: 密码哈希（PBKDF2-HMAC-SHA256/哈希/验证/重新哈希判断）
- APIKeyManager: API 密钥管理（加密/解密/生成/脱敏/格式验证）
- JWTManager: JWT 令牌（签发/验证/刷新/不安全解码）
- CSRFTokenManager: CSRF 令牌（生成/验证/防重放/清理）
- RateLimiter: 速率限制（滑动窗口/令牌桶/重置/状态）
- MultiRateLimiter: 多级速率限制（配置/检查/重置）
- SecurityUtils: 安全工具函数（密钥生成/密码生成/常量时间比较/HMAC/输入净化/SQL注入检测/XSS检测/安全重定向/Base64）
- SessionTokenManager: 会话令牌管理（创建/验证/吊销/黑名单清理）
- 全局实例获取函数
"""
import time
import threading
from unittest.mock import patch

import pytest

from backend.utils.security import (
    PasswordHasher,
    APIKeyManager,
    JWTManager,
    CSRFTokenManager,
    RateLimiter,
    MultiRateLimiter,
    RateLimitResult,
    SecurityUtils,
    SessionTokenManager,
    get_password_hasher,
    get_api_key_manager,
    get_jwt_manager,
    get_csrf_manager,
    get_rate_limiter,
    get_multi_rate_limiter,
)


# ===== PasswordHasher 测试 =====


class TestPasswordHasher:
    """PasswordHasher 密码哈希器测试"""

    def test_hash_returns_string(self):
        """哈希返回字符串"""
        hasher = PasswordHasher(iterations=1000)  # 低迭代数加速测试
        result = hasher.hash("mypassword")
        assert isinstance(result, str)

    def test_hash_format(self):
        """哈希格式"""
        hasher = PasswordHasher(iterations=1000)
        result = hasher.hash("mypassword")
        parts = result.split("$")
        assert len(parts) == 4
        assert parts[0] == "pbkdf2"
        assert parts[1] == "1000"
        # salt 和 hash 是十六进制字符串
        assert len(parts[2]) > 0
        assert len(parts[3]) > 0

    def test_hash_different_passwords(self):
        """不同密码不同哈希"""
        hasher = PasswordHasher(iterations=1000)
        h1 = hasher.hash("password1")
        h2 = hasher.hash("password2")
        assert h1 != h2

    def test_hash_same_password_different_salt(self):
        """相同密码不同盐"""
        hasher = PasswordHasher(iterations=1000)
        h1 = hasher.hash("mypassword")
        h2 = hasher.hash("mypassword")
        assert h1 != h2  # 盐不同

    def test_verify_correct_password(self):
        """验证正确密码"""
        hasher = PasswordHasher(iterations=1000)
        hashed = hasher.hash("mypassword")
        assert hasher.verify("mypassword", hashed) is True

    def test_verify_wrong_password(self):
        """验证错误密码"""
        hasher = PasswordHasher(iterations=1000)
        hashed = hasher.hash("mypassword")
        assert hasher.verify("wrongpassword", hashed) is False

    def test_verify_empty_password(self):
        """验证空密码"""
        hasher = PasswordHasher(iterations=1000)
        assert hasher.verify("", "somehash") is False

    def test_verify_empty_hash(self):
        """验证空哈希"""
        hasher = PasswordHasher(iterations=1000)
        assert hasher.verify("password", "") is False

    def test_hash_empty_password_raises(self):
        """空密码哈希抛出异常"""
        hasher = PasswordHasher(iterations=1000)
        with pytest.raises(ValueError):
            hasher.hash("")

    def test_verify_invalid_hash_format(self):
        """验证无效哈希格式"""
        hasher = PasswordHasher(iterations=1000)
        assert hasher.verify("password", "invalid_hash") is False

    def test_verify_wrong_algorithm(self):
        """验证错误算法"""
        hasher = PasswordHasher(iterations=1000)
        assert hasher.verify("password", "bcrypt$1000$salt$hash") is False

    def test_verify_corrupted_hash(self):
        """验证损坏的哈希"""
        hasher = PasswordHasher(iterations=1000)
        assert hasher.verify("password", "pbkdf2$1000$not_hex$alsonot_hex") is False

    def test_needs_rehash_low_iterations(self):
        """需要重新哈希（迭代数低）"""
        hasher = PasswordHasher(iterations=100000)
        old_hash = PasswordHasher(iterations=1000).hash("password")
        assert hasher.needs_rehash(old_hash) is True

    def test_needs_rehash_sufficient_iterations(self):
        """不需要重新哈希"""
        hasher = PasswordHasher(iterations=1000)
        hashed = hasher.hash("password")
        assert hasher.needs_rehash(hashed) is False

    def test_needs_rehash_custom_threshold(self):
        """自定义阈值"""
        hasher = PasswordHasher(iterations=100000)
        hashed = hasher.hash("password")
        assert hasher.needs_rehash(hashed, min_iterations=200000) is True

    def test_needs_rehash_empty(self):
        """空哈希需要重新哈希"""
        hasher = PasswordHasher(iterations=1000)
        assert hasher.needs_rehash("") is True

    def test_needs_rehash_invalid_format(self):
        """无效格式需要重新哈希"""
        hasher = PasswordHasher(iterations=1000)
        assert hasher.needs_rehash("invalid") is True

    def test_default_iterations(self):
        """默认迭代数"""
        hasher = PasswordHasher()
        assert hasher.iterations == 100000

    def test_custom_iterations(self):
        """自定义迭代数"""
        hasher = PasswordHasher(iterations=50000)
        assert hasher.iterations == 50000


# ===== APIKeyManager 测试 =====


class TestAPIKeyManager:
    """APIKeyManager API 密钥管理器测试"""

    def test_encrypt_decrypt_roundtrip(self):
        """加密解密往返"""
        manager = APIKeyManager(secret_key="test-secret-key")
        plaintext = "sk-abcdef123456"
        encrypted = manager.encrypt(plaintext)
        decrypted = manager.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_returns_different_ciphertext(self):
        """相同明文不同密文（IV 随机）"""
        manager = APIKeyManager(secret_key="test-secret-key")
        plaintext = "sk-test"
        e1 = manager.encrypt(plaintext)
        e2 = manager.encrypt(plaintext)
        assert e1 != e2

    def test_encrypt_empty(self):
        """空明文加密"""
        manager = APIKeyManager(secret_key="test-secret-key")
        assert manager.encrypt("") == ""

    def test_decrypt_empty(self):
        """空密文解密"""
        manager = APIKeyManager(secret_key="test-secret-key")
        assert manager.decrypt("") == ""

    def test_decrypt_invalid_ciphertext(self):
        """无效密文解密"""
        manager = APIKeyManager(secret_key="test-secret-key")
        with pytest.raises(ValueError):
            manager.decrypt("invalid_ciphertext")

    def test_decrypt_wrong_key(self):
        """错误密钥解密"""
        manager1 = APIKeyManager(secret_key="key1")
        manager2 = APIKeyManager(secret_key="key2")
        encrypted = manager1.encrypt("secret")
        with pytest.raises(ValueError):
            manager2.decrypt(encrypted)

    def test_decrypt_tampered_ciphertext(self):
        """篡改的密文解密"""
        manager = APIKeyManager(secret_key="test-secret-key")
        encrypted = manager.encrypt("secret")
        # 篡改密文
        tampered = encrypted[:-5] + "AAAAA"
        with pytest.raises(ValueError):
            manager.decrypt(tampered)

    def test_generate_api_key(self):
        """生成 API 密钥"""
        manager = APIKeyManager()
        key = manager.generate_api_key()
        assert key.startswith("sk-")

    def test_generate_api_key_custom_prefix(self):
        """自定义前缀"""
        manager = APIKeyManager()
        key = manager.generate_api_key(prefix="pk")
        assert key.startswith("pk-")

    def test_generate_api_key_custom_length(self):
        """自定义长度"""
        manager = APIKeyManager()
        key = manager.generate_api_key(length=64)
        assert len(key) > 64  # prefix + token

    def test_mask_api_key(self):
        """脱敏 API 密钥"""
        manager = APIKeyManager()
        key = "sk-abcdefghijklmnopqrstuvwxyz123456"
        masked = manager.mask_api_key(key)
        assert masked.startswith("sk-a")
        assert masked.endswith("3456")
        assert "*" in masked

    def test_mask_api_key_short(self):
        """短密钥全掩码"""
        manager = APIKeyManager()
        masked = manager.mask_api_key("short")
        assert masked == "*****"

    def test_mask_api_key_empty(self):
        """空密钥"""
        manager = APIKeyManager()
        assert manager.mask_api_key("") == ""

    def test_mask_api_key_custom_visible(self):
        """自定义可见字符数"""
        manager = APIKeyManager()
        key = "sk-abcdefghijklmnopqrstuvwxyz"
        masked = manager.mask_api_key(key, visible_start=2, visible_end=2)
        assert masked.startswith("sk")
        assert masked.endswith("yz")

    def test_is_valid_format_valid(self):
        """有效格式"""
        manager = APIKeyManager()
        assert manager.is_valid_format("sk-abcdef123456") is True

    def test_is_valid_format_short(self):
        """太短"""
        manager = APIKeyManager()
        assert manager.is_valid_format("short") is False

    def test_is_valid_format_empty(self):
        """空"""
        manager = APIKeyManager()
        assert manager.is_valid_format("") is False

    def test_is_valid_format_special_chars(self):
        """特殊字符"""
        manager = APIKeyManager()
        assert manager.is_valid_format("sk-abc!@#def") is False

    def test_is_valid_format_with_underscore_hyphen(self):
        """下划线连字符"""
        manager = APIKeyManager()
        assert manager.is_valid_format("sk-abc_def-123") is True

    def test_auto_generate_secret_key(self):
        """自动生成密钥"""
        manager = APIKeyManager()
        assert manager._secret_key is not None
        assert len(manager._secret_key) > 0

    def test_custom_secret_key(self):
        """自定义密钥"""
        manager = APIKeyManager(secret_key="my-custom-secret")
        assert manager._secret_key == "my-custom-secret"


# ===== JWTManager 测试 =====


class TestJWTManager:
    """JWTManager JWT 令牌管理器测试"""

    def test_create_token(self):
        """签发令牌"""
        manager = JWTManager(secret_key="test-secret")
        token = manager.create_token({"user_id": "123"})
        assert isinstance(token, str)
        assert token.count(".") == 2  # JWT 三段式

    def test_verify_token_valid(self):
        """验证有效令牌"""
        manager = JWTManager(secret_key="test-secret")
        token = manager.create_token({"user_id": "123"})
        payload = manager.verify_token(token)
        assert payload is not None
        assert payload["user_id"] == "123"

    def test_verify_token_invalid_signature(self):
        """验证错误签名"""
        manager1 = JWTManager(secret_key="secret1")
        manager2 = JWTManager(secret_key="secret2")
        token = manager1.create_token({"user_id": "123"})
        assert manager2.verify_token(token) is None

    def test_verify_token_expired(self):
        """验证过期令牌"""
        manager = JWTManager(secret_key="test-secret")
        token = manager.create_token({"user_id": "123"}, expires_in=-1)
        assert manager.verify_token(token) is None

    def test_verify_token_skip_exp(self):
        """跳过过期验证"""
        manager = JWTManager(secret_key="test-secret")
        token = manager.create_token({"user_id": "123"}, expires_in=-1)
        payload = manager.verify_token(token, verify_exp=False)
        assert payload is not None
        assert payload["user_id"] == "123"

    def test_verify_token_empty(self):
        """验证空令牌"""
        manager = JWTManager(secret_key="test-secret")
        assert manager.verify_token("") is None

    def test_verify_token_malformed(self):
        """验证格式错误令牌"""
        manager = JWTManager(secret_key="test-secret")
        assert manager.verify_token("not.a.jwt.token") is None
        assert manager.verify_token("onlyonepart") is None
        assert manager.verify_token("two.parts") is None

    def test_token_contains_standard_claims(self):
        """令牌包含标准声明"""
        manager = JWTManager(secret_key="test-secret", issuer="test-issuer")
        token = manager.create_token({"user_id": "123"})
        payload = manager.verify_token(token)
        assert payload is not None
        assert "iss" in payload
        assert "iat" in payload
        assert "exp" in payload
        assert payload["iss"] == "test-issuer"

    def test_token_with_subject(self):
        """带主题"""
        manager = JWTManager(secret_key="test-secret")
        token = manager.create_token({"data": "value"}, subject="user-123")
        payload = manager.verify_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"

    def test_token_with_audience(self):
        """带受众"""
        manager = JWTManager(secret_key="test-secret")
        token = manager.create_token({"data": "value"}, audience="my-app")
        payload = manager.verify_token(token)
        assert payload is not None
        assert payload["aud"] == "my-app"

    def test_refresh_token(self):
        """刷新令牌"""
        manager = JWTManager(secret_key="test-secret")
        token = manager.create_token({"user_id": "123"}, expires_in=3600)
        new_token = manager.refresh_token(token)
        assert new_token is not None
        payload = manager.verify_token(new_token)
        assert payload is not None
        assert payload["user_id"] == "123"

    def test_refresh_expired_token(self):
        """刷新过期令牌"""
        manager = JWTManager(secret_key="test-secret")
        token = manager.create_token({"user_id": "123"}, expires_in=-1)
        new_token = manager.refresh_token(token)
        assert new_token is not None  # 刷新不验证过期

    def test_refresh_invalid_token(self):
        """刷新无效令牌"""
        manager = JWTManager(secret_key="test-secret")
        assert manager.refresh_token("invalid") is None

    def test_decode_token_unsafe(self):
        """不安全解码"""
        manager = JWTManager(secret_key="test-secret")
        token = manager.create_token({"user_id": "123"})
        payload = manager.decode_token_unsafe(token)
        assert payload is not None
        assert payload["user_id"] == "123"

    def test_decode_token_unsafe_invalid(self):
        """不安全解码无效令牌"""
        manager = JWTManager(secret_key="test-secret")
        assert manager.decode_token_unsafe("invalid") is None
        assert manager.decode_token_unsafe("") is None

    def test_decode_token_unsafe_wrong_signature(self):
        """不安全解码不验证签名"""
        manager1 = JWTManager(secret_key="secret1")
        manager2 = JWTManager(secret_key="secret2")
        token = manager1.create_token({"user_id": "123"})
        # 不安全解码不验证签名，应成功
        payload = manager2.decode_token_unsafe(token)
        assert payload is not None
        assert payload["user_id"] == "123"

    def test_default_issuer(self):
        """默认签发者"""
        manager = JWTManager(secret_key="test-secret")
        assert manager.issuer == "thesisminer"

    def test_custom_issuer(self):
        """自定义签发者"""
        manager = JWTManager(secret_key="test-secret", issuer="custom-issuer")
        assert manager.issuer == "custom-issuer"


# ===== CSRFTokenManager 测试 =====


class TestCSRFTokenManager:
    """CSRFTokenManager CSRF 令牌管理器测试"""

    def test_generate_token(self):
        """生成令牌"""
        manager = CSRFTokenManager(secret_key="test-secret")
        token = manager.generate_token()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_token_with_session(self):
        """带会话 ID 生成令牌"""
        manager = CSRFTokenManager(secret_key="test-secret")
        token = manager.generate_token(session_id="sess-123")
        assert isinstance(token, str)

    def test_validate_token_valid(self):
        """验证有效令牌"""
        manager = CSRFTokenManager(secret_key="test-secret")
        token = manager.generate_token(session_id="sess-123")
        assert manager.validate_token(token, session_id="sess-123") is True

    def test_validate_token_wrong_session(self):
        """验证错误会话"""
        manager = CSRFTokenManager(secret_key="test-secret")
        token = manager.generate_token(session_id="sess-123")
        assert manager.validate_token(token, session_id="wrong-session") is False

    def test_validate_token_empty(self):
        """验证空令牌"""
        manager = CSRFTokenManager(secret_key="test-secret")
        assert manager.validate_token("") is False

    def test_validate_token_invalid(self):
        """验证无效令牌"""
        manager = CSRFTokenManager(secret_key="test-secret")
        assert manager.validate_token("invalid-token") is False

    def test_validate_token_replay(self):
        """防重放攻击"""
        manager = CSRFTokenManager(secret_key="test-secret")
        token = manager.generate_token(session_id="sess-123")
        # 第一次验证成功
        assert manager.validate_token(token, session_id="sess-123") is True
        # 第二次验证应失败（已使用）
        assert manager.validate_token(token, session_id="sess-123") is False

    def test_token_ttl_expiration(self):
        """令牌过期"""
        manager = CSRFTokenManager(secret_key="test-secret", token_ttl=0)
        token = manager.generate_token(session_id="sess-123")
        time.sleep(0.01)
        assert manager.validate_token(token, session_id="sess-123") is False

    def test_clear_used_tokens(self):
        """清理已使用令牌"""
        manager = CSRFTokenManager(secret_key="test-secret")
        token = manager.generate_token(session_id="sess-123")
        manager.validate_token(token, session_id="sess-123")
        manager.clear_used_tokens()
        assert len(manager._used_tokens) == 0

    def test_different_tokens(self):
        """不同令牌"""
        manager = CSRFTokenManager(secret_key="test-secret")
        t1 = manager.generate_token()
        t2 = manager.generate_token()
        assert t1 != t2


# ===== RateLimiter 测试 =====


class TestRateLimiter:
    """RateLimiter 速率限制器测试"""

    def test_check_allowed(self):
        """允许请求"""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        result = limiter.check("user-1")
        assert result.allowed is True
        assert result.remaining == 9

    def test_check_blocked(self):
        """阻止请求"""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.check("user-1")
        limiter.check("user-1")
        result = limiter.check("user-1")
        assert result.allowed is False
        assert result.remaining == 0

    def test_different_keys_independent(self):
        """不同键独立限流"""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.check("user-1")
        limiter.check("user-1")
        result = limiter.check("user-2")
        assert result.allowed is True

    def test_reset(self):
        """重置"""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.check("user-1")
        limiter.check("user-1")
        limiter.reset("user-1")
        result = limiter.check("user-1")
        assert result.allowed is True

    def test_reset_all(self):
        """重置所有"""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.check("user-1")
        limiter.check("user-2")
        limiter.reset_all()
        assert limiter.check("user-1").allowed is True
        assert limiter.check("user-2").allowed is True

    def test_get_status(self):
        """获取状态"""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        limiter.check("user-1")
        status = limiter.get_status("user-1")
        assert status["algorithm"] == "sliding_window"
        assert status["current_count"] == 1
        assert status["remaining"] == 9

    def test_token_bucket_algorithm(self):
        """令牌桶算法"""
        limiter = RateLimiter(
            max_requests=10,
            window_seconds=60,
            algorithm="token_bucket",
            burst_size=5,
        )
        result = limiter.check("user-1")
        assert result.allowed is True

    def test_token_bucket_burst(self):
        """令牌桶突发"""
        limiter = RateLimiter(
            max_requests=10,
            window_seconds=60,
            algorithm="token_bucket",
            burst_size=3,
        )
        results = [limiter.check("user-1") for _ in range(5)]
        allowed = sum(1 for r in results if r.allowed)
        # 突发大小为 3，应允许 3 个
        assert allowed == 3

    def test_rate_limit_result_dataclass(self):
        """RateLimitResult 数据类"""
        result = RateLimitResult(
            allowed=True,
            remaining=5,
            reset_at=time.time() + 60,
        )
        assert result.allowed is True
        assert result.remaining == 5
        assert result.retry_after == 0.0

    def test_retry_after_when_blocked(self):
        """被阻止时返回重试时间"""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        limiter.check("user-1")
        result = limiter.check("user-1")
        assert result.allowed is False
        assert result.retry_after > 0

    def test_remaining_decreases(self):
        """剩余数递减"""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        r1 = limiter.check("user-1")
        r2 = limiter.check("user-1")
        assert r1.remaining == 4
        assert r2.remaining == 3


# ===== MultiRateLimiter 测试 =====


class TestMultiRateLimiter:
    """MultiRateLimiter 多级速率限制器测试"""

    def test_configure(self):
        """配置限流策略"""
        limiter = MultiRateLimiter()
        limiter.configure("api", max_requests=100, window_seconds=60)
        assert limiter.get_limiter("api") is not None

    def test_check_configured(self):
        """检查已配置策略"""
        limiter = MultiRateLimiter()
        limiter.configure("api", max_requests=10, window_seconds=60)
        result = limiter.check("api", "user-1")
        assert result.allowed is True

    def test_check_unconfigured(self):
        """检查未配置策略（放行）"""
        limiter = MultiRateLimiter()
        result = limiter.check("unknown", "user-1")
        assert result.allowed is True

    def test_get_limiter_nonexistent(self):
        """获取不存在的限流器"""
        limiter = MultiRateLimiter()
        assert limiter.get_limiter("nonexistent") is None

    def test_reset_all(self):
        """重置所有"""
        limiter = MultiRateLimiter()
        limiter.configure("api", max_requests=1, window_seconds=60)
        limiter.check("api", "user-1")
        limiter.reset_all()
        assert limiter.check("api", "user-1").allowed is True

    def test_multiple_strategies(self):
        """多策略独立"""
        limiter = MultiRateLimiter()
        limiter.configure("api", max_requests=2, window_seconds=60)
        limiter.configure("auth", max_requests=5, window_seconds=60)
        # API 策略
        limiter.check("api", "user-1")
        limiter.check("api", "user-1")
        assert limiter.check("api", "user-1").allowed is False
        # Auth 策略独立
        assert limiter.check("auth", "user-1").allowed is True


# ===== SecurityUtils 测试 =====


class TestSecurityUtils:
    """SecurityUtils 安全工具函数测试"""

    def test_generate_secret(self):
        """生成随机密钥"""
        secret = SecurityUtils.generate_secret()
        assert isinstance(secret, str)
        assert len(secret) > 0

    def test_generate_secret_custom_length(self):
        """自定义长度密钥"""
        secret = SecurityUtils.generate_secret(length=64)
        assert len(secret) > 0

    def test_generate_password(self):
        """生成密码"""
        password = SecurityUtils.generate_password()
        assert isinstance(password, str)
        assert len(password) == 16

    def test_generate_password_custom_length(self):
        """自定义长度密码"""
        password = SecurityUtils.generate_password(length=32)
        assert len(password) == 32

    def test_generate_password_no_symbols(self):
        """无符号密码"""
        password = SecurityUtils.generate_password(include_symbols=False)
        assert len(password) == 16

    def test_constant_time_compare_equal(self):
        """常量时间比较相等"""
        assert SecurityUtils.constant_time_compare("hello", "hello") is True

    def test_constant_time_compare_different(self):
        """常量时间比较不等"""
        assert SecurityUtils.constant_time_compare("hello", "world") is False

    def test_hmac_sign(self):
        """HMAC 签名"""
        sig = SecurityUtils.hmac_sign("key", "message")
        assert isinstance(sig, str)
        assert len(sig) > 0

    def test_hmac_verify_valid(self):
        """HMAC 验签有效"""
        sig = SecurityUtils.hmac_sign("key", "message")
        assert SecurityUtils.hmac_verify("key", "message", sig) is True

    def test_hmac_verify_invalid(self):
        """HMAC 验签无效"""
        sig = SecurityUtils.hmac_sign("key", "message")
        assert SecurityUtils.hmac_verify("key", "wrong", sig) is False

    def test_hmac_verify_wrong_key(self):
        """HMAC 错误密钥"""
        sig = SecurityUtils.hmac_sign("key1", "message")
        assert SecurityUtils.hmac_verify("key2", "message", sig) is False

    def test_hash_password(self):
        """简单密码哈希"""
        hashed, salt = SecurityUtils.hash_password("mypassword")
        assert isinstance(hashed, str)
        assert isinstance(salt, str)
        assert len(hashed) > 0
        assert len(salt) > 0

    def test_hash_password_with_salt(self):
        """带盐密码哈希"""
        salt = "mysalt"
        hashed, returned_salt = SecurityUtils.hash_password("password", salt=salt)
        assert returned_salt == salt

    def test_hash_password_consistent(self):
        """密码哈希一致"""
        h1, salt = SecurityUtils.hash_password("password")
        h2, _ = SecurityUtils.hash_password("password", salt=salt)
        assert h1 == h2

    def test_sanitize_input(self):
        """净化输入"""
        text = "hello\x00world\x01"
        result = SecurityUtils.sanitize_input(text)
        assert "\x00" not in result
        assert "\x01" not in result
        assert "hello" in result
        assert "world" in result

    def test_sanitize_input_max_length(self):
        """净化输入长度限制"""
        text = "a" * 20000
        result = SecurityUtils.sanitize_input(text, max_length=1000)
        assert len(result) == 1000

    def test_sanitize_input_empty(self):
        """净化空输入"""
        assert SecurityUtils.sanitize_input("") == ""

    def test_sanitize_input_preserves_newlines(self):
        """保留换行符"""
        text = "line1\nline2\ttab"
        result = SecurityUtils.sanitize_input(text)
        assert "\n" in result
        assert "\t" in result

    def test_detect_sql_injection_safe(self):
        """检测安全输入"""
        assert SecurityUtils.detect_sql_injection("normal text") is False

    def test_detect_sql_injection_or(self):
        """检测 OR 注入"""
        assert SecurityUtils.detect_sql_injection("' OR '1'='1") is True

    def test_detect_sql_injection_union(self):
        """检测 UNION 注入"""
        assert SecurityUtils.detect_sql_injection("UNION SELECT * FROM users") is True

    def test_detect_sql_injection_drop(self):
        """检测 DROP 注入"""
        assert SecurityUtils.detect_sql_injection("DROP TABLE users") is True

    def test_detect_sql_injection_delete(self):
        """检测 DELETE 注入"""
        assert SecurityUtils.detect_sql_injection("DELETE FROM users") is True

    def test_detect_sql_injection_insert(self):
        """检测 INSERT 注入"""
        assert SecurityUtils.detect_sql_injection("INSERT INTO users VALUES") is True

    def test_detect_sql_injection_empty(self):
        """空输入"""
        assert SecurityUtils.detect_sql_injection("") is False

    def test_detect_xss_safe(self):
        """检测安全输入"""
        assert SecurityUtils.detect_xss("normal text") is False

    def test_detect_xss_script_tag(self):
        """检测 script 标签"""
        assert SecurityUtils.detect_xss("<script>alert('xss')</script>") is True

    def test_detect_xss_javascript_protocol(self):
        """检测 javascript 协议"""
        assert SecurityUtils.detect_xss("javascript:alert(1)") is True

    def test_detect_xss_event_handler(self):
        """检测事件处理器"""
        assert SecurityUtils.detect_xss("onclick=alert(1)") is True

    def test_detect_xss_iframe(self):
        """检测 iframe"""
        assert SecurityUtils.detect_xss("<iframe src='evil'></iframe>") is True

    def test_detect_xss_empty(self):
        """空输入"""
        assert SecurityUtils.detect_xss("") is False

    def test_is_safe_redirect_url_relative(self):
        """安全相对路径重定向"""
        assert SecurityUtils.is_safe_redirect_url("/path", []) is True

    def test_is_safe_redirect_url_allowed_host(self):
        """允许的主机"""
        assert SecurityUtils.is_safe_redirect_url("https://example.com/path", ["example.com"]) is True

    def test_is_safe_redirect_url_disallowed_host(self):
        """不允许的主机"""
        assert SecurityUtils.is_safe_redirect_url("https://evil.com/path", ["example.com"]) is False

    def test_is_safe_redirect_url_empty(self):
        """空 URL"""
        assert SecurityUtils.is_safe_redirect_url("", []) is False

    def test_encode_base64(self):
        """Base64 编码"""
        result = SecurityUtils.encode_base64("hello")
        assert isinstance(result, str)

    def test_decode_base64(self):
        """Base64 解码"""
        encoded = SecurityUtils.encode_base64("hello")
        assert SecurityUtils.decode_base64(encoded) == "hello"

    def test_url_safe_encode(self):
        """URL 安全编码"""
        result = SecurityUtils.url_safe_encode("hello world")
        assert isinstance(result, str)
        assert " " not in result

    def test_url_safe_decode(self):
        """URL 安全解码"""
        encoded = SecurityUtils.url_safe_encode("hello world")
        assert SecurityUtils.url_safe_decode(encoded) == "hello world"


# ===== SessionTokenManager 测试 =====


class TestSessionTokenManager:
    """SessionTokenManager 会话令牌管理器测试"""

    def test_create_session(self):
        """创建会话"""
        manager = SessionTokenManager(secret_key="test-secret")
        token = manager.create_session("user-123")
        assert isinstance(token, str)
        assert token.count(".") == 2

    def test_verify_session_valid(self):
        """验证有效会话"""
        manager = SessionTokenManager(secret_key="test-secret")
        token = manager.create_session("user-123")
        payload = manager.verify_session(token)
        assert payload is not None
        assert payload["user_id"] == "user-123"

    def test_verify_session_invalid(self):
        """验证无效会话"""
        manager = SessionTokenManager(secret_key="test-secret")
        assert manager.verify_session("invalid-token") is None

    def test_verify_session_revoked(self):
        """验证已吊销会话"""
        manager = SessionTokenManager(secret_key="test-secret")
        token = manager.create_session("user-123")
        manager.revoke_session(token)
        assert manager.verify_session(token) is None

    def test_revoke_session(self):
        """吊销会话"""
        manager = SessionTokenManager(secret_key="test-secret")
        token = manager.create_session("user-123")
        manager.revoke_session(token)
        assert token in manager._blacklist

    def test_create_session_with_extra_payload(self):
        """带额外负载创建会话"""
        manager = SessionTokenManager(secret_key="test-secret")
        token = manager.create_session("user-123", extra_payload={"role": "admin"})
        payload = manager.verify_session(token)
        assert payload is not None
        assert payload["role"] == "admin"

    def test_cleanup_blacklist(self):
        """清理黑名单"""
        manager = SessionTokenManager(secret_key="test-secret")
        # 添加令牌到黑名单
        for i in range(10):
            manager.revoke_session(f"token-{i}")
        manager.cleanup_blacklist(max_size=5)
        assert len(manager._blacklist) == 0

    def test_default_ttl(self):
        """默认 TTL"""
        manager = SessionTokenManager(secret_key="test-secret")
        assert manager.default_ttl == 86400

    def test_custom_ttl(self):
        """自定义 TTL"""
        manager = SessionTokenManager(secret_key="test-secret", default_ttl=3600)
        assert manager.default_ttl == 3600


# ===== 全局实例测试 =====


class TestGlobalInstances:
    """全局实例获取函数测试"""

    def test_get_password_hasher(self):
        """获取密码哈希器"""
        hasher = get_password_hasher()
        assert isinstance(hasher, PasswordHasher)

    def test_get_api_key_manager(self):
        """获取 API 密钥管理器"""
        manager = get_api_key_manager()
        assert isinstance(manager, APIKeyManager)

    def test_get_jwt_manager(self):
        """获取 JWT 管理器"""
        manager = get_jwt_manager()
        assert isinstance(manager, JWTManager)

    def test_get_csrf_manager(self):
        """获取 CSRF 管理器"""
        manager = get_csrf_manager()
        assert isinstance(manager, CSRFTokenManager)

    def test_get_rate_limiter(self):
        """获取速率限制器"""
        limiter = get_rate_limiter()
        assert isinstance(limiter, RateLimiter)

    def test_get_multi_rate_limiter(self):
        """获取多级速率限制器"""
        limiter = get_multi_rate_limiter()
        assert isinstance(limiter, MultiRateLimiter)

    def test_singleton_instances(self):
        """单例"""
        assert get_password_hasher() is get_password_hasher()
        assert get_jwt_manager() is get_jwt_manager()


# ===== 集成测试 =====


class TestIntegration:
    """集成测试"""

    def test_password_hash_verify_workflow(self):
        """密码哈希验证工作流"""
        hasher = PasswordHasher(iterations=1000)
        password = "MySecurePassword123!"
        hashed = hasher.hash(password)
        assert hasher.verify(password, hashed) is True
        assert hasher.verify("wrong", hashed) is False

    def test_jwt_full_workflow(self):
        """JWT 完整工作流"""
        manager = JWTManager(secret_key="integration-secret")
        # 创建令牌
        token = manager.create_token(
            {"user_id": "123", "role": "admin"},
            expires_in=3600,
            subject="user-123",
        )
        # 验证令牌
        payload = manager.verify_token(token)
        assert payload is not None
        assert payload["user_id"] == "123"
        # 刷新令牌
        new_token = manager.refresh_token(token)
        assert new_token is not None
        new_payload = manager.verify_token(new_token)
        assert new_payload["user_id"] == "123"

    def test_csrf_protection_workflow(self):
        """CSRF 保护工作流"""
        manager = CSRFTokenManager(secret_key="csrf-secret")
        session_id = "sess-123"
        # 生成令牌
        token = manager.generate_token(session_id=session_id)
        # 验证令牌
        assert manager.validate_token(token, session_id=session_id) is True
        # 重放攻击被阻止
        assert manager.validate_token(token, session_id=session_id) is False

    def test_rate_limiting_workflow(self):
        """速率限制工作流"""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        # 前 5 个请求允许
        for i in range(5):
            result = limiter.check("user-1")
            assert result.allowed is True
        # 第 6 个请求被阻止
        result = limiter.check("user-1")
        assert result.allowed is False

    def test_api_key_encryption_workflow(self):
        """API 密钥加密工作流"""
        manager = APIKeyManager(secret_key="encryption-secret")
        # 生成密钥
        api_key = manager.generate_api_key()
        # 加密
        encrypted = manager.encrypt(api_key)
        # 脱敏
        masked = manager.mask_api_key(api_key)
        # 解密
        decrypted = manager.decrypt(encrypted)
        assert decrypted == api_key
        assert masked != api_key

    def test_session_management_workflow(self):
        """会话管理工作流"""
        manager = SessionTokenManager(secret_key="session-secret")
        # 创建会话
        token = manager.create_session("user-123", extra_payload={"role": "user"})
        # 验证会话
        payload = manager.verify_session(token)
        assert payload is not None
        # 吊销会话
        manager.revoke_session(token)
        # 验证已吊销
        assert manager.verify_session(token) is None

    def test_security_utils_input_validation(self):
        """安全工具输入验证"""
        # 安全输入
        safe_input = "normal user input"
        assert SecurityUtils.detect_sql_injection(safe_input) is False
        assert SecurityUtils.detect_xss(safe_input) is False
        assert SecurityUtils.sanitize_input(safe_input) == safe_input
        # 恶意输入
        malicious_sql = "' OR 1=1 --"
        assert SecurityUtils.detect_sql_injection(malicious_sql) is True
        malicious_xss = "<script>alert(1)</script>"
        assert SecurityUtils.detect_xss(malicious_xss) is True


# ===== 边界情况测试 =====


class TestEdgeCases:
    """边界情况测试"""

    def test_password_hasher_unicode(self):
        """Unicode 密码"""
        hasher = PasswordHasher(iterations=1000)
        hashed = hasher.hash("密码123")
        assert hasher.verify("密码123", hashed) is True

    def test_jwt_empty_payload(self):
        """空负载 JWT"""
        manager = JWTManager(secret_key="test-secret")
        token = manager.create_token({})
        payload = manager.verify_token(token)
        assert payload is not None

    def test_rate_limiter_zero_max(self):
        """最大请求数为零"""
        limiter = RateLimiter(max_requests=0, window_seconds=60)
        result = limiter.check("user-1")
        assert result.allowed is False

    def test_csrf_token_no_session(self):
        """无会话 CSRF 令牌"""
        manager = CSRFTokenManager(secret_key="test-secret")
        token = manager.generate_token()
        assert manager.validate_token(token) is True

    def test_api_key_manager_long_plaintext(self):
        """长明文加密"""
        manager = APIKeyManager(secret_key="test-secret")
        plaintext = "a" * 10000
        encrypted = manager.encrypt(plaintext)
        decrypted = manager.decrypt(encrypted)
        assert decrypted == plaintext

    def test_password_hasher_long_password(self):
        """长密码"""
        hasher = PasswordHasher(iterations=1000)
        password = "a" * 1000
        hashed = hasher.hash(password)
        assert hasher.verify(password, hashed) is True

    def test_jwt_special_characters_in_payload(self):
        """JWT 负载特殊字符"""
        manager = JWTManager(secret_key="test-secret")
        token = manager.create_token({"name": "你好世界!@#$%"})
        payload = manager.verify_token(token)
        assert payload is not None
        assert payload["name"] == "你好世界!@#$%"

    def test_rate_limiter_concurrent(self):
        """并发限流"""
        limiter = RateLimiter(max_requests=100, window_seconds=60)
        results = []
        errors = []

        def worker():
            try:
                for _ in range(10):
                    result = limiter.check("concurrent-user")
                    results.append(result.allowed)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        # 100 个请求应全部允许
        assert all(results)

    def test_security_utils_empty_inputs(self):
        """空输入安全工具"""
        assert SecurityUtils.sanitize_input("") == ""
        assert SecurityUtils.detect_sql_injection("") is False
        assert SecurityUtils.detect_xss("") is False
        assert SecurityUtils.is_safe_redirect_url("", []) is False
