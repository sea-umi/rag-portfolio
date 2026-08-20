from fastapi.testclient import TestClient

from app.main import app, get_gemini_service
from app.schemas import SearchHit
from app.services.supabase import get_vector_store


class FakeGemini:
    def embed_query(self, question: str) -> list[float]:
        return [0.1, 0.2]

    def generate_answer(self, question: str, context: str) -> str:
        return "入社6ヶ月経過後に10日付与されます。"


class FakeVectorStore:
    def __init__(self, results: list[SearchHit]):
        self.results = results

    def search(self, query_embedding, *, match_threshold, match_count):
        return self.results


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ask_returns_no_information_without_search_hits() -> None:
    app.dependency_overrides[get_gemini_service] = lambda: FakeGemini()
    app.dependency_overrides[get_vector_store] = lambda: FakeVectorStore([])
    try:
        client = TestClient(app)
        response = client.post("/api/v1/ask", json={"question": "育児休業の条件"})
        assert response.status_code == 200
        assert response.json() == {
            "answer": "該当する情報が見つかりません",
            "sources": [],
            "found": False,
        }
    finally:
        app.dependency_overrides.clear()


def test_ask_includes_file_and_page_for_search_hits() -> None:
    app.dependency_overrides[get_gemini_service] = lambda: FakeGemini()
    app.dependency_overrides[get_vector_store] = lambda: FakeVectorStore(
        [
            SearchHit(
                file_name="case3-doc1-employment-rules.pdf",
                page_number=2,
                chunk_index=0,
                content="入社6ヶ月経過後に10日付与される。",
                similarity=0.9,
            )
        ]
    )
    try:
        client = TestClient(app)
        response = client.post("/api/v1/ask", json={"question": "有給休暇"})
        assert response.status_code == 200
        assert response.json()["sources"] == [
            {"file_name": "case3-doc1-employment-rules.pdf", "page_number": 2}
        ]
    finally:
        app.dependency_overrides.clear()
