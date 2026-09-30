import asyncio
import json
import re
from unittest.mock import Mock

import httpx
from structlog.contextvars import bind_contextvars, clear_contextvars

from app import logging_config
from app import main
from app.agent import AgentResult
from app.pii import hash_user_id


def test_request_context_headers_and_agent_propagation(monkeypatch, tmp_path):
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    run = Mock(return_value=AgentResult("ok", 1, 1, 20, 10, 0.001, 0.9))
    monkeypatch.setattr(main.agent, "run", run)
    monkeypatch.setenv("APP_ENV", "test")

    async def send_requests():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        ) as client:
            bind_contextvars(stale_field="must disappear", correlation_id="old")
            try:
                return await asyncio.gather(*(
                    client.post("/chat", headers={"x-request-id": "req-client01"} if i == 0 else {},
                                json={"user_id": f"user-{i}", "session_id": f"session-{i}",
                                      "feature": "qa", "message": "CCCD 079203012345"})
                    for i in range(3)
                ))
            finally:
                clear_contextvars()

    responses = asyncio.run(send_requests())
    events = [json.loads(line) for line in log_path.read_text().splitlines()]
    ids = []
    for i, response in enumerate(responses):
        assert response.status_code == 200
        cid = response.headers["x-request-id"]
        ids.append(cid)
        assert response.json()["correlation_id"] == cid
        assert float(response.headers["x-response-time-ms"]) >= 0
        assert cid == "req-client01" if i == 0 else re.fullmatch(r"req-[0-9a-f]{8}", cid)
        matched = [event for event in events if event.get("correlation_id") == cid]
        assert [event["event"] for event in matched] == ["request_received", "response_sent"]
        for event in matched:
            assert event["user_id_hash"] == hash_user_id(f"user-{i}")
            assert event["session_id"] == f"session-{i}"
            assert event["feature"] == "qa"
            assert event["model"] == main.agent.model
            assert event["env"] == "test"
            assert "stale_field" not in event
        assert run.call_args_list[i].kwargs["correlation_id"] == cid
    assert len(set(ids)) == 3
    assert "079203012345" not in log_path.read_text()
