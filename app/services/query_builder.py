"""Boolean X-Ray query builder for public search engines (not LinkedIn scraping)."""
from app.models import QueryRequest, QueryResponse

BUCKET_TERMS = {
    "A": ('("Final Year B.Tech" OR "2026 Graduate" OR "computer science student" OR "recent graduate")', '("AI Engineer" OR "Software Engineer" OR "machine learning")'),
    "B": ('("Associate Software Engineer" OR "Junior Data Analyst" OR "Software Developer" OR "Backend Engineer")', '("1 year" OR "2 years" OR "generative AI" OR "LLM")'),
    "C": ('("QA engineer" OR "Java developer" OR "Technical support engineer" OR "Data analyst")', '(transitioning OR "learning generative AI" OR "moving to software development")'),
}
BUCKET_DESCRIPTIONS = {
    "A": "Students and Freshers", "B": "Early Career Professionals (1–2 YOE)",
    "C": "Career Switchers",
}


def _quote_filter(value: str) -> str:
    # Avoid injecting Boolean operators/parentheses from user input into query syntax.
    clean = " ".join(value.replace('"', "").replace("(", " ").replace(")", " ").split())
    return f'"{clean}"' if clean else ""


def build_bucket_query_a(keyword: str = "", location: str = "") -> str:
    return _build("A", keyword, location)


def build_bucket_query_b(keyword: str = "", location: str = "") -> str:
    return _build("B", keyword, location)


def build_bucket_query_c(keyword: str = "", location: str = "") -> str:
    return _build("C", keyword, location)


def _build(bucket: str, keyword: str, location: str) -> str:
    first, second = BUCKET_TERMS[bucket]
    filters = [_quote_filter(keyword), _quote_filter(location)]
    suffix = " ".join(item for item in filters if item)
    return f"site:linkedin.com/in/ {first} {second}" + (f" {suffix}" if suffix else "")


def build_queries(request: QueryRequest) -> QueryResponse:
    functions = {"A": build_bucket_query_a, "B": build_bucket_query_b, "C": build_bucket_query_c}
    buckets = list(dict.fromkeys(request.buckets))
    return QueryResponse(
        queries=[functions[b](request.keyword, request.location) for b in buckets],
        bucket_descriptions={b: BUCKET_DESCRIPTIONS[b] for b in buckets},
    )
