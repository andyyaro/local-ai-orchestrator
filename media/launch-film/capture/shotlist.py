"""The shots of the take dash-run, keyed to the narration (assets/vo.js) and the scene windows (sound/timing.json).
Read by capture/conform.py. Everything here is derived from the take's own marks and page events, so a re-take only
needs a re-run of conform.py.

  goal    s3 19.412-28.235  the idle dashboard as the window settles; the pointer clicks the Task box; the goal
                            typed (1x); Run pipeline pressed; the page scrolls to Progress; the supervisor works and
                            ticks (sped up, labelled); the builder starts.
  judge   s4 28.235-38.823  the builder ticks on "builder"; Loop 1 of 3; the judge ticks on "judge" (sped up); the
                            pointer opens the judge row (1x): its own verdict "'total_score': N, 'pass': True" is open
                            by "pass"; held for the push-in; on "counts" the page scrolls to Score progression
                            (1x): "Current score 0/100".
  repair  s5 38.823-51.176  loop 2 at speed (critic on "critic", fixer, judge); if a model claimed the limit was met,
                            the pointer opens that row on the claim in the voice gap (1x, held); loop 3 and the
                            synthesizer at speed; the run ends; the page scrolls to Run summary (1x), landing on
                            "failed"; on the beat at 47.647 the film cuts past the captions to Validator failures.
  local   s6 51.176-58.235  the pointer opens "Metrics summary (Phase 5)" (1x) on "call"; the page scrolls to the
                            per-role table and "Total runtime"; held until the window lifts away.
"""
from __future__ import annotations

FPS = 30

# rects measured on recorded frames (CSS px of the 1280x720 viewport), for push-ins the recorder could not measure
# exactly: the recorder kept the claim's first 90 characters (two lines); the claim itself is the end of line two
EXTRA_RECTS = {"claim_meets": {"frame": 1308, "rect": [655, 423, 302, 24],
                               "text": "meets the 50-word tolerance for exact target word count.",
                               "how": "measured on take frame 1308 (2x pixels / 2)"}}


def split(take, a, b):
    i = sum(take.tt[k] - take.tt[k - 1] for k in range(a + 1, b + 1) if take.mode[k] == "i")
    w = sum(take.tt[k] - take.tt[k - 1] for k in range(a + 1, b + 1) if take.mode[k] == "w")
    return i, w


def advance(take, a, film, fac):
    """The take frame reached after `film` seconds from frame a, with i frames at 1x and waiting at fac."""
    t, k = 0.0, a
    while k + 1 < take.n:
        d = take.tt[k + 1] - take.tt[k]
        step = d if take.mode[k + 1] == "i" else d / fac
        if t + step > film + 1e-9:
            break
        t += step
        k += 1
    return k


def block(take, f):
    """The run of i frames (one 1x interaction) that contains frame f: [first, last]."""
    a = f
    while a > 0 and take.mode[a - 1] == "i":
        a -= 1
    b = f
    while b + 1 < take.n and take.mode[b + 1] == "i":
        b += 1
    return a, b


def first_move(take, a, b, park_x):
    """The first frame in a..b where the pointer starts heading to the park position (the right margin)."""
    for k in range(a + 1, b + 1):
        if take.F[k][3] > take.F[k - 1][3] + 0.5 and abs(take.F[b][3] - park_x) < 2:
            return k - 1
    return None


def shots(take, W, beat, TM):
    s3a, s3b = TM["s3"]
    s4a, s4b = TM["s4"]
    s5a, s5b = TM["s5"]
    s6a, s6b = TM["s6"]
    park = take.meta.get("park_x", 1128.0)
    out = {}

    # ---------------------------------------------------------------- goal (s3)
    run = take.m("run_press")
    click = take.m("task_click")
    move0 = block(take, click)[0] + 30            # the idle hold is 30 frames; then the pointer starts to move
    RP = 19.45 + (run - move0) / FPS              # the pointer comes in as the window settles; Run pressed at RP
    a0 = run - round((RP - s3a) * FPS)
    assert a0 >= 0, a0
    sup = take.ev("supervisor:done")
    bd = take.ev("builder:done")
    jd = take.ev("judge:done")
    T_JD = W("v06", "judge")                      # loop 1's judge ticks on "judge" (30.15)
    # ONE speed from Run pipeline to the judge's tick, across s3 and s4, so the corner label holds still; with it the
    # supervisor ticks just after "fast path" and the builder on "builder" (checked below)
    i_all, w_all = split(take, run, jd)
    F = w_all / (T_JD - RP - i_all)
    b3 = advance(take, run, s3b - RP, F)
    t_sup = RP + split(take, run, sup)[0] + split(take, run, sup)[1] / F
    t_bd = RP + split(take, run, bd)[0] + split(take, run, bd)[1] / F
    out["goal"] = ([("play", s3a, RP, a0, run), ("fast", RP, s3b, run, b3)],
                   f"1x until Run pipeline is pressed ({RP:.2f}); then the run at {F:.1f}x (labelled) through s3 and "
                   f"s4: the supervisor ticks at {t_sup:.2f}, the builder at {t_bd:.2f}. The window can step left for "
                   "the fast/normal/deep note from 'fast' (25.20) while the take plays on.")

    # ---------------------------------------------------------------- judge (s4)
    j1 = take.m("judge1_open")
    ib0, ib1 = block(take, j1)
    f4 = F
    i5, w5 = split(take, jd, ib0)
    T_IB0 = T_JD + i5 + w5 / f4
    T_OPEN = T_IB0 + (j1 - ib0) / FPS
    pk = first_move(take, j1, take.m("score_view"), park)
    open_end = pk if pk else j1 + 20
    T_OPEN_END = T_IB0 + (open_end - ib0) / FPS
    sv = take.m("score_view")
    T_PARK = W("v07", "code") + 0.1               # the page heads for the score as the voice says "code counts"
    T_SV = T_PARK + (sv - open_end) / FPS
    assert T_OPEN_END < W("v06", "pass") + 0.4, (T_OPEN_END, "the verdict must be open by 'pass'")
    out["judge"] = ([("fast", s4a, T_JD, b3, jd), ("fast", T_JD, T_IB0, jd, ib0),
                     ("play", T_IB0, T_OPEN_END, ib0, open_end), ("hold", T_OPEN_END, T_PARK, open_end),
                     ("play", T_PARK, T_SV, open_end, sv), ("hold", T_SV, s4b, sv + 3)],
                    f"judge row clicked at {T_OPEN:.2f}, verdict open {T_OPEN_END:.2f}-{T_PARK:.2f} (push-in on the "
                    f"verdict, rects.judge1_open_text); Score progression in view from {T_SV:.2f}.")

    # ---------------------------------------------------------------- repair (s5)
    sv_end = block(take, sv)[1]
    j2d = take.ev("judge:done", nth=1)
    pr0 = block(take, take.m("summary_view"))[0]
    smv = take.m("summary_view")
    T_FAILED = W("v09", "failed")                 # 46.38
    T_PR0 = beat(T_FAILED - (smv - pr0) / FPS)    # CUT on the beat; the scroll lands on "failed"
    T_FAILED = T_PR0 + (smv - pr0) / FPS
    T_CUT = beat(W("v10", "miss") - 0.6)          # the cut to Validator failures, on a beat before "miss"
    vv = take.m("validators_view")
    segs = []
    T_J2D = beat(W("v08", "exact"), "down")       # loop 2's judge ticks on the beat before "exact count" (40.588)
    if "claim_open" in take.marks:
        # loop 2 at speed; then 1x: the pointer opens the row whose model claimed the limit was met, the page scrolls
        # to the claim; held for the push-in. Then CUT at T_PR0 past loop 3 (not shown) to the finished run.
        co = take.m("claim_open")
        cb0, cb1 = block(take, co)
        cpk = first_move(take, co, cb1, park) or cb1
        cv = cpk - 3                               # the claim in view (after the scroll to it)
        f6 = split(take, sv_end, j2d)[1] / (T_J2D - s5a - split(take, sv_end, j2d)[0])
        T_CB0 = T_J2D + split(take, j2d, cb0)[0] + split(take, j2d, cb0)[1] / f6
        T_CV = T_CB0 + (cv - cb0) / FPS
        segs += [("fast", s5a, T_J2D, sv_end, j2d), ("fast", T_J2D, T_CB0, j2d, cb0), ("play", T_CB0, T_CV, cb0, cv),
                 ("hold", T_CV, T_PR0, cv)]
        note = (f"loop 2 at {f6:.0f}x; the pointer opens the claim row ({take.meta.get('claim_row')}) at "
                f"{T_CB0 + (co - cb0) / FPS:.2f}, the claim in view {T_CV:.2f}-{T_PR0:.2f} (push-in on "
                f"rects.claim_open_text); CUT at {T_PR0:.3f} past loop 3 to the finished run; ")
    else:
        segs += [("fast", s5a, T_J2D, sv_end, j2d), ("fast", T_J2D, T_PR0, j2d, pr0)]
        note = "loops 2 and 3 at speed; "
    segs += [("play", T_PR0, T_FAILED, pr0, smv), ("hold", T_FAILED, T_CUT, smv + 2), ("hold", T_CUT, s5b, vv)]
    out["repair"] = (segs, note + f"Run summary lands on 'failed' {T_FAILED:.2f} (rects.final_score, rects.result); "
                     f"CUT at {T_CUT:.3f} to Validator failures (rects.vf_caption, rects.vf_table): the scroll in "
                     "between is never shown, so the 'Run saved to:' caption (the scratch path) stays out of frame.")

    # ---------------------------------------------------------------- local (s6)
    mo = take.m("metrics_open")
    mb0 = take.m("validators_view") + 8           # after the held frames, the pointer sets off for the expander
    mb1 = take.n - 1
    T_MO = W("v11", "call")                       # the click on "call" (52.03)
    T_MB0 = T_MO - (mo - mb0) / FPS
    T_MB1 = T_MB0 + (mb1 - mb0) / FPS
    out["local"] = ([("hold", s6a, T_MB0, mb0), ("play", T_MB0, T_MB1, mb0, mb1), ("hold", T_MB1, s6b, mb1)],
                    f"Metrics summary opened {T_MO:.2f}; the per-role table and Total runtime in view from "
                    f"{T_MB0 + (take.m('metrics_view') - mb0) / FPS:.2f} (rects.role_table, rects.runtime).")
    return out
