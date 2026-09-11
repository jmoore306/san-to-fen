import argparse
import json
import sys

from .board import Board
from .notation import apply_san, moves_to_square, split_moves


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
    parser.add_argument(
        "--from-fen",
        metavar="FEN",
        help="start from this position instead of the initial one",
    )
    parser.add_argument(
        "--explain",
        metavar="SQUARE",
        help="after replaying the moves, list SAN for every legal move "
             "that could put a piece on this square next",
    )
    return parser


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    text = " ".join(args.moves)
    tokens = split_moves(text)

    if args.from_fen is None:
        board = Board.initial()
    else:
        try:
            board = Board.from_fen(args.from_fen)
        except ValueError as exc:
            if args.json:
                print(json.dumps({
                    "ok": False,
                    "error": f"invalid --from-fen value: {exc}",
                    "failed_move": None,
                    "moves_played": [],
                }))
            else:
                print(f"invalid --from-fen value: {exc}", file=sys.stderr)
            return 1

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

    reachable_by = None
    if args.explain is not None:
        try:
            reachable_by = moves_to_square(board, args.explain)
        except ValueError as exc:
            if args.json:
                print(json.dumps({
                    "ok": False,
                    "error": f"invalid --explain value: {exc}",
                    "failed_move": None,
                    "moves_played": played,
                }))
            else:
                print(f"invalid --explain value: {exc}", file=sys.stderr)
            return 1

    if args.json:
        result = {
            "ok": True,
            "fen": fen,
            "side_to_move": board.side_to_move,
            "fullmove_number": board.fullmove_number,
            "halfmove_clock": board.halfmove_clock,
            "moves_played": played,
        }
        if args.explain is not None:
            result["explain_square"] = args.explain
            result["reachable_by"] = reachable_by
        print(json.dumps(result))
    else:
        print(fen)
        side = "White" if board.side_to_move == "w" else "Black"
        print(f"{side} to move, move {board.fullmove_number}")
        if args.explain is not None:
            if reachable_by:
                print(f"moves that could reach {args.explain}: {', '.join(reachable_by)}")
            else:
                print(f"no legal move reaches {args.explain}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
