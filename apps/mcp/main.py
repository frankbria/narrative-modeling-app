# apps/mcp/main.py
import sys
import os

try:
    import uvicorn
    from mcp.server.fastmcp import FastMCP

    from auth import BearerAuthMiddleware, require_api_key
    from tools.eda_summary import EdaInput, run_eda_summary

    mcp = FastMCP("Narrative Modeling Application")

    @mcp.tool()
    async def eda_summary_tool(params: EdaInput) -> dict:
        """Generate an EDA summary for a dataset the caller owns.

        Accepts a `dataset_id` and `user_id`; the S3 location is resolved and
        ownership-checked server-side.
        """
        return await run_eda_summary(params)

    if __name__ == "__main__":
        # Bind to localhost by default: the only intended caller is the backend.
        host = os.environ.get("MCP_HOST", "127.0.0.1")
        port = int(os.environ.get("PORT", 10000))

        # Fail closed: never expose the tool (S3-reading) surface without a token.
        try:
            api_key = require_api_key(os.environ.get("MCP_API_KEY"))
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        app = BearerAuthMiddleware(mcp.sse_app(), api_key)
        uvicorn.run(app, host=host, port=port)

except SystemExit:
    raise
except Exception:
    import traceback

    print(" MCP startup failed")
    traceback.print_exc()
    sys.exit(1)
