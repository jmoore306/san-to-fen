"""Parsing and application of Standard Algebraic Notation (SAN) move text.

This handles the notation itself, geometric move resolution, and rejects
moves that leave the mover's own king in check, including castling out of,
through, or into check.
"""

import re

from .board import square_index, square_name

_MOVE_NUMBER_RE = re.compile(r"^\d+\.+(.*)$")
_RESULT_TOKENS = {"1-0", "0-1", "1/2-1/2", "*"}
_SQUARE_RE = re.compile(r"^[a-h][1-8]$")


def split_moves(text):
    """Turn a blob of PGN-ish move text into a flat list of SAN tokens,
    dropping move numbers ("12." or "12...") and result markers."""
    moves = []
    for raw in text.split():
        if raw in _RESULT_TOKENS:
            continue
        match = _MOVE_NUMBER_RE.match(raw)
        if match:
            remainder = match.group(1)
            if remainder:
                moves.append(remainder)
            continue
        moves.append(raw)
    return moves


def _validate_castle_path(board, color, kingside):
    rank = 0 if color == "w" else 7
    if color == "w":
        right = "K" if kingside else "Q"
    else:
        right = "k" if kingside else "q"
    if right not in board.castling_rights:
        raise ValueError("castling not available (no rights recorded for that side)")
    between = [rank * 8 + 5, rank * 8 + 6] if kingside else [rank * 8 + 1, rank * 8 + 2, rank * 8 + 3]
    for square in between:
        if board.squares[square] is not None:
            raise ValueError("castling blocked by a piece")

    # The king must not start, pass through, or land on an attacked
    # square. The rook's path isn't restricted the same way.
    enemy = "b" if color == "w" else "w"
    king_path = [rank * 8 + 4, rank * 8 + 5, rank * 8 + 6] if kingside \
        else [rank * 8 + 4, rank * 8 + 3, rank * 8 + 2]
    for square in king_path:
        if board.is_square_attacked(square, enemy):
            raise ValueError("cannot castle out of, through, or into check")


def apply_san(board, raw_token):
    """Mutate board in place by applying one SAN move. Raises ValueError
    with a human-readable reason if the move cannot be resolved."""
    token = raw_token.rstrip("+#")
    color = board.side_to_move

    if token in ("O-O", "0-0"):
        rank = 0 if color == "w" else 7
        _validate_castle_path(board, color, kingside=True)
        board.apply(rank * 8 + 4, rank * 8 + 6, castle="kingside")
        return

    if token in ("O-O-O", "0-0-0"):
        rank = 0 if color == "w" else 7
        _validate_castle_path(board, color, kingside=False)
        board.apply(rank * 8 + 4, rank * 8 + 2, castle="queenside")
        return

    promotion = None
    if "=" in token:
        token, promotion = token.split("=")

    if token and token[0] in "NBRQK":
        piece = token[0]
        rest = token[1:]
    else:
        piece = "P"
        rest = token

    capture = "x" in rest
    rest_clean = rest.replace("x", "")
    if len(rest_clean) < 2:
        raise ValueError(f"cannot parse move '{raw_token}'")

    dest_name = rest_clean[-2:]
    disambig = rest_clean[:-2]
    if not _SQUARE_RE.match(dest_name):
        raise ValueError(f"invalid destination square in move '{raw_token}'")
    dest = square_index(dest_name)

    disambig_file = None
    disambig_rank = None
    for ch in disambig:
        if ch in "abcdefgh":
            disambig_file = ch
        elif ch in "12345678":
            disambig_rank = ch

    if piece == "P":
        if capture and disambig_file is None:
            raise ValueError(f"pawn capture '{raw_token}' needs a from-file (e.g. 'exd5')")
        candidates = board.find_pawn_candidates(color, dest, capture, disambig_file)
    else:
        candidates = board.find_candidates(piece, color, dest)
        if disambig_file is not None:
            candidates = [c for c in candidates if c % 8 == ord(disambig_file) - ord("a")]
        if disambig_rank is not None:
            candidates = [c for c in candidates if c // 8 == int(disambig_rank) - 1]

    if not candidates:
        name = "pawn" if piece == "P" else piece
        raise ValueError(f"no {name} can reach {dest_name} (move '{raw_token}')")
    if len(candidates) > 1:
        raise ValueError(f"ambiguous move '{raw_token}': multiple pieces can reach {dest_name}")

    frm = candidates[0]
    is_en_passant = piece == "P" and capture and board.squares[dest] is None

    trial = board.clone()
    trial.apply(frm, dest, promotion=promotion, is_en_passant=is_en_passant)
    enemy = "b" if color == "w" else "w"
    if trial.is_square_attacked(trial.find_king(color), enemy):
        raise ValueError(f"illegal move '{raw_token}': leaves own king in check")

    board.squares = trial.squares
    board.side_to_move = trial.side_to_move
    board.castling_rights = trial.castling_rights
    board.en_passant = trial.en_passant
    board.halfmove_clock = trial.halfmove_clock
    board.fullmove_number = trial.fullmove_number


def _leaves_own_king_in_check(board, frm, to, color, promotion=None, is_en_passant=False):
    trial = board.clone()
    trial.apply(frm, to, promotion=promotion, is_en_passant=is_en_passant)
    enemy = "b" if color == "w" else "w"
    return trial.is_square_attacked(trial.find_king(color), enemy)


def _disambiguator(frm, siblings):
    """The minimal SAN disambiguation text needed to tell frm apart from
    the other candidate squares in siblings that can reach the same
    destination."""
    if len(siblings) == 1:
        return ""
    frm_file, frm_rank = frm % 8, frm // 8
    if sum(1 for f in siblings if f % 8 == frm_file) == 1:
        return chr(ord("a") + frm_file)
    if sum(1 for f in siblings if f // 8 == frm_rank) == 1:
        return str(frm_rank + 1)
    return square_name(frm)


def moves_to_square(board, dest_name):
    """The SAN for every legal move, by the side to move, that lands a
    piece on dest_name. Raises ValueError if dest_name isn't a square."""
    if not _SQUARE_RE.match(dest_name):
        raise ValueError(f"invalid square '{dest_name}'")

    dest = square_index(dest_name)
    color = board.side_to_move
    is_capture = board.squares[dest] is not None
    results = []

    for piece in "NBRQ":
        legal = [f for f in board.find_candidates(piece, color, dest)
                 if not _leaves_own_king_in_check(board, f, dest, color)]
        for frm in legal:
            disambig = _disambiguator(frm, legal)
            results.append(f"{piece}{disambig}{'x' if is_capture else ''}{dest_name}")

    for frm in board.find_candidates("K", color, dest):
        if not _leaves_own_king_in_check(board, frm, dest, color):
            results.append(f"K{'x' if is_capture else ''}{dest_name}")

    dest_rank = dest // 8
    promotion_rank = 7 if color == "w" else 0
    for frm, capture in board.find_pawn_sources(color, dest):
        is_en_passant = capture and not is_capture
        if _leaves_own_king_in_check(board, frm, dest, color, is_en_passant=is_en_passant):
            continue
        prefix = f"{square_name(frm)[0]}x" if capture else ""
        if dest_rank == promotion_rank:
            results.extend(f"{prefix}{dest_name}={promo}" for promo in "QRBN")
        else:
            results.append(f"{prefix}{dest_name}")

    for kingside, king_file in ((True, 6), (False, 2)):
        home_rank = 0 if color == "w" else 7
        if dest != home_rank * 8 + king_file:
            continue
        try:
            _validate_castle_path(board, color, kingside=kingside)
        except ValueError:
            continue
        results.append("O-O" if kingside else "O-O-O")

    return sorted(set(results))
