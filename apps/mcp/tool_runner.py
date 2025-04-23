from typing import Callable, Dict, Any
from tools import eda_summary  # import additional tools as you add them

# Registry mapping tool names to functions
TOOL_REGISTRY: Dict[str, Callable[[str, Dict[str, Any]], Dict[str, Any]]] = {
    "eda_summary": eda_summary.run,
    # Add more tools here:
    # "null_analysis": null_analysis.run,
    # "model_train": model_train.run,
}


def run_tool(
    tool_name: str, dataset_id: str, parameters: Dict[str, Any]
) -> Dict[str, Any]:
    if tool_name not in TOOL_REGISTRY:
        raise ValueError(f"Tool '{tool_name}' is not registered.")

    tool_fn = TOOL_REGISTRY[tool_name]
    return tool_fn(dataset_id, parameters)
