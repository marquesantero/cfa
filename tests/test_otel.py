"""Tests for cfa.otel — OpenTelemetry integration."""


class TestOTel:
    def test_enable_otel_returns_bool(self):
        from cfa.observability.otel import enable_otel
        result = enable_otel()
        assert isinstance(result, bool)

    def test_cfa_span_noop_without_otel(self):
        from cfa.observability.otel import cfa_span
        with cfa_span("test", phase="govern"):
            pass
