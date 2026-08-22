import argparse
import json
import sys

from .board import Board
from .notation import apply_san, split_moves


def build_arg_parser():
    parser = argparse.ArgumentParser(
        prog="sanfen",
        description="Replay a sequence of SAN chess moves from the starting "
                     "position and report the resulting FEN.",
    )
    parser.add_argument(
        "moves",
        nargs="+",
        help='SAN move text, e.g. "1. e4 e5 2. Nf3 Nc6" (one quoted '
             "argument or several bare words both work)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON instead of plain text",
    )
    return parser


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    text = " ".join(args.moves)
    tokens = split_moves(text)
    board = Board.initial()
    played = []

    for token in tokens:
        try:
            apply_san(board, token)
        except ValueError as exc:
            if args.json:
                print(json.dumps({
                    "ok": False,
                    "error": str(exc),
                    "failed_move": token,
                    "moves_played": played,
                }))
            else:
                print(f"error on move '{token}': {exc}", file=sys.stderr)
                if played:
                    print(f"moves played before failure: {' '.join(played)}", file=sys.stderr)
            return 1
        played.append(token)

    fen = board.fen()

    if args.json:
        print(json.dumps({
            "ok": True,
            "fen": fen,
            "side_to_move": board.side_to_move,
            "fullmove_number": board.fullmove_number,
            "halfmove_clock": board.halfmove_clock,
            "moves_played": played,
        }))
    else:
        print(fen)
        side = "White" if board.side_to_move == "w" else "Black"
        print(f"{side} to move, move {board.fullmove_number}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
