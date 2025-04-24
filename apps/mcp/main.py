# apps/mcp/main.py
import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "fastmcp", "src"))
)

try:
    from fastmcp.server.server import FastMCP
    from tools.eda_summary import EdaInput, eda_summary

    mcp = FastMCP("Narrative Modeling Application")

    @mcp.tool()
    async def eda_summary_tool(params: EdaInput) -> dict:
        """Generate an EDA summary for a given CSV file stored at an S3 URI."""
        return eda_summary(params)

    if __name__ == "__main__":
        mcp.run()

except Exception as e:
    import traceback

    print(" MCP startup failed")
    traceback.print_exc()
    sys.exit(1)
