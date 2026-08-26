"""Minimal 8x8 board model with FEN output.

Squares are indexed 0..63 as rank * 8 + file, so a1 = 0 and h8 = 63.
Pieces are single characters, uppercase for white, lowercase for black,
using the usual PNBRQK letters.
"""

KNIGHT_OFFSETS = [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)]
KING_OFFSETS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
BISHOP_DIRS = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
ROOK_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
QUEEN_DIRS = BISHOP_DIRS + ROOK_DIRS

# Corners a rook starts on, and the castling right each one guards.
ROOK_HOME_RIGHTS = {0: "Q", 7: "K", 56: "q", 63: "k"}


def square_index(name):
    file_ = ord(name[0]) - ord("a")
    rank = int(name[1]) - 1
    return rank * 8 + file_


def square_name(index):
    file_ = index % 8
    rank = index // 8
    return chr(ord("a") + file_) + str(rank + 1)


class Board:
    def __init__(self, squares, side_to_move, castling_rights, en_passant,
                 halfmove_clock, fullmove_number):
        self.squares = squares
        self.side_to_move = side_to_move
        self.castling_rights = castling_rights
        self.en_passant = en_passant
        self.halfmove_clock = halfmove_clock
        self.fullmove_number = fullmove_number

    @classmethod
    def initial(cls):
        squares = [None] * 64
        for file_, ch in enumerate("RNBQKBNR"):
            squares[file_] = ch
        for file_ in range(8):
            squares[8 + file_] = "P"
        for file_ in range(8):
            squares[48 + file_] = "p"
        for file_, ch in enumerate("rnbqkbnr"):
            squares[56 + file_] = ch
        return cls(squares, "w", set("KQkq"), None, 0, 1)

    def find_candidates(self, piece, color, dest):
        """Squares holding a piece of the given type/color that could
        geometrically reach dest, ignoring whether that would leave the
        mover's own king in check."""
        target = piece if color == "w" else piece.lower()
        dest_file, dest_rank = dest % 8, dest // 8
        candidates = []

        if piece == "N":
            offsets = KNIGHT_OFFSETS
        elif piece == "K":
            offsets = KING_OFFSETS
        else:
            offsets = None

        if offsets is not None:
            for df, dr in offsets:
                f, r = dest_file + df, dest_rank + dr
                if 0 <= f < 8 and 0 <= r < 8:
                    idx = r * 8 + f
                    if self.squares[idx] == target:
                        candidates.append(idx)
            return candidates

        dirs = BISHOP_DIRS if piece == "B" else ROOK_DIRS if piece == "R" else QUEEN_DIRS
        for df, dr in dirs:
            f, r = dest_file + df, dest_rank + dr
            while 0 <= f < 8 and 0 <= r < 8:
                idx = r * 8 + f
                occupant = self.squares[idx]
                if occupant is not None:
                    if occupant == target:
                        candidates.append(idx)
                    break
                f += df
                r += dr
        return candidates

    def clone(self):
        return Board(list(self.squares), self.side_to_move, set(self.castling_rights),
                     self.en_passant, self.halfmove_clock, self.fullmove_number)

    def find_king(self, color):
        target = "K" if color == "w" else "k"
        for idx, occupant in enumerate(self.squares):
            if occupant == target:
                return idx
        raise ValueError(f"no {color} king on the board")

    def is_square_attacked(self, square, by_color):
        """Whether by_color has a piece that could move to square right
        now. Ignores whose turn it is - this is used to check for check,
        not to validate whose move it would be."""
        file_, rank = square % 8, square // 8
        direction = 1 if by_color == "w" else -1
        pawn_rank = rank - direction
        pawn = "P" if by_color == "w" else "p"
        if 0 <= pawn_rank < 8:
            for df in (-1, 1):
                f = file_ + df
                if 0 <= f < 8 and self.squares[pawn_rank * 8 + f] == pawn:
                    return True
        for piece in ("N", "B", "R", "Q", "K"):
            if self.find_candidates(piece, by_color, square):
                return True
        return False

    def find_pawn_candidates(self, color, dest, capture, disambig_file):
        direction = 1 if color == "w" else -1
        dest_file, dest_rank = dest % 8, dest // 8
        target = "P" if color == "w" else "p"
        candidates = []

        if capture:
            from_file = ord(disambig_file) - ord("a")
            from_rank = dest_rank - direction
            if 0 <= from_rank < 8:
                idx = from_rank * 8 + from_file
                if self.squares[idx] == target:
                    candidates.append(idx)
            return candidates

        one_back = dest - direction * 8
        if 0 <= one_back < 64 and self.squares[one_back] == target:
            candidates.append(one_back)

        double_push_rank = 3 if color == "w" else 4
        if dest_rank == double_push_rank:
            two_back = dest - direction * 16
            if 0 <= two_back < 64 and self.squares[two_back] == target and self.squares[one_back] is None:
                candidates.append(two_back)

        return candidates

    def apply(self, frm, to, promotion=None, is_en_passant=False, castle=None):
        moving_piece = self.squares[frm]
        color = "w" if moving_piece.isupper() else "b"
        is_pawn_move = moving_piece.upper() == "P"
        is_capture = self.squares[to] is not None or is_en_passant

        if castle is not None:
            rank = frm // 8
            rook_from = rank * 8 + (7 if castle == "kingside" else 0)
            rook_to = rank * 8 + (5 if castle == "kingside" else 3)
            self.squares[to] = self.squares[frm]
            self.squares[frm] = None
            self.squares[rook_to] = self.squares[rook_from]
            self.squares[rook_from] = None
            self._strip_castling_rights(color)
        else:
            if promotion is None:
                landing = moving_piece
            else:
                landing = promotion.upper() if color == "w" else promotion.lower()
            self.squares[to] = landing
            self.squares[frm] = None

            if is_en_passant:
                captured_square = to - 8 if color == "w" else to + 8
                self.squares[captured_square] = None

            if moving_piece.upper() == "K":
                self._strip_castling_rights(color)
            self._strip_rook_right(frm)
            self._strip_rook_right(to)

        self.en_passant = None
        if is_pawn_move and abs(to - frm) == 16:
            self.en_passant = (frm + to) // 2

        if is_pawn_move or is_capture:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        if self.side_to_move == "b":
            self.fullmove_number += 1
        self.side_to_move = "b" if color == "w" else "w"

    def _strip_castling_rights(self, color):
        if color == "w":
            self.castling_rights -= {"K", "Q"}
        else:
            self.castling_rights -= {"k", "q"}

    def _strip_rook_right(self, square):
        right = ROOK_HOME_RIGHTS.get(square)
        if right is not None:
            self.castling_rights.discard(right)

    def fen(self):
        rows = []
        for rank in range(7, -1, -1):
            row = ""
            empty = 0
            for file_ in range(8):
                piece = self.squares[rank * 8 + file_]
                if piece is None:
                    empty += 1
                else:
                    if empty:
                        row += str(empty)
                        empty = 0
                    row += piece
            if empty:
                row += str(empty)
            rows.append(row)
        board_field = "/".join(rows)
        castling_field = "".join(c for c in "KQkq" if c in self.castling_rights) or "-"
        ep_field = square_name(self.en_passant) if self.en_passant is not None else "-"
        return (f"{board_field} {self.side_to_move} {castling_field} {ep_field} "
                f"{self.halfmove_clock} {self.fullmove_number}")
