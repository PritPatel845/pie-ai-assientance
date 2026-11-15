from __future__ import annotations

import pytest

from pie.safety.permissions import Tier
from pie.tools.base import ToolSpec


def test_tool_spec_requires_domain_verb_name_and_closed_object_schema() -> None:
    schema = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    spec = ToolSpec("mac.open_app", "Open an app.", schema, Tier.REVERSIBLE)
    assert spec.timeout_s == 30.0
    assert spec.platforms == ("darwin",)

    with pytest.raises(ValueError, match="name"):
        ToolSpec("Open App", "Invalid.", schema, Tier.READ)
    with pytest.raises(ValueError, match="additionalProperties"):
        ToolSpec(
            "mac.unsafe",
            "Invalid schema.",
            {"type": "object", "properties": {}},
            Tier.READ,
        )
    with pytest.raises(ValueError, match="timeout"):
        ToolSpec("mac.invalid", "Invalid timeout.", schema, Tier.READ, timeout_s=0)
