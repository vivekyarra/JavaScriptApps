"""Export JSON Schemas for tool input and output (structured output contract)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pharos.schemas import AlternativesResult, CaseInput, CompareResult, DecisionResult, ScreenResult, SubmittalCheck

out = Path(__file__).resolve().parent.parent / "schemas"
out.mkdir(exist_ok=True)
for name, model in {"case_input": CaseInput, "compare_result": CompareResult, "screen_result": ScreenResult, "decision_result": DecisionResult, "submittal_check": SubmittalCheck, "alternatives_result": AlternativesResult}.items():
    (out / f"{name}.schema.json").write_text(json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8")
print("wrote", sorted(p.name for p in out.glob("*.json")))
