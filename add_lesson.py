import json
from pathlib import Path

path = Path(__file__).resolve().parent / "data" / "lessons.json"
lessons = json.loads(path.read_text(encoding="utf-8"))

new_lesson = {
    "title": "Understanding en passant",
    "topic": "rules",
    "difficulty": "beginner",
    "content": (
        "En passant is a special pawn capture. When an opposing pawn "
        "moves two squares from its starting square and lands beside "
        "your pawn, your pawn may capture it as though it had moved "
        "only one square. This capture is available only on your "
        "immediately following move. A white pawn must be on its fifth "
        "rank, or a black pawn on its fourth rank, to make this capture. "
        "For example, with a white pawn on e5, if Black plays d7-d5, "
        "White may play e5xd6 en passant, removing the black pawn "
        "from d5. The capture must be legal: it cannot leave your "
        "own king in check."
    ),
}

if any(lesson["title"] == new_lesson["title"] for lesson in lessons):
    print("Lesson already exists; no changes made.")
else:
    lessons.append(new_lesson)
    path.write_text(
        json.dumps(lessons, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print("Added draft lesson:", new_lesson["title"])