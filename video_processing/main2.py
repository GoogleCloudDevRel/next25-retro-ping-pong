import asyncio
from v2 import VideoProcessor


async def main():
    processor = VideoProcessor()
    await processor.run()

if __name__ == "__main__":
    asyncio.run(main())