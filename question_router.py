import re

from chat_rag import ask_chess
from game_search import search_games
from opening_search import search_openings


def answer_question(question: str):
    question = question.strip()

    if not question or len(question) > 1000:
        raise ValueError("Enter a question between 1 and 1,000 characters.")

    # Explicit commands first; other questions use lesson retrieval.
    command = re.fullmatch(
        r"show\s+(opening|games)\s+(.+)",
        question,
        flags=re.IGNORECASE,
    )

    if not command:
        return ask_chess(question)

    kind = command.group(1).lower()
    name = command.group(2).strip().rstrip("?.!").strip()

    if not name or len(name) > 100:
        return {
            "answer": "Enter an opening name between 1 and 100 characters.",
            "sources": [],
            "board_examples": [],
            "status": "no_match",
        }

    if kind == "opening":
        boards = search_openings(name, limit=3)
        answer = (
            "Here are matching opening lines from our game dataset. "
            "Use Next and Previous to replay them."
        )
    else:
        boards = search_games(name, limit=3)
        answer = (
            "Here are matching example games from our dataset. "
            "These are recorded games, not recommendations for best play."
        )

    if not boards:
        return {
            "answer": "No matching records found in our dataset.",
            "sources": [],
            "board_examples": [],
            "status": "no_match",
        }

    return {
        "answer": answer,
        "sources": [],
        "board_examples": boards,
        "status": "database_result",
    }