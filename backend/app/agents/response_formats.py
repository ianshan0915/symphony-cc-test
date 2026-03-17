"""Predefined response formats for structured agent output (SYM-92).

These Pydantic models can be passed as ``response_format`` to
``create_deep_agent()`` to obtain validated structured data alongside
the standard unstructured text response.  When a ``response_format`` is
configured the agent returns the structured payload in
``result["structured_response"]`` (via ``ainvoke()``) or in the
``structured_response`` key of the final state update (via ``astream()``).

Common use cases
----------------
- **Data extraction** — pull structured fields from unstructured text
- **Report generation** — produce JSON reports with sections and metadata
- **Form filling** — populate form fields from conversational context
- **API integration** — output must conform to a strict JSON schema

Assistant-level configuration
------------------------------
Assistants can configure a persistent response format by storing the
format name in their ``metadata_`` dict::

    assistant.metadata_ = {"response_format": "data_extraction"}

The ``response_format`` key accepts any name registered in
:data:`RESPONSE_FORMAT_REGISTRY`.

Programmatic usage
------------------
Pass a Pydantic class directly to ``create_deep_agent()``::

    from app.agents.response_formats import ReportResponse

    agent = create_deep_agent(response_format=ReportResponse)

Or use the registry helper::

    from app.agents.response_formats import get_response_format

    agent = create_deep_agent(response_format=get_response_format("report"))
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------


class ExtractedField(BaseModel):
    """A single extracted field from unstructured text."""

    name: str = Field(..., description="Field name")
    value: Any = Field(..., description="Extracted value")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score 0-1"
    )


class DataExtractionResponse(BaseModel):
    """Structured data extraction from unstructured text.

    Use when the agent must identify and extract specific named fields
    from a document, email, form scan, or any unstructured source.
    Low-confidence or missing fields are noted in ``extraction_notes``.

    Example::

        agent = create_deep_agent(response_format=DataExtractionResponse)
    """

    fields: list[ExtractedField] = Field(
        default_factory=list,
        description="Extracted fields with values and confidence scores",
    )
    source_summary: str = Field(
        default="",
        description="Brief summary of the source text",
    )
    extraction_notes: str | None = Field(
        default=None,
        description="Notes on ambiguities or low-confidence fields",
    )


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


class ReportSection(BaseModel):
    """A single section in a generated report."""

    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Section body content")
    subsections: list[ReportSection] = Field(
        default_factory=list,
        description="Optional nested subsections",
    )


ReportSection.model_rebuild()


class ReportResponse(BaseModel):
    """Structured report generation output.

    Use when the agent must produce a well-formed report with a title,
    executive summary, body sections, and a conclusion.

    Example::

        agent = create_deep_agent(response_format=ReportResponse)
    """

    title: str = Field(..., description="Report title")
    executive_summary: str = Field(
        ..., description="High-level overview of findings"
    )
    sections: list[ReportSection] = Field(
        default_factory=list, description="Report body sections"
    )
    conclusion: str = Field(
        default="", description="Closing remarks and recommendations"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary metadata (date, author, version, etc.)",
    )


# ---------------------------------------------------------------------------
# Form filling
# ---------------------------------------------------------------------------


class FormField(BaseModel):
    """A single form field with its populated value."""

    field_id: str = Field(..., description="Form field identifier")
    label: str = Field(..., description="Human-readable field label")
    value: Any = Field(default=None, description="Populated field value")
    is_required: bool = Field(
        default=False, description="Whether the field is mandatory"
    )
    validation_error: str | None = Field(
        default=None,
        description="Validation error message if the value is invalid",
    )


class FormFillResponse(BaseModel):
    """Structured form-filling output.

    Use when the agent must populate form fields from conversational
    context or documents.  Includes a completeness flag and a list of
    required fields that could not be filled.

    Example::

        agent = create_deep_agent(response_format=FormFillResponse)
    """

    form_id: str = Field(default="", description="Identifier of the form being filled")
    fields: list[FormField] = Field(
        default_factory=list, description="Populated form fields"
    )
    is_complete: bool = Field(
        default=False,
        description="True when all required fields are populated",
    )
    missing_required: list[str] = Field(
        default_factory=list,
        description="IDs of required fields that could not be filled",
    )


# ---------------------------------------------------------------------------
# API integration
# ---------------------------------------------------------------------------


class APIIntegrationResponse(BaseModel):
    """Generic API-friendly structured response.

    Use when the agent's output must conform to a strict schema for
    downstream API consumption.  Provides a status code, a typed
    payload, and optional error details.

    Example::

        agent = create_deep_agent(response_format=APIIntegrationResponse)
    """

    status: str = Field(
        default="success",
        description="Response status: 'success', 'partial', or 'error'",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured output payload",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Error messages when status is 'error' or 'partial'",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (processing time, model, version, etc.)",
    )


# ---------------------------------------------------------------------------
# Registry of predefined formats
# ---------------------------------------------------------------------------

#: Maps format name → Pydantic model class for use with
#: :func:`~app.agents.response_formats.get_response_format`.
RESPONSE_FORMAT_REGISTRY: dict[str, type[BaseModel]] = {
    "data_extraction": DataExtractionResponse,
    "report": ReportResponse,
    "form_fill": FormFillResponse,
    "api_integration": APIIntegrationResponse,
}


def get_response_format(name: str) -> type[BaseModel] | None:
    """Return a predefined response format class by registry name.

    Parameters
    ----------
    name:
        One of ``"data_extraction"``, ``"report"``, ``"form_fill"``,
        or ``"api_integration"``.

    Returns
    -------
    type[BaseModel] | None
        The Pydantic model class, or ``None`` if *name* is not registered.

    Example::

        fmt = get_response_format("report")
        agent = create_deep_agent(response_format=fmt)
    """
    return RESPONSE_FORMAT_REGISTRY.get(name)
