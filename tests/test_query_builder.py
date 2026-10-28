from app.models import QueryRequest
from app.services.query_builder import build_queries


def test_queries_cover_each_bucket_and_filters():
    result = build_queries(QueryRequest(buckets=["A", "B", "C"], keyword="Python", location="Toronto"))
    assert len(result.queries) == 3
    assert all("site:linkedin.com/in/" in q for q in result.queries)
    assert all('"Python"' in q and '"Toronto"' in q for q in result.queries)
    assert "Final Year B.Tech" in result.queries[0]
    assert "Associate Software Engineer" in result.queries[1]
    assert "QA engineer" in result.queries[2]


def test_filter_syntax_is_quoted():
    result = build_queries(QueryRequest(buckets=["A"], keyword='AI" OR site:evil.test'))
    assert '"AI OR site:evil.test"' in result.queries[0]
    assert "site:evil.test" not in result.queries[0].split('"')[0]
