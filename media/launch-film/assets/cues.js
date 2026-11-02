/* Shared by index.html (the dashboard window) and every scene: the voice's word times, the eases, and the cue points
   both sides need, so a move of the window and the note it makes room for can never drift apart.
   All times are absolute film seconds; a scene subtracts its own start (TM.sN[0]).
   Needs window.VO (assets/vo.js), window.TM (assets/timing.js) and window.EDIT (assets/edit.js) loaded first. */
(function () {
  const VO = window.VO, TM = window.TM, SH = window.EDIT.shots;
  const norm = (s) => s.toLowerCase().replace(/[^a-z0-9]/g, "");
  // the time of the nth word of line k that equals w (else starts with w); "a|b" tries both; falls back to the line's start
  const WA = (k, w, nth = 0) => {
    const alts = w.split("|");
    for (const exact of [true, false]) {
      let c = 0;
      for (const x of VO[k].words) {
        const t = norm(x.w);
        if (alts.some((a) => (exact ? t === a : t.startsWith(a)))) { if (c === nth) return x.t0; c++; }
      }
    }
    return VO[k].start;
  };
  // one ease family (as the Outbreak films): EO arrivals, EI exits, EIO moves from rest to rest
  const EO = (p) => (p >= 1 ? 1 : 1 - Math.pow(2, -10 * p));
  const EI = (p) => (p <= 0 ? 0 : Math.pow(2, 10 * (p - 1)));
  const EIO = (p) => (p <= 0 ? 0 : p >= 1 ? 1 : p < 0.5 ? EI(2 * p) / 2 : (1 + EO(2 * p - 1)) / 2);

  const ASIDE_D = 0.7;                                   // the window's step aside and return, seconds
  // a note may arrive only once the window has cleared its place: 0.45 s into the step aside (EIO at 0.64 = 0.9 of the way)
  const CLEAR = 0.45;
  const aside4 = SH.judge.marks.score_view - 0.02;
  const CUE = {
    win: TM.s3[0],                                       // the window settles (0.9 s)
    // s3: the path note, on "fast"
    aside3: WA("v05", "fast") - CLEAR,
    note3: WA("v05", "fast"),
    out3: TM.s4[0] - 0.9,
    back3: TM.s4[0] - 0.65,
    // s4: the validator note once Score progression has landed and the window has stepped clear ("too many"), "Forced to 0" on "zero"
    aside4,
    note4: Math.max(WA("v07", "too") + 0.12, aside4 + CLEAR),
    zero: WA("v07", "zero"),
    out4: TM.s5[0] - 0.95,
    back4: TM.s5[0] - 0.72,
    // s5: the loop 2 fixer's claim, the cut to the finished run, "failed", the cut to Validator failures
    claim: SH.repair.rects.claim_open_text.t,
    claimChip: SH.repair.rects.claim_open_text.t + 0.6,  // after the push has landed, in the voice gap
    cut1: SH.repair.cuts[0].t,
    failed: WA("v09", "failed"),
    cut2: SH.repair.cuts[1].t,
    // s6: the window lifts away ("up" exit, 0.5 s) at the end of the scene
    exit: TM.s6[1] - 0.5,
  };
  window.FILM = { WA, EO, EI, EIO, CUE, ASIDE_D, FPS: 30 };
})();
