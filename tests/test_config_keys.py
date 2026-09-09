from aamt.config import Settings


def test_keys_from_csv(monkeypatch):
    for k in list(__import__("os").environ):
        if k.startswith("OPENROUTER_API_KEY"):
            monkeypatch.delenv(k, raising=False)
    s = Settings(openrouter_api_keys="sk-a, sk-b ,sk-c")
    assert s.resolved_openrouter_keys() == ["sk-a", "sk-b", "sk-c"]


def test_keys_from_numbered_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY_1", "sk-1")
    monkeypatch.setenv("OPENROUTER_API_KEY_2", "sk-2")
    monkeypatch.setenv("OPENROUTER_API_KEY_3", "  ")  # blank ignored
    s = Settings(openrouter_api_keys="")
    keys = s.resolved_openrouter_keys()
    assert "sk-1" in keys and "sk-2" in keys and "  " not in keys


def test_csv_takes_precedence(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY_1", "sk-env")
    s = Settings(openrouter_api_keys="sk-csv")
    assert s.resolved_openrouter_keys() == ["sk-csv"]


def test_rotator_round_robin_and_cooldown():
    from aamt.llm.provider import KeyRotator

    r = KeyRotator(["a", "b", "c"], cooldown_s=999)
    assert r.current() == "a"
    assert r.next_available() == "b"
    assert r.next_available() == "c"
    assert r.next_available() == "a"

    r2 = KeyRotator(["a", "b", "c"], cooldown_s=999)
    r2.penalize("b")
    # from a, the next non-cooled key is c (b is on cooldown)
    assert r2.next_available() == "c"
