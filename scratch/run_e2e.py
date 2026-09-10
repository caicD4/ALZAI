import sys
import asyncio
from main import run_pipeline_demo

async def run_all():
    print("=== REQUEST A ===")
    await run_pipeline_demo("sam altman is secretly evil", format_arg="x_thread")

    print("\n\n=== REQUEST B ===")
    await run_pipeline_demo("Why modern AI agent architectures are shifting from single prompts to multi-agent orchestration", format_arg="linkedin")

    print("\n\n=== REQUEST C ===")
    await run_pipeline_demo("Explain mixture of experts", format_arg="article")

if __name__ == "__main__":
    asyncio.run(run_all())
