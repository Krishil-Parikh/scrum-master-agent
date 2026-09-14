from app.config import get_settings


def test_settings_load_with_defaults():
    settings = get_settings()
    assert settings.openrouter_model  # cheap Mistral model id, non-empty
    assert settings.app_port == 8000
    assert isinstance(settings.cors_origin_list, list)
    assert "http://localhost:5173" in settings.cors_origin_list


def test_settings_is_cached_singleton():
    assert get_settings() is get_settings()
