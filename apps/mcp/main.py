from fastmcp import FastMCP
from tools.eda_summary import EdaSummaryTool

app = FastMCP(
    tools=[EdaSummaryTool], title="FastMCP", version="0.1.0"  # register all tools here
)
