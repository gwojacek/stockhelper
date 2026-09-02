# Fibo formation rules

This document defines what the scanner should display in each Trójpolówki Fibo
column. The column changes describe the life cycle of **one unchanged pair of
anchors**; reaching a later column must not cause the scanner to search for a
different pair merely to keep the instrument on the board.

## Rules shared by every column

- A long formation starts at a meaningful, confirmed local swing low which
  launches the measured incline. A short formation starts at the equivalent
  local swing high which launches the decline.
- A long formation ends at the confirmed swing high of that same uninterrupted
  impulse. A short formation ends at the confirmed swing low.
- Anchor prices are candle extremes (`Low`/`High`), never closes or interpolated
  values. Anchor dates and prices must therefore point to visible extrema on the
  chart.
- The first anchor must precede the second anchor and the impulse between them
  must have meaningful duration, displacement and direction. A candle selected
  only because it makes the desired 61.8 value is not a valid anchor.
- Between a long formation's first anchor and its top, no candle may make a
  lower low; that newer low becomes the only possible launch anchor. The short
  rule is mirrored: no higher high may occur before the measured bottom.
- The second anchor must be the actual top/bottom of the measured leg. It must
  not be an interior candle while that same leg continues to a more extreme
  price.
- A completed month-long sideways phase separates market legs. An old anchor
  before that phase is not joined to a later breakout; the new formation starts
  at the structural swing low/high which launches the post-range move.
- A completed month-long range after the second anchor also ends the active
  correction when the correction is dominated by that range or finishes parked
  inside it. A temporary monthly shelf followed by renewed directional progress
  toward 61.8 does not end the setup merely because one rolling sub-window was
  flat. A later breakout from a genuinely completed range must establish a new
  formation.
- A normal, short pause within a coherent impulse does not by itself move an
  anchor. Re-anchoring is allowed only when market structure creates a genuinely
  new impulse, not because another anchor pair happens to pass the Fibo filters.
- Once price invalidates the 100% anchor, breaks the pattern stop, or completes
  an old 61.8 cycle without a valid reversal, that formation is finished. It is
  not resurrected using arbitrary nearby extrema.
- Long and short rules are exact mirrors. The descriptions below use a long
  formation for readability.

## Column 1 — steep impulse

- Both anchors already satisfy all shared structural rules: confirmed launch
  low to confirmed impulse high.
- The rise is sufficiently large and fast to qualify as a 3P impulse.
- There is no completed, disqualifying side trend between the anchors.
- The correction has not yet entered the actionable 23.6-to-61.8 pullback area,
  or price returned to the impulse side of 23.6 without touching 61.8.
- No 61.8 reversal pattern is required at this stage.

## Column 2 — correction in progress

- The same valid anchors from column 1 remain fixed.
- Price has reached/crossed 23.6 and is correcting toward 61.8.
- Pullback progress is below the near-61.8 threshold (75% of the distance from
  23.6 to 61.8).
- The correction has not invalidated the 100% anchor and has not become a new,
  completed monthly side trend.
- A reversal pattern is not required yet.

## Column 3 — near or freshly touching 61.8

- The same structurally valid anchors remain fixed.
- Pullback progress is at least 75% of the 23.6-to-61.8 interval, or the current
  candle has freshly touched/crossed 61.8.
- A fresh 61.8 touch remains actionable while its one-, two-, or three-candle
  confirmation can still complete; it must be visually highlighted.
- No completed valid pattern is required yet. This is a watch/confirmation
  column, not a reason to force different anchors until a pattern appears.
- If the first-touch confirmation window expires without a valid pattern, the
  formation drops out instead of being re-anchored to manufacture another 61.8
  event.

## Column 4 — confirmed 61.8 reversal

- The same structurally valid anchors remain fixed.
- The first 61.8 touch belongs to a supported one-, two-, or three-candle
  reversal formation (for example hammer, engulfing, harami, piercing/dark
  cloud, or morning/evening star in the appropriate direction).
- The final pattern candle confirms on the correct side of 61.8.
- The signal is recent (currently no older than 14 days).
- No later close has crossed the pattern stop loss; for a long formation the
  stop is the pattern low, and for a short formation it is the pattern high.

## Non-goals

- Do not enumerate many local-extreme pairs and select whichever produces a
  desired scanner status.
- Do not relax swing-point, impulse-duration, correction-duration, or dominance
  rules solely for a named instrument.
- Do not move either anchor when a setup advances from one board column to the
  next.
