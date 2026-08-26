# sanfen

A game score written in SAN ("1. e4 e5 2. Nf3 Nc6 3. Bb5") tells you every
move that was played, but it doesn't tell you what the board looks like at
any given point - you have to replay it in your head, or paste it into a
GUI. `sanfen` does the replay for you and prints the resulting position as
FEN (Forsyth-Edwards Notation), which is the format most chess tools expect
as input.

It answers one question: given a starting position and a list of SAN moves,
what FEN do you end up with?

## Usage

```
$ sanfen "1. e4 e5 2. Nf3 Nc6 3. Bb5"
r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3
Black to move, move 3
```

Bare words work too, without move numbers:

```
$ sanfen e4 e5 Nf3 Nc6
r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3
White to move, move 3
```

Pass `--json` for scripting:

```
$ sanfen --json "1. e4 e5 2. Nf3 Nc6"
{"ok": true, "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3", "side_to_move": "w", "fullmove_number": 3, "halfmove_clock": 2, "moves_played": ["e4", "e5", "Nf3", "Nc6"]}
```

If a move can't be resolved, the JSON output reports the failure instead of
raising a traceback, and the process exits with status 1:

```
$ sanfen --json "1. e4 e5 2. Nf3 Nf9"
{"ok": false, "error": "invalid destination square in move 'Nf9'", "failed_move": "Nf9", "moves_played": ["e4", "e5", "Nf3"]}
```

## Install

No dependencies. Either run it in place:

```
python -m sanfen.cli "1. e4 e5"
```

or install it so the `sanfen` command is on your PATH:

```
pip install -e .
```

## Current scope

Move resolution finds which piece of the right type can reach the
destination square, including standard disambiguation (`Nbd2`, `R1a3`,
`exd5`), captures, en passant, castling, and promotion, and it rejects a
move if playing it would leave the mover's own king in check (walking a
pinned piece off its pin, moving the king into an attacked square, and
so on). What it does **not** do yet is reject castling through or out of
check - a castle is only checked for landing the king in check, the same
as any other move, not for the squares it passes through. See the
roadmap for where this is headed.

## Roadmap

- Reject castling through or out of check
- Add a `--from-fen` flag to start from an arbitrary position instead of the initial one
- Add a mode that takes a target square/piece and explains which SAN moves could reach it
- Read move lists from a PGN file, not just command-line text
