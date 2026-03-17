"""Tests for response_format structured output support (SYM-92).

Covers:
- Predefined response format models and registry
- factory.py response_format parameter pass-through
- deepagents_adapter structured response extraction
- AgentService: get_agent() with response_format (including agent cache)
- AgentService: stream_response() captures structured_response and includes
  it in the message_end SSE event
- chat.py request schema accepts response_format (Literal validation)
- HTTP-layer: assistant metadata fallback and precedence
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessageChunk
from pydantic import BaseModel, ValidationError

from app.agents.deepagents_adapter import extract_structured_response
from app.agents.factory import create_deep_agent
from app.agents.response_formats import (
    RESPONSE_FORMAT_REGISTRY,
    APIIntegrationResponse,
    DataExtractionResponse,
    ExtractedField,
    FormFillResponse,
    ReportResponse,
    get_response_format,
)
from app.services.agent_service import AgentService
from app.services.sse import SSEEvent

# ---------------------------------------------------------------------------
# Helpers shared with test_streaming.py
# ---------------------------------------------------------------------------


def _make_mock_agent(stream_chunks: list[tuple[str, Any]]) -> MagicMock:
    """Create a mock agent whose ``astream()`` yields the given (mode, chunk) pairs."""
    mock_agent = MagicMock()

    async def fake_astream(*args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        for chunk in stream_chunks:
            yield chunk

    mock_agent.astream = fake_astream
    return mock_agent


async def _collect_events(svc: AgentService, **kwargs: Any) -> list[SSEEvent]:
    """Collect all SSE events from stream_response."""
    events: list[SSEEvent] = []
    async for evt in svc.stream_response(**kwargs):
        events.append(evt)
    return events


# ---------------------------------------------------------------------------
# Predefined response format models
# ---------------------------------------------------------------------------


class TestResponseFormatModels:
    """Tests for the predefined Pydantic response format models."""

    def test_data_extraction_defaults(self) -> None:
        """DataExtractionResponse should have sensible defaults."""
        resp = DataExtractionResponse()
        assert resp.fields == []
        assert resp.source_summary == ""
        assert resp.extraction_notes is None

    def test_data_extraction_with_fields(self) -> None:
        """DataExtractionResponse should accept a list of ExtractedField objects."""
        resp = DataExtractionResponse(
            fields=[
                ExtractedField(name="name", value="Alice", confidence=0.95),
                ExtractedField(name="age", value=30),
            ],
            source_summary="Short bio",
        )
        assert len(resp.fields) == 2
        assert resp.fields[0].name == "name"
        assert resp.fields[0].confidence == 0.95
        assert resp.fields[1].confidence == 1.0  # default

    def test_extracted_field_confidence_bounds(self) -> None:
        """ExtractedField confidence must be between 0 and 1."""
        with pytest.raises(ValidationError):
            ExtractedField(name="x", value=1, confidence=1.5)
        with pytest.raises(ValidationError):
            ExtractedField(name="x", value=1, confidence=-0.1)

    def test_report_response_defaults(self) -> None:
        """ReportResponse should require title and executive_summary."""
        resp = ReportResponse(title="My Report", executive_summary="Overview here")
        assert resp.sections == []
        assert resp.conclusion == ""
        assert resp.metadata == {}

    def test_report_response_with_sections(self) -> None:
        """ReportResponse should accept nested sections."""
        from app.agents.response_formats import ReportSection

        resp = ReportResponse(
            title="Analysis",
            executive_summary="Summary",
            sections=[
                ReportSection(
                    title="Introduction",
                    content="Background info",
                    subsections=[
                        ReportSection(title="Sub", content="detail"),
                    ],
                )
            ],
        )
        assert len(resp.sections) == 1
        assert len(resp.sections[0].subsections) == 1

    def test_form_fill_defaults(self) -> None:
        """FormFillResponse should have correct defaults."""
        resp = FormFillResponse()
        assert resp.form_id == ""
        assert resp.fields == []
        assert resp.is_complete is False
        assert resp.missing_required == []

    def test_api_integration_response_defaults(self) -> None:
        """APIIntegrationResponse defaults should reflect a successful empty response."""
        resp = APIIntegrationResponse()
        assert resp.status == "success"
        assert resp.payload == {}
        assert resp.errors == []
        assert resp.metadata == {}

    def test_api_integration_error_status(self) -> None:
        """APIIntegrationResponse should accept error status with messages."""
        resp = APIIntegrationResponse(
            status="error",
            errors=["Invalid input", "Missing field"],
        )
        assert resp.status == "error"
        assert len(resp.errors) == 2


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestResponseFormatRegistry:
    """Tests for RESPONSE_FORMAT_REGISTRY and get_response_format()."""

    def test_registry_contains_all_formats(self) -> None:
        assert "data_extraction" in RESPONSE_FORMAT_REGISTRY
        assert "report" in RESPONSE_FORMAT_REGISTRY
        assert "form_fill" in RESPONSE_FORMAT_REGISTRY
        assert "api_integration" in RESPONSE_FORMAT_REGISTRY

    def test_registry_values_are_pydantic_models(self) -> None:
        for name, cls in RESPONSE_FORMAT_REGISTRY.items():
            assert issubclass(cls, BaseModel), f"{name} is not a Pydantic BaseModel subclass"

    def test_get_response_format_known(self) -> None:
        assert get_response_format("data_extraction") is DataExtractionResponse
        assert get_response_format("report") is ReportResponse
        assert get_response_format("form_fill") is FormFillResponse
        assert get_response_format("api_integration") is APIIntegrationResponse

    def test_get_response_format_unknown_returns_none(self) -> None:
        assert get_response_format("nonexistent") is None
        assert get_response_format("") is None


# ---------------------------------------------------------------------------
# factory.py pass-through
# ---------------------------------------------------------------------------


class TestFactoryResponseFormat:
    """Tests that create_deep_agent() forwards response_format to deepagents."""

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_response_format_is_forwarded(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        """When response_format is provided it should be forwarded to _deepagents_create."""
        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        agent = create_deep_agent(response_format=DataExtractionResponse)
        assert agent is not None

        call_kwargs = mock_da_create.call_args.kwargs
        assert call_kwargs.get("response_format") is DataExtractionResponse

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_no_response_format_omits_key(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        """When response_format is None the key should not appear in create_kwargs."""
        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        create_deep_agent()

        call_kwargs = mock_da_create.call_args.kwargs
        assert "response_format" not in call_kwargs

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_response_format_with_assistant_type(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        """response_format and assistant_type can be combined."""
        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        create_deep_agent(assistant_type="researcher", response_format=ReportResponse)

        call_kwargs = mock_da_create.call_args.kwargs
        assert call_kwargs.get("response_format") is ReportResponse


# ---------------------------------------------------------------------------
# deepagents_adapter structured response extraction
# ---------------------------------------------------------------------------


class TestExtractStructuredResponse:
    """Tests for extract_structured_response() in deepagents_adapter."""

    def test_returns_none_when_key_absent(self) -> None:
        update = {"agent": {"messages": []}}
        assert extract_structured_response(update) is None

    def test_returns_none_when_value_is_none(self) -> None:
        update = {"agent": {"structured_response": None}}
        assert extract_structured_response(update) is None

    def test_returns_dict_when_already_a_dict(self) -> None:
        payload = {"name": "Alice", "age": 30}
        update = {"agent": {"structured_response": payload}}
        result = extract_structured_response(update)
        assert result == payload

    def test_serialises_pydantic_v2_model(self) -> None:
        """extract_structured_response should call model_dump() on Pydantic v2 instances."""
        instance = DataExtractionResponse(
            fields=[ExtractedField(name="x", value=1)],
            source_summary="test",
        )
        update = {"agent": {"structured_response": instance}}
        result = extract_structured_response(update)
        assert isinstance(result, dict)
        assert "fields" in result
        assert result["source_summary"] == "test"

    def test_skips_interrupt_key(self) -> None:
        """The __interrupt__ key should be ignored."""
        update = {
            "__interrupt__": [{"tool_name": "search"}],
            "agent": {"structured_response": {"val": 42}},
        }
        result = extract_structured_response(update)
        assert result == {"val": 42}

    def test_returns_first_non_none_across_nodes(self) -> None:
        """When multiple nodes have structured_response, first non-None wins."""
        update = {
            "node_a": {"structured_response": None},
            "node_b": {"structured_response": {"answer": "yes"}},
        }
        result = extract_structured_response(update)
        assert result == {"answer": "yes"}

    def test_skips_non_dict_node_outputs(self) -> None:
        update = {"agent": [1, 2, 3]}
        assert extract_structured_response(update) is None

    def test_coerces_non_dict_non_pydantic_to_value_wrapper(self) -> None:
        """Non-dict, non-Pydantic values are wrapped in {'value': ...}."""
        update = {"agent": {"structured_response": "plain string"}}
        result = extract_structured_response(update)
        assert result == {"value": "plain string"}


# ---------------------------------------------------------------------------
# AgentService.get_agent() with response_format
# ---------------------------------------------------------------------------


class TestAgentServiceGetAgent:
    """Tests for AgentService.get_agent() with response_format parameter."""

    def test_returns_singleton_without_response_format(self) -> None:
        """Without response_format the cached singleton is returned."""
        mock_agent = MagicMock()
        svc = AgentService(agent=mock_agent)
        assert svc.get_agent() is mock_agent
        assert svc.get_agent(assistant_type="general") is mock_agent

    @patch("app.services.agent_service.create_deep_agent")
    def test_creates_new_agent_with_response_format(self, mock_create: MagicMock) -> None:
        """A new agent is created when response_format is specified."""
        new_agent = MagicMock()
        mock_create.return_value = new_agent

        svc = AgentService(agent=MagicMock())
        result = svc.get_agent(response_format=DataExtractionResponse)

        assert result is new_agent
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs.get("response_format") is DataExtractionResponse

    @patch("app.services.agent_service.create_deep_agent")
    def test_creates_new_agent_with_type_and_format(self, mock_create: MagicMock) -> None:
        """Both assistant_type and response_format are forwarded."""
        mock_create.return_value = MagicMock()

        svc = AgentService(agent=MagicMock())
        svc.get_agent(assistant_type="researcher", response_format=ReportResponse)

        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs.get("assistant_type") == "researcher"
        assert call_kwargs.get("response_format") is ReportResponse


# ---------------------------------------------------------------------------
# AgentService.stream_response() structured_response in message_end
# ---------------------------------------------------------------------------


class TestStreamResponseStructuredOutput:
    """Tests for structured_response propagation through the streaming pipeline."""

    @pytest.mark.asyncio
    async def test_message_end_includes_structured_response(self) -> None:
        """When the agent returns structured_response it appears in message_end."""
        structured_payload = {
            "fields": [],
            "source_summary": "test extract",
            "extraction_notes": None,
        }
        chunks: list[tuple[str, Any]] = [
            ("messages", (AIMessageChunk(content="Extraction complete."), {})),
            (
                "updates",
                {"agent": {"structured_response": structured_payload}},
            ),
        ]
        svc = AgentService(agent=_make_mock_agent(chunks))

        events = await _collect_events(svc, thread_id="t1", user_message="extract data")
        end_evt = next(e for e in events if e.event == "message_end")

        assert "structured_response" in end_evt.data
        assert end_evt.data["structured_response"] == structured_payload

    @pytest.mark.asyncio
    async def test_message_end_no_structured_response_when_absent(self) -> None:
        """When no structured_response is present it is omitted from message_end."""
        chunks: list[tuple[str, Any]] = [
            ("messages", (AIMessageChunk(content="Plain response."), {})),
        ]
        svc = AgentService(agent=_make_mock_agent(chunks))

        events = await _collect_events(svc, thread_id="t1", user_message="hello")
        end_evt = next(e for e in events if e.event == "message_end")

        assert "structured_response" not in end_evt.data

    @pytest.mark.asyncio
    async def test_message_end_content_preserved_alongside_structured_response(self) -> None:
        """Full text content should still appear in message_end with structured_response."""
        structured_payload = {
            "status": "success",
            "payload": {"answer": 42},
            "errors": [],
            "metadata": {},
        }
        chunks: list[tuple[str, Any]] = [
            ("messages", (AIMessageChunk(content="The answer is "), {})),
            ("messages", (AIMessageChunk(content="42."), {})),
            (
                "updates",
                {"agent": {"structured_response": structured_payload}},
            ),
        ]
        svc = AgentService(agent=_make_mock_agent(chunks))

        events = await _collect_events(svc, thread_id="t1", user_message="what is the answer?")
        end_evt = next(e for e in events if e.event == "message_end")

        assert end_evt.data["content"] == "The answer is 42."
        assert end_evt.data["structured_response"] == structured_payload

    @pytest.mark.asyncio
    async def test_structured_response_from_pydantic_instance(self) -> None:
        """Pydantic instances in the state are serialised to dicts in message_end."""
        instance = APIIntegrationResponse(
            status="success",
            payload={"result": "done"},
        )
        chunks: list[tuple[str, Any]] = [
            (
                "updates",
                {"agent": {"structured_response": instance}},
            ),
        ]
        svc = AgentService(agent=_make_mock_agent(chunks))

        events = await _collect_events(svc, thread_id="t1", user_message="run task")
        end_evt = next(e for e in events if e.event == "message_end")

        assert "structured_response" in end_evt.data
        sr = end_evt.data["structured_response"]
        assert isinstance(sr, dict)
        assert sr["status"] == "success"
        assert sr["payload"] == {"result": "done"}

    @pytest.mark.asyncio
    async def test_response_format_passed_to_get_agent(self) -> None:
        """stream_response should forward response_format to get_agent."""
        chunks: list[tuple[str, Any]] = []
        svc = AgentService(agent=_make_mock_agent(chunks))

        with patch.object(svc, "get_agent", wraps=svc.get_agent) as mock_get_agent:
            mock_get_agent.return_value = _make_mock_agent(chunks)
            await _collect_events(
                svc,
                thread_id="t1",
                user_message="hi",
                response_format=ReportResponse,
            )
            mock_get_agent.assert_called_once_with(
                None,
                response_format=ReportResponse,
            )


# ---------------------------------------------------------------------------
# SSEEvent encoding with structured_response
# ---------------------------------------------------------------------------


class TestSSEEventStructuredResponse:
    """Tests for SSEEvent encoding with structured_response data."""

    def test_message_end_with_structured_response_encodes_correctly(self) -> None:
        """message_end event with structured_response should encode as valid SSE."""
        evt = SSEEvent(
            event="message_end",
            data={
                "thread_id": "abc",
                "content": "Done",
                "tool_calls": None,
                "structured_response": {"fields": [], "source_summary": "hello"},
            },
        )
        encoded = evt.encode()
        assert "event: message_end" in encoded
        assert "structured_response" in encoded
        assert encoded.endswith("\n\n")


# ---------------------------------------------------------------------------
# APIIntegrationResponse.status Literal constraint
# ---------------------------------------------------------------------------


class TestAPIIntegrationResponseStatus:
    """Tests that APIIntegrationResponse.status enforces Literal constraint."""

    def test_valid_status_success(self) -> None:
        resp = APIIntegrationResponse(status="success")
        assert resp.status == "success"

    def test_valid_status_partial(self) -> None:
        resp = APIIntegrationResponse(status="partial")
        assert resp.status == "partial"

    def test_valid_status_error(self) -> None:
        resp = APIIntegrationResponse(status="error")
        assert resp.status == "error"

    def test_invalid_status_raises_validation_error(self) -> None:
        """Arbitrary strings must be rejected by Pydantic validation."""
        with pytest.raises(ValidationError):
            APIIntegrationResponse(status="unknown_status")  # type: ignore[arg-type]

    def test_invalid_status_typo(self) -> None:
        with pytest.raises(ValidationError):
            APIIntegrationResponse(status="succes")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AgentService agent cache
# ---------------------------------------------------------------------------


class TestAgentServiceCache:
    """Tests for per-(assistant_type, response_format) agent caching in get_agent()."""

    @patch("app.services.agent_service.create_deep_agent")
    def test_same_format_reuses_cached_agent(self, mock_create: MagicMock) -> None:
        """Calling get_agent() twice with the same format returns the same instance."""
        cached_agent = MagicMock()
        mock_create.return_value = cached_agent

        svc = AgentService(agent=MagicMock())
        result1 = svc.get_agent(response_format=DataExtractionResponse)
        result2 = svc.get_agent(response_format=DataExtractionResponse)

        assert result1 is result2
        # create_deep_agent should only be called once
        mock_create.assert_called_once()

    @patch("app.services.agent_service.create_deep_agent")
    def test_different_formats_create_separate_agents(self, mock_create: MagicMock) -> None:
        """Different response_format classes produce separate cached entries."""
        agent_a = MagicMock()
        agent_b = MagicMock()
        mock_create.side_effect = [agent_a, agent_b]

        svc = AgentService(agent=MagicMock())
        result_a = svc.get_agent(response_format=DataExtractionResponse)
        result_b = svc.get_agent(response_format=ReportResponse)

        assert result_a is agent_a
        assert result_b is agent_b
        assert mock_create.call_count == 2

    @patch("app.services.agent_service.create_deep_agent")
    def test_type_and_format_combination_cached(self, mock_create: MagicMock) -> None:
        """(assistant_type, response_format) combinations are cached independently."""
        agent_1 = MagicMock()
        agent_2 = MagicMock()
        mock_create.side_effect = [agent_1, agent_2]

        svc = AgentService(agent=MagicMock())
        r1 = svc.get_agent(assistant_type="researcher", response_format=ReportResponse)
        r2 = svc.get_agent(assistant_type="coder", response_format=ReportResponse)

        assert r1 is agent_1
        assert r2 is agent_2
        assert mock_create.call_count == 2

    @patch("app.services.agent_service.create_deep_agent")
    def test_same_type_and_format_reuses_cache(self, mock_create: MagicMock) -> None:
        """The same (assistant_type, response_format) pair is served from cache."""
        shared_agent = MagicMock()
        mock_create.return_value = shared_agent

        svc = AgentService(agent=MagicMock())
        r1 = svc.get_agent(assistant_type="researcher", response_format=ReportResponse)
        r2 = svc.get_agent(assistant_type="researcher", response_format=ReportResponse)

        assert r1 is r2
        mock_create.assert_called_once()


# ---------------------------------------------------------------------------
# ChatRequest Literal validation for response_format
# ---------------------------------------------------------------------------


class TestChatRequestResponseFormatValidation:
    """Tests that ChatRequest.response_format enforces Literal values."""

    def test_valid_format_names_accepted(self) -> None:
        """All registry keys should be accepted by ChatRequest."""
        from app.api.routes.chat import ChatRequest

        for name in ["data_extraction", "report", "form_fill", "api_integration"]:
            req = ChatRequest(message="hello", response_format=name)  # type: ignore[arg-type]
            assert req.response_format == name

    def test_none_format_accepted(self) -> None:
        from app.api.routes.chat import ChatRequest

        req = ChatRequest(message="hello", response_format=None)
        assert req.response_format is None

    def test_invalid_format_name_raises_validation_error(self) -> None:
        """Unknown format names must be rejected at deserialization."""
        from app.api.routes.chat import ChatRequest

        with pytest.raises(ValidationError):
            ChatRequest(message="hello", response_format="nonexistent_format")  # type: ignore[arg-type]

    def test_typo_in_format_name_raises_validation_error(self) -> None:
        from app.api.routes.chat import ChatRequest

        with pytest.raises(ValidationError):
            ChatRequest(message="hello", response_format="data_extration")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# HTTP-layer: assistant metadata response_format resolution
# ---------------------------------------------------------------------------


class TestChatStreamResponseFormatHTTP:
    """Integration-level tests for response_format in the chat_stream HTTP endpoint."""

    @pytest.mark.asyncio
    async def test_unknown_response_format_returns_422(self, client) -> None:
        """An unknown response_format name in the request body must return 422."""
        resp = await client.post(
            "/chat/stream",
            json={"message": "hello", "response_format": "not_a_real_format"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_valid_response_format_forwarded_to_stream(self, client, db_session) -> None:
        """A valid response_format name is forwarded to stream_response()."""
        from app.services.agent_service import agent_service

        captured: dict = {}

        async def mock_stream(**kwargs: Any) -> AsyncIterator[SSEEvent]:
            captured.update(kwargs)
            yield SSEEvent(event="message_start", data={"thread_id": kwargs["thread_id"]})
            yield SSEEvent(
                event="message_end",
                data={
                    "thread_id": kwargs["thread_id"],
                    "content": "done",
                    "tool_calls": None,
                },
            )

        original = agent_service.stream_response
        agent_service.stream_response = mock_stream  # type: ignore[assignment]
        try:
            resp = await client.post(
                "/chat/stream",
                json={"message": "extract data", "response_format": "data_extraction"},
            )
            assert resp.status_code == 200
            assert captured.get("response_format") is DataExtractionResponse
        finally:
            agent_service.stream_response = original  # type: ignore[assignment]

    @pytest.mark.asyncio
    async def test_assistant_metadata_response_format_used_when_request_omits_it(
        self, client, db_session
    ) -> None:
        """When the request omits response_format, assistant metadata is used."""
        from app.models.assistant import AssistantCreate
        from app.services.agent_service import agent_service
        from app.services.assistant_service import AssistantService

        assistant_svc = AssistantService(db_session)
        assistant = await assistant_svc.create(
            AssistantCreate(
                name="report-assistant",
                description="Generates reports",
                model="gpt-4o",
                tools_enabled=[],
                metadata={"response_format": "report"},
            )
        )

        captured: dict = {}

        async def mock_stream(**kwargs: Any) -> AsyncIterator[SSEEvent]:
            captured.update(kwargs)
            yield SSEEvent(event="message_start", data={"thread_id": kwargs["thread_id"]})
            yield SSEEvent(
                event="message_end",
                data={
                    "thread_id": kwargs["thread_id"],
                    "content": "report done",
                    "tool_calls": None,
                },
            )

        original = agent_service.stream_response
        agent_service.stream_response = mock_stream  # type: ignore[assignment]
        try:
            resp = await client.post(
                f"/chat/stream?assistant_id={assistant.id}",
                json={"message": "generate a report"},
            )
            assert resp.status_code == 200
            assert captured.get("response_format") is ReportResponse
        finally:
            agent_service.stream_response = original  # type: ignore[assignment]

    @pytest.mark.asyncio
    async def test_request_response_format_overrides_assistant_metadata(
        self, client, db_session
    ) -> None:
        """A request-level response_format overrides the assistant's metadata value."""
        from app.models.assistant import AssistantCreate
        from app.services.agent_service import agent_service
        from app.services.assistant_service import AssistantService

        assistant_svc = AssistantService(db_session)
        assistant = await assistant_svc.create(
            AssistantCreate(
                name="form-assistant",
                description="Fills forms",
                model="gpt-4o",
                tools_enabled=[],
                metadata={"response_format": "form_fill"},
            )
        )

        captured: dict = {}

        async def mock_stream(**kwargs: Any) -> AsyncIterator[SSEEvent]:
            captured.update(kwargs)
            yield SSEEvent(event="message_start", data={"thread_id": kwargs["thread_id"]})
            yield SSEEvent(
                event="message_end",
                data={
                    "thread_id": kwargs["thread_id"],
                    "content": "done",
                    "tool_calls": None,
                },
            )

        original = agent_service.stream_response
        agent_service.stream_response = mock_stream  # type: ignore[assignment]
        try:
            # Request-level "report" should override assistant's "form_fill"
            resp = await client.post(
                f"/chat/stream?assistant_id={assistant.id}",
                json={"message": "hello", "response_format": "report"},
            )
            assert resp.status_code == 200
            # The captured format should be ReportResponse, not FormFillResponse
            assert captured.get("response_format") is ReportResponse
        finally:
            agent_service.stream_response = original  # type: ignore[assignment]
