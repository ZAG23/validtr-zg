"""Tests for scorer/context_compressor.py — the optional headroom integration."""

from scorer import context_compressor


class TestDisabledByDefault:
    def test_disabled_without_opt_in(self, monkeypatch):
        monkeypatch.delenv("VALIDTR_COMPRESS_ARTIFACTS", raising=False)
        monkeypatch.setattr(context_compressor, "_headroom", object())
        assert context_compressor.compression_enabled() is False

    def test_disabled_without_package(self, monkeypatch):
        monkeypatch.setenv("VALIDTR_COMPRESS_ARTIFACTS", "1")
        monkeypatch.setattr(context_compressor, "_headroom", None)
        assert context_compressor.compression_enabled() is False

    def test_compress_text_returns_none_when_disabled(self, monkeypatch):
        monkeypatch.delenv("VALIDTR_COMPRESS_ARTIFACTS", raising=False)
        assert context_compressor.compress_text("some long text", model_limit=100) is None


class TestCompressWiring:
    def test_compress_text_uses_headroom_result(self, monkeypatch):
        monkeypatch.setenv("VALIDTR_COMPRESS_ARTIFACTS", "1")

        class _Result:
            messages = [{"role": "user", "content": "compressed!"}]

        class _FakeHeadroom:
            def compress(self, messages, model_limit, optimize):
                assert messages[0]["content"] == "original text"
                assert optimize is True
                return _Result()

        monkeypatch.setattr(context_compressor, "_headroom", _FakeHeadroom())
        result = context_compressor.compress_text("original text", model_limit=50)
        assert result == "compressed!"

    def test_compress_text_returns_none_on_exception(self, monkeypatch):
        monkeypatch.setenv("VALIDTR_COMPRESS_ARTIFACTS", "1")

        class _FailingHeadroom:
            def compress(self, **kwargs):
                raise RuntimeError("boom")

        monkeypatch.setattr(context_compressor, "_headroom", _FailingHeadroom())
        assert context_compressor.compress_text("text", model_limit=50) is None
