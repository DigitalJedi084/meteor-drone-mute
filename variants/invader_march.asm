; Meteor background sound: "invader march"
; Four descending plucked bass notes (G2 F2 E2 D2) on a loop. The tempo creeps up from
; ~0.73 s to ~0.3 s per note as the player keeps scoring. Timer 1 (the harsh channel) stays off.
;
; Replaces the drone code at $50B7-$5152 in U2. Fixed entry points:
;   $50B7  start (bytecode op $55 at ball/game start)   $50CC  restore after a sound effect
;   $50EC  step (U1 event table; $19 = "run native code from $50ED")

LEVEL:   EQU $02F7          ; 0..MAXLVL intensity
SUB:     EQU $02F8          ; scoring steps since last level-up
NOTEP:   EQU $02F9          ; word: pointer into NOTES
SCRIPT:  EQU $6D
HOLD:    EQU $48
STEPTMR: EQU $5D
MAXLVL:  EQU 13
K:       EQU 8
DECAY:   EQU 9000           ; T3: 16 envelope steps ~0.29 s
GAP0:    EQU 22             ; ticks per note at level 0

         ORG $50B7
start:   LDX #0
         STX SCRIPT         ; stop any sound script (as the original did)
         STX LEVEL          ; LEVEL = SUB = 0
         LDX #NOTES+6       ; first step wraps to the first note
         STX NOTEP
         BRA note

         ORG $50CC
restore: RTS                ; after an effect: next note arrives on schedule

         ORG $50EC
         FCB $19            ; bytecode: switch to native code
step:    LDAA HOLD
         CMPA #$19
         BCS note
         INC SUB
         LDAA SUB
         CMPA #K
         BCS note
         CLR SUB
         LDAA LEVEL
         CMPA #MAXLVL
         BCC note
         INC LEVEL
note:    LDAB #GAP0
         SUBB LEVEL
         STAB STEPTMR
         LDX NOTEP
         INX
         INX
         CPX #NOTES+8
         BNE note2
         LDX #NOTES
note2:   STX NOTEP
         LDAA SCRIPT
         ORAA SCRIPT+1
         BNE done           ; an effect owns the board; keep time but stay quiet
         LDX 0,X
         STX $A4            ; T2 latch = pitch
         LDX #DECAY
         STX $A6            ; T3 latch = decay speed
         CLRA
         STAA $A1           ; CR2 = $00: T2 off, $A0 -> CR3
         LDAA #$92
         STAA $A0           ; CR3 = $92: T3 runs (envelope clock)
         LDAA #$01
         STAA $A1           ; CR2 = $01: $A0 -> CR1
         LDAA #$12
         STAA $A0           ; CR1 = $12: T1 output off, timers out of reset
         LDAA #$93
         STAA $A1           ; CR2 = $93: T2 output on
         CLRA
         STAA $C0           ; envelope: one-shot, falling (full volume, decays to silence)
done:    RTS

NOTES:   FDB 5101, 5726, 6066, 6809   ; G2 98 Hz, F2 87.3, E2 82.4, D2 73.4 (PinMAME 1 MHz clock)
