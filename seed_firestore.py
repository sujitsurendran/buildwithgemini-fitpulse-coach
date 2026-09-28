"""Seed script for FitPulse Coach Firestore collection."""

import google.auth
from google.auth.transport.requests import Request
from google.cloud import firestore

# Hardcoded project ID as required to prevent project number resolution issues on Agent Platform
PROJECT_ID = "qwiklabs-gcp-03-4842e70d567f"


def seed_database():
    creds, _ = google.auth.default()
    if hasattr(creds, "refresh"):
        try:
            creds.refresh(Request())
        except Exception:
            pass

    db = firestore.Client(project=PROJECT_ID, credentials=creds)

    exercises = [
        {
            "id": "push_ups",
            "name": "Push-Ups",
            "category": "Bodyweight",
            "muscle_group": "Chest",
            "equipment": "None",
            "difficulty": "Beginner",
            "instructions": "Place hands shoulder-width apart, keep body in a straight line, lower chest to floor and push back up.",
        },
        {
            "id": "barbell_squat",
            "name": "Barbell Back Squat",
            "category": "Strength",
            "muscle_group": "Legs",
            "equipment": "Barbell",
            "difficulty": "Intermediate",
            "instructions": "Rest barbell across upper back, bend knees and hips to lower into squat, drive through heels to stand.",
        },
        {
            "id": "dumbbell_row",
            "name": "Single-Arm Dumbbell Row",
            "category": "Strength",
            "muscle_group": "Back",
            "equipment": "Dumbbell",
            "difficulty": "Beginner",
            "instructions": "Place one knee and hand on bench, pull dumbbell to hip with elbow tucked, lower under control.",
        },
        {
            "id": "plank",
            "name": "Forearm Plank",
            "category": "Core",
            "muscle_group": "Abs",
            "equipment": "None",
            "difficulty": "Beginner",
            "instructions": "Hold body on forearms and toes in a rigid straight line, engaging core and glutes.",
        },
        {
            "id": "dumbbell_bench_press",
            "name": "Dumbbell Bench Press",
            "category": "Strength",
            "muscle_group": "Chest",
            "equipment": "Dumbbell",
            "difficulty": "Intermediate",
            "instructions": "Lie back on bench with dumbbells at chest height, press upward until arms are extended, lower slowly.",
        },
    ]

    for ex in exercises:
        doc_ref = db.collection("exercises").document(ex["id"])
        doc_ref.set(ex)
        print(f"Seeded exercise: {ex['name']}")

    print("Firestore seeding complete!")


if __name__ == "__main__":
    seed_database()
