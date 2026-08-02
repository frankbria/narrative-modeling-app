"""CORS origin parsing (#365 review side-catch)."""

from app.config import _parse_cors_origins


class TestBracketedOriginLists:
    """`[http://a,http://b]` is not valid JSON, so it used to fall through to the
    comma split with the brackets attached — producing `[http://a` and `http://b]`,
    origins that can never match anything, silently. `.env.example` shipped in
    exactly that form, so it is the shape people copy.
    """

    def test_a_bracketed_unquoted_list_parses(self):
        assert _parse_cors_origins("[http://a,http://b]") == ["http://a", "http://b"]

    def test_a_single_bracketed_origin_parses(self):
        assert _parse_cors_origins("[http://localhost:3000]") == [
            "http://localhost:3000"
        ]

    def test_proper_json_still_parses(self):
        assert _parse_cors_origins('["http://a","http://b"]') == [
            "http://a",
            "http://b",
        ]

    def test_plain_csv_still_parses(self):
        assert _parse_cors_origins("http://a,http://b") == ["http://a", "http://b"]

    def test_blank_is_still_the_wildcard(self):
        assert _parse_cors_origins("") == ["*"]
