
import json
from pathlib import Path


# Candidate window lengths in seconds
WINDOW_DURATIONS = [20, 30, 40, 50, 60]

# Small offsets allow the hook to begin just before a dramatic event
START_OFFSETS = [0, 1.5, 3]


def seconds_to_timestamp(seconds):
    minutes = int(seconds // 60)
    remaining = seconds % 60
    return f"{minutes:02d}:{remaining:05.2f}"


def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


# Collect dramatic events that overlap a candidate window
def get_dramatic_moments(moments, start, end):

    selected = []

    for moment in moments:

        event_start = moment.get("start_seconds")

        if event_start is None:
            continue

        event_end = moment.get("end_seconds")

        if event_end is None:
            event_end = event_start

        if event_start <= end and event_end >= start:
            selected.append(moment)

    return selected


# Find all screenplay events inside a time window
def get_window_events(events, start, end):

    selected = []

    for event in events:

        event_start = event.get("start_seconds")

        if event_start is None:
            continue

        event_end = event.get("end_seconds")

        if event_end is None:
            event_end = event_start

        if event_start <= end and event_end >= start:
            selected.append(event)

    return sorted(
        selected,
        key=lambda x: x["start_seconds"]
    )


# Calculate preliminary hook signals
def calculate_hook_score(events, window_start):

    score = 0

    for event in events:

        event_start = event["start_seconds"]

        relative_start = event_start - window_start

        if 0 <= relative_start <= 3:

            if event.get("type") == "dialogue":
                score += 3

            elif event.get("type") == "action":
                score += 2

            elif event.get("type") == "camera":
                score += 1

    return min(score, 10)


# Calculate preliminary dramatic ending signals
def calculate_ending_score(events, window_end):

    score = 0

    suspense_words = [
        "secret", "truth", "wait", "who",
        "why", "never", "impossible",
        "what", "stop", "no"
    ]

    for event in events:

        event_end = event.get("end_seconds")

        if event_end is None:
            continue

        # Check events occurring in the final 5 seconds
        if 0 <= window_end - event_end <= 5:

            description = event.get(
                "description", ""
            ).lower()

            if event.get("type") == "dialogue":
                score += 2

            if any(word in description for word in suspense_words):
                score += 2

            if event.get("type") == "action":
                score += 1

    return min(score, 10)


# Generate candidate windows for one episode
def generate_episode_candidates(episode, story):

    events = episode.get("events", [])

    moments = story.get("dramatic_moments", [])

    if not events:
        return []

    # Determine episode duration from scene boundaries
    scene_ends = [
        scene["end_seconds"]
        for scene in episode.get("scenes", [])
        if scene.get("end_seconds") is not None
    ]

    if not scene_ends:
        return []

    episode_duration = max(scene_ends)

    # Sort all events by timestamp
    events = sorted(
        events,
        key=lambda x: x["start_seconds"]
    )

    # Generate possible starting positions
    start_positions = set()

    for event in events:

        event_start = event["start_seconds"]

        for offset in START_OFFSETS:

            start = max(0, event_start - offset)

            start_positions.add(round(start, 2))

    candidates = []

    for start in sorted(start_positions):

        for duration in WINDOW_DURATIONS:

            end = round(start + duration, 2)

            # Do not exceed episode duration
            if end > episode_duration:
                continue

            window_events = get_window_events(
                events, start, end
            )

            if not window_events:
                continue

            dramatic_moments = get_dramatic_moments(
                moments, start, end
            )

            hook_score = calculate_hook_score(
                window_events, start
            )

            ending_score = calculate_ending_score(
                window_events, end
            )

            # Preliminary score, not final promo quality
            drama_score = min(
                len(dramatic_moments) * 1.5,
                10
            )

            preliminary_score = round(
                hook_score * 0.35
                + ending_score * 0.35
                + drama_score * 0.30,
                2
            )

            candidates.append({

                "episode_number": episode.get(
                    "episode_number"
                ),

                "start": seconds_to_timestamp(start),
                "end": seconds_to_timestamp(end),

                "start_seconds": start,
                "end_seconds": end,

                "duration": duration,

                "hook_score": hook_score,
                "ending_score": ending_score,
                "drama_score": round(drama_score, 2),

                "preliminary_score": preliminary_score,

                "event_count": len(window_events),

                "dramatic_moment_count": len(
                    dramatic_moments
                ),

                "events": window_events,

                "dramatic_moments": dramatic_moments
            })

    return candidates


# Remove duplicate candidates
def remove_duplicate_candidates(candidates):

    unique = {}

    for candidate in candidates:

        key = (
            candidate["episode_number"],
            candidate["start"],
            candidate["end"]
        )

        unique[key] = candidate

    return list(unique.values())


# Generate candidates for all episodes
def generate_all_candidates(
    parsed_file,
    story_file,
    output_file
):

    episodes = load_json(parsed_file)
    stories = load_json(story_file)

    # Match story analysis with parsed episodes
    story_lookup = {
        story["episode_number"]: story
        for story in stories
    }

    all_candidates = []

    for episode in episodes:

        episode_number = episode["episode_number"]

        story = story_lookup.get(episode_number)

        if not story:
            print(
                f"Skipping {episode_number}: "
                "Story analysis missing"
            )
            continue

        candidates = generate_episode_candidates(
            episode, story
        )

        all_candidates.extend(candidates)

        print(
            f"{episode_number} | "
            f"Candidates generated: {len(candidates)}"
        )

    all_candidates = remove_duplicate_candidates(
        all_candidates
    )

    # Sort by preliminary score
    all_candidates.sort(
        key=lambda x: x["preliminary_score"],
        reverse=True
    )

    output_file = Path(output_file)
    output_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with output_file.open(
        "w", encoding="utf-8"
    ) as file:

        json.dump(
            all_candidates,
            file,
            indent=4,
            ensure_ascii=False
        )

    print("\n========== CANDIDATE SUMMARY ==========")

    print("Episodes processed:", len(episodes))
    print("Total candidates:", len(all_candidates))

    if all_candidates:
        print(
            "Highest preliminary score:",
            all_candidates[0]["preliminary_score"]
        )

    print("Output saved:", output_file)

    return all_candidates


if __name__ == "__main__":

    generate_all_candidates(
        parsed_file="outputs/parsed_episodes.json",
        story_file="outputs/story_context.json",
        output_file="outputs/candidates.json"
    )
