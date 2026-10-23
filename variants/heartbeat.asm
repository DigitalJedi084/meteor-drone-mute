; Meteor background sound: "heartbeat"
; Low lub-dub thumps (55 Hz then 49 Hz) with a quick decay. The pulse rises from ~50 to ~110 bpm
; as the player keeps scoring. Timer 1 (the harsh channel) stays off.
;
; Replaces the drone code at $50B7-$5152 in U2. Fixed entry points:
;   $50B7  start (bytecode op $55 at ball/game start)   $50CC  restore after a sound effect
;   $50EC  step (U1 event table; $19 = "run native code from $50ED")

LEVEL:   EQU $02F7          ; 0..MAXLVL intensity
SUB:     EQU $02F8          ; scoring steps since last level-up
PHASE:   EQU $02F9          ; 0 = next is lub, 1 = next is dub
SCRIPT:  EQU $6D
HOLD:    EQU $48
STEPTMR: EQU $5D
MAXLVL:  EQU 16
K:       EQU 6
LUB:     EQU 9090           ; 55 Hz
DUB:     EQU 10203          ; 49 Hz
DECAY:   EQU 5000           ; T3: 16 envelope steps ~0.16 s
GAP:     EQU 6              ; 25 Hz ticks between lub and dub
BEAT0:   EQU 30             ; ticks per beat at level 0 (50 bpm); level 16 = 14 ticks (107 bpm)

         ORG $50B7
start:   LDX #0
         STX SCRIPT         ; stop any sound script (as the original did)
         STX LEVEL          ; LEVEL = SUB = 0
         CLR PHASE
         BRA beat

         ORG $50CC
restore: RTS                ; after an effect: next beat arrives on schedule

         ORG $50EC
         FCB $19            ; bytecode: switch to native code
step:    LDAA HOLD
         CMPA #$19
         BCS beat
         INC SUB
         LDAA SUB
         CMPA #K
         BCS beat
         CLR SUB
         LDAA LEVEL
         CMPA #MAXLVL
         BCC beat
         INC LEVEL
beat:    LDAB #GAP
         LDX #LUB
         LDAA PHASE
         BEQ play
         LDAB #BEAT0-GAP    ; dub, then rest until the next lub
         SUBB LEVEL
         LDX #DUB
play:    EORA #1
         STAA PHASE
         STAB STEPTMR
         LDAA SCRIPT
         ORAA SCRIPT+1
         BNE done           ; an effect owns the board; skip this thump
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
