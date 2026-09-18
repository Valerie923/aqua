import io

from fastapi.testclient import TestClient
from PIL import Image

from app import main
from app.routers import demo


def _write_jpeg(path):
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (90, 120, 80)).save(buf, format="JPEG")
    path.write_bytes(buf.getvalue())


def test_scenarios_file_is_valid_form_input():
    from app.schemas import FormAnswers

    scenarios = demo.load_scenarios()
    assert len(scenarios) == 3
    for sc in scenarios:
        FormAnswers.model_validate({"site": sc["site"], **sc["answers"]})


def test_only_scenarios_with_photos_are_listed(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "PHOTOS_DIR", tmp_path)
    assert demo.available_scenarios() == []

    folder = tmp_path / "bishan_park"
    folder.mkdir()
    for role in ("upstream", "downstream"):
        _write_jpeg(folder / f"{role}.jpg")
    assert demo.available_scenarios() == []  # context missing

    _write_jpeg(folder / "context.png")
    listed = demo.available_scenarios()
    assert [sc["id"] for sc in listed] == ["bishan_park"]
    assert listed[0]["photos"] == {
        "upstream": "/demo-photos/bishan_park/upstream.jpg",
        "downstream": "/demo-photos/bishan_park/downstream.jpg",
        "context": "/demo-photos/bishan_park/context.png",
    }

    with TestClient(main.app) as client:
        body = client.get("/api/demo").json()
        assert body[0]["id"] == "bishan_park" and "answers" not in body[0]
        assert client.get("/demo-photos/bishan_park/context.png").status_code == 200
        assert client.get("/demo-photos/bishan_park/biodiversity.jpg").status_code == 404
        assert client.get("/demo-photos/bishan_park/../scenarios.json").status_code == 404


def test_about_and_submissions_pages_are_served():
    with TestClient(main.app) as client:
        assert client.get("/about.html").status_code == 200
        assert "validation layer" in client.get("/about.html").text
        assert client.get("/submissions.html").status_code == 200
