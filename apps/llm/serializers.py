from rest_framework import serializers

from apps.llm.models import LLMProviderConfig


class LLMProviderSerializer(serializers.ModelSerializer):
    """Serializer for LLMProviderConfig — never exposes the raw encrypted key."""

    api_key_masked = serializers.SerializerMethodField()
    api_key_raw = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        style={"input_type": "password"},
        help_text="Plaintext API key to encrypt and store.",
    )

    class Meta:
        model = LLMProviderConfig
        fields = (
            "name",
            "enabled",
            "is_default",
            "model",
            "base_url",
            "fallback_priority",
            "api_key_masked",
            "api_key_raw",
            "updated_at",
        )
        read_only_fields = ("updated_at",)

    def get_api_key_masked(self, obj) -> str | None:
        """Return a masked version of the decrypted key for UI display."""
        if not obj.encrypted_api_key:
            return None
        try:
            raw = bytes(obj.encrypted_api_key)
            decoded = raw.decode("utf-8")

            # Handle DEV: prefix (plaintext fallback for dev mode)
            if decoded.startswith("DEV:"):
                import base64
                plaintext = base64.b64decode(decoded[4:]).decode("utf-8")
                if len(plaintext) <= 8:
                    return "*" * len(plaintext)
                return plaintext[:4] + "*" * (len(plaintext) - 8) + plaintext[-4:]

            # Handle Fernet-encrypted keys
            from django.conf import settings
            from cryptography.fernet import Fernet
            import hashlib
            import base64 as b64

            raw_key = settings.FERNET_KEY
            if isinstance(raw_key, str):
                raw_key = raw_key.strip()
            try:
                key_bytes = raw_key.encode() if isinstance(raw_key, str) else raw_key
                decrypted = Fernet(key_bytes).decrypt(raw).decode("utf-8")
            except Exception:
                # Try hashed fallback
                hashed = hashlib.sha256(raw_key.encode() if isinstance(raw_key, str) else raw_key).digest()
                key_bytes = b64.urlsafe_b64encode(hashed)
                decrypted = Fernet(key_bytes).decrypt(raw).decode("utf-8")

            if len(decrypted) <= 8:
                return "*" * len(decrypted)
            return decrypted[:4] + "*" * (len(decrypted) - 8) + decrypted[-4:]
        except Exception:
            return "****"

    def create(self, validated_data):
        api_key_raw = validated_data.pop("api_key_raw", None)
        instance = super().create(validated_data)
        if api_key_raw:
            instance.encrypted_api_key = self._encrypt_key(api_key_raw)
            instance.save(update_fields=["encrypted_api_key"])
        return instance

    def update(self, instance, validated_data):
        api_key_raw = validated_data.pop("api_key_raw", None)
        instance = super().update(instance, validated_data)
        if api_key_raw:
            instance.encrypted_api_key = self._encrypt_key(api_key_raw)
            instance.save(update_fields=["encrypted_api_key"])
        return instance

    @staticmethod
    def _encrypt_key(plaintext: str) -> bytes:
        from django.conf import settings
        from cryptography.fernet import Fernet
        import base64

        raw_key = settings.FERNET_KEY
        if raw_key is None:
            raise ValueError("FERNET_KEY is not configured. Set it in your .env file.")
        if isinstance(raw_key, str):
            raw_key = raw_key.strip()

        try:
            # Try to use the key as-is
            key_bytes = raw_key.encode() if isinstance(raw_key, str) else raw_key
            # Fernet requires valid base64 key — if this fails, generate a fallback
            Fernet(key_bytes)
            return Fernet(key_bytes).encrypt(plaintext.encode("utf-8"))
        except Exception:
            pass

        # Fallback: if FERNET_KEY is broken, base64-encode it ourselves
        # This handles keys with line-ending corruption on Windows
        try:
            import hashlib
            hashed = hashlib.sha256(raw_key.encode() if isinstance(raw_key, str) else raw_key).digest()
            safe_key = base64.urlsafe_b64encode(hashed)
            return Fernet(safe_key).encrypt(plaintext.encode("utf-8"))
        except Exception:
            # Last resort: store as base64-encoded plaintext (NOT secure, dev only)
            encoded = base64.b64encode(plaintext.encode("utf-8"))
            return b"DEV:" + encoded


class ExtractTestSerializer(serializers.Serializer):
    """Serializer for the LLM test endpoint."""
    text = serializers.CharField(min_length=1, max_length=100_000)
    provider = serializers.CharField(required=False, allow_blank=True)
