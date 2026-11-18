
import json
import re
from pathlib import Path
from collections import Counter, defaultdict


# Dramatic signals to help identify promo opportunities
DRAMA_CATEGORIES = {
    "betrayal": [
        "betray", "cheat", "abandon", "lied", "deceive",
        "changed my mind", "unfaithful"
    ],

    "revenge": [
        "revenge", "pay for this", "regret", "punish",
        "make you suffer", "destroy you"
    ],

    "romance": [
        "love", "kiss", "heart", "marry", "husband",
        "wife", "desire", "passion"
    ],

    "confrontation": [
        "face me", "how dare you", "listen to me",
        "tell me the truth", "you cannot", "stop"
    ],

    "threat": [
        "kill", "threat", "danger", "destroy",
        "warn", "murder"
    ],

    "revelation": [
        "secret", "truth", "reveal", "surprise",
        "actually", "confess", "hidden"
    ]
}


EMOTIONAL_SIGNALS = {
    "anger": ["angry", "furious", "rage", "outraged"],
    "sadness": ["heartbroken", "crying", "devastated", "grief"],
    "shock": ["shocked", "stunned", "gasping", "disbelief"],
    "fear": ["terrified", "afraid", "fear", "panic"],
    "romantic": ["seductive", "loving", "passionate", "intimate"]
}


# Identify drama categories in text
def detect_drama_categories(text):

    text = text.lower()
    detected = []

    for category, keywords in DRAMA_CATEGORIES.items():

        if any(keyword in text for keyword in keywords):
            detected.append(category)

    return detected


# Identify emotional signals
def detect_emotions(text):

    text = text.lower()
    emotions = []

    for emotion, keywords in EMOTIONAL_SIGNALS.items():

        if any(keyword in text for keyword in keywords):
            emotions.append(emotion)

    return emotions


# Extract characters from dialogue events
def extract_characters(events):

    characters = Counter()

    for event in events:

        if event.get("type") == "dialogue":

            character = event.get("character")

            if character:
                characters[character] += 1

    return dict(characters.most_common())


# Identify important dramatic events
def extract_dramatic_moments(events):

    moments = []

    for event in events:

        description = event.get("description", "")
        label = event.get("label", "")

        combined_text = f"{label} {description}"

        categories = detect_drama_categories(combined_text)
        emotions = detect_emotions(combined_text)

        if categories or emotions:

            moments.append({
              "scene_number": event.get("scene_number"),
              "type": event.get("type"),
              "character": event.get("character"),
              "start": event.get("start"),
              "end": event.get("end"),

    # Added fields for candidate generation
              "start_seconds": event.get("start_seconds"),
              "end_seconds": event.get("end_seconds"),

              "description": description,
              "drama_categories": categories,
              "emotions": emotions
            })

    return moments


# Analyze an individual episode
def analyze_episode(episode):

    events = episode.get("events", [])

    category_counts = Counter()
    emotion_counts = Counter()

    dramatic_moments = extract_dramatic_moments(events)

    for moment in dramatic_moments:

        category_counts.update(moment["drama_categories"])
        emotion_counts.update(moment["emotions"])

    return {
        "episode_number": episode.get("episode_number"),
        "file_name": episode.get("file_name"),
        "logline": episode.get("logline"),
        "continuity_notes": episode.get("continuity_notes"),

        "total_scenes": episode.get("total_scenes", 0),
        "total_events": len(events),

        "characters": extract_characters(events),

        "drama_categories": dict(category_counts),
        "emotional_signals": dict(emotion_counts),

        "dramatic_moments": dramatic_moments
    }


# Analyze all episodes
def analyze_all_episodes(input_file, output_file):

    with open(input_file, "r", encoding="utf-8") as file:
        episodes = json.load(file)

    analyzed_episodes = []

    for episode in episodes:

        result = analyze_episode(episode)
        analyzed_episodes.append(result)

        print(
            f"{result['episode_number']} | "
            f"Characters: {len(result['characters'])} | "
            f"Dramatic moments: {len(result['dramatic_moments'])}"
        )

    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(
            analyzed_episodes,
            file,
            indent=4,
            ensure_ascii=False
        )

    print("\n========== STORY ANALYSIS SUMMARY ==========")
    print("Episodes analyzed:", len(analyzed_episodes))
    print("Output saved:", output_file)

    return analyzed_episodes


if __name__ == "__main__":

    analyze_all_episodes(
        input_file="outputs/parsed_episodes.json",
        output_file="outputs/story_context.json"
    )
