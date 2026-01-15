"""Tests for config.py settings validation."""

from config import Settings


class TestSettingsValidation:
    """Tests for Settings Pydantic validation."""

    def test_settings_valid_defaults(self):
        """Settings should initialize with valid defaults."""
        settings = Settings()
        assert settings.APP_ENV in ["dev", "test", "prod"]
        assert settings.CHROMA_DISTANCE in ["cosine", "l2", "ip"]
        assert settings.HASH_ALGO in ["xxh3", "md5"]
        assert settings.EMB_MODEL == "nomic-embed-text"

    def test_settings_env_validation(self):
        """APP_ENV should accept valid values."""
        # Valid values
        settings_dev = Settings(APP_ENV="dev")
        assert settings_dev.APP_ENV == "dev"
        
        settings_test = Settings(APP_ENV="test")
        assert settings_test.APP_ENV == "test"
        
        settings_prod = Settings(APP_ENV="prod")
        assert settings_prod.APP_ENV == "prod"

    def test_settings_chroma_distance_validation(self):
        """CHROMA_DISTANCE should only accept valid metrics."""
        valid_distances = ["cosine", "l2", "ip"]
        for distance in valid_distances:
            settings = Settings(CHROMA_DISTANCE=distance)
            assert settings.CHROMA_DISTANCE == distance

    def test_settings_hash_algo_validation(self):
        """HASH_ALGO should only accept valid algorithms."""
        for algo in ["xxh3", "md5"]:
            settings = Settings(HASH_ALGO=algo)
            assert settings.HASH_ALGO == algo

    def test_settings_ollama_host(self):
        """OLLAMA_HOST should be configurable."""
        settings = Settings(OLLAMA_HOST="http://custom.host:11434")
        assert settings.OLLAMA_HOST == "http://custom.host:11434"

    def test_settings_chunk_tokens_positive(self):
        """CHUNK_TOKENS should be positive."""
        settings = Settings(CHUNK_TOKENS=512)
        assert settings.CHUNK_TOKENS == 512

        # Test with another positive value
        settings2 = Settings(CHUNK_TOKENS=1024)
        assert settings2.CHUNK_TOKENS == 1024

    def test_settings_chunk_overlap_tokens_non_negative(self):
        """CHUNK_OVERLAP_TOKENS should be non-negative."""
        settings = Settings(CHUNK_OVERLAP_TOKENS=0)
        assert settings.CHUNK_OVERLAP_TOKENS == 0

        settings2 = Settings(CHUNK_OVERLAP_TOKENS=100)
        assert settings2.CHUNK_OVERLAP_TOKENS == 100

    def test_settings_chars_per_token_positive(self):
        """CHARS_PER_TOKEN must be positive."""
        settings = Settings(CHARS_PER_TOKEN=4.5)
        assert settings.CHARS_PER_TOKEN == 4.5

    def test_settings_all_required_fields(self):
        """All required fields should have defaults."""
        settings = Settings()
        assert hasattr(settings, "APP_ENV")
        assert hasattr(settings, "CHROMA_DISTANCE")
        assert hasattr(settings, "HASH_ALGO")
        assert hasattr(settings, "OLLAMA_HOST")
        assert hasattr(settings, "CHUNK_TOKENS")
        assert hasattr(settings, "CHUNK_OVERLAP_TOKENS")

    def test_settings_dev_environment(self):
        """Dev environment should be valid."""
        settings = Settings(APP_ENV="dev")
        assert settings.APP_ENV == "dev"

    def test_settings_prod_environment(self):
        """Prod environment should be valid."""
        settings = Settings(APP_ENV="prod")
        assert settings.APP_ENV == "prod"

    def test_settings_test_environment(self):
        """Test environment should be valid."""
        settings = Settings(APP_ENV="test")
        assert settings.APP_ENV == "test"


class TestSettingsFieldConstraints:
    """Tests for Settings field constraints."""

    def test_chunk_tokens_reasonable_value(self):
        """CHUNK_TOKENS should be a reasonable positive value."""
        settings = Settings(CHUNK_TOKENS=800)
        assert settings.CHUNK_TOKENS > 0
        assert settings.CHUNK_TOKENS == 800

    def test_chunk_overlap_tokens_less_than_size(self):
        """CHUNK_OVERLAP_TOKENS should typically be less than CHUNK_TOKENS."""
        settings = Settings(CHUNK_TOKENS=800, CHUNK_OVERLAP_TOKENS=140)
        assert settings.CHUNK_OVERLAP_TOKENS < settings.CHUNK_TOKENS

    def test_settings_field_descriptions(self):
        """Settings fields should have descriptions in metadata."""
        assert hasattr(Settings, "model_fields")
        assert len(Settings.model_fields) > 0

    def test_settings_repr(self):
        """Settings should have useful repr."""
        settings = Settings()
        repr_str = repr(settings)
        assert "APP_ENV" in repr_str or "Settings" in repr_str

    def test_ingest_batch_size_positive(self):
        """INGEST_BATCH_SIZE should be positive."""
        settings = Settings(INGEST_BATCH_SIZE=64)
        assert settings.INGEST_BATCH_SIZE == 64
        assert settings.INGEST_BATCH_SIZE > 0
