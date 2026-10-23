# Stern Meteor (1979) – the rising background drone

ROM set analysed: PinMAME `meteorb` (`cpu_u1.716`, `cpu_u2b.716`, `cpu_u5b.716`, `cpu_u6b.716`),
the set your VPX table loads (`cGameName="meteorb"`).

## Hardware

- MP-200 MPU, 6800 CPU. ROM: U1 `$1000`, U5 `$1800`, U2 `$5000`, U6 `$5800`.
- No sound ROM. The SB-300 sound board is a **Motorola 6840 timer chip (PTM)** that the main CPU
  writes directly: `$A0/$A1` control registers, `$A2` = timer 1 latch, `$A4` = timer 2, `$A6` = timer 3,
  plus a control latch at `$C0`. Each timer's output is a square wave, with frequency ≈ 894,886 / (2·(latch+1)) Hz.

## How the drone works

**1. Sound scripts.** In the IRQ, U2/U6 run a small sound-script interpreter (`$5E7B`). The
script pointer is at `$6D`. Opcodes: `$8x hh ll` writes a 6840 register, `0 n` waits, `2/3` loop,
`4` jumps, `5` sets `$C0`, `6/7` sweep the timer values, and `8` is **STOP**. Game bytecode starts a script with
opcode `$57 aaaa` (force) or `$58 aaaa` (only if nothing important is playing).

**2. The drone is the "idle" sound.** STOP (`$5F1C`) puts the timers in reset. Then, if a game
is in progress (`$1F` bit 7), it jumps to `$50B2`, which calls **`$50CC`**:

```
50CC  LDX $02F7 / STX $A2     ; timer 1 latch <- drone value 1
50D1  LDX $02F9 / STX $A4     ; timer 2 latch <- drone value 2
50D6  ...      / STX $A0     ; control registers: T3 off, then
50DE  LDX #$9293 / STX $A0    ;   CR1=$92, CR2=$93: T1 + T2 outputs ON, continuous square wave
50E3  CLR $C0, CLR $4C, DEC $02FF
```

So whenever no effect is playing, the board falls back to two square waves.

**3. Initial pitch** (`$50B7`, called from game bytecode `55 50 B7` in U5): T1 = `$3010`,
T2 = `$3000`. That's about 36.4 Hz and 36.3 Hz. The tiny detune gives the slow, beating rumble.

**4. The ramp** (`$50ED`, slot `$37` in the U1 event table, run when timer byte `$5D` expires;
the slow timers tick at 30 Hz):

- Each step subtracts `$0100` from both latch values. A smaller latch means a higher pitch.
- The step interval gets longer as the pitch rises, based on T2's high byte: 1 s (≥`$1D`),
  1.5 s (≥`$0D`), 2 s (≥`$05`), 4 s below that.
- It only steps while you're scoring: `$48` is set to `$FF` (about 2 s) by the score-award code at `$5783`.
  It also only steps when the drone has been reloaded since the last step (flag `$02FF`). So it
  pauses during sound effects and when the ball is idle.
- When T2 reaches `$00xx` (about 1.7 kHz), T2 wraps back to `$3000` and T1 is set to `$0180`.
- Sweeping from about 36 Hz up to about 1.7 kHz takes roughly 75 s of continuous scoring.

## The patches (`patch_meteor.py`)

Both keep the boot self-test working. Reset sums all 8 KB of ROM and halts at `$5F84` unless the
total is `00` mod 256.

| | Changes | Effect |
|---|---|---|
| **clean** (recommended) | U2 `+DF/+E0`: `92 93` → `01 01`; U2 `+B9`: `10` → `33` (checksum) | The drone routine still runs, but it leaves the 6840 in reset with outputs off. That's the same end state as the game's own STOP. All sound effects, including the game-start sound, are unchanged. |
| **forum** | U2 `+CC/+CD`: `FE 02` → `39 C7`; U1 `+A6/+A9`: swap `57`/`2F` | `$50CC` becomes RTS, so the timers are never re-armed. The U1 swap puts a bytecode RETURN ahead of `57 58EF` in the start-game routine (`$109C`: take a credit, bump the audit, play the start sound), so the start sound is gone. |

**Why the forum patch also needs the U1 swap (as best I can tell):** `$50B7` kills any playing
script (`$6D = 0`). With `$50CC` turned into RTS, nothing silences the 6840 after that. So if
`$50B7` fires while an effect is still playing, that effect's last tone keeps sounding. The
start-game sweep is the obvious case, so it was removed. The clean patch silences the timers at that point
instead, so no effect can get stuck and the start sound can stay.

## Replacement background sounds (`variants/`)

Each variant rewrites the drone block (`$50B7-$5152` in U2) with a gentler sound. The entry
points stay the same, and one unused byte balances the boot checksum. None of them use timer 1 (the harsh pulse
channel). All of them use the SB-300's timer 3 volume envelope, which PinMAME models as a 16-step
fade driven by timer 3 (`$C0` bits: 0 up, 1 alternate, 2 continuous, 3 noise).

| Variant | Sound | Gets more intense by |
|---|---|---|
| `breathing_bass` | Square bass swelling in and out, one note per breath: A–F–G–E | breaths go from 4 s to 2 s |
| `heartbeat` | lub-dub thumps at 55/49 Hz with a fast decay | pulse goes from ~50 to ~110 bpm |
| `invader_march` | four descending plucked notes G–F–E–D | notes go from 0.73 s to 0.3 s apart |

Like the original, the intensity only climbs while you're scoring (`$48` hold), and it resets when `$50B7` runs at
ball/game start. Sound effects take over the board while they play. Breathing bass restarts its
note when they stop; the other two keep time and come back in on the beat. Pitches assume PinMAME's
1 MHz 6840 clock, so they'd sound about 10% lower on a real machine.

- `variants/*.asm` – source; `tools/build_variants.py <meteorb.zip> variants` assembles them into
  `variants/<name>/meteorb.zip`.
- `tools/simulate.py` runs a variant's actual ROM code in a 6800 emulator (`tools/emu6800.py`)
  against simulated scoring and sound effects, and renders it through PinMAME's SB-300 model.
  `previews/rom_*.wav` are those renders. The other previews are the idea sketches from `tools/sb300_preview.py`.
- `install-variant.ps1 <name>` switches what VPinMAME loads (`breathing_bass`, `heartbeat`,
  `invader_march`, `clean`, `forum`, `original`).

## Installing

The patched ROM zips are included. To rebuild them from your own `meteorb.zip`:

```
python patch_meteor.py path\to\meteorb.zip .
```

Back up your existing `VPinMAME\roms\meteorb.zip`, then copy `clean\meteorb.zip` over it.
VPinMAME may warn about a CRC mismatch for `cpu_u2b.716`. That's expected for a modified ROM.
To undo, restore the backup.
