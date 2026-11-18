
import json
import requests
from pathlib import Path


# ---------------- CONFIGURATION ----------------

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:3b"

INPUT_FILE = "outputs/candidates.json"
OUTPUT_FILE = "outputs/llm_evaluations.json"

# Start small to test the model
TOP_CANDIDATES = 20


# ---------------- PREPARE CANDIDATE TEXT ----------------

def prepare_candidate(candidate):

    timeline = []

    events = sorted(
        candidate.get("events", []),
        key=lambda x: x.get("start_seconds", 0)
    )

    for event in events:

        event_type = event.get("type", "unknown")
        character = event.get("character") or event.get("label") or "NARRATION"

        timeline.append({
            "start": event.get("start"),
            "end": event.get("end"),
            "type": event_type,
            "character": character,
            "description": event.get("description", "")
        })

    return {
        "episode": candidate.get("episode_number"),
        "clip_start": candidate.get("start"),
        "clip_end": candidate.get("end"),
        "duration": candidate.get("duration"),
        "timeline": timeline
    }


# ---------------- BUILD LLM PROMPT ----------------


def build_prompt(candidate_data):

    return f"""
You are an experienced short-form drama promo editor.

Your task is to evaluate a screenplay clip for
Instagram Reels, TikTok and YouTube Shorts.

Evaluate the actual dialogue, actions and events.

CLIP:
{json.dumps(candidate_data, indent=2, ensure_ascii=False)}

Evaluate these three criteria independently.

1. HOOK STRENGTH (1-10)

Evaluate ONLY the first 3 seconds.

Consider:
- Surprising dialogue
- Immediate conflict
- Strong visual action
- Mystery or suspense
- Emotional intensity

2. CLIFFHANGER QUALITY (1-10)

Evaluate the final moments.

Consider:
- Unanswered questions
- Unexpected revelations
- Threats
- Suspense
- Unresolved confrontations

3. STANDALONE CLARITY (1-10)

Evaluate whether a new viewer can understand:
- Who is involved?
- What is happening?
- What is at stake?

SCORING CALIBRATION:

Use the complete 1-10 scale.

1-2: Extremely weak. Almost no relevant promotional value.
3-4: Weak. Limited engagement or significant confusion.
5-6: Average. Some interesting moments, but noticeable weaknesses.
7-8: Strong. Compelling and suitable for promotion.
9-10: Excellent. Extremely engaging, clear and memorable.

IMPORTANT:
- Do not automatically assign 1 or 10.
- Do not give identical scores unless independently justified.
- A minor weakness does not justify a score of 1.
- Evaluate each criterion independently.
- Base every score on specific evidence in the clip.
- Do not invent dialogue or events.
- Do not reward dramatic keywords without considering context.
- A clip can have a strong hook but weak clarity.
- A clip can have excellent suspense but a weak opening.

Return ONLY valid JSON.

Use this exact structure:

{{
    "hook_score": 0,
    "cliffhanger_score": 0,
    "clarity_score": 0,
    "hook_analysis": "Explain using actual dialogue or action.",
    "cliffhanger_analysis": "Explain using the actual ending.",
    "clarity_analysis": "Explain what a new viewer understands.",
    "strengths": [],
    "weaknesses": [],
    "verdict": "STRONG"
}}

The three scores must be integers between 1 and 10.
The zeroes above are placeholders, NOT suggested scores.

Verdict rules:
- STRONG: Overall quality is 7 or above.
- MODERATE: Overall quality is 5 or above but below 7.
- WEAK: Overall quality is below 5.
"""


# ---------------- REMOVE DUPLICATE CANDIDATES ----------------

def remove_duplicate_candidates(candidates, overlap_threshold=0.80):

    selected = []

    # Candidates should already be sorted by preliminary score
    for candidate in candidates:

        episode = candidate.get("episode_number")
        start = candidate.get("start_seconds")
        end = candidate.get("end_seconds")

        is_duplicate = False

        for existing in selected:

            # Compare only candidates from the same episode
            if episode != existing.get("episode_number"):
                continue

            existing_start = existing.get("start_seconds")
            existing_end = existing.get("end_seconds")

            if None in (start, end, existing_start, existing_end):
                continue

            # Calculate overlapping duration
            overlap = max(
                0,
                min(end, existing_end) - max(start, existing_start)
            )

            duration_a = end - start
            duration_b = existing_end - existing_start

            shorter_duration = min(duration_a, duration_b)

            if shorter_duration <= 0:
                continue

            overlap_ratio = overlap / shorter_duration

            if overlap_ratio >= overlap_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            selected.append(candidate)

    return selected

# ---------------- EVALUATE ONE CANDIDATE ----------------

def evaluate_candidate(candidate):

    candidate_data = prepare_candidate(candidate)
    prompt = build_prompt(candidate_data)

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a strict promotional video evaluator. "
                    "Return valid JSON only."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.2
        }
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=300
    )

    response.raise_for_status()

    response_data = response.json()

    result_text = response_data["message"]["content"]

    evaluation = json.loads(result_text)

    # Validate and normalize scores
    score_fields = [
        "hook_score",
        "cliffhanger_score",
        "clarity_score"
    ]

    for field in score_fields:

        score = float(evaluation[field])

        if not 1 <= score <= 10:
            raise ValueError(f"Invalid {field}: {score}")

        evaluation[field] = score

    # Calculate our own overall score
    evaluation["overall_score"] = round(
        (
            evaluation["hook_score"] * 0.30
            + evaluation["cliffhanger_score"] * 0.40
            + evaluation["clarity_score"] * 0.30
        ),
        2
    )

    return evaluation


# ---------------- MAIN EVALUATION PIPELINE ----------------

def run_evaluation():

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        candidates = json.load(file)

    print("Total available candidates:", len(candidates))

    # Sort by preliminary score
    
# Sort by preliminary score
    candidates.sort(
    key=lambda x: x.get("preliminary_score", 0),
    reverse=True
    )

# Remove overlapping candidates
    candidates = remove_duplicate_candidates(candidates)

    print("Candidates after duplicate removal:", len(candidates))

# Select top candidates for LLM evaluation
    selected_candidates = candidates[:TOP_CANDIDATES]


    print("Candidates selected for LLM evaluation:", len(selected_candidates))

    results = []

    for index, candidate in enumerate(selected_candidates, start=1):

        print(
            f"\nEvaluating {index}/{len(selected_candidates)} | "
            f"{candidate.get('episode_number')} | "
            f"{candidate.get('start')} - {candidate.get('end')}"
        )

        try:

            evaluation = evaluate_candidate(candidate)

            result = {
                "episode_number": candidate.get("episode_number"),
                "start": candidate.get("start"),
                "end": candidate.get("end"),
                "duration": candidate.get("duration"),
                "preliminary_score": candidate.get("preliminary_score"),
                "llm_evaluation": evaluation
            }

            results.append(result)

            print("Hook:", evaluation["hook_score"])
            print("Cliffhanger:", evaluation["cliffhanger_score"])
            print("Clarity:", evaluation["clarity_score"])
            print("Overall:", evaluation["overall_score"])
            print("Verdict:", evaluation["verdict"])

        except Exception as error:

            print("Evaluation failed:", error)

    # Rank successful evaluations
    results.sort(
        key=lambda x: x["llm_evaluation"]["overall_score"],
        reverse=True
    )

    output_path = Path(OUTPUT_FILE)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            results,
            file,
            indent=4,
            ensure_ascii=False
        )

    print("\n========== LLM EVALUATION SUMMARY ==========")
    print("Candidates evaluated successfully:", len(results))
    print("Output saved:", output_path)


if __name__ == "__main__":
    run_evaluation()
