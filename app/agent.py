# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
import os
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools import FunctionTool, ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from app.a2ui_utils import a2ui_callback

# Hardcoded project ID and Cloud Storage bucket as required for Agent Platform compatibility
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-03-4842e70d567f"
GCS_BUCKET_NAME = "fitpulse-coach-public-4842e70d567f"

# Load Agent Engine resource name from deployment_metadata.json
AGENT_ENGINE_RESOURCE_NAME = "projects/673706048933/locations/us-east1/reasoningEngines/8162226767818391552"
metadata_file = Path(__file__).resolve().parent.parent / "deployment_metadata.json"
if metadata_file.exists():
    try:
        data = json.loads(metadata_file.read_text())
        AGENT_ENGINE_RESOURCE_NAME = data.get("remote_agent_runtime_id", AGENT_ENGINE_RESOURCE_NAME)
    except Exception:
        pass


def get_firestore_client() -> firestore.Client:
    """Helper to return a Firestore client targeting the hardcoded project ID."""
    return firestore.Client(project=FIRESTORE_PROJECT_ID)


async def generate_workout_badge_image(prompt: str, tool_context: ToolContext) -> str:
    """Generate a custom workout badge or fitness achievement image using gemini-3.1-flash-lite-image in the global region.

    Saves the image as a session artifact for the local Playground, uploads the bytes directly to a public Cloud Storage bucket, and returns its public HTTPS URL.

    Args:
        prompt: Description of the workout badge or image to generate (e.g. 'Gold fitness badge with text 100 PUSHUPS CLUB').

    Returns:
        The public HTTPS Cloud Storage URL (https://storage.googleapis.com/<bucket>/<object>) of the generated image.
    """
    genai_client = genai.Client(
        vertexai=True,
        project=FIRESTORE_PROJECT_ID,
        location="global",
    )

    response = genai_client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
        ),
    )

    image_bytes = None
    mime_type = "image/png"

    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                image_bytes = part.inline_data.data
                if part.inline_data.mime_type:
                    mime_type = part.inline_data.mime_type
                break

    if not image_bytes:
        return "Error: Failed to generate image bytes from gemini-3.1-flash-lite-image model."

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    ext = "jpg" if "jpeg" in mime_type else "png"
    filename = f"workout_badge_{timestamp}.{ext}"

    # (1) Save with tool_context.save_artifact for Playground Artifacts panel
    artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    await tool_context.save_artifact(filename=filename, artifact=artifact_part)

    # (2) Upload image bytes directly to public Cloud Storage bucket
    storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
    return public_url


import base64

async def generate_fitness_video(prompt: str, tool_context: ToolContext) -> str:
    """Generate a short fitness or bodybuilding video using Google's Omni model (gemini-omni-flash-preview) in the global region.

    Saves the video with tool_context.save_artifact for the Playground's Artifacts panel, uploads the video bytes directly to the public Cloud Storage bucket, and returns its public HTTPS URL.

    Args:
        prompt: Description of the fitness or bodybuilding video to generate (e.g. 'A short 5-second cinematic video of a bodybuilder performing heavy dumbbell curls').

    Returns:
        The public HTTPS Cloud Storage URL (https://storage.googleapis.com/<bucket>/<object>) of the generated video.
    """
    genai_client = genai.Client(
        vertexai=True,
        project=FIRESTORE_PROJECT_ID,
        location="global",
    )

    interaction = genai_client.interactions.create(
        model="gemini-omni-flash-preview",
        input=prompt,
    )

    video_bytes = None
    if hasattr(interaction, "output_video") and interaction.output_video and getattr(interaction.output_video, "data", None):
        raw_data = interaction.output_video.data
        if isinstance(raw_data, str):
            try:
                video_bytes = base64.b64decode(raw_data)
            except Exception:
                video_bytes = raw_data.encode("utf-8")
        else:
            video_bytes = raw_data
    elif hasattr(interaction, "outputs") and interaction.outputs:
        for out in interaction.outputs:
            if getattr(out, "output_video", None) and getattr(out.output_video, "data", None):
                raw_data = out.output_video.data
                if isinstance(raw_data, str):
                    try:
                        video_bytes = base64.b64decode(raw_data)
                    except Exception:
                        video_bytes = raw_data.encode("utf-8")
                else:
                    video_bytes = raw_data
                break

    if not video_bytes:
        return "Error: Failed to generate video bytes from gemini-omni-flash-preview model."

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"workout_video_{timestamp}.mp4"

    # (1) Save with tool_context.save_artifact for Playground Artifacts panel
    artifact_part = types.Part.from_bytes(data=video_bytes, mime_type="video/mp4")
    await tool_context.save_artifact(filename=filename, artifact=artifact_part)

    # (2) Upload video bytes directly to public Cloud Storage bucket
    storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(video_bytes, content_type="video/mp4")

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
    return public_url


def get_muscle_anatomy_info(muscle_name: str = "") -> list[dict]:
    """Fetch real anatomical muscle data and SVG diagram URLs from the public wger Workout Manager API.

    Args:
        muscle_name: Optional muscle name or body part (e.g. Chest, Biceps, Abs, Quads, Glutes) to filter by.

    Returns:
        A list of matching muscle objects with scientific names, common English names, and main/secondary SVG diagram URLs.
    """
    api_key = os.getenv("WGER_API_KEY", "")
    url = "https://wger.de/api/v2/muscle/"

    headers = {"User-Agent": "FitPulseCoach/1.0"}
    if api_key:
        headers["Authorization"] = f"Token {api_key}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            results = data.get("results", [])
            if muscle_name:
                q = muscle_name.lower().strip()
                filtered = [
                    m
                    for m in results
                    if q in m.get("name", "").lower() or q in m.get("name_en", "").lower()
                ]
                return filtered
            return results
    except Exception as e:
        return [{"error": f"Failed to fetch muscle anatomy info: {str(e)}"}]


def calculate_fitness_metrics(
    metric_type: str,
    weight_lbs: float = 0.0,
    reps: int = 0,
    height_inches: float = 0.0,
    age: int = 0,
    gender: str = "male",
) -> dict:
    """Calculate fitness metrics like 1RM (one-rep max), BMI, or BMR.

    Args:
        metric_type: Metric to calculate: '1rm', 'bmi', or 'bmr'.
        weight_lbs: Body weight or weight lifted in pounds.
        reps: Repetitions completed (required for 1rm).
        height_inches: Body height in inches (required for bmi and bmr).
        age: Age in years (required for bmr).
        gender: 'male' or 'female' (used for bmr).

    Returns:
        A dictionary containing the calculated metric results.
    """
    m_type = metric_type.lower().strip()

    if m_type == "1rm":
        if reps <= 0 or weight_lbs <= 0:
            return {"error": "weight_lbs and reps must be positive for 1RM calculation."}
        one_rep_max = round(weight_lbs * (1 + reps / 30.0), 1)
        return {
            "metric": "1RM (One-Rep Max)",
            "weight_lbs": weight_lbs,
            "reps": reps,
            "estimated_1rm_lbs": one_rep_max,
        }

    elif m_type == "bmi":
        if height_inches <= 0 or weight_lbs <= 0:
            return {"error": "weight_lbs and height_inches must be positive for BMI calculation."}
        bmi = round((weight_lbs / (height_inches ** 2)) * 703, 1)
        category = "Underweight" if bmi < 18.5 else ("Normal weight" if bmi < 25 else ("Overweight" if bmi < 30 else "Obese"))
        return {
            "metric": "BMI (Body Mass Index)",
            "bmi": bmi,
            "category": category,
        }

    elif m_type == "bmr":
        if height_inches <= 0 or weight_lbs <= 0 or age <= 0:
            return {"error": "weight_lbs, height_inches, and age must be positive for BMR calculation."}
        weight_kg = weight_lbs * 0.453592
        height_cm = height_inches * 2.54
        gender_offset = 5 if gender.lower() == "male" else -161
        bmr = round(10 * weight_kg + 6.25 * height_cm - 5 * age + gender_offset)
        return {
            "metric": "BMR (Basal Metabolic Rate)",
            "bmr_calories": bmr,
            "estimated_tdee_sedentary": round(bmr * 1.2),
            "estimated_tdee_moderate": round(bmr * 1.55),
        }

    else:
        return {"error": f"Unknown metric_type '{metric_type}'. Supported metric_types are '1rm', 'bmi', and 'bmr'."}


def search_exercise_catalog(muscle_group: str = "", equipment: str = "") -> list[dict]:
    """Search the exercise catalog in Firestore.

    Args:
        muscle_group: Filter by target muscle group (e.g. Chest, Legs, Back, Abs).
        equipment: Filter by equipment required (e.g. None, Barbell, Dumbbell).

    Returns:
        A list of matching exercise documents from Firestore.
    """
    db = get_firestore_client()
    docs = db.collection("exercises").stream()

    results = []
    for doc in docs:
        data = doc.to_dict()
        if muscle_group and muscle_group.lower() not in data.get("muscle_group", "").lower():
            continue
        if equipment and equipment.lower() not in data.get("equipment", "").lower():
            continue
        results.append(data)

    return results


def log_workout_entry(user_id: str, exercise_name: str, sets: int, reps: int, weight_lbs: float = 0.0) -> str:
    """Log a completed workout entry into Firestore.

    Args:
        user_id: The ID of the user logging the workout.
        exercise_name: Name of the exercise completed (e.g. Push-Ups, Barbell Squat).
        sets: Number of sets completed.
        reps: Number of reps per set.
        weight_lbs: Weight used in pounds (0 for bodyweight).

    Returns:
        A string confirming the workout log creation.
    """
    db = get_firestore_client()
    log_data = {
        "user_id": user_id,
        "exercise_name": exercise_name,
        "sets": sets,
        "reps": reps,
        "weight_lbs": weight_lbs,
        "logged_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    doc_ref = db.collection("workout_logs").document()
    doc_ref.set(log_data)
    return f"Successfully logged workout for {user_id}: {sets} sets of {reps} reps for '{exercise_name}'."


def get_user_workout_history(user_id: str) -> list[dict]:
    """Retrieve the workout history for a given user from Firestore.

    Args:
        user_id: The ID of the user whose history is requested.

    Returns:
        A list of logged workout entries.
    """
    db = get_firestore_client()
    query = db.collection("workout_logs").where("user_id", "==", user_id).stream()

    history = [doc.to_dict() for doc in query]
    return history


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        city: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    elif "nyc" in query.lower() or "new york" in query.lower():
        tz_identifier = "America/New_York"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are FitPulse Coach, a helpful AI fitness assistant. "
        "You MUST remember all workout repetitions (reps), sets, weights, exercise performance, fitness goals, and user preferences across conversations. "
        "Whenever the user states their reps, sets, or exercise performance (e.g. 'I did 50 pushups', '10 reps of 100lb bench press'), "
        "explicitly log and confirm the reps so they are extracted into long-term Memory Bank storage. "
        "You can search the exercise catalog, log workout entries, retrieve workout history, "
        "calculate fitness metrics (1RM, BMI, BMR), fetch real anatomical muscle information, "
        "generate workout achievement badge images, execute Python code safely in a sandbox using the execute_code tool, "
        "and provide weather or time information."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None


sandbox_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=AGENT_ENGINE_RESOURCE_NAME,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=a2ui_instruction,
    code_executor=sandbox_executor,
    tools=[
        PreloadMemoryTool(),
        generate_workout_badge_image,
        generate_fitness_video,
        get_muscle_anatomy_info,
        calculate_fitness_metrics,
        search_exercise_catalog,
        log_workout_entry,
        get_user_workout_history,
        get_weather,
        get_current_time,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
