import asyncio
import os
import shutil
from pathlib import Path
from playwright.async_api import async_playwright

async def record():
    os.makedirs("demo_videos", exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir="demo_videos",
            record_video_size={"width": 1280, "height": 720}
        )
        page = await context.new_page()

        print("1. Opening FitPulse Coach at http://localhost:8080...")
        await page.goto("http://localhost:8080")
        await page.wait_for_timeout(2000)

        # Trigger upbeat lo-fi music playback
        print("Playing upbeat lo-fi background music...")
        await page.click("#lofiBtn")
        await page.wait_for_timeout(2000)

        print("2. Sending Prompt 1: Logging workout and calculating 1RM...")
        await page.fill("#input", "Log 3 sets of 10 pushups for athlete_alex and calculate my 1RM for 185 lbs x 8 reps")
        await page.wait_for_timeout(1000)
        await page.click("button.send-btn")

        # Wait for agent response
        await page.wait_for_timeout(10000)

        print("3. Sending Prompt 2: Rich tool call generating gold workout badge...")
        await page.fill("#input", "Generate my 100 Pushups Club gold achievement workout badge")
        await page.wait_for_timeout(1000)
        await page.click("button.send-btn")

        # Wait for badge generation and A2UI card render
        await page.wait_for_timeout(15000)

        # Get recorded video path before closing
        video = page.video
        video_path = await video.path() if video else None

        await context.close()
        await browser.close()
        print(f"Recorded video saved to: {video_path}")

        if video_path and os.path.exists(video_path):
            artifact_dir = Path("/config/.gemini/antigravity/brain/58785453-3853-4e19-804c-a33aa8f96782")
            target_path = artifact_dir / "demo_recording.webm"
            shutil.copy(video_path, target_path)
            print(f"Copied demo video to artifact directory: {target_path}")

if __name__ == "__main__":
    asyncio.run(record())
