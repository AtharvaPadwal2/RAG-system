import chess


BOARD_EXAMPLES = {
    "Understanding a knight fork": {
        "fen": "4k3/8/2q1r3/8/3N4/8/8/6K1 w - - 0 1",
        "moves": [],
        "arrows": [
            ["d4", "c6"],
            ["d4", "e6"],
        ],
        "highlights": ["d4", "c6", "e6"],
        "caption": (
            "The white knight on d4 attacks the black queen on c6 "
            "and rook on e6. This illustrates a fork; whether it "
            "wins material depends on the position."
        ),
    },
    "Understanding en passant": {
        "fen": "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2",
        "moves": ["e5d6"],
        "arrows": [
            ["e5", "d6"],
        ],
        "highlights": ["e5", "d5", "d6"],
        "caption": (
            "Black has just played d7-d5. White can capture "
            "en passant with e5xd6, removing the pawn from d5."
        ),
    },
}


def get_board_example(lesson_title: str):
    return BOARD_EXAMPLES.get(lesson_title)


if __name__ == "__main__":
    for title, example in BOARD_EXAMPLES.items():
        board = chess.Board(example["fen"])

        if not board.is_valid():
            raise ValueError(f"Invalid board: {title}")

        if title == "Understanding a knight fork":
            knight = chess.parse_square("d4")
            targets = {
                chess.parse_square("c6"),
                chess.parse_square("e6"),
            }

            if not targets.issubset(set(board.attacks(knight))):
                raise ValueError("Knight does not attack both targets.")

        for uci in example["moves"]:
            move = chess.Move.from_uci(uci)

            if move not in board.legal_moves:
                raise ValueError(f"Illegal demonstration move: {uci}")

            if title == "Understanding en passant":
                if not board.is_en_passant(move):
                    raise ValueError("Move is not an en passant capture.")

            board.push(move)

        print("Verified:", title)