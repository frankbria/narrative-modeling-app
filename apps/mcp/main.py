from fastmcp import FastMCP
from tools.eda_summary import EdaInput, eda_summary

mcp = FastMCP("Narrative Modeling Application")


@mcp.tool()
async def eda_summary_tool(params: EdaInput) -> dict:
    """Generate an EDA summary for a given CSV file stored at an S3 URI."""
    return eda_summary(params)


if __name__ == "__main__":
    mcp.run()
