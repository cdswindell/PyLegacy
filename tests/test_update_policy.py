from pytrain.utils.update_policy import self_update_disabled


def test_self_update_disabled(monkeypatch):
    monkeypatch.delenv("PYTRAIN_DISABLE_SELF_UPDATE", raising=False)
    assert self_update_disabled() is False
    for value in ("1", "true", "YES", "On"):
        monkeypatch.setenv("PYTRAIN_DISABLE_SELF_UPDATE", value)
        assert self_update_disabled() is True
    monkeypatch.setenv("PYTRAIN_DISABLE_SELF_UPDATE", "0")
    assert self_update_disabled() is False
