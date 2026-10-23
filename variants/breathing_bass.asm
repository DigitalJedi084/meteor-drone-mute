; Meteor background sound: "breathing bass"
; A soft square-wave bass note swells in and fades out once per breath, cycling Am - F - G - E.
; Breaths quicken from 4 s to 2 s as the player keeps scoring. Timer 1 (the harsh channel) stays off.
;
; Replaces the drone code at $50B7-$5152 in U2. Fixed entry points:
;   $50B7  start (bytecode op $55 at ball/game start)   $50CC  restore after a sound effect
;   $50EC  step (U1 event table; $19 = "run native code from $50ED")

LEVEL:   EQU $02F7          ; 0..MAXLVL intensity
SUB:     EQU $02F8          ; scoring steps since last level-up
NOTEP:   EQU $02F9          ; word: pointer into NOTES
SCRIPT:  EQU $6D            ; word: active sound script (0 = none)
HOLD:    EQU $48            ; >= $19 for ~2 s after any score
STEPTMR: EQU $5D            ; 30 Hz countdown that fires the step
MAXLVL:  EQU 15
K:       EQU 2              ; scoring steps per level

         ORG $50B7
start:   LDX #0
         STX SCRIPT         ; stop any sound script (as the original did)
         STX LEVEL          ; LEVEL = SUB = 0
         LDX #NOTES
         STX NOTEP
         BSR restore
         BRA rearm

         ORG $50CC
restore: BSR ticks          ; B = breath length in 30 Hz ticks
         TBA                ; T3 latch = ticks * 520  (16 env steps up + 16 down = one breath)
         LSRA
         LSRA
         LSRA
         LSRA
         LSRA
         ABA
         ABA
         ASLB
         ASLB
         ASLB
         STAA $A6
         STAB $A7
         BRA play           ; rest of restore lives after the step code

ticks:   LDAB LEVEL         ; B = 120 - 4*LEVEL  (4 s .. 2 s)
         ASLB
         ASLB
         NEGB
         ADDB #120
         RTS

         ORG $50EC
         FCB $19            ; bytecode: switch to native code
step:    LDAA HOLD
         CMPA #$19
         BCS advance
         INC SUB
         LDAA SUB
         CMPA #K
         BCS advance
         CLR SUB
         LDAA LEVEL
         CMPA #MAXLVL
         BCC advance
         INC LEVEL
advance: LDX NOTEP
         INX
         INX
         CPX #NOTES+8
         BNE adv2
         LDX #NOTES
adv2:    STX NOTEP
         LDX SCRIPT
         BNE rearm          ; an effect owns the board; restore runs when it stops
         BSR restore
rearm:   BSR ticks
         STAB STEPTMR
         RTS

play:    LDX NOTEP
         LDX 0,X
         STX $A4            ; T2 latch = note
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
         LDAA #$07
         STAA $C0           ; envelope: continuous, alternate, start rising
         RTS

NOTES:   FDB 4544, 5726, 5101, 6066   ; A2 110 Hz, F2 87.3, G2 98, E2 82.4 (PinMAME 1 MHz clock)
