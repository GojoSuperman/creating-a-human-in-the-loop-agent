from agent import settings as s


def test_spec_constants_are_pinned():
    # 스펙 §1.3·§1.5·§3.4·§2.2·§4.2·§5 의 값. 바꾸려면 스펙부터 고친다.
    assert s.N_ITEMS == 200 and s.SEED == 42
    assert s.DEV_WEEK == "2011-06-06"
    assert s.TEST_WEEKS == ("2011-09-05", "2011-10-03")
    assert not set(s.DEMO_WEEKS) & {s.DEV_WEEK, *s.TEST_WEEKS}      # 재생 전용 주는 검증에 섞이지 않는다
    assert s.LABEL_LOSS_GBP == 100.0
    assert s.GBP_KRW == 1800
    assert s.MAX_RATE == 0.25
    assert s.REDO_MAX == 2 and s.EDIT_MAX_MULT == 10
    assert s.LLM_CONCURRENCY == 8
    assert s.STALE_HOURS == 72 and s.SESSION_TTL_HOURS == 24


def test_db_urls_default_to_separate_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert s.store_url().startswith("sqlite:///") and s.store_url().endswith("app.sqlite")
    assert s.checkpoint_url().endswith("checkpoints.sqlite")


def test_db_urls_use_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    assert s.store_url() == s.checkpoint_url() == "postgresql://u:p@h/db"


def test_load_env_does_not_override(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("FOO_TEST=from_file\nBAR_TEST=b\n# 주석\n", encoding="utf-8")
    monkeypatch.setenv("FOO_TEST", "already")
    monkeypatch.delenv("BAR_TEST", raising=False)
    s.load_env(env)
    import os
    assert os.environ["FOO_TEST"] == "already"
    assert os.environ["BAR_TEST"] == "b"
