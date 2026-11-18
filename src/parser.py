
import re
import json
from pathlib import Path


# Convert screenplay timestamps into seconds
def timestamp_to_seconds(timestamp):
    if not timestamp:
        return None

    minutes, seconds = timestamp.split(":")
    return round(int(minutes) * 60 + float(seconds), 2)


# Convert seconds back into screenplay timestamp format
def seconds_to_timestamp(total_seconds):
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:05.2f}"


# Extract episode-level information
def extract_episode_metadata(content):
    metadata = {}

    patterns = {
        "episode_number": r"EPISODE NUMBER:\s*(.+)",
        "logline": r"EPISODE LOGLINE:\s*(.+)",
        "continuity_notes": r"CONTINUITY NOTES:\s*(.+)"
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, content)
        metadata[key] = match.group(1).strip() if match else None

    return metadata


# Extract individual events from a scene
def extract_scene_events(scene_content, scene_number):

    events = []

    # Find blocks such as CAMERA, ACTION and character dialogue
    pattern = re.compile(
        r"^\*\*(?P<label>.+?):\*\*\s*\n"
        r"Start:\s*\((?P<start>\d{2}:\d{2}\.\d{2})\)"
        r"\s*\|\s*End:\s*\((?P<end>\d{2}:\d{2}\.\d{2})\)"
        r"\s*\n(?P<description>.*?)"
        r"(?=^\*\*.+?:\*\*|^SCENE\s+\d+|^--- SCRIPT END ---|\Z)",
        re.MULTILINE | re.DOTALL
    )

    for match in pattern.finditer(scene_content):

        label = match.group("label").strip()
        start = match.group("start")
        end = match.group("end")
        description = match.group("description").strip()

        # Identify event type
        if label == "CAMERA":
            event_type = "camera"
            character = None

        elif label == "ACTION":
            event_type = "action"
            character = None

        elif label == "SOUND FX":
            event_type = "sound_effect"
            character = None

        else:
            event_type = "dialogue"

            # Extract character name, excluding emotion description
            character = re.sub(r"\s*\([^)]*\)", "", label).strip()

        events.append({
            "scene_number": scene_number,
            "type": event_type,
            "label": label,
            "character": character,
            "start": start,
            "end": end,
            "start_seconds": timestamp_to_seconds(start),
            "end_seconds": timestamp_to_seconds(end),
            "description": description
        })

    return events


# Parse one complete screenplay
def parse_screenplay(file_path):

    file_path = Path(file_path)
    content = file_path.read_text(encoding="utf-8-sig")

    metadata = extract_episode_metadata(content)

    scenes = []

    # Split the screenplay into individual scenes
    scene_pattern = re.compile(
        r"^SCENE\s+(\d+)\s*\n(.*?)"
        r"(?=^SCENE\s+\d+|^--- SCRIPT END ---|\Z)",
        re.MULTILINE | re.DOTALL
    )

    for match in scene_pattern.finditer(content):

        scene_number = int(match.group(1))
        scene_content = match.group(2)

        heading_match = re.search(
            r"Scene heading:\s*(.+)",
            scene_content
        )

        start_match = re.search(
            r"Scene start:\s*(\d{2}:\d{2}\.\d{2})",
            scene_content
        )

        end_match = re.search(
            r"Scene end:\s*(\d{2}:\d{2}\.\d{2})",
            scene_content
        )

        scene = {
            "scene_number": scene_number,
            "heading": heading_match.group(1).strip()
                       if heading_match else None,
            "start": start_match.group(1)
                     if start_match else None,
            "end": end_match.group(1)
                   if end_match else None,
            "start_seconds": timestamp_to_seconds(
                start_match.group(1) if start_match else None
            ),
            "end_seconds": timestamp_to_seconds(
                end_match.group(1) if end_match else None
            ),
            "events": extract_scene_events(
                scene_content, scene_number
            )
        }

        scenes.append(scene)

    # Combine all events for convenient analysis
    all_events = []

    for scene in scenes:
        all_events.extend(scene["events"])

    return {
        "file_name": file_path.name,
        **metadata,
        "total_scenes": len(scenes),
        "total_events": len(all_events),
        "scenes": scenes,
        "events": all_events
    }


# Parse every screenplay in the input directory
def parse_all_episodes(input_directory, output_file):

    input_directory = Path(input_directory)

    files = sorted(input_directory.glob("*.txt"))

    results = []

    for file_path in files:

        try:
            result = parse_screenplay(file_path)
            results.append(result)

            print(
                f"Processed {result['episode_number']} | "
                f"Scenes: {result['total_scenes']} | "
                f"Events: {result['total_events']}"
            )

        except Exception as error:
            print(f"Error processing {file_path.name}: {error}")

    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(results, file, indent=4, ensure_ascii=False)

    print("\n========== PARSING SUMMARY ==========")
    print(f"Total files found: {len(files)}")
    print(f"Successfully processed: {len(results)}")
    print(f"Saved output: {output_file}")

    return results


if __name__ == "__main__":

    parse_all_episodes(
        input_directory="data/scripts",
        output_file="outputs/parsed_episodes.json"
    )
