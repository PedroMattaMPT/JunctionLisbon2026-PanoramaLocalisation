/* @ds-bundle: {"format":4,"namespace":"Aqui","components":[{"name":"Button"},{"name":"CostTag"},{"name":"KeyCap"},{"name":"Badge"},{"name":"Stamp"},{"name":"Tabs"},{"name":"Toggle"},{"name":"Segmented"},{"name":"Tooltip"},{"name":"Toast"},{"name":"Dialog"},{"name":"EmptyState"},{"name":"WaitState"},{"name":"Icon"},{"name":"Density"},{"name":"Wordmark"},{"name":"RunBar"},{"name":"Timer"},{"name":"MultiplierChip"},{"name":"ScoreReadout"},{"name":"GpuMeter"},{"name":"SystemBadge"},{"name":"ModelChip"},{"name":"ModelRoster"},{"name":"CaseCard"},{"name":"ShortcutBar"},{"name":"CleanStateCheck"},{"name":"DropZone"},{"name":"FilenameParse"},{"name":"PanoramaStrip"},{"name":"BearingRuler"},{"name":"Viewer360"},{"name":"ZoomCrop"},{"name":"LayerToggles"},{"name":"MatchView"},{"name":"StageRow"},{"name":"StageTimeline"},{"name":"EvidenceCard"},{"name":"PolarityChip"},{"name":"ConfidenceMeter"},{"name":"CorrelationBracket"},{"name":"CaptionBar"},{"name":"LeaderLines"},{"name":"CandidateRow"},{"name":"CandidateList"},{"name":"RuledOutRow"},{"name":"Funnel"},{"name":"EvidenceMatrix"},{"name":"MapView"},{"name":"UncertaintyRing"},{"name":"SurveyMark"},{"name":"MapLegend"},{"name":"QuestionCard"},{"name":"QuestionOption"},{"name":"AnswerReceipt"},{"name":"CueComposer"},{"name":"CoordinateBlock"},{"name":"AnswerSlots"},{"name":"ChoiceNote"},{"name":"ScoreCurve"},{"name":"EventLog"},{"name":"ReplayScrubber"},{"name":"ExportBar"},{"name":"StackedBar"},{"name":"LanguageVote"},{"name":"SceneShares"},{"name":"CompassDial"},{"name":"EstimateBars"},{"name":"GainMeter"}]} */
(() => {
  var __defProp = Object.defineProperty;
  var __export = (target, all) => {
    for (var name in all)
      __defProp(target, name, { get: all[name], enumerable: true });
  };

  // src/base.tsx
  var base_exports = {};
  __export(base_exports, {
    Badge: () => Badge,
    Button: () => Button,
    CostTag: () => CostTag,
    Density: () => Density,
    Dialog: () => Dialog,
    EmptyState: () => EmptyState,
    KeyCap: () => KeyCap,
    Segmented: () => Segmented,
    Stamp: () => Stamp,
    Tabs: () => Tabs,
    Toast: () => Toast,
    Toggle: () => Toggle,
    Tooltip: () => Tooltip,
    WaitState: () => WaitState
  });

  // src/rt.ts
  var R = window.React;
  var h = R.createElement;
  var Fragment = R.Fragment;
  var { useState, useEffect, useRef, useMemo, useContext, createContext, useCallback, useId } = R;
  var DensityContext = createContext("console");
  function useDensity() {
    return useContext(DensityContext);
  }
  var TYPE = {
    console: { title: "console-title", heading: "console-heading", body: "console-body", label: "console-label", micro: "console-micro", data: "console-data", dataSm: "console-data-sm", readout: "console-readout", inference: "inference", stamp: "stamp", caption: "console-heading", headline: "narrative-title", score: "console-readout", display: "narrative-title" },
    stage: { title: "stage-title", heading: "stage-body aq-strong", body: "stage-body", label: "stage-label", micro: "stage-label", data: "stage-data", dataSm: "stage-label aq-mono", readout: "stage-readout", inference: "stage-inference", stamp: "stage-stamp", caption: "stage-caption", headline: "narrative-headline", score: "stage-score", display: "narrative-display" }
  };
  function useT() {
    return TYPE[useDensity()];
  }
  var cx = (...a) => a.filter(Boolean).join(" ");
  var MINUS = "−";
  var num = (x, d = 2) => (x < 0 ? MINUS : "") + Math.abs(x).toFixed(d);
  var fmtCoord = (lat, lng) => `${num(lat, 5)}, ${num(lng, 5)}`;
  var fmtEst = (x) => x == null ? "unknown" : x.toFixed(2);
  var fmtMult = (m) => "×" + m.toFixed(m === 0.8 || m === 0.5 ? 1 : 2);
  function fmtDist(m) {
    if (m == null) return "unknown";
    if (m < 1e3) return `${Math.round(m)} m`;
    if (m < 1e4) return `${(m / 1e3).toFixed(1)} km`;
    return `${Math.round(m / 1e3)} km`;
  }
  function fmtTime(s) {
    const neg = s < 0;
    s = Math.abs(Math.round(s));
    const m = Math.floor(s / 60), r = s % 60;
    return (neg ? MINUS : "") + String(m).padStart(2, "0") + ":" + String(r).padStart(2, "0");
  }
  var fmtInt = (n) => Math.round(n).toLocaleString("en-US");
  var fmtPct = (x, d = 0) => (x * 100).toFixed(d) + "%";
  var fmtSigned = (x, d = 2) => (x > 0 ? "+" : x < 0 ? MINUS : "±") + Math.abs(x).toFixed(d);
  var RANK_W = Array.from({ length: 10 }, (_, i) => Math.pow(0.95, i));
  var theta = (dMeters, urban) => {
    const d = dMeters < 10 ? 0 : dMeters;
    return urban ? 2 / (1 + d / 100) : 2 / (1 + d / 1e4);
  };
  var MAX_SCORE = 1e3 * 2 * RANK_W.reduce((a, b) => a + b, 0);

  // src/icons.tsx
  var ICONS = {
    // actors
    model: [["p", "M1.5 8c1.8-3.2 4-4.5 6.5-4.5s4.7 1.3 6.5 4.5c-1.8 3.2-4 4.5-6.5 4.5S3.3 11.2 1.5 8z"], ["c", 8, 8, 2.25], ["C", 8, 8, 0.9]],
    solver: [["p", "M8 2v12M4 14h8M2.5 4.5h11"], ["p", "M2.5 4.5L1 9h3L2.5 4.5zM13.5 4.5L12 9h3l-1.5-4.5z"]],
    team: [["c", 8, 5, 2.75], ["p", "M2.5 14.5c.6-3 2.8-4.75 5.5-4.75s4.9 1.75 5.5 4.75"]],
    // evidence kinds
    text: [["p", "M2 2.5h12v11H2z"], ["p", "M5 5.5h6M8 5.5v5.5"]],
    object: [["p", "M2 5V2h3M11 2h3v3M14 11v3h-3M5 14H2v-3"], ["p", "M6 6h4v4H6z"]],
    checklist: [["p", "M7 4h7M7 8h7M7 12h7"], ["p", "M1.75 4l1.25 1.25L5 3M1.75 8l1.25 1.25L5 7"], ["c", 3.25, 12, 1.1]],
    measure: [["c", 8, 8, 6], ["p", "M8 2v6h6"]],
    sun: [["c", 8, 8, 2.75], ["p", "M8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.4 1.4M11.6 11.6L13 13M13 3l-1.4 1.4M4.4 11.6L3 13"]],
    compass: [["c", 8, 8, 6.25], ["f", "M8 3.5l1.6 4.5H6.4L8 3.5z"], ["p", "M6.4 8L8 12.5 9.6 8"]],
    language: [["p", "M2 2.5h12v8.5H8l-3 2.5V11H2z"], ["p", "M5 6h6M5 8.5h3.5"]],
    neighbour: [["p", "M4.5 1.5h10v8h-10z"], ["p", "M1.5 5.5v9h10"], ["p", "M6.5 8l2.5-2.5 2 2 1.5-1.5 2 2"]],
    region: [["p", "M2 4l4-2 4 2 4-2v10l-4 2-4-2-4 2z"], ["p", "M6 2v10M10 4v10"]],
    name: [["p", "M8 15V1.5"], ["p", "M8 2.5h5.5l1.5 2-1.5 2H8M8 8H2.5L1 10l1.5 2H8"]],
    contradiction: [["p", "M2 5.5h10.5M10 3l2.5 2.5L10 8M14 10.5H3.5M6 8l-2.5 2.5L6 13"]],
    infer: [["C", 8, 3.5, 1.6], ["C", 3.5, 12, 1.6], ["C", 12.5, 12, 1.6]],
    estimate: [["p", "M2 6c1.5-1.5 3-1.5 4.5 0s3 1.5 4.5 0 2.5-1.2 3-1M2 10.5c1.5-1.5 3-1.5 4.5 0s3 1.5 4.5 0 2.5-1.2 3-1"]],
    // stage status
    queued: [["c", 8, 8, 4.5]],
    running: [["C", 8, 8, 4.5]],
    done: [["p", "M3 8.5l3 3 7-7"]],
    skipped: [["p", "M2 11.5c1.5-5 10.5-5 12 0"], ["p", "M11.5 9.5l2.5 2 1-3"], ["c", 8, 12.5, 1.25]],
    failed: [["p", "M3.5 3.5l9 9M12.5 3.5l-9 9"]],
    timeout: [["p", "M4 1.5h8M4 14.5h8M5 1.5c0 4 6 4.5 6 6.5s-6 2.5-6 6.5M11 1.5c0 4-6 4.5-6 6.5s6 2.5 6 6.5"]],
    // polarity (filled shapes so they survive print and colour-blindness)
    support: [["f", "M8 3l5.5 9h-11z"]],
    contra: [["f", "M8 13L2.5 4h11z"]],
    neutral: [["C", 8, 8, 3.25]],
    // human loop and cost
    cost: [["p", "M14.5 4.5v7H5.5L1.5 8l4-3.5z"], ["c", 5.75, 8, 1]],
    question: [["p", "M2 2h12v12H2z"], ["p", "M6 6.25c0-1.25.9-2 2-2s2 .75 2 1.9c0 1.6-2 1.6-2 3.1"], ["C", 8, 11.5, 0.8]],
    cue: [["p", "M2 13.5h3l8.5-8.5-3-3L2 10.5z"], ["p", "M9 3.5l3 3"]],
    skip: [["p", "M1.5 11c2-5.5 11-5.5 13 0"], ["p", "M12 8.5l2.5 2.5L15.5 8"]],
    clock: [["c", 8, 8, 6.25], ["p", "M8 4.5V8l2.5 2"]],
    key: [["p", "M1.5 3.5h13v9h-13z"], ["p", "M4 6.5h1M7.5 6.5h1M11 6.5h1M5 9.5h6"]],
    // navigation and actions
    link: [["p", "M9 2h5v5M14 2L7 9"], ["p", "M12 10v4H2V4h4"]],
    copy: [["p", "M5.5 5.5h8v8h-8z"], ["p", "M10.5 2.5h-8v8"]],
    qr: [["p", "M2 2h5v5H2zM9 2h5v5H9zM2 9h5v5H2z"], ["p", "M9.5 9.5h1.5v1.5H9.5zM12.5 12.5H14V14h-1.5zM9.5 12.5H11V14H9.5zM12.5 9.5H14V11h-1.5z"]],
    download: [["p", "M8 1.5v9M4.5 7l3.5 3.5L11.5 7M2 12v2.5h12V12"]],
    drop: [["p", "M8 10V1.5M4.5 5L8 1.5 11.5 5"], ["p", "M1.5 9.5v5h13v-5"]],
    submit: [["p", "M2 8h9.5M8 4.5L11.5 8 8 11.5"], ["p", "M14 2v12"]],
    layers: [["p", "M8 2l6.5 3.5L8 9 1.5 5.5z"], ["p", "M1.5 8.5L8 12l6.5-3.5"], ["p", "M1.5 11.5L8 15l6.5-3.5"]],
    hidden: [["p", "M1.5 8c1.8-3.2 4-4.5 6.5-4.5s4.7 1.3 6.5 4.5c-1.8 3.2-4 4.5-6.5 4.5S3.3 11.2 1.5 8z"], ["p", "M2.5 13.5l11-11"]],
    crosshair: [["c", 8, 8, 5], ["p", "M8 1v4M8 11v4M1 8h4M11 8h4"]],
    camera: [["p", "M1.5 4.5h3l1.5-2h4l1.5 2h3v9h-13z"], ["c", 8, 9, 2.5]],
    photo: [["p", "M1.5 2.5h13v11h-13z"], ["p", "M1.5 11l4-4 3 3 2-2 4 4"], ["C", 11, 5.5, 1.1]],
    play: [["f", "M4 2.5l9 5.5-9 5.5z"]],
    pause: [["f", "M3.5 2.5h3v11h-3zM9.5 2.5h3v11h-3z"]],
    back: [["f", "M14 2.5v11l-6-5.5zM8 2.5v11L2 8z"]],
    forward: [["f", "M2 2.5v11l6-5.5zM8 2.5v11l6-5.5z"]],
    chevronDown: [["p", "M3.5 6l4.5 4.5L12.5 6"]],
    chevronRight: [["p", "M6 3.5l4.5 4.5L6 12.5"]],
    close: [["p", "M3.5 3.5l9 9M12.5 3.5l-9 9"]],
    warning: [["p", "M8 1.75l6.75 12H1.25z"], ["p", "M8 6v3.75"], ["C", 8, 11.75, 0.8]],
    info: [["c", 8, 8, 6.25], ["p", "M8 7v4.5"], ["C", 8, 4.75, 0.8]],
    lock: [["p", "M3 7h10v7.5H3z"], ["p", "M5 7V5a3 3 0 016 0v2"]],
    gpu: [["p", "M3.5 3.5h9v9h-9z"], ["p", "M6 6h4v4H6zM6 1v2.5M10 1v2.5M6 12.5V15M10 12.5V15M1 6h2.5M1 10h2.5M12.5 6H15M12.5 10H15"]],
    online: [["C", 8, 8, 2.5], ["p", "M4 4a5.7 5.7 0 000 8M12 4a5.7 5.7 0 010 8"]],
    offline: [["c", 8, 8, 2.5], ["p", "M4 4a5.7 5.7 0 000 8M12 4a5.7 5.7 0 010 8M2 14L14 2"]],
    clean: [["p", "M3 1.5h7l3 3v10H3z"], ["p", "M10 1.5v3h3"]],
    water: [["p", "M1 5.5c1.75-1.5 3.25-1.5 5 0s3.25 1.5 5 0 2.75-1.5 4 0M1 10.5c1.75-1.5 3.25-1.5 5 0s3.25 1.5 5 0 2.75-1.5 4 0"]],
    skyline: [["p", "M1 14.5h14M2 14.5V8h3v6.5M5 14.5V4h4v10.5M9 14.5V7h2.5V5H14v9.5"]],
    mask: [["p", "M1.5 9.5h13v5h-13z"], ["p", "M3 14.5l4-5M7 14.5l4-5M11 14.5l3.5-4.4"]],
    sector: [["p", "M8 8L3 2.5a8 8 0 0110 0z"], ["c", 8, 8, 1]],
    zoom: [["c", 6.75, 6.75, 4.75], ["p", "M10.25 10.25L14.5 14.5"]],
    ruler: [["p", "M1.5 5.5h13v5h-13z"], ["p", "M4 5.5v2M6.5 5.5v3M9 5.5v2M11.5 5.5v3"]],
    matrix: [["p", "M2 2h12v12H2zM2 6h12M2 10h12M6 2v12M10 2v12"]],
    log: [["p", "M5 3.5h9.5M5 8h9.5M5 12.5h9.5"], ["C", 2.25, 3.5, 0.9], ["C", 2.25, 8, 0.9], ["C", 2.25, 12.5, 0.9]],
    bracket: [["p", "M5 1.5H2.5v13H5"], ["p", "M7 4.5h7M7 8h7M7 11.5h7"]],
    pin: [["c", 8, 8, 6], ["f", "M8 3.5l3.9 6.75H4.1z"]],
    replay: [["p", "M2.5 8a5.5 5.5 0 105.5-5.5H5"], ["p", "M6.5 0.75L4.75 2.5 6.5 4.25"]],
    plus: [["p", "M8 2.5v11M2.5 8h11"]],
    minus: [["p", "M2.5 8h11"]],
    file: [["p", "M3 1.5h7l3 3v10H3z"], ["p", "M10 1.5v3h3M5.5 8.5h5M5.5 11h5"]],
    special: [["p", "M2 3.5h12v9H2z"], ["p", "M5 6l2.5 4M7.5 6L5 10M9.5 7h2c.9 0 1 1.5 0 1.5h-.75.75c1 0 1 1.5 0 1.5h-2"]]
  };
  function Icon({ name, size, title, className, style }) {
    const els = ICONS[name] || ICONS.info;
    const kids = els.map((e, i) => {
      if (e[0] === "p") return h("path", { key: i, d: e[1], fill: "none" });
      if (e[0] === "f") return h("path", { key: i, d: e[1], fill: "currentColor", stroke: "none" });
      if (e[0] === "c") return h("circle", { key: i, cx: e[1], cy: e[2], r: e[3], fill: "none" });
      return h("circle", { key: i, cx: e[1], cy: e[2], r: e[3], fill: "currentColor", stroke: "none" });
    });
    return h("svg", {
      className: cx("aq-icon", className),
      viewBox: "0 0 16 16",
      width: size || void 0,
      height: size || void 0,
      stroke: "currentColor",
      strokeWidth: 1.5,
      strokeLinecap: "square",
      strokeLinejoin: "miter",
      role: title ? "img" : void 0,
      "aria-hidden": title ? void 0 : true,
      "aria-label": title,
      style,
      focusable: "false"
    }, title ? h("title", null, title) : null, ...kids);
  }

  // src/base.tsx
  function Density({ value = "console", theme, className, style, children }) {
    return h(DensityContext.Provider, { value }, h("div", { "data-density": value, "data-theme": theme, className: cx("aq-root", className), style }, children));
  }
  function CostTag({ multiplier, label }) {
    const T = useT();
    return h(
      "span",
      { className: cx("aq-costtag", T.data), title: `Costs ${fmtMult(multiplier)} on every guess after this` },
      h(Icon, { name: "cost" }),
      h("span", null, fmtMult(multiplier)),
      label ? h("span", { className: "aq-costtag-l" }, label) : null
    );
  }
  function Button({ variant = "secondary", icon, cost, shortcut, busy, disabled, pressed, forceState, onClick, children, title, className }) {
    const T = useT();
    return h(
      "button",
      {
        type: "button",
        className: cx("aq-btn", "aq-btn-" + variant, T.label, forceState && "is-" + forceState, busy && "is-busy", className),
        disabled: disabled || !!busy,
        "aria-pressed": pressed,
        onClick,
        title,
        "aria-busy": busy ? true : void 0
      },
      icon ? h(Icon, { name: icon }) : null,
      h("span", { className: "aq-btn-l" }, busy || children),
      variant === "skip" ? h("span", { className: "aq-free" }, "free") : null,
      cost != null ? h(CostTag, { multiplier: cost }) : null,
      shortcut ? h(KeyCap, null, shortcut) : null
    );
  }
  function KeyCap({ children }) {
    const T = useT();
    return h("kbd", { className: cx("aq-key", T.dataSm) }, children);
  }
  function Badge({ tone = "neutral", icon, solid, children, title }) {
    const T = useT();
    return h("span", { className: cx("aq-badge", "aq-tone-" + tone, solid && "is-solid", T.label), title }, icon ? h(Icon, { name: icon }) : null, children);
  }
  function Stamp({ kind = "ruled-out", children }) {
    const T = useT();
    const text = children || { "ruled-out": "RULED OUT", confirmed: "CONFIRMED BY MATCH", submitted: "SUBMITTED", estimate: "ESTIMATE" }[kind];
    return h("span", { className: cx("aq-stamp", "aq-stamp-" + kind, T.stamp) }, text);
  }
  function Tabs({ tabs, value, onChange, label }) {
    const T = useT();
    const [cur, setCur] = useState(value);
    const sel = onChange ? value : cur;
    return h(
      "div",
      { className: "aq-tabs", role: "tablist", "aria-label": label },
      tabs.map((t) => h("button", {
        key: t.id,
        role: "tab",
        type: "button",
        "aria-selected": sel === t.id,
        tabIndex: sel === t.id ? 0 : -1,
        className: cx("aq-tab", T.label, sel === t.id && "is-on"),
        onClick: () => onChange ? onChange(t.id) : setCur(t.id)
      }, t.icon ? h(Icon, { name: t.icon }) : null, t.label, t.count != null ? h("span", { className: cx("aq-tab-n", T.dataSm) }, t.count) : null))
    );
  }
  function Toggle({ label, on = false, swatch, icon, disabled, onChange, hint }) {
    const T = useT();
    const [s, setS] = useState(on);
    const val = onChange ? on : s;
    return h(
      "label",
      { className: cx("aq-toggle", T.label, val && "is-on", disabled && "is-disabled") },
      h("input", { type: "checkbox", role: "switch", checked: val, disabled, onChange: (e) => onChange ? onChange(e.target.checked) : setS(e.target.checked) }),
      h("span", { className: "aq-toggle-track", "aria-hidden": true }, h("span", { className: "aq-toggle-knob" })),
      swatch ? h("span", { className: "aq-swatch", style: { background: swatch } }) : null,
      icon ? h(Icon, { name: icon }) : null,
      h("span", { className: "aq-toggle-l" }, label),
      hint ? h("span", { className: cx("aq-toggle-hint", T.micro) }, hint) : null
    );
  }
  function Segmented({ options, value, label, onChange }) {
    const T = useT();
    const [cur, setCur] = useState(value);
    const sel = onChange ? value : cur;
    return h(
      "div",
      { className: "aq-seg", role: "radiogroup", "aria-label": label },
      options.map((o) => h(
        "button",
        { key: o.id, type: "button", role: "radio", "aria-checked": sel === o.id, className: cx("aq-seg-o", T.label, sel === o.id && "is-on"), onClick: () => onChange ? onChange(o.id) : setCur(o.id) },
        o.icon ? h(Icon, { name: o.icon }) : null,
        o.label
      ))
    );
  }
  function Tooltip({ content, open, children, side = "top" }) {
    const T = useT();
    return h("span", { className: cx("aq-tip-wrap", open && "is-open") }, children, h("span", { role: "tooltip", className: cx("aq-tip", "aq-tip-" + side, T.micro) }, content));
  }
  function Toast({ tone = "neutral", icon, title, body, action }) {
    const T = useT();
    return h(
      "div",
      { className: cx("aq-toast", "aq-tone-" + tone), role: "status" },
      h(Icon, { name: icon || (tone === "contra" ? "warning" : tone === "cost" ? "cost" : "info") }),
      h("div", { className: "aq-toast-b" }, h("div", { className: T.heading }, title), body ? h("div", { className: cx(T.body, "aq-ink2") }, body) : null),
      action ? h(Button, { variant: "quiet" }, action) : null
    );
  }
  function Dialog({ title, children, actions, inline, tone = "neutral" }) {
    const T = useT();
    const box = h(
      "div",
      { className: cx("aq-dialog", "aq-tone-" + tone), role: "dialog", "aria-modal": true, "aria-label": title },
      h("div", { className: cx("aq-dialog-t", T.title) }, title),
      h("div", { className: cx("aq-dialog-b", T.body) }, children),
      actions ? h("div", { className: "aq-dialog-a" }, actions) : null
    );
    return h("div", { className: cx("aq-scrim", inline && "is-inline") }, box);
  }
  function EmptyState({ icon = "info", title, body, action }) {
    const T = useT();
    return h("div", { className: "aq-empty" }, h(Icon, { name: icon }), h("div", { className: T.heading }, title), body ? h("div", { className: cx(T.body, "aq-ink2") }, body) : null, action || null);
  }
  function WaitState({ what, who, elapsed, deadline, partial, fallback }) {
    const T = useT();
    const frac = deadline ? Math.min(1, elapsed / deadline) : 0;
    return h(
      "div",
      { className: "aq-wait", role: "status", "aria-live": "polite" },
      h("div", { className: "aq-wait-h" }, h(Icon, { name: "running", className: "aq-ink1" }), h("span", { className: T.heading }, what), who ? h("span", { className: cx("aq-ink3", T.label) }, who) : null),
      deadline ? h("div", { className: "aq-deadline", "aria-hidden": true }, h("span", { style: { width: `${frac * 100}%` } })) : null,
      h("div", { className: cx("aq-wait-m", T.data) }, h("span", null, fmtTime(elapsed)), deadline ? h("span", { className: "aq-ink3" }, ` of ${fmtTime(deadline)} deadline`) : null),
      partial ? h("div", { className: cx(T.body, "aq-ink2") }, partial) : null,
      fallback ? h("div", { className: cx(T.micro, "aq-ink3") }, `If it runs out: ${fallback}`) : null
    );
  }

  // src/shell.tsx
  var shell_exports = {};
  __export(shell_exports, {
    CaseCard: () => CaseCard,
    CleanStateCheck: () => CleanStateCheck,
    GpuMeter: () => GpuMeter,
    ModelChip: () => ModelChip,
    ModelRoster: () => ModelRoster,
    MultiplierChip: () => MultiplierChip,
    RunBar: () => RunBar,
    ScoreReadout: () => ScoreReadout,
    ShortcutBar: () => ShortcutBar,
    SystemBadge: () => SystemBadge,
    Timer: () => Timer,
    Wordmark: () => Wordmark
  });

  // src/wordmark-data.ts
  var WORDMARK = { vb: "-20 -1540 4060 2010", d: "M691 -659 697 -614Q576 -575 502 -539Q427 -503 388 -466Q348 -429 334 -388Q319 -347 319 -296Q319 -212 362 -171Q406 -130 470 -130Q519 -130 555 -150Q591 -169 612 -207Q632 -246 632 -303V-768Q632 -862 585 -912Q537 -962 439 -962Q392 -962 347 -956Q302 -950 275 -939L324 -986Q319 -937 312 -895Q305 -853 296 -823Q286 -793 274 -776Q259 -758 231 -747Q202 -736 170 -736Q127 -736 105 -752Q82 -767 82 -798Q82 -841 124 -885Q166 -929 235 -965Q303 -1002 385 -1024Q467 -1046 545 -1046Q667 -1046 740 -1011Q813 -976 846 -912Q879 -848 879 -762V-189Q879 -159 888 -141Q898 -122 915 -114Q933 -106 956 -106Q986 -106 1016 -115Q1046 -124 1078 -145V-109Q1003 -27 942 -2Q881 22 811 22Q745 22 707 -5Q668 -32 651 -86Q634 -140 631 -219L638 -216Q620 -143 581 -89Q543 -36 488 -7Q434 22 367 22Q235 22 154 -46Q73 -114 73 -239Q73 -304 95 -354Q117 -404 181 -449Q245 -495 368 -545Q491 -595 691 -659Z M1376 -547Q1376 -405 1406 -313Q1436 -221 1499 -177Q1561 -133 1657 -133Q1727 -133 1790 -157Q1854 -181 1911 -241L1922 -218Q1861 -146 1810 -99Q1759 -53 1714 -26Q1669 1 1627 12Q1585 22 1544 22Q1413 22 1318 -38Q1222 -99 1170 -208Q1117 -317 1117 -462Q1117 -648 1190 -778Q1262 -909 1389 -978Q1516 -1046 1681 -1046Q1741 -1046 1802 -1038Q1863 -1030 1922 -1012Q1980 -994 2031 -966L1916 -951L2130 -1047L2147 -1036L2103 -824V383L2232 414V443H1707V414L1856 383V-787Q1856 -879 1796 -935Q1736 -992 1643 -992Q1559 -992 1499 -944Q1439 -895 1407 -796Q1376 -698 1376 -547Z M2635 -324Q2635 -263 2655 -223Q2676 -183 2717 -164Q2759 -145 2824 -145Q2891 -145 2952 -165Q3013 -185 3058 -212L3070 -189Q2993 -122 2937 -81Q2882 -40 2837 -18Q2793 5 2752 12Q2711 20 2662 20Q2522 20 2455 -57Q2389 -135 2389 -294V-933L2228 -975V-1013L2643 -1034L2635 -938ZM3019 30 3012 -161V-933L2854 -975V-1013L3269 -1034L3258 -938V-121Q3267 -117 3286 -108Q3305 -99 3328 -89Q3351 -78 3374 -68Q3396 -57 3412 -50V-26L3029 30Z M3841 -1055V-854V-59L3967 -28V0H3466V-28L3595 -60V-827Q3584 -836 3563 -851Q3543 -866 3517 -886Q3490 -907 3459 -931V-952L3831 -1055Z", cx: 3713, cy: -1245, dot: 112, ring: 262 };

  // src/shell.tsx
  function Wordmark({ size = 24, mark, title = "Aqui" }) {
    const W = WORDMARK;
    const ring = h("circle", { cx: W.cx, cy: W.cy, r: W.ring, fill: "none", stroke: "currentColor", strokeWidth: 52, strokeDasharray: "360 190", strokeDashoffset: 120, className: "aq-wm-ring" });
    const dot = h("circle", { cx: W.cx, cy: W.cy, r: W.dot, className: "aq-wm-dot" });
    if (mark) {
      return h(
        "svg",
        { className: "aq-wordmark is-mark", viewBox: "16 4 32 52", height: size, width: Math.round(size * 32 / 52), role: "img", "aria-label": title },
        h("rect", { x: 26.5, y: 31, width: 11, height: 24, fill: "currentColor" }),
        h("circle", { cx: 32, cy: 17.5, r: 10, fill: "none", strokeWidth: 4, strokeDasharray: "14 7", strokeDashoffset: 4, className: "aq-wm-ring" }),
        h("circle", { cx: 32, cy: 17.5, r: 4.5, className: "aq-wm-dot" })
      );
    }
    return h("svg", { className: "aq-wordmark", viewBox: W.vb, height: size, width: Math.round(size * 4060 / 2010), role: "img", "aria-label": title }, h("path", { d: W.d, fill: "currentColor" }), ring, dot);
  }
  function Timer({ label, used, budget, warnAt = 0.8, compact }) {
    const T = useT();
    const frac = used / budget;
    const state = frac > 1 ? "over" : frac >= warnAt ? "warn" : "ok";
    return h(
      "div",
      { className: cx("aq-timer", "is-" + state, compact && "is-compact"), role: "timer", "aria-label": `${label}: ${fmtTime(used)} of ${fmtTime(budget)}` },
      h("div", { className: cx("aq-timer-l", T.micro) }, h(Icon, { name: "clock" }), label),
      h(
        "div",
        { className: "aq-timer-v" },
        h("span", { className: T.readout }, fmtTime(used)),
        h("span", { className: cx(T.data, "aq-ink3") }, " / " + fmtTime(budget)),
        state === "over" ? h("span", { className: cx("aq-over", T.label) }, "+" + fmtTime(used - budget) + " over") : null
      ),
      h("div", { className: "aq-timer-bar", "aria-hidden": true }, h("span", { style: { width: `${Math.min(1, frac) * 100}%` } }), h("i", { style: { left: `${warnAt * 100}%` } }))
    );
  }
  function MultiplierChip({ value, history = [], open }) {
    const T = useT();
    const [o, setO] = useState(!!open);
    const spent = value < 1;
    return h(
      "div",
      { className: "aq-mult-wrap" },
      h(
        "button",
        { type: "button", className: cx("aq-mult", spent && "is-spent"), "aria-expanded": o, onClick: () => setO(!o), title: "Multiplier applied to every guess produced from now on" },
        h("span", { className: cx(T.micro, "aq-mult-l") }, "Multiplier"),
        h("span", { className: T.readout }, fmtMult(value)),
        h(Icon, { name: "chevronDown" })
      ),
      o ? h(
        "div",
        { className: "aq-mult-pop", role: "dialog", "aria-label": "Multiplier history" },
        h("div", { className: cx(T.label, "aq-ink2") }, "Applies to every guess produced after it, for this panorama only"),
        h("ol", { className: "aq-mult-list" }, history.map((e, i) => {
          var _a, _b;
          return h(
            "li",
            { key: i, className: T.body },
            h("span", { className: cx(T.data, "aq-ink3") }, fmtTime(e.t)),
            h("span", null, e.what),
            h("span", { className: cx(T.data, e.m < ((_b = (_a = history[i - 1]) == null ? void 0 : _a.m) != null ? _b : 1) ? "aq-c-cost" : "aq-ink2") }, fmtMult(e.m))
          );
        }))
      ) : null
    );
  }
  function ScoreReadout({ expected, range, max = MAX_SCORE, special, urbanUnknown, size = "md" }) {
    const T = useT();
    const k = special ? 3 : 1;
    if (urbanUnknown) {
      return h(
        "div",
        { className: "aq-score is-split" },
        h("div", { className: cx(T.micro, "aq-score-l") }, "Expected score · label unknown"),
        h(
          "div",
          { className: "aq-score-two" },
          h("span", null, h("span", { className: cx(T.label, "aq-ink3") }, "if Urban "), h("span", { className: T.readout }, "≈ " + fmtInt(urbanUnknown.urban * k))),
          h("span", null, h("span", { className: cx(T.label, "aq-ink3") }, "if non-Urban "), h("span", { className: T.readout }, "≈ " + fmtInt(urbanUnknown.nonUrban * k)))
        )
      );
    }
    return h(
      "div",
      { className: cx("aq-score", size === "xl" && "is-xl") },
      h("div", { className: cx(T.micro, "aq-score-l") }, special ? "Expected score · estimate · ×3 Special One" : "Expected score · estimate"),
      h(
        "div",
        { className: "aq-score-v" },
        h("span", { className: size === "xl" ? T.score : T.readout }, "≈ " + fmtInt(expected * k)),
        h("span", { className: cx(T.data, "aq-ink3") }, " of " + fmtInt(Math.floor(max * k)))
      ),
      range ? h("div", { className: cx(T.micro, "aq-ink3") }, `range ${fmtInt(range[0] * k)}–${fmtInt(range[1] * k)}`) : null
    );
  }
  function GpuMeter({ used, total = 16, models, compact }) {
    const T = useT();
    const warn = used > total * 0.875;
    return h(
      "div",
      { className: cx("aq-gpu", warn && "is-warn", compact && "is-compact") },
      h("div", { className: cx(T.micro, "aq-gpu-l") }, h(Icon, { name: "gpu" }), "GPU memory"),
      h("div", { className: "aq-gpu-v" }, h("span", { className: T.data }, used.toFixed(1)), h("span", { className: cx(T.data, "aq-ink3") }, ` / ${total} GB`)),
      h(
        "div",
        { className: "aq-gpu-bar", role: "meter", "aria-valuemin": 0, "aria-valuemax": total, "aria-valuenow": used },
        models && models.length ? models.map((m, i) => h("span", { key: i, title: `${m.name} ${m.gb} GB`, style: { width: `${m.gb / total * 100}%` } })) : h("span", { style: { width: `${used / total * 100}%` } })
      )
    );
  }
  function SystemBadge({ kind, speed }) {
    const T = useT();
    const map = {
      "worker-online": ["online", "GPU worker online", "ok"],
      "worker-offline": ["offline", "GPU worker offline — answer kept", "bad"],
      "tiles-offline": ["offline", "Map tiles offline · outlines", "warn"],
      clean: ["clean", "Clean state verified", "ok"],
      replay: ["replay", `Replay ${speed || 1}× · real timestamps`, "replay"]
    };
    const [icon, text, tone] = map[kind];
    return h("span", { className: cx("aq-sys", "is-" + tone, T.label) }, h(Icon, { name: icon }), text);
  }
  function ModelChip({ name, role, actor = "model", local = true, size = "md" }) {
    const T = useT();
    const sub = actor === "solver" ? "code, not a model" : actor === "team" ? "human" : local ? "local · open weights" : null;
    return h(
      "span",
      { className: cx("aq-mchip", "aq-actor-" + actor, "is-" + size) },
      h(Icon, { name: actor }),
      h("span", { className: cx(T.label, "aq-mchip-n") }, name),
      size === "md" && (role || sub) ? h("span", { className: cx(T.micro, "aq-mchip-r") }, [role, sub].filter(Boolean).join(" · ")) : null
    );
  }
  function ModelRoster({ models, compact, title = "Local models" }) {
    const T = useT();
    const total = models.filter((m) => m.state === "resident" || m.state === "running").reduce((a, m) => a + (m.gb || 0), 0);
    return h(
      "div",
      { className: cx("aq-roster", compact && "is-compact") },
      h("div", { className: "aq-roster-h" }, h("span", { className: T.heading }, title), h("span", { className: cx(T.micro, "aq-ink3") }, `all open weights · ${total.toFixed(1)} GB resident`)),
      h("ul", null, models.map((m) => h(
        "li",
        { key: m.id, className: cx("aq-roster-row", "is-" + m.state) },
        h(Icon, { name: m.state === "running" ? "running" : m.state === "standby" ? "queued" : "model", className: "aq-roster-i" }),
        h("span", { className: "aq-roster-n" }, h("span", { className: T.label }, m.name), compact ? null : h("span", { className: cx(T.micro, "aq-ink3") }, m.role)),
        h("span", { className: cx(T.micro, "aq-roster-s") }, m.state === "standby" ? "fallback · standby" : m.state),
        h("span", { className: cx(T.dataSm, "aq-roster-g") }, m.cpu ? "CPU" : m.gb ? `${m.gb.toFixed(1)} GB` : "—")
      )))
    );
  }
  function CaseCard(p) {
    const T = useT();
    const words = { waiting: "Waiting", processing: "Processing", "needs-answer": "Question waiting", done: "Answer ready", submitted: "Submitted" };
    const icon = { waiting: "queued", processing: "running", "needs-answer": "question", done: "done", submitted: "submit" };
    return h(
      "div",
      { className: cx("aq-case", "is-" + p.status, p.special && "is-special", p.current && "is-current"), tabIndex: 0, role: "button", "aria-label": `${p.label}, ${words[p.status]}` },
      h("div", { className: "aq-case-h" }, h(Icon, { name: "lock", className: "aq-ink3" }), h("span", { className: T.heading }, p.label), p.special ? h(Badge, { tone: "outline", icon: "special" }, "×3 Special One") : null),
      h("div", { className: cx("aq-case-s", T.label) }, h(Icon, { name: icon[p.status] }), words[p.status]),
      h(
        "div",
        { className: cx("aq-case-m", T.data) },
        p.status === "processing" ? h("span", { className: "aq-ink2" }, `${p.stage} · ${fmtTime(p.elapsed || 0)}`) : null,
        p.status === "needs-answer" ? h("span", { className: "aq-ink2" }, `gain +${Math.round((p.gain || 0) * 100)}% vs 5.26%`) : null,
        (p.status === "done" || p.status === "submitted" || p.status === "needs-answer") && p.expected ? h("span", null, "≈ " + fmtInt(p.expected * (p.special ? 3 : 1))) : null,
        p.multiplier != null && p.status !== "waiting" ? h("span", { className: p.multiplier < 1 ? "aq-c-cost" : "aq-ink3" }, fmtMult(p.multiplier)) : null,
        p.used != null ? h("span", { className: "aq-ink3" }, fmtTime(p.used)) : null,
        p.status === "waiting" ? h("span", { className: "aq-ink3" }, "sealed until it runs") : null
      )
    );
  }
  function ShortcutBar({ keys }) {
    const T = useT();
    return h("div", { className: "aq-keys", role: "note", "aria-label": "Keyboard shortcuts" }, keys.map((k, i) => h("span", { key: i, className: cx("aq-keys-i", T.micro) }, h(KeyCap, null, k.k), k.label)));
  }
  function CleanStateCheck({ items, caseLabel = "this case" }) {
    const T = useT();
    const list = items || [{ label: "New model conversation", ok: true }, { label: "Evidence file empty", ok: true }, { label: "Nothing carried over from other cases", ok: true }];
    return h(
      "div",
      { className: "aq-clean", role: "status" },
      h("div", { className: "aq-clean-h" }, h(Icon, { name: "clean" }), h("span", { className: T.heading }, `Clean state for ${caseLabel}`)),
      h("ul", null, list.map((it, i) => h("li", { key: i, className: cx(T.body, it.ok ? "" : "is-bad") }, h(Icon, { name: it.ok ? "done" : "failed" }), it.label)))
    );
  }
  function RunBar({ c, special, online = true, tilesOffline, replay, showWordmark = true }) {
    const T = useT();
    const r = c.run;
    const unknown = c.urban === "unknown";
    return h(
      "header",
      { className: "aq-runbar", role: "banner" },
      showWordmark ? h("div", { className: "aq-runbar-wm" }, h(Wordmark, { size: useDensity() === "stage" ? 36 : 22 })) : null,
      h(
        "div",
        { className: "aq-runbar-case" },
        h("span", { className: T.heading }, c.label),
        special || c.special ? h(Badge, { tone: "outline", icon: "special" }, "×3 Special One") : null,
        h("span", { className: cx(T.micro, "aq-ink3") }, `${c.urban === "urban" ? "Urban" : c.urban === "non-urban" ? "Non-urban" : "Urban label unknown"} · ${c.urbanSource}`)
      ),
      h(Timer, { label: "This panorama", used: r.used, budget: r.budget }),
      h(Timer, { label: "Session", used: r.session, budget: r.sessionBudget, compact: true }),
      h(MultiplierChip, { value: r.multiplier, history: c.multiplierHistory }),
      unknown ? h(ScoreReadout, { expected: r.expected, urbanUnknown: r.split }) : h(ScoreReadout, { expected: r.expected, special: special || c.special }),
      h(GpuMeter, { used: r.gpu, total: r.gpuMax, compact: true }),
      h("div", { className: "aq-runbar-sys" }, replay ? h(SystemBadge, { kind: "replay", speed: replay }) : h(SystemBadge, { kind: online ? "worker-online" : "worker-offline" }), tilesOffline ? h(SystemBadge, { kind: "tiles-offline" }) : null)
    );
  }

  // src/panorama.tsx
  var panorama_exports = {};
  __export(panorama_exports, {
    BearingRuler: () => BearingRuler,
    LayerToggles: () => LayerToggles,
    PanoramaStrip: () => PanoramaStrip,
    PerspScene: () => PerspScene,
    Viewer360: () => Viewer360,
    ZoomCrop: () => ZoomCrop,
    sceneFor: () => sceneFor
  });

  // src/scene.ts
  var D2R = Math.PI / 180;
  var R2D = 180 / Math.PI;
  var dir = (yaw) => [Math.sin(yaw * D2R), Math.cos(yaw * D2R)];
  var EYE = 1.7;
  var P = {
    sky: "#b9c9d3",
    skyR: "#c6d4dc",
    ground: "#8d8a84",
    pave: "#9b978f",
    quay: "#7c7a75",
    water: "#4d6670",
    water2: "#5b7580",
    granite: "#8e8c87",
    granite2: "#a19d95",
    plaster: "#d8cfbd",
    ochre: "#c9a35a",
    white: "#e6e2d8",
    azulejo: "#5f7fa8",
    azulejo2: "#dfe5ec",
    window: "#3b4247",
    window2: "#4a5257",
    door: "#2f3437",
    roof: "#9a5a43",
    far: "#9aa4a6",
    far2: "#8b979b",
    hill: "#7f8f86",
    sign: "#2c3236",
    signText: "#efe9dc",
    field: "#b8a46a",
    field2: "#a8955c",
    soil: "#9a6448",
    soil2: "#8a573e",
    grass: "#8d9a5c",
    trunk: "#8b4a32",
    trunkOld: "#5f564b",
    canopy: "#55663f",
    canopy2: "#4a5a37",
    farm: "#efece4",
    trim: "#3f6aa0",
    hills: "#8a9a8a",
    hills2: "#99a796"
  };
  function facade(polys, kp, o) {
    const m = (o.a + o.b) / 2;
    const end = (yaw) => {
      const k = o.d / Math.cos((yaw - m) * D2R);
      const [s, c] = dir(yaw);
      return [s * k, c * k];
    };
    const A2 = end(o.a), B2 = end(o.b);
    const L = Math.hypot(B2[0] - A2[0], B2[1] - A2[1]);
    const at = (u, z) => [A2[0] + (B2[0] - A2[0]) * (u / L), A2[1] + (B2[1] - A2[1]) * (u / L), z];
    const depth = o.d;
    polys.push({ pts: [at(0, 0), at(L, 0), at(L, o.h), at(0, o.h)], fill: o.color, depth, seg: "building", kind: "wall" });
    polys.push({ pts: [at(0, o.h), at(L, o.h), at(L, o.h + 0.6), at(0, o.h + 0.6)], fill: P.roof, depth: depth - 0.01, seg: "building" });
    if (o.azulejo) polys.push({ pts: [at(L * 0.08, 3.2), at(L * 0.92, 3.2), at(L * 0.92, o.h - 0.4), at(L * 0.08, o.h - 0.4)], fill: P.azulejo, depth: depth - 0.02, seg: "building", kind: "azulejo" });
    const bay = o.bay || 3.2, n = Math.max(1, Math.floor(L / bay));
    const floors = o.floors || Math.max(1, Math.floor((o.h - 3.4) / 3.1));
    for (let i = 0; i < n; i++) {
      const u0 = (i + 0.3) * (L / n), u1 = (i + 0.7) * (L / n);
      for (let f = 0; f < floors; f++) {
        const z0 = 3.8 + f * 3.1, z1 = z0 + 1.8;
        if (z1 > o.h - 0.3) break;
        polys.push({ pts: [at(u0, z0), at(u1, z0), at(u1, z1), at(u0, z1)], fill: (i + f) % 3 ? P.window : P.window2, depth: depth - 0.03, seg: "building", kind: "window" });
        kp.push(at(u0, z0), at(u1, z1), at(u0, z1), at(u1, z0));
        if (o.balcony && f < 2) polys.push({ pts: [at(u0 - 0.25, z0 - 0.1), at(u1 + 0.25, z0 - 0.1), at(u1 + 0.25, z0 + 0.7), at(u0 - 0.25, z0 + 0.7)], fill: "none", stroke: "#2a2f33", sw: 1.2, depth: depth - 0.04, seg: "building" });
      }
      if (o.shop !== false) polys.push({ pts: [at(u0 - 0.2, 0), at(u1 + 0.2, 0), at(u1 + 0.2, 2.6), at(u0 - 0.2, 2.6)], fill: P.door, depth: depth - 0.03, seg: "building", kind: "door" });
    }
  }
  var URBAN = null;
  function urbanScene() {
    if (URBAN) return URBAN;
    const polys = [], discs = [], kp = [];
    for (let y = 104; y < 172; y += 5.5) facade(polys, [], { a: y, b: y + 5, d: 210 + y % 3 * 15, h: 10 + y * 7 % 9, color: y % 2 ? P.far : P.far2, bay: 6, floors: 2, shop: false });
    polys.push(...groundStrip(102, 174, 240, 260, P.hill, "building", 34));
    polys.push(groundPoly(arcPts(100, 176, 9, 200, 20), P.water, "water", 150));
    polys.push(groundPoly(arcPts(100, 176, 7.5, 9, 20), P.quay, "road", 8));
    facade(polys, kp, { a: 18, b: 74, d: 17, h: 14.5, color: P.plaster, floors: 3, balcony: true });
    facade(polys, kp, { a: 74, b: 104, d: 28, h: 17, color: P.ochre, floors: 4 });
    facade(polys, kp, { a: 172, b: 236, d: 14, h: 13, color: P.granite2, floors: 3 });
    facade(polys, kp, { a: 236, b: 281, d: 10, h: 11.5, color: P.white, floors: 2, balcony: true });
    facade(polys, kp, { a: 281, b: 321, d: 12, h: 15, color: P.granite, floors: 3, balcony: true });
    facade(polys, kp, { a: 321, b: 360, d: 16, h: 16, color: P.azulejo2, azulejo: true, floors: 3 });
    facade(polys, kp, { a: 0, b: 18, d: 16, h: 16, color: P.azulejo2, azulejo: true, floors: 3 });
    sign(polys, 38, 6.5, 17, 7, 2.6);
    sign(polys, 212.5, -3.1, 14, 4.2, 1.6);
    sign(polys, 289, 2, 12, 5, 1.4);
    for (const y of [246, 252, 258]) post(polys, y, 5.2, 0.9, 0.16, "#3a3f42");
    post(polys, 96, 9, 5.5, 0.12, "#2f3437");
    URBAN = { polys, discs, sky: P.sky, ground: P.pave, groundSeg: "road", sun: { yaw: 141, el: 22 }, keypoints: kp };
    return URBAN;
  }
  var RURAL = null;
  function ruralScene() {
    if (RURAL) return RURAL;
    const polys = [], discs = [];
    polys.push(groundPoly(arcPts(0, 360, 60, 900, 72), P.field, "grass", 600));
    polys.push(groundPoly(arcPts(0, 360, 18, 60, 72), P.field2, "grass", 40));
    polys.push(groundPoly(blob(40, 9, 5, 3), P.grass, "grass", 9));
    polys.push(groundPoly(blob(250, 11, 6, 4), P.grass, "grass", 11));
    polys.push(groundPoly(blob(150, 26, 9, 5), P.soil, "ground", 26));
    polys.push(groundPoly(blob(300, 40, 14, 6), P.soil2, "ground", 40));
    const track = [];
    const tr = [];
    for (let t = 0; t <= 1.001; t += 0.05) {
      const dd = 2 + t * 160, yaw = 200 + Math.sin(t * 3) * 14;
      const [s, c] = dir(yaw);
      const [ps, pc] = dir(yaw + 90);
      const w2 = 1.6 + t * 0.4;
      track.push([s * dd + ps * w2, c * dd + pc * w2, 0]);
      tr.unshift([s * dd - ps * w2, c * dd - pc * w2, 0]);
    }
    polys.push({ pts: [...track, ...tr], fill: P.soil, depth: 20, seg: "ground", kind: "track" });
    {
      const [s, c] = dir(70), [ps, pc] = dir(160);
      const d = 420, w2 = 9;
      const a = [s * d - ps * w2, c * d - pc * w2, 0], b = [s * d + ps * w2, c * d + pc * w2, 0];
      polys.push({ pts: [a, b, [b[0], b[1], 5], [a[0], a[1], 5]], fill: P.farm, depth: d, seg: "building", kind: "farm" });
      polys.push({ pts: [a, b, [b[0], b[1], 0.9], [a[0], a[1], 0.9]], fill: P.trim, depth: d - 0.1, seg: "building" });
      polys.push({ pts: [[a[0], a[1], 5], [b[0], b[1], 5], [b[0], b[1], 5.4], [a[0], a[1], 5.4]], fill: P.trim, depth: d - 0.1, seg: "building" });
    }
    const trees = [[12, 16, 1], [30, 70, 0], [48, 120, 0], [88, 24, 1], [104, 260, 0], [118, 60, 0], [140, 180, 0], [150, 34, 1], [168, 95, 0], [184, 130, 0], [228, 19, 1], [246, 140, 0], [262, 48, 0], [282, 230, 0], [300, 13, 1], [318, 85, 0], [334, 38, 1], [352, 110, 0], [60, 160, 0], [210, 220, 0], [5, 300, 0], [74, 340, 0], [196, 310, 0], [330, 260, 0]];
    for (const [yaw, d, cork] of trees) tree(polys, discs, yaw, d, !!cork);
    const horizon = (y) => 0.9 + 0.55 * Math.sin((y * 2 + 30) * D2R) + 0.35 * Math.sin((y * 5 + 10) * D2R) + 0.2 * Math.sin(y * 11 * D2R);
    RURAL = { polys, discs, sky: P.skyR, ground: "#b09a62", groundSeg: "grass", horizon, horizonFill: P.hills, sun: { yaw: 178, el: 61 } };
    return RURAL;
  }
  function sign(polys, yaw, pitch, d, w2, hh) {
    const [s, c] = dir(yaw), [ps, pc] = dir(yaw + 90);
    const r = d, z = EYE + r * Math.tan(pitch * D2R), hw = Math.tan(w2 / 2 * D2R) * r, hh2 = Math.tan(hh / 2 * D2R) * r;
    const cx2 = s * (r - 0.3), cy = c * (r - 0.3);
    polys.push({ pts: [[cx2 - ps * hw, cy - pc * hw, z - hh2], [cx2 + ps * hw, cy + pc * hw, z - hh2], [cx2 + ps * hw, cy + pc * hw, z + hh2], [cx2 - ps * hw, cy - pc * hw, z + hh2]], fill: P.sign, depth: r - 0.3, seg: "building", kind: "sign" });
  }
  function post(polys, yaw, d, hgt, w2, fill) {
    const [s, c] = dir(yaw), [ps, pc] = dir(yaw + 90);
    const x = s * d, y = c * d;
    polys.push({ pts: [[x - ps * w2, y - pc * w2, 0], [x + ps * w2, y + pc * w2, 0], [x + ps * w2, y + pc * w2, hgt], [x - ps * w2, y - pc * w2, hgt]], fill, depth: d, seg: "building" });
  }
  function tree(polys, discs, yaw, d, cork) {
    const [s, c] = dir(yaw), [ps, pc] = dir(yaw + 90);
    const x = s * d, y = c * d, tw = 0.35, th = 2.2;
    polys.push({ pts: [[x - ps * tw, y - pc * tw, 0], [x + ps * tw, y + pc * tw, 0], [x + ps * tw, y + pc * tw, th + 0.6], [x - ps * tw, y - pc * tw, th + 0.6]], fill: cork ? P.trunk : P.trunkOld, depth: d, seg: "tree", kind: cork ? "cork" : "holm" });
    discs.push({ c: [x, y, th + 2.4], r: 4.2, ry: 2.4, fill: cork ? P.canopy : P.canopy2, depth: d - 0.5, seg: "tree" });
  }
  function arcPts(a, b, r0, r1, n) {
    const out = [];
    for (let i = 0; i <= n; i++) {
      const y = a + (b - a) * i / n;
      const [s, c] = dir(y);
      out.push([s * r1, c * r1, 0]);
    }
    for (let i = n; i >= 0; i--) {
      const y = a + (b - a) * i / n;
      const [s, c] = dir(y);
      out.push([s * r0, c * r0, 0]);
    }
    return out;
  }
  function blob(yaw, d, rx, ry) {
    const [s, c] = dir(yaw);
    const out = [];
    for (let i = 0; i < 18; i++) {
      const t = i / 18 * Math.PI * 2;
      out.push([s * d + Math.cos(t) * rx, c * d + Math.sin(t) * ry, 0]);
    }
    return out;
  }
  function groundPoly(pts, fill, seg, depth) {
    return { pts, fill, seg, depth };
  }
  function groundStrip(a, b, d, h2, fill, seg, n) {
    const pts = [];
    for (let i = 0; i <= n; i++) {
      const y = a + (b - a) * i / n;
      const [s, c] = dir(y);
      const z = 18 + 22 * Math.sin(i / n * Math.PI) + 6 * Math.sin(i * 1.7);
      pts.push([s * (d + 40), c * (d + 40), z]);
    }
    for (let i = n; i >= 0; i--) {
      const y = a + (b - a) * i / n;
      const [s, c] = dir(y);
      pts.push([s * (d + 40), c * (d + 40), 0]);
    }
    return [{ pts, fill, seg, depth: d + 40 }];
  }
  function toYawPitch(p, cam = [0, 0, EYE]) {
    const dx = p[0] - cam[0], dy = p[1] - cam[1], dz = p[2] - cam[2];
    let yaw = Math.atan2(dx, dy) * R2D;
    if (yaw < 0) yaw += 360;
    return [yaw, Math.atan2(dz, Math.hypot(dx, dy)) * R2D];
  }
  function densify(pts, maxLen) {
    const out = [];
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i], b = pts[(i + 1) % pts.length];
      const L = Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]);
      const n = Math.max(1, Math.ceil(L / maxLen));
      for (let k = 0; k < n; k++) out.push([a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n, a[2] + (b[2] - a[2]) * k / n]);
    }
    return out;
  }
  function equiPts(pts, W, H) {
    const dense = densify(pts, 1.5);
    let prev = null;
    const raw = [];
    for (const p of dense) {
      let [yaw, pitch] = toYawPitch(p);
      if (prev != null) {
        while (yaw - prev > 180) yaw -= 360;
        while (yaw - prev < -180) yaw += 360;
      }
      prev = yaw;
      raw.push([yaw / 360 * W, (90 - pitch) / 180 * H]);
    }
    const xs = raw.map((r) => r[0]);
    const min = Math.min(...xs), max = Math.max(...xs);
    const copies = [raw];
    if (min < 0) copies.push(raw.map((r) => [r[0] + W, r[1]]));
    if (max > W) copies.push(raw.map((r) => [r[0] - W, r[1]]));
    return copies;
  }
  function persp(pts, cam) {
    const f = cam.w / 2 / Math.tan(cam.fov / 2 * D2R);
    const [s, c] = dir(cam.yaw);
    const pr = (cam.pitch || 0) * D2R, cp = Math.cos(pr), sp = Math.sin(pr);
    const rel = densify(pts, 2).map((p) => {
      const dx = p[0] - cam.pos[0], dy = p[1] - cam.pos[1], dz = p[2] - cam.pos[2];
      const fwd0 = dx * s + dy * c, right = dx * c - dy * s;
      const fwd = fwd0 * cp + dz * sp, up = -fwd0 * sp + dz * cp;
      return [right, up, fwd];
    });
    const near = 0.3;
    const clipped = [];
    for (let i = 0; i < rel.length; i++) {
      const a = rel[i], b = rel[(i + 1) % rel.length];
      const ain = a[2] >= near, bin = b[2] >= near;
      if (ain) clipped.push(a);
      if (ain !== bin) {
        const t = (near - a[2]) / (b[2] - a[2]);
        clipped.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, near]);
      }
    }
    if (clipped.length < 3) return null;
    return clipped.map(([x, y, z]) => [cam.w / 2 + x / z * f, cam.h / 2 - y / z * f]);
  }
  function perspPoint(p, cam) {
    const r = persp([p, p, p], cam);
    return r ? r[0] : null;
  }
  var yawPitchToXY = (yaw, pitch, W, H) => [(yaw % 360 + 360) % 360 / 360 * W, (90 - pitch) / 180 * H];
  function skyline(sc, step = 2) {
    const out = [];
    for (let y = 0; y <= 360; y += step) {
      let best = sc.horizon ? sc.horizon(y) : 0;
      for (const p of sc.polys) {
        if (p.seg !== "building" && p.seg !== "tree") continue;
        if (p.kind && p.kind !== "wall" && p.kind !== "farm" && p.kind !== "cork" && p.kind !== "holm") continue;
        const yp = p.pts.map((q) => toYawPitch(q));
        const ys = yp.map((q) => q[0]);
        let lo = Math.min(...ys), hi = Math.max(...ys);
        if (hi - lo > 180) continue;
        if (y >= lo && y <= hi) best = Math.max(best, ...yp.map((q) => q[1]));
      }
      for (const d of sc.discs) {
        const [dy, dp] = toYawPitch(d.c);
        const ar = Math.atan2(d.r, Math.hypot(d.c[0], d.c[1])) * R2D;
        if (Math.abs((y - dy + 540) % 360 - 180) < ar) best = Math.max(best, dp + Math.atan2(d.ry || d.r, Math.hypot(d.c[0], d.c[1])) * R2D * 0.9);
      }
      out.push([y, best]);
    }
    return out;
  }

  // src/panorama.tsx
  var D2R2 = Math.PI / 180;
  var sceneFor = (c) => c.scene === "rural" ? ruralScene() : urbanScene();
  var SEG_VAR = { sky: "var(--seg-sky)", building: "var(--seg-building)", tree: "var(--seg-tree)", grass: "var(--seg-grass)", water: "var(--seg-water)", road: "var(--seg-road)", ground: "var(--seg-ground)" };
  var pts2 = (a) => a.map((p) => p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  function EquiScene({ sc, W, H, seg }) {
    const els = [];
    els.push(h("rect", { key: "sky", x: 0, y: 0, width: W, height: H / 2 + 1, fill: seg ? SEG_VAR.sky : sc.sky }));
    els.push(h("rect", { key: "gr", x: 0, y: H / 2, width: W, height: H / 2, fill: seg ? SEG_VAR[sc.groundSeg] : sc.ground }));
    if (!seg) for (const dd of sc.horizon ? [4, 9, 20] : [2.2, 3.2, 4.6, 6.5, 9.5]) {
      const y = (90 + Math.atan2(1.7, dd) / D2R2) / 180 * H;
      els.push(h("line", { key: "pv" + dd, x1: 0, x2: W, y1: y, y2: y, stroke: "#00000014", strokeWidth: 1 }));
    }
    if (sc.horizon) {
      const top = [];
      for (let y = 0; y <= 360; y += 2) top.push(yawPitchToXY(y === 360 ? 359.999 : y, sc.horizon(y), W, H));
      els.push(h("polygon", { key: "hz", points: pts2([...top, [W, H / 2 + 1], [0, H / 2 + 1]]), fill: seg ? SEG_VAR.tree : sc.horizonFill }));
    }
    if (sc.sun && !seg) {
      const [x, y] = yawPitchToXY(sc.sun.yaw, sc.sun.el, W, H);
      els.push(h("circle", { key: "sun", cx: x, cy: y, r: Math.max(2.5, W / 360 * 1.4), fill: "#f7f3e6" }));
    }
    const polys = [...sc.polys].sort((a, b) => b.depth - a.depth);
    polys.forEach((p, i) => {
      if (seg && (p.kind === "window" || p.kind === "door" || p.kind === "sign" || p.fill === "none")) return;
      for (const cp of equiPts(p.pts, W, H)) els.push(h("polygon", { key: "p" + i + "_" + cp[0][0].toFixed(0), points: pts2(cp), fill: seg ? SEG_VAR[p.seg || "building"] : p.fill, stroke: seg ? "none" : p.stroke, strokeWidth: p.sw }));
    });
    sc.discs.forEach((d, i) => {
      const [yaw, pitch] = toYawPitch(d.c);
      const dist = Math.hypot(d.c[0], d.c[1]);
      const rx = Math.atan2(d.r, dist) / D2R2 / 360 * W, ry = Math.atan2(d.ry || d.r, dist) / D2R2 / 180 * H;
      const [x, y] = yawPitchToXY(yaw, pitch, W, H);
      for (const dx of [0, W, -W]) els.push(h("ellipse", { key: "d" + i + dx, cx: x + dx, cy: y, rx, ry, fill: seg ? SEG_VAR.tree : d.fill }));
    });
    return h("g", { className: seg ? "aq-seg-layer" : void 0 }, els);
  }
  function BearingRuler({ width, mode = "yaw", offset = 0, err, marks = [], fov }) {
    const stage = useDensity() === "stage";
    const H = stage ? 48 : 28;
    const W = width;
    const ticks = [];
    const x = (yaw) => (yaw % 360 + 360) % 360 / 360 * W;
    for (let b = 0; b < 360; b += 5) {
      const yaw = mode === "bearing" ? b - offset : b;
      const X = x(yaw);
      const major = b % 45 === 0, mid = b % 15 === 0;
      ticks.push(h("line", { key: "t" + b, x1: X, x2: X, y1: 0, y2: major ? H * 0.42 : mid ? H * 0.28 : H * 0.16, className: major ? "aq-ruler-major" : "aq-ruler-minor" }));
      if (major) {
        const card = mode === "bearing" ? { 0: "N", 90: "E", 180: "S", 270: "W" }[b] : null;
        ticks.push(h("text", { key: "l" + b, x: X, y: H - (stage ? 8 : 5), textAnchor: X < 12 ? "start" : X > W - 12 ? "end" : "middle", className: cx("aq-ruler-txt", card && "is-card") }, card ? `${card} ${b}°` : `${b}°`));
      }
    }
    let errBand = null;
    if (mode === "bearing" && err) {
      const X = x(-offset);
      const half = err / 360 * W;
      errBand = h("rect", { x: X - half, y: 0, width: half * 2, height: H * 0.42, className: "aq-ruler-err" });
    }
    return h(
      "div",
      { className: cx("aq-ruler", "is-" + mode) },
      h(
        "svg",
        { viewBox: `0 0 ${W} ${H}`, width: "100%", height: H, preserveAspectRatio: "none", "aria-hidden": true },
        h("rect", { x: 0, y: 0, width: W, height: H, className: "aq-ruler-bg" }),
        errBand,
        fov ? h("rect", { x: x(fov.yaw - fov.fov / 2), y: 0, width: fov.fov / 360 * W, height: 3, className: "aq-ruler-fov" }) : null,
        ticks,
        marks.map((m, i) => h("path", { key: "m" + i, d: `M${x(m.yaw)} 0 l5 7 h-10z`, className: cx("aq-ruler-mark", m.tone && "is-" + m.tone) }))
      ),
      h("div", { className: cx("aq-ruler-cap", useT().micro) }, mode === "bearing" ? `True bearing · sun fix ± ${err}°` : "Camera yaw · north unknown")
    );
  }
  function PanoramaStrip({ c, width = 640, layers = {}, selected, ruler = "yaw", fov, showRejected = true, crop, visibleBoxes, fadedBoxes, label = true, labelMode = "all" }) {
    var _a, _b;
    const T = useT();
    const stage = useDensity() === "stage";
    const uid = useId().replace(/:/g, "");
    const W = width, H = width / 2;
    const sc = sceneFor(c);
    const L = { sectors: false, mask: true, boxes: true, text: true, seg: false, sun: false, water: false, skyline: false, ...layers };
    const [y0, y1] = crop ? [(90 - crop[0]) / 180 * H, (90 - crop[1]) / 180 * H] : [0, H];
    const xy = (yaw, pitch) => yawPitchToXY(yaw, pitch, W, H);
    const lw = stage ? 2.5 : 1.5;
    const overlays = [];
    if (L.sectors) {
      for (let i = 0; i < 8; i++) {
        const X = i * W / 8;
        overlays.push(h("line", { key: "s" + i, x1: X, x2: X, y1: H * 0.25, y2: H * 0.82, className: "aq-ov-sector" }));
        overlays.push(h("text", { key: "st" + i, x: X + W / 16, y: H * 0.25 + (stage ? 26 : 14), textAnchor: "middle", className: "aq-ov-lab" }, `V${i + 1}`));
      }
      overlays.push(h("line", { key: "sky", x1: 0, x2: W, y1: H * 0.25, y2: H * 0.25, className: "aq-ov-sector" }));
      overlays.push(h("text", { key: "skyt", x: 6, y: H * 0.25 - 6, className: "aq-ov-lab" }, "sky view above 45°"));
    }
    if (L.mask) {
      const my = H * 0.82;
      const maskLabel = label && labelMode === "all";
      overlays.push(h("rect", { key: "mask", x: 0, y: my, width: W, height: H - my, fill: `url(#hatch${uid})`, className: "aq-ov-mask" }));
      overlays.push(h("line", { key: "maskl", x1: 0, x2: W, y1: my, y2: my, className: "aq-ov-maskline" }));
      if (maskLabel) overlays.push(h("text", { key: "maskt", x: 6, y: my + (stage ? 26 : 14), className: "aq-ov-lab" }, "photographer mask · bottom 18% · excluded"));
    }
    if (L.skyline) {
      const sl = skyline(sc, 2).map(([y, p]) => xy(y === 360 ? 359.99 : y, p));
      overlays.push(h("polyline", { key: "sl", points: pts2(sl), className: "aq-ov-skyline" }));
    }
    const boxIds = (id) => !visibleBoxes || visibleBoxes.includes(id);
    if (L.boxes && c.detections) c.detections.forEach((b) => {
      if (!boxIds(b.id)) return;
      if (!b.kept && !showRejected) return;
      const [x0, yy0] = xy(b.yaw - b.w / 2, b.pitch + b.h / 2), [x1, yy1] = xy(b.yaw + b.w / 2, b.pitch - b.h / 2);
      const w2 = x1 - x0, hh = yy1 - yy0, k = Math.min(w2, hh) * 0.3;
      const sel = selected === b.id;
      const faded = fadedBoxes && fadedBoxes.includes(b.id);
      const d = `M${x0} ${yy0 + k}V${yy0}H${x0 + k}M${x1 - k} ${yy0}H${x1}V${yy0 + k}M${x1} ${yy1 - k}V${yy1}H${x1 - k}M${x0 + k} ${yy1}H${x0}V${yy1 - k}`;
      overlays.push(h(
        "g",
        { key: b.id, className: cx("aq-ov-box", !b.kept && "is-rejected", sel && "is-sel", faded && "is-faded"), "data-link": b.id },
        h("path", { d, className: "aq-ov-halo", strokeWidth: lw + 2.5 }),
        h("path", { d, strokeWidth: sel ? lw + 1 : lw }),
        !b.kept ? h("line", { x1: x0, y1: yy1, x2: x1, y2: yy0, strokeWidth: lw }) : null,
        label && (labelMode === "all" || sel) ? h(OnPhotoLabel, { x: x0, y: yy0 - 3, text: b.kept ? `${b.label} ${b.score.toFixed(2)}` : `${b.label} · rejected`, strike: !b.kept }) : null
      ));
    });
    if (L.text && c.texts) c.texts.forEach((t) => {
      const [x0, yy0] = xy(t.yaw - t.w / 2, t.pitch + t.h / 2), [x1, yy1] = xy(t.yaw + t.w / 2, t.pitch - t.h / 2);
      const sel = selected === t.id;
      overlays.push(h(
        "g",
        { key: t.id, className: cx("aq-ov-text", sel && "is-sel"), "data-link": t.id },
        h("rect", { x: x0, y: yy0, width: x1 - x0, height: yy1 - yy0, className: "aq-ov-halo", strokeWidth: lw + 2.5 }),
        h("rect", { x: x0, y: yy0, width: x1 - x0, height: yy1 - yy0, strokeWidth: sel ? lw + 1 : lw }),
        label && (labelMode !== "selected" || sel) ? h(OnPhotoLabel, { x: Math.min(x0, W - (t.text.length + 8) * (stage ? 12.4 : 6.8) - 8), y: yy1 + (stage ? 30 : 15), text: `“${t.text}” ${t.conf.toFixed(2)}`, mono: true }) : null
      ));
    });
    if (L.sun && c.sun) {
      const [x, y] = xy(c.sun.yaw, c.sun.elevation);
      const r = stage ? 16 : 9;
      overlays.push(h(
        "g",
        { key: "sun", className: "aq-ov-sun" },
        h("circle", { cx: x, cy: y, r: r + 2, className: "aq-ov-halo", strokeWidth: lw + 2.5 }),
        h("circle", { cx: x, cy: y, r, strokeWidth: lw }),
        h("path", { d: `M${x - r * 1.8} ${y}h${r * 0.8}M${x + r} ${y}h${r * 0.8}M${x} ${y - r * 1.8}v${r * 0.8}M${x} ${y + r}v${r * 0.8}`, strokeWidth: lw }),
        label ? h(OnPhotoLabel, { x: x + r * 2, y: y + 4, text: `sun · yaw ${c.sun.yaw}° · elevation ${c.sun.elevation}°` }) : null
      ));
    }
    if (L.water && c.water) {
      const wy = c.water.bearing - c.yawToBearing;
      const [x, y] = xy(wy, -1.5);
      const s = stage ? 1.8 : 1;
      overlays.push(h(
        "g",
        { key: "water", className: "aq-ov-water" },
        h("path", { d: `M${x} ${y - 30 * s}v${26 * s}m-${6 * s} -${7 * s}l${6 * s} ${7 * s} ${6 * s} -${7 * s}`, className: "aq-ov-halo", strokeWidth: lw + 2.5, fill: "none" }),
        h("path", { d: `M${x} ${y - 30 * s}v${26 * s}m-${6 * s} -${7 * s}l${6 * s} ${7 * s} ${6 * s} -${7 * s}`, strokeWidth: lw, fill: "none" }),
        label ? h(OnPhotoLabel, { x: x + 8, y: y - 22 * s, text: `water · bearing ~${c.water.bearing}°` }) : null
      ));
    }
    if (fov) {
      const vf = fov.fov * 0.62;
      const [x0, yy0] = xy(fov.yaw - fov.fov / 2, vf / 2), [x1, yy1] = xy(fov.yaw + fov.fov / 2, -vf / 2);
      const k = 10;
      const d = `M${x0} ${yy0 + k}V${yy0}H${x0 + k}M${x1 - k} ${yy0}H${x1}V${yy0 + k}M${x1} ${yy1 - k}V${yy1}H${x1 - k}M${x0 + k} ${yy1}H${x0}V${yy1 - k}`;
      overlays.push(h("g", { key: "fov", className: "aq-ov-fov" }, h("path", { d, className: "aq-ov-halo", strokeWidth: lw + 3 }), h("path", { d, strokeWidth: lw + 0.5 }), label ? h(OnPhotoLabel, { x: x0 + 4, y: yy1 - 6, text: `360° view · yaw ${fov.yaw}°` }) : null));
    }
    const vb = `0 ${y0} ${W} ${y1 - y0}`;
    const marks = [];
    const selObj = (c.texts || []).concat(c.detections || []).find((o) => o.id === selected);
    if (selObj) marks.push({ yaw: selObj.yaw, tone: "select" });
    return h(
      "figure",
      { className: "aq-pano", style: { width: W } },
      h(
        "svg",
        { className: "aq-pano-svg", viewBox: vb, width: W, height: y1 - y0, role: "img", "aria-label": `Panorama ${c.file}, ${(_a = c.size) == null ? void 0 : _a[0]}×${(_b = c.size) == null ? void 0 : _b[1]}` },
        h("defs", null, h("pattern", { id: "hatch" + uid, width: 8, height: 8, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, h("line", { x1: 0, y1: 0, x2: 0, y2: 8, className: "aq-hatch-line" }))),
        h(EquiScene, { sc, W, H }),
        L.seg ? h("g", { opacity: 0.62 }, h(EquiScene, { sc, W, H, seg: true })) : null,
        overlays
      ),
      ruler ? h(BearingRuler, { width: W, mode: ruler, offset: c.yawToBearing, err: c.yawToBearingErr, marks, fov }) : null
    );
  }
  function OnPhotoLabel({ x, y, text, mono, strike }) {
    const stage = useDensity() === "stage";
    const fs = stage ? 20 : 11, pad = stage ? 6 : 3, cw = fs * (mono ? 0.62 : 0.56);
    const w2 = text.length * cw + pad * 2, hh = fs + pad * 2 - 2;
    return h(
      "g",
      { className: "aq-ov-label" },
      h("rect", { x, y: y - hh, width: w2, height: hh, rx: 2, className: "aq-ov-plate" }),
      h("text", { x: x + pad, y: y - pad - 1, className: cx("aq-ov-ltxt", mono && "is-mono"), style: { fontSize: fs } }, text),
      strike ? h("line", { x1: x + pad, x2: x + w2 - pad, y1: y - hh / 2, y2: y - hh / 2, className: "aq-ov-strike" }) : null
    );
  }
  function PerspScene({ sc, cam, seg }) {
    const els = [];
    const hz = perspPoint([cam.pos[0] + dir(cam.yaw)[0] * 1e5, cam.pos[1] + dir(cam.yaw)[1] * 1e5, cam.pos[2]], cam);
    const hy = Math.max(0, Math.min(cam.h, hz ? hz[1] : cam.h / 2));
    els.push(h("rect", { key: "sky", x: 0, y: 0, width: cam.w, height: hy + 1, fill: sc.sky }), h("rect", { key: "gr", x: 0, y: hy, width: cam.w, height: Math.max(0, cam.h - hy), fill: sc.ground }));
    if (sc.horizon) {
      const top = [];
      for (let a = -cam.fov; a <= cam.fov; a += 2) {
        const y = cam.yaw + a;
        const e = sc.horizon((y % 360 + 360) % 360);
        const dd = 1e5;
        const [s, c] = dir(y);
        const p = perspPoint([cam.pos[0] + s * dd, cam.pos[1] + c * dd, cam.pos[2] + Math.tan(e * D2R2) * dd], cam);
        if (p) top.push(p);
      }
      if (top.length) els.push(h("polygon", { key: "hz", points: pts2([...top, [top[top.length - 1][0], hy + 2], [top[0][0], hy + 2]]), fill: sc.horizonFill }));
    }
    if (sc.sun) {
      const dd = 1e5;
      const [s, c] = dir(sc.sun.yaw);
      const p = perspPoint([cam.pos[0] + s * dd * Math.cos(sc.sun.el * D2R2), cam.pos[1] + c * dd * Math.cos(sc.sun.el * D2R2), cam.pos[2] + dd * Math.sin(sc.sun.el * D2R2)], cam);
      if (p && p[0] > -40 && p[0] < cam.w + 40) els.push(h("circle", { key: "sun", cx: p[0], cy: p[1], r: cam.w / cam.fov * 1.2, fill: "#f7f3e6" }));
    }
    const dist = (p) => {
      const m = p.reduce((a, q) => [a[0] + q[0], a[1] + q[1]], [0, 0]);
      return Math.hypot(m[0] / p.length - cam.pos[0], m[1] / p.length - cam.pos[1]);
    };
    const items = [...sc.polys.map((p) => ({ t: "p", p, d: dist(p.pts) - (p.kind === "window" || p.kind === "door" || p.kind === "sign" || p.kind === "azulejo" ? 0.05 : 0) })), ...sc.discs.map((d) => ({ t: "d", p: d, d: Math.hypot(d.c[0] - cam.pos[0], d.c[1] - cam.pos[1]) - 0.5 }))];
    items.sort((a, b) => {
      const ga = a.t === "p" && a.p.pts.every((q) => q[2] === 0), gb = b.t === "p" && b.p.pts.every((q) => q[2] === 0);
      if (ga !== gb) return ga ? -1 : 1;
      return b.d - a.d;
    });
    items.forEach((it, i) => {
      if (it.t === "p") {
        const sp = persp(it.p.pts, cam);
        if (sp) els.push(h("polygon", { key: i, points: pts2(sp), fill: seg ? SEG_VAR[it.p.seg] : it.p.fill, stroke: it.p.stroke, strokeWidth: it.p.sw }));
      } else {
        const d = it.p;
        const cpt = perspPoint(d.c, cam);
        if (!cpt) return;
        const e = perspPoint([d.c[0], d.c[1], d.c[2] + (d.ry || d.r)], cam);
        const ry = e ? Math.abs(cpt[1] - e[1]) : 4;
        els.push(h("ellipse", { key: i, cx: cpt[0], cy: cpt[1], rx: ry * (d.r / (d.ry || d.r)), ry, fill: d.fill }));
      }
    });
    return h("g", null, els);
  }
  var dirPoint = (yaw, pitch, cam) => {
    const dd = 100;
    const [s, c] = dir(yaw);
    return perspPoint([cam.pos[0] + s * dd * Math.cos(pitch * D2R2), cam.pos[1] + c * dd * Math.cos(pitch * D2R2), cam.pos[2] + dd * Math.sin(pitch * D2R2)], cam);
  };
  function Viewer360({ c, yaw = 212, pitch = 0, fov = 90, width = 560, height = 320, selected, synced = true, showBoxes = true }) {
    const T = useT();
    const stage = useDensity() === "stage";
    const sc = sceneFor(c);
    const cam = { pos: [0, 0, 1.7], yaw, pitch, fov, w: width, h: height };
    const bearing = c.yawToBearing != null ? Math.round(((yaw + c.yawToBearing) % 360 + 360) % 360) : null;
    const lw = stage ? 3 : 1.75;
    const boxes = [];
    if (showBoxes) for (const t of [...c.texts || [], ...(c.detections || []).filter((d) => d.kept)]) {
      const a = dirPoint(t.yaw - t.w / 2, t.pitch + t.h / 2, cam), b = dirPoint(t.yaw + t.w / 2, t.pitch - t.h / 2, cam);
      if (!a || !b || a[0] < 0 || b[0] > width) continue;
      const isText = !!t.text;
      const sel = selected === t.id;
      boxes.push(h(
        "g",
        { key: t.id, className: cx(isText ? "aq-ov-text" : "aq-ov-box", sel && "is-sel"), "data-link": t.id },
        h("rect", { x: a[0], y: a[1], width: b[0] - a[0], height: b[1] - a[1], className: "aq-ov-halo", strokeWidth: lw + 2.5, fill: "none" }),
        h("rect", { x: a[0], y: a[1], width: b[0] - a[0], height: b[1] - a[1], strokeWidth: sel ? lw + 1 : lw, fill: "none" }),
        h(OnPhotoLabel, { x: a[0], y: isText ? b[1] + (stage ? 30 : 16) : a[1] - 3, text: isText ? `“${t.text}” ${t.conf.toFixed(2)}` : `${t.label} ${t.score.toFixed(2)}`, mono: isText })
      ));
    }
    return h(
      "figure",
      { className: "aq-v360", style: { width } },
      h(
        "svg",
        { viewBox: `0 0 ${width} ${height}`, width, height, role: "img", "aria-label": `360° view at yaw ${yaw}°` },
        h(PerspScene, { sc, cam }),
        boxes,
        h("path", { d: `M${width / 2 - 8} ${height / 2}h16M${width / 2} ${height / 2 - 8}v16`, className: "aq-v360-cross" })
      ),
      h(
        "figcaption",
        { className: "aq-v360-bar" },
        h("span", { className: T.label }, h(Icon, { name: "camera" }), " 360° view"),
        h("span", { className: cx(T.data, "aq-ink2") }, `yaw ${yaw}°`),
        bearing != null ? h("span", { className: cx(T.data, "aq-ink2") }, `bearing ${bearing}° ± ${c.yawToBearingErr}°`) : null,
        h("span", { className: cx(T.data, "aq-ink3") }, `fov ${fov}°`),
        h("span", { className: cx("aq-v360-sync", T.micro, synced ? "is-on" : "is-off") }, h(Icon, { name: synced ? "done" : "warning" }), synced ? "synced with strip" : "not synced — click to re-sync")
      )
    );
  }
  function ZoomCrop({ c, target, width = 280, height = 160, fov = 14, note }) {
    var _a, _b, _c, _d;
    const T = useT();
    const stage = useDensity() === "stage";
    const t = [...c.texts || [], ...c.detections || []].find((o) => o.id === target);
    if (!t) return null;
    const sc = sceneFor(c);
    const fv = Math.max(fov, t.w * 1.7, t.h * 1.7 * width / height);
    const cam = { pos: [0, 0, 1.7], yaw: t.yaw, pitch: t.pitch, fov: fv, w: width, h: height };
    const a = dirPoint(t.yaw - t.w / 2, t.pitch + t.h / 2, cam), b = dirPoint(t.yaw + t.w / 2, t.pitch - t.h / 2, cam);
    const isText = !!t.text;
    const px = Math.round(t.w / 360 * (((_a = c.size) == null ? void 0 : _a[0]) || 6080)), py = Math.round(t.h / 180 * (((_b = c.size) == null ? void 0 : _b[1]) || 3040));
    return h(
      "figure",
      { className: "aq-crop", "data-link": t.id, style: { width } },
      h(
        "svg",
        { viewBox: `0 0 ${width} ${height}`, width, height, role: "img", "aria-label": `Crop of ${isText ? t.text : t.label}` },
        h(PerspScene, { sc, cam }),
        a && b ? h("rect", { x: Math.min(a[0], b[0]), y: Math.min(a[1], b[1]), width: Math.abs(b[0] - a[0]), height: Math.abs(b[1] - a[1]), className: isText ? "aq-crop-box is-text" : "aq-crop-box", strokeWidth: stage ? 3 : 1.5, fill: "none" }) : null,
        isText && a && b ? h("text", { x: (a[0] + b[0]) / 2, y: (a[1] + b[1]) / 2 + (stage ? 8 : 4), textAnchor: "middle", className: "aq-crop-sign", style: { fontSize: Math.min((b[1] - a[1]) * 0.62, (b[0] - a[0]) / Math.max(4, t.text.length) * 1.5) } }, t.text) : null
      ),
      h(
        "figcaption",
        { className: "aq-crop-cap" },
        h("span", { className: isText ? T.data : T.label }, isText ? `“${t.text}”` : t.label),
        h("span", { className: cx(T.data, "aq-ink2") }, (isText ? t.conf : t.score).toFixed(2)),
        h("span", { className: cx(T.micro, "aq-ink3") }, note || `full resolution · ${px}×${py} px of ${(_c = c.size) == null ? void 0 : _c[0]}×${(_d = c.size) == null ? void 0 : _d[1]} · yaw ${t.yaw}°`)
      )
    );
  }
  var LAYER_META = {
    sectors: ["View sectors", "sector"],
    mask: ["Photographer mask", "mask"],
    boxes: ["Detection boxes", "object", "var(--model)"],
    text: ["Text and readings", "text", "var(--model)"],
    seg: ["Segmentation tint", "measure"],
    sun: ["Sun marker", "sun"],
    water: ["Water direction", "water"],
    skyline: ["Skyline trace", "skyline"]
  };
  function LayerToggles({ layers, counts = {}, onChange, columns = 2 }) {
    const T = useT();
    return h(
      "fieldset",
      { className: "aq-layers", style: { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` } },
      h("legend", { className: cx(T.label, "aq-ink3") }, h(Icon, { name: "layers" }), " Layers"),
      Object.keys(LAYER_META).map((k) => h(Toggle, { key: k, label: LAYER_META[k][0], icon: LAYER_META[k][1], on: !!layers[k], hint: counts[k], onChange: onChange ? (v) => onChange(k, v) : void 0 }))
    );
  }

  // src/reasoning.tsx
  var reasoning_exports = {};
  __export(reasoning_exports, {
    CaptionBar: () => CaptionBar,
    CorrelationBracket: () => CorrelationBracket,
    EvidenceCard: () => EvidenceCard,
    PolarityChip: () => PolarityChip,
    StageRow: () => StageRow,
    StageTimeline: () => StageTimeline
  });

  // src/charts.tsx
  var charts_exports = {};
  __export(charts_exports, {
    CompassDial: () => CompassDial,
    ConfidenceMeter: () => ConfidenceMeter,
    EstimateBars: () => EstimateBars,
    GainMeter: () => GainMeter,
    LanguageVote: () => LanguageVote,
    SceneShares: () => SceneShares,
    StackedBar: () => StackedBar
  });
  function ConfidenceMeter({ value, level, showValue = true }) {
    const T = useT();
    const lv = level || (value == null ? "unknown" : value >= 0.8 ? "high" : value >= 0.5 ? "med" : "low");
    const n = { high: 3, med: 2, low: 1, unknown: 0 }[lv];
    const word = { high: "high", med: "medium", low: "low", unknown: "unknown" }[lv];
    return h(
      "span",
      { className: cx("aq-conf", "is-" + lv), title: `Confidence ${word}${value != null ? " · " + fmtEst(value) : ""}` },
      h("span", { className: "aq-conf-cells", "aria-hidden": true }, [0, 1, 2].map((i) => h("i", { key: i, className: i < n ? "is-on" : "" }))),
      showValue && value != null ? h("span", { className: T.dataSm }, fmtEst(value)) : null,
      h("span", { className: cx(T.micro, "aq-conf-w") }, word)
    );
  }
  function StackedBar({ parts, caption, height, labelMin = 0.09, title }) {
    const T = useT();
    const stage = useDensity() === "stage";
    const total = parts.reduce((a, p) => a + p.v, 0) || 1;
    const hh = height || (stage ? 36 : 18);
    return h(
      "figure",
      { className: "aq-stack" },
      title ? h("figcaption", { className: cx(T.label, "aq-stack-t") }, title) : null,
      h(
        "div",
        { className: "aq-stack-bar", style: { height: hh }, role: "img", "aria-label": parts.map((p) => `${p.label || p.id} ${fmtPct(p.v / total)}`).join(", ") },
        parts.filter((p) => p.v > 0).map((p) => h(
          "span",
          { key: p.id, className: cx("aq-stack-seg", p.hatch && "is-hatch"), style: { flexGrow: p.v / total, background: p.color } },
          p.v / total >= labelMin ? h("b", { className: T.dataSm }, `${p.label || p.id} ${Math.round(p.v / total * 100)}`) : null
        ))
      ),
      h("ul", { className: cx("aq-stack-legend", T.micro) }, parts.map((p) => h("li", { key: p.id, className: p.v === 0 ? "is-zero" : "" }, h("i", { style: { background: p.color }, className: p.hatch ? "is-hatch" : "" }), h("span", null, p.label || p.id), h("span", { className: "aq-num" }, p.v.toFixed(2))))),
      caption ? h("div", { className: cx(T.micro, "aq-ink3") }, caption) : null
    );
  }
  function LanguageVote({ votes, voters = 3 }) {
    const parts = votes.map((x, i) => ({ id: x.id, v: x.v, color: i % 2 ? "var(--model-soft)" : "var(--model)" }));
    return h(StackedBar, { parts, title: `Language vote · ${voters} voters`, caption: "Share of votes, not a probability of country" });
  }
  var SEG_COL = { sky: "var(--seg-sky)", building: "var(--seg-building)", grass: "var(--seg-grass)", tree: "var(--seg-tree)", road: "var(--seg-road)", water: "var(--seg-water)", ground: "var(--seg-ground)", masked: "var(--seg-masked)" };
  var SEG_ORDER = ["sky", "building", "grass", "tree", "road", "water", "ground", "masked"];
  function SceneShares({ shares, masked = 0 }) {
    const map = Object.fromEntries(shares.map((s) => [s.id, s.v]));
    if (masked) map.masked = masked;
    const parts = SEG_ORDER.filter((k) => map[k] != null).map((k) => ({ id: k, label: k, v: map[k], color: SEG_COL[k], hatch: k === "masked" }));
    return h(StackedBar, { parts, title: "Scene shares (EoMT-L)", caption: "visible share, not land cover", labelMin: 0.12 });
  }
  function CompassDial({ yawToBearing, err = 0, sun, water, size, viewYaw }) {
    const T = useT();
    const stage = useDensity() === "stage";
    const S = size || (stage ? 300 : 168);
    const c = S / 2, R2 = S / 2 - (stage ? 34 : 20);
    const pt = (bearing, r) => [c + Math.sin(bearing * Math.PI / 180) * r, c - Math.cos(bearing * Math.PI / 180) * r];
    const known = yawToBearing != null;
    const els = [h("circle", { key: "ring", cx: c, cy: c, r: R2, className: "aq-dial-ring" })];
    for (let b = 0; b < 360; b += 15) {
      const [x1, y1] = pt(b, R2);
      const [x2, y2] = pt(b, R2 - (b % 90 === 0 ? 10 : 5));
      els.push(h("line", { key: "t" + b, x1, y1, x2, y2, className: b % 90 === 0 ? "aq-dial-major" : "aq-dial-minor" }));
    }
    if (known) {
      ["N", "E", "S", "W"].forEach((l, i) => {
        const [x, y] = pt(i * 90, R2 + (stage ? 18 : 11));
        els.push(h("text", { key: l, x, y: y + (stage ? 7 : 4), textAnchor: "middle", className: cx("aq-dial-card", l === "N" && "is-n") }, l));
      });
      const y0 = yawToBearing;
      const a1 = y0 - err, a2 = y0 + err;
      const [x1, y1] = pt(a1, R2 - 12), [x2, y2] = pt(a2, R2 - 12);
      els.push(h("path", { key: "err", d: `M${c} ${c}L${x1} ${y1}A${R2 - 12} ${R2 - 12} 0 0 1 ${x2} ${y2}Z`, className: "aq-dial-err" }));
      const [ax, ay] = pt(y0, R2 - 14);
      els.push(h("line", { key: "yaw0", x1: c, y1: c, x2: ax, y2: ay, className: "aq-dial-yaw" }));
      els.push(h("text", { key: "yaw0t", x: ax, y: ay - 4, textAnchor: "middle", className: "aq-dial-lab" }, "yaw 0"));
      if (sun) {
        const [sx, sy] = pt(sun.azimuth, R2 - 12 - (R2 - 24) * (sun.elevation / 90));
        els.push(h("g", { key: "sun", className: "aq-dial-sun" }, h("circle", { cx: sx, cy: sy, r: stage ? 9 : 5 }), h("line", { x1: c, y1: c, x2: sx, y2: sy })));
      }
      if (water != null) {
        const [wx, wy] = pt(water, R2 - 4);
        els.push(h("g", { key: "w", className: "aq-dial-water" }, h("circle", { cx: wx, cy: wy, r: stage ? 6 : 3.5 })));
      }
      if (viewYaw != null) {
        const [vx, vy] = pt(viewYaw + y0, R2 - 4);
        els.push(h("line", { key: "v", x1: c, y1: c, x2: vx, y2: vy, className: "aq-dial-view" }));
      }
    } else {
      els.push(h("text", { key: "q", x: c, y: c + 4, textAnchor: "middle", className: "aq-dial-lab" }, "north unknown"));
      const [ax, ay] = pt(0, R2 - 14);
      els.push(h("line", { key: "yaw0", x1: c, y1: c, x2: ax, y2: ay, className: "aq-dial-yaw is-unknown" }));
    }
    els.push(h("circle", { key: "c", cx: c, cy: c, r: 2.5, className: "aq-dial-c" }));
    return h(
      "figure",
      { className: "aq-dial" },
      h("svg", { viewBox: `0 0 ${S} ${S}`, width: S, height: S, role: "img", "aria-label": known ? `Image yaw 0 points to bearing ${yawToBearing}° ± ${err}°` : "North unknown" }, els),
      h(
        "figcaption",
        { className: cx("aq-dial-cap") },
        known ? h(
          Fragment,
          null,
          h("div", { className: T.data }, `yaw 0 at ${yawToBearing}° ± ${err}°`),
          sun ? h("div", { className: cx(T.micro, "aq-ink2") }, h(Icon, { name: "sun" }), ` sun az ${sun.azimuth}° · el ${sun.elevation}°`) : null,
          water != null ? h("div", { className: cx(T.micro, "aq-ink2") }, h(Icon, { name: "water" }), ` water ~${water}°`) : null
        ) : h("div", { className: cx(T.micro, "aq-ink3") }, "No sun found; bearings stay as camera yaw")
      )
    );
  }
  function EstimateBars({ rows, tone = "solver", max, title, caption, mode = "single" }) {
    const T = useT();
    const M = max || Math.max(...rows.map((r) => Math.max(r.hi || r.v, r.before || 0)), 0.01);
    const pct = (x) => `${Math.min(100, x / M * 100)}%`;
    return h(
      "figure",
      { className: cx("aq-ebars", "aq-tone-" + tone) },
      title ? h("figcaption", { className: cx(T.label, "aq-ebars-t") }, title) : null,
      h("div", { className: "aq-ebars-rows" }, rows.map((r, i) => h(
        "div",
        { key: i, className: cx("aq-ebar", r.other && "is-other") },
        h("span", { className: cx(T.body, "aq-ebar-n") }, r.name),
        h(
          "span",
          { className: "aq-ebar-track" },
          mode === "beforeAfter" && r.before != null ? h("i", { className: "aq-ebar-before", style: { width: pct(r.before) } }) : null,
          h("b", { className: "aq-ebar-fill", style: { width: pct(r.v) } }),
          r.lo != null && r.hi != null ? h("em", { className: "aq-ebar-range", style: { left: pct(r.lo), width: `calc(${pct(r.hi)} - ${pct(r.lo)})` } }) : null
        ),
        h("span", { className: cx(T.data, "aq-ebar-v") }, mode === "beforeAfter" && r.before != null ? `${fmtEst(r.before)} › ${fmtEst(r.v)}` : fmtEst(r.v)),
        r.note ? h("span", { className: cx(T.micro, "aq-ebar-note") }, r.note) : null
      ))),
      caption ? h("div", { className: cx(T.micro, "aq-ink3") }, caption) : null
    );
  }
  function GainMeter({ gain, breakEven = 1 / 0.95 - 1, cueLine, max = 0.3 }) {
    const T = useT();
    const pct = (x) => `${Math.min(100, Math.max(0, x / max * 100))}%`;
    const worth = gain > breakEven;
    return h(
      "figure",
      { className: cx("aq-gain", worth ? "is-worth" : "is-not") },
      h(
        "div",
        { className: "aq-gain-head" },
        h("span", { className: T.label }, "Expected gain"),
        h("span", { className: T.readout }, fmtSigned(gain * 100, 0) + "%"),
        h("span", { className: cx(T.micro, "aq-ink3") }, worth ? `above the ${fmtPct(breakEven, 2)} break-even` : `below the ${fmtPct(breakEven, 2)} break-even — not worth asking`)
      ),
      h(
        "div",
        { className: "aq-gain-track", role: "img", "aria-label": `Expected gain ${fmtPct(gain)} against break-even ${fmtPct(breakEven, 2)}` },
        h("b", { style: { width: pct(gain) } }),
        h("i", { className: "aq-gain-line", style: { left: pct(breakEven) } }, h("span", { className: T.micro }, `${fmtPct(breakEven, 2)} · ×0.95`)),
        cueLine ? h("i", { className: "aq-gain-line is-cue", style: { left: pct(0.25) } }, h("span", { className: T.micro }, "25% · cue ×0.8")) : null
      ),
      h("div", { className: cx("aq-gain-axis", T.micro) }, h("span", null, "0%"), h("span", null, fmtPct(max)))
    );
  }

  // src/reasoning.tsx
  var STATUS_WORD = { queued: "Queued", running: "Running", done: "Done", skipped: "Skipped", failed: "Failed", timed_out: "Timed out" };
  var STATUS_ICON = { queued: "queued", running: "running", done: "done", skipped: "skipped", failed: "failed", timed_out: "timeout" };
  function StageRow({ stage: s, compact, pass }) {
    const T = useT();
    const st = s.status;
    return h(
      "li",
      { className: cx("aq-stage", "is-" + st, compact && "is-compact") },
      h("span", { className: "aq-stage-i", title: STATUS_WORD[st] }, h(Icon, { name: STATUS_ICON[st] })),
      h(
        "span",
        { className: "aq-stage-n" },
        h("span", { className: T.heading }, s.name),
        s.optional ? h("span", { className: cx(T.micro, "aq-ink3") }, " optional") : null,
        pass ? h("span", { className: cx(T.micro, "aq-ink3") }, ` · pass ${pass}`) : null,
        compact ? null : h("span", { className: cx("aq-stage-m", T.micro) }, (s.models || []).join(" · "))
      ),
      h("span", { className: cx("aq-stage-w", T.micro) }, STATUS_WORD[st]),
      h("span", { className: cx("aq-stage-d", T.dataSm) }, s.dur != null ? s.dur >= 60 ? fmtTime(s.dur) : s.dur.toFixed(1) + " s" : "—"),
      compact ? null : h("span", { className: cx("aq-stage-g", T.dataSm) }, s.cpu ? "CPU" : s.gb ? s.gb.toFixed(1) + " GB" : ""),
      st === "running" && s.deadline ? h("span", { className: "aq-stage-dl", "aria-label": `${s.dur} s of ${s.deadline} s deadline` }, h("span", { className: "aq-stage-dl-t" }, h("b", { style: { width: `${Math.min(1, s.dur / s.deadline) * 100}%` } })), h("span", { className: cx(T.micro, "aq-ink3") }, `${s.dur.toFixed(0)} s of ${s.deadline} s deadline, then fallback`)) : null,
      s.note || s.fallback ? h("span", { className: cx("aq-stage-note", T.micro) }, s.fallback ? h(Fragment, null, h(Icon, { name: "warning" }), ` ${s.note || ""} Fallback ran: ${s.fallback}`) : s.note) : null
    );
  }
  function StageTimeline({ stages, compact, title = "Stages", loopFrom, loopTo }) {
    const T = useT();
    const done = stages.filter((s) => s.status === "done").length;
    const i0 = loopFrom ? stages.findIndex((s) => s.id === loopFrom) : -1, i1 = loopTo ? stages.findIndex((s) => s.id === loopTo) : -1;
    return h(
      "section",
      { className: cx("aq-timeline", compact && "is-compact") },
      h("div", { className: "aq-timeline-h" }, h("span", { className: T.title }, title), h("span", { className: cx(T.micro, "aq-ink3") }, `${done} of ${stages.length} done · real durations`)),
      h(
        "ol",
        { className: "aq-timeline-l", style: i0 >= 0 ? { "--loop-a": i0, "--loop-b": i1 } : void 0 },
        stages.map((s, i) => h(StageRow, { key: s.id, stage: s, compact, pass: i0 >= 0 && i >= i0 && i <= i1 ? 2 : void 0 }))
      ),
      i0 >= 0 ? h("div", { className: cx(T.micro, "aq-ink3", "aq-timeline-loop") }, h(Icon, { name: "replay" }), ` ${stages[i0].name} to ${stages[i1].name} ran again after the answer`) : null
    );
  }
  var KIND = {
    text: ["text", "Text read"],
    object: ["object", "Objects found"],
    checklist: ["checklist", "Checklist answer"],
    measure: ["measure", "Scene measure"],
    sun: ["sun", "Sun and compass"],
    language: ["language", "Language vote"],
    neighbour: ["neighbour", "Reference-photo neighbours"],
    region: ["region", "Region estimate"],
    name: ["name", "Name match"],
    contradiction: ["contradiction", "Contradiction"]
  };
  function PolarityChip({ name, pol }) {
    const T = useT();
    const k = pol > 0 ? "support" : pol < 0 ? "contra" : "neutral";
    return h("span", { className: cx("aq-pol", "is-" + k, T.label), title: `${k === "support" ? "Supports" : k === "contra" ? "Contradicts" : "Neutral on"} ${name}` }, h(Icon, { name: k }), name);
  }
  function EvidenceCard({ e, names = {}, selected, compact, isNew, crop, showActor = true }) {
    const T = useT();
    const [icon, label] = KIND[e.kind] || ["info", e.kind];
    const pols = Object.entries(e.pol || {});
    const isContra = e.kind === "contradiction";
    return h(
      "article",
      { className: cx("aq-ev", "is-" + e.kind, selected && "is-sel", e.notVisible && "is-nv", e.empty && "is-empty", isNew && "is-new", compact && "is-compact"), "data-link": e.id, tabIndex: 0, "aria-label": `${label}: ${e.obs}` },
      h(
        "header",
        { className: "aq-ev-h" },
        h(Icon, { name: icon }),
        h("span", { className: T.label }, label),
        h("span", { className: cx(T.micro, "aq-ink3") }, e.stage),
        isNew ? h("span", { className: cx("aq-ev-new", T.micro) }, "new") : null,
        h("span", { className: cx(T.dataSm, "aq-ev-t") }, fmtTime(e.t || 0))
      ),
      h(
        "div",
        { className: "aq-ev-obs" },
        crop || null,
        h(
          "div",
          { className: "aq-ev-obs-b" },
          h("span", { className: cx("aq-ev-reg", T.micro) }, isContra ? "In conflict" : e.notVisible ? "Can't tell" : "Observed"),
          h("span", { className: cx(T.data, "aq-ev-obs-t") }, e.obs),
          e.conf != null ? h(ConfidenceMeter, { value: e.conf }) : null
        )
      ),
      e.inference ? h("div", { className: "aq-ev-inf" }, h(Icon, { name: "infer" }), h("span", { className: T.inference }, e.inference)) : null,
      e.estimate && !compact ? h("div", { className: "aq-ev-est" }, h(Icon, { name: "estimate" }), h("span", { className: T.data }, `${e.estimate.label} ${fmtEst(e.estimate.v)}`), h("span", { className: cx(T.micro, "aq-ink3") }, "estimate, not a calibrated probability")) : null,
      pols.length && !compact ? h("div", { className: "aq-ev-pol" }, pols.map(([k, v]) => h(PolarityChip, { key: k, name: names[k] || k, pol: v }))) : null,
      showActor && !compact ? h("footer", { className: "aq-ev-f" }, h(ModelChip, { name: e.model, actor: e.actor, size: "sm" }), e.actor === "model" ? h("span", { className: cx(T.micro, "aq-ink3") }, e.sub || "local · open weights") : h("span", { className: cx(T.micro, "aq-ink3") }, "code, not a model")) : null
    );
  }
  function CorrelationBracket({ label, cap, note, children }) {
    const T = useT();
    return h(
      "section",
      { className: "aq-corr", "aria-label": label },
      h("div", { className: "aq-corr-h" }, h(Icon, { name: "bracket" }), h("span", { className: T.label }, label), cap != null ? h(Badge, { tone: "solver" }, `weight capped at ${cap.toFixed(2)}`) : null),
      note ? h("div", { className: cx(T.micro, "aq-ink3") }, note) : null,
      h("div", { className: "aq-corr-b" }, children)
    );
  }
  function CaptionBar({ headline, caption, actor = "model", source, t, speed }) {
    const T = useT();
    return h(
      "div",
      { className: "aq-caption", role: "status", "aria-live": "polite" },
      h("div", { className: "aq-caption-l" }, h("div", { className: cx(T.headline, "aq-caption-h") }, headline), h("div", { className: cx(T.caption, "aq-caption-c") }, caption)),
      h(
        "div",
        { className: "aq-caption-r" },
        source ? h(ModelChip, { name: source, actor, size: "sm" }) : null,
        t != null ? h("span", { className: cx(T.data, "aq-ink3") }, `log ${fmtTime(t)}`) : null,
        speed ? h("span", { className: cx("aq-sys is-replay", T.label) }, h(Icon, { name: "replay" }), `${speed}×`) : null
      )
    );
  }

  // src/beliefs.tsx
  var beliefs_exports = {};
  __export(beliefs_exports, {
    CandidateList: () => CandidateList,
    CandidateRow: () => CandidateRow,
    EvidenceMatrix: () => EvidenceMatrix,
    Funnel: () => Funnel,
    RuledOutRow: () => RuledOutRow
  });
  function CandidateRow({ c, selected, max = 1, showDelta = true, ghost }) {
    const T = useT();
    const pct = (x) => `${Math.min(100, x / max * 100)}%`;
    const d = c.delta || 0;
    return h(
      "div",
      { className: cx("aq-cand", selected && "is-sel", c.other && "is-other", ghost && "is-ghost"), "data-link": c.id, tabIndex: c.other ? -1 : 0, role: "row" },
      h("span", { className: cx("aq-cand-rank", T.data) }, c.other ? "" : c.rank),
      h(
        "span",
        { className: "aq-cand-n" },
        h("span", { className: T.heading }, c.name),
        c.other ? null : h("span", { className: cx(T.micro, "aq-cand-lvl") }, c.level),
        c.contradictedBy ? h("span", { className: cx(T.micro, "aq-c-contra", "aq-cand-x") }, h(Icon, { name: "contra" }), ` contradicted by ${c.contradictedBy}`) : null,
        c.keptNote ? h("span", { className: cx(T.micro, "aq-ink3", "aq-cand-x") }, c.keptNote) : null,
        c.lookalike ? h("span", { className: cx(T.micro, "aq-ink2", "aq-cand-x") }, h(Icon, { name: "neighbour" }), " look-alike of the Alentejo montado") : null
      ),
      h(
        "span",
        { className: "aq-cand-bar", role: "img", "aria-label": `estimate ${fmtEst(c.v)}${c.lo != null ? `, range ${fmtEst(c.lo)} to ${fmtEst(c.hi)}` : ""}` },
        h("b", { style: { width: pct(c.v) } }),
        c.lo != null ? h("em", { style: { left: pct(c.lo), width: `calc(${pct(c.hi)} - ${pct(c.lo)})` } }) : null
      ),
      h("span", { className: cx("aq-cand-v", T.data) }, fmtEst(c.v), c.lo != null ? h("span", { className: cx(T.micro, "aq-ink3") }, ` ${fmtEst(c.lo)}–${fmtEst(c.hi)}`) : null),
      h(
        "span",
        { className: "aq-cand-meta" },
        showDelta ? h("span", { className: cx("aq-cand-d", T.dataSm, d > 5e-3 ? "is-up" : d < -5e-3 ? "is-down" : ""), title: "change since the last update" }, d > 5e-3 ? h(Icon, { name: "support" }) : d < -5e-3 ? h(Icon, { name: "contra" }) : null, Math.abs(d) < 5e-3 ? "±0.00" : fmtSigned(d)) : null,
        c.other ? null : h("span", { className: cx("aq-cand-c", T.dataSm), title: `${c.sup} supporting, ${c.con} contradicting` }, h("span", { className: "aq-c-support" }, h(Icon, { name: "support" }), c.sup), h("span", { className: "aq-c-contra" }, h(Icon, { name: "contra" }), c.con))
      )
    );
  }
  function CandidateList({ candidates, selected, title = "Candidates", ruledOut = [], showDelta = true, caption = "Estimates from the solver · bar = estimate, band = range" }) {
    const T = useT();
    const max = Math.max(...candidates.map((c) => c.hi || c.v));
    return h(
      "section",
      { className: "aq-cands", role: "table", "aria-label": title },
      h("div", { className: "aq-cands-h" }, h("span", { className: T.title }, title), h("span", { className: cx(T.micro, "aq-ink3") }, caption)),
      candidates.map((c) => h(CandidateRow, { key: c.id, c, selected: selected === c.id, max, showDelta })),
      ruledOut.map((r, i) => h(RuledOutRow, { key: i, r }))
    );
  }
  function RuledOutRow({ r, byLabels, stamp }) {
    const T = useT();
    return h(
      "div",
      { className: "aq-ruled", role: "row" },
      h(Icon, { name: "failed", className: "aq-c-contra" }),
      h(
        "span",
        { className: "aq-ruled-b" },
        h("s", { className: T.heading }, r.name),
        r.level ? h("span", { className: cx(T.micro, "aq-ink3") }, " " + r.level) : null,
        h("span", { className: cx(T.body, "aq-ruled-why") }, "Ruled out because ", h("span", { className: "aq-ink1" }, r.reason)),
        r.by && byLabels ? h("span", { className: "aq-ruled-by" }, r.by.map((b) => h(Badge, { key: b, tone: "contra", icon: "contra" }, byLabels[b] || b))) : null
      ),
      stamp ? h(Stamp, { kind: "ruled-out" }) : null
    );
  }
  function Funnel({ levels, current }) {
    const T = useT();
    const cur = current != null ? current : levels.length - 1;
    return h("ol", { className: "aq-funnel", "aria-label": "Narrowing from country to spot" }, levels.map((l, i) => h(
      "li",
      { key: i, className: cx("aq-funnel-r", i === cur && "is-cur", i > cur && "is-later"), style: { "--w": `${100 - i * 14}%` } },
      h("span", { className: cx(T.micro, "aq-funnel-lvl") }, l.level),
      h("span", { className: cx(T.heading, "aq-funnel-n") }, l.name),
      h("span", { className: cx(T.data, "aq-funnel-v") }, fmtEst(l.v))
    )));
  }
  function EvidenceMatrix({ evidence, candidates, names, groups = [], selected, dense }) {
    const T = useT();
    const inGroup = (id) => groups.find((g) => g.members.includes(id));
    const rows = evidence.filter((e) => Object.keys(e.pol || {}).length);
    const col = (k) => rows.reduce((a, e) => {
      const p = (e.pol || {})[k];
      return [a[0] + (p > 0 ? 1 : 0), a[1] + (p < 0 ? 1 : 0)];
    }, [0, 0]);
    return h(
      "div",
      { className: cx("aq-matrix", dense && "is-dense"), role: "table", "aria-label": "Evidence by candidate" },
      h(
        "div",
        { className: "aq-mx-row aq-mx-head", role: "row", style: { gridTemplateColumns: `minmax(0, 1fr) repeat(${candidates.length}, var(--mx-col))` } },
        h("span", { className: cx(T.micro, "aq-ink3"), role: "columnheader" }, "Evidence"),
        candidates.map((k) => h("span", { key: k, role: "columnheader", className: cx(T.label, "aq-mx-ch") }, names[k] || k))
      ),
      rows.map((e, i) => {
        const g = inGroup(e.id);
        const first = g && g.members[0] === e.id;
        return h(
          "div",
          { key: e.id, role: "row", className: cx("aq-mx-row", g && "is-grouped", first && "is-gfirst", selected === e.id && "is-sel"), "data-link": e.id, style: { gridTemplateColumns: `minmax(0, 1fr) repeat(${candidates.length}, var(--mx-col))` } },
          h(
            "span",
            { className: "aq-mx-rh", role: "rowheader" },
            h(Icon, { name: e.kind === "contradiction" ? "contradiction" : { text: "text", language: "language", checklist: "checklist", measure: "measure", sun: "sun", neighbour: "neighbour", region: "region", name: "name", object: "object" }[e.kind] }),
            h("span", { className: cx(T.dataSm, "aq-mx-obs") }, e.obs),
            g && first ? h("span", { className: cx(T.micro, "aq-mx-g") }, g.label) : null
          ),
          candidates.map((k) => {
            const p = (e.pol || {})[k];
            const kind = p > 0 ? "support" : p < 0 ? "contra" : p === 0 ? "neutral" : "none";
            return h("span", { key: k, role: "cell", className: cx("aq-mx-c", "is-" + kind), title: kind === "none" ? "not applicable" : `${kind} · ${names[k]}` }, kind === "none" ? h("span", { className: "aq-mx-dot" }) : h(Icon, { name: kind }));
          })
        );
      }),
      h(
        "div",
        { className: "aq-mx-row aq-mx-foot", role: "row", style: { gridTemplateColumns: `minmax(0, 1fr) repeat(${candidates.length}, var(--mx-col))` } },
        h("span", { className: cx(T.micro, "aq-ink3") }, "Totals (correlated rows count once)"),
        candidates.map((k) => {
          const [s, c] = col(k);
          return h("span", { key: k, className: cx(T.dataSm, "aq-mx-tot") }, h("span", { className: "aq-c-support" }, s), " / ", h("span", { className: "aq-c-contra" }, c));
        })
      )
    );
  }

  // src/map.tsx
  var map_exports = {};
  __export(map_exports, {
    M_PER_DEG: () => M_PER_DEG,
    MapLegend: () => MapLegend,
    MapView: () => MapView,
    SurveyMark: () => SurveyMark,
    UncertaintyRing: () => UncertaintyRing,
    projector: () => projector
  });

  // src/geo-data.ts
  var REGIONS = [{ "id": "FR-59", "name": "Nord", "c": "FRA", "r": ["_xbBs|C|FkD`B|@~DuAlFuOyBgDi@{HdDmEpImAbBaTdJqD_BsBBoNlDsFAqCbGnC@mBdCy@tD|Es@vE_Bx@l@bCoAlKxAnNeApUmJ_DcAfHaBuAaCxB{BqB_CjDeAjJgCg@i@uBiAdCrAxC_BdU}B`@cAmAeAtI_L|HsCu["], "nuts": "Hauts-de-France" }, { "id": "FR-08", "name": "Ardennes", "c": "FRA", "r": ["a~`B_lHh@oBjJnDxAwClFTEsFzEkKGsDzCmAf@wDbBtEu@`JlCdAnDmAnDpCtAWvAjC@jTaBvBBdIaFpL_AdIi@kAcJr@}EyJqAp@wDoAgDbAj@uLgBeLgEgAyCkG"], "nuts": "Grand Est" }, { "id": "FR-02", "name": "Aisne", "c": "FRA", "r": ["mr`BgaGh@gDfDcAvDnApAq@|ExJtBu@nKr@[pIbAh@vA|KxDq@nAoC~@rF`EnAp@kDjI`Ki@|DaBf@sDbKgCRw@|CuCkAg@fH{BcBsBnB{@uEgCy@c@iCmBzAkOb@o@~AkKoGuAfADgRwAoMnAmKi@}CzA_@f@yG"], "nuts": "Hauts-de-France" }, { "id": "FR-55", "name": "Meuse", "c": "FRA", "r": ["q{_B}oIbFmDxCUc@uHjBsCbDqApDhA`@kAhD?HyB~Gy@pAnD~D[`DbBdF_ApBrApCaBhDzP{KtZgGhBmBvCyDk@iA_DmCq@}@rAoGhA{MuHoDlAaC{@i@mArA}GcCwE"], "nuts": "Grand Est" }, { "id": "FR-54", "name": "Meurthe-et-Moselle", "c": "FRA", "r": ["yw_BcfJdCkJrEFfG_EtA`AjCk@~@rCrB_ArE_JRkIzCLdCkCp@sJlDiHpBmOnDmF|FrPqCpKtCtKwAlFbAt@GzE|Az@FvGqBlEsCk@QdGqC`BqBsAmEbAyDgB_EZw@kDwAz@aCm@oB|@KnBwCKw@lA{CkAmEvBaAlBn@`HiBdAiBaC}@qL"], "nuts": "Grand Est" }, { "id": "FR-57", "name": "Moselle", "c": "FRA", "r": ["}q_BqkKz@mIrOsKTwEyBUBaDp@}DrCcAcAiAhAcK_CoGhGuM~D`DEzLiFlOtHbE|AeF`Ah@fAgAaCyDbEcFlChBx@eA~ChAhBzIoDlFqBlOmDhHq@rJeCjC{CMSjIkFxJ{Ad@_AsCkCj@uAaAgG~DsEGpAaAsBqMvAmH"], "nuts": "Grand Est" }, { "id": "ES-CE", "name": "Ceuta", "c": "ESP", "r": ["m_eAxlI{CrBn@sDUs@`CrB"], "nuts": "Ceuta" }, { "id": "FR-06", "name": "Alpes-Maritimes", "c": "FRA", "r": ["ubuAo_N`MbLrCo@t@r@LnDnCpB|@dJhEXLdIdCtAkAjB_DaAqBpGwCb@sBpFa@aCaCKqAkE\\iGwGnJgF|B{E_BwDmG`FqEhFwTmBkQpD}B"], "nuts": "Provence-Alpes-Côte-d'Azur" }, { "id": "FR-04", "name": "Alpes-de-Haute-Provence", "c": "FRA", "r": ["cfvAspL`AOtDzEbEcDj@pAtBAvDlGzE~AfF}BvGoJ]hG~AxErBAVbPrBpCaCzE`GnLyCbE`@~ImE`H`@~BkDwAkB`DwDgAYpAuBEuBcE~@wBsA]?eLkDdCNuDoBRaD{BcCqIlDiEeDm@eCsEvCkEVcH{DmCiF{N"], "nuts": "Provence-Alpes-Côte-d'Azur" }, { "id": "FR-05", "name": "Hautes-Alpes", "c": "FRA", "r": ["oivA}vLt@_@MnClHtQzDlCWbHwCjEdCrEdDl@mDhEFzBdGfIfCI}@|CxEmB?dLgCImCpBc@bGmCjCWqCsBv@MeJwBtAiDcBc@}GuDwA]aFqBkAgAqUyG~@c@lEwEwAlCaKkCsIh@r@dCaBl@mCpEk@xB{MlGoB"], "nuts": "Provence-Alpes-Côte-d'Azur" }, { "id": "FR-73", "name": "Savoie", "c": "FRA", "r": ["sxwAeyLlBkDlDfC`C]xAhBF~D~CdFu@vEhBnLbBxBiEtQyFt@oC{BeDjCmB`JZ`AbDFyAtHqLvHgCcImL{CnEwAxCyEA_HtCiFg@wCwKaKl@mAtBPzA}FfBSiA{DfC_AnBeHbGg@xAwD"], "nuts": "Auvergne-Rhône-Alpes" }, { "id": "FR-74", "name": "Haute-Savoie", "c": "FRA", "r": ["iuxA{uLdCpC~@fHxB`@hApCgB|@{A|FuBQk@bBtKjJf@vCuChFLjGeDlFgOtBmBuRsDyGuCdCwBmBaDqTrAyIfChAxC{ChFzBnAmEzBb@@_CvFuE"], "nuts": "Auvergne-Rhône-Alpes" }, { "id": "FR-64", "name": "Pyrénées-Atlantiques", "c": "FRA", "r": ["upsAdlB}D|A[iGuGeHnAqCSwFmBaFrCcB}CkVr@sLaBkElAs@gAmMn@aF`EoC|A|@OoBrD_@x@dB~GrBrCpEhBAvAbEfI`@nAlFa@zEdAdA_FtI{Bf@AlJsB|KaB~Gw@h@s@y@^zBvBb@WtDiA|@iB{BwEk@qAtHhA|BeB`ALvD"], "nuts": "Nouvelle-Aquitaine" }, { "id": "ES-NA", "name": "Navarra", "c": "ESP", "r": ["}psAjlBE}DdBaAIcA_Ay@d@}Fj@w@vEj@hBzBzAiBDiCwBc@i@mAHm@nAp@j@gAvBmNlAiDIyHbAqA\\xB~BvAjC`@t@hA|ApFzAd@PhEv@t@Ta@vAbBHfBh@h@vAIpChCfALh@c@rBhB|C~@fEo@~AqAReAr@?~FlE[nCT`C{AdDD`CkCtJwAPyCyCDmGqCP{B~Hu@JoDbFK|C_@ZY]]j@?bF}AlDM~F{DIOf@l@x@e@tA}BuCf@kCq@mBcCt@k@qAoDiAyBTeAi@a@}@B{CkAsC}CcAgCmEeDEWuCaCgD"], "nuts": "Foral de Navarra" }, { "id": "ES-SS", "name": "Gipuzkoa", "c": "ESP", "r": ["svsAboBxADRy@fAc@`CfDVtCnEb@|AnDpCv@vA~C?tDbBlAAv@aBrCm@fJRn@e@vAw@[o@mBkBX]yAmFUI_AqAqAg@j@qAaAr@sFWqDv@gCoBoIj@qAM[]h@gBeFPa@"], "nuts": "País Vasco" }, { "id": "ES-HU", "name": "Huesca", "c": "ESP", "r": ["myrApm@bAIdAwDxC}CUaAo@C`@{EgBiEpBoDQsCbAEvAmA~@_DqA_L^iCpAiA_B}CdAmB[{NjCiBf@iBpElA`@x@xDyAzBI`L~AjFdB|BjDp@u@zAAnBxDxAfAZtBvCxCjCk@ZqC|Aa@fBvA^zAnCXk@`Ep@j@GlBd@dAhAl@QlDm@bARlBkE`AgFdDXnCiBjDkBhAeBvEoEfA_BbDsBxAUzFoAvC{@V{Ac@Qy@p@iA{@cAuIPeBs@wCZMdA|AMbCdAGjB`A|@Wz@mFoDs@Ly@tBgAWeJfAw@yAgA|@oA]_AmA{BUmBoA]yB"], "nuts": "Aragón" }, { "id": "FR-31", "name": "Haute-Garonne", "c": "FRA", "r": ["_trAoo@KnFjHACzJ_IDa@kDsD}DuClAx@tCmC_AqBpFuD}FqDkAiE}IHcG~AoDaImBsAsFiA]wJzMy@eLrAaD}A_F{@rBeC_OnEo@j@_ClFcDrAjAhHkOy@yBp@sA|Bh@z@fHw@tAhDjAnDvHaBfGjCp@Z`BeDdCEfCfCwCxBbI|AkCbA|AaCrERnC|BxCtDGdDrHzDc@e@~C"], "nuts": "Occitanie" }, { "id": "ES-L", "name": "Lérida", "c": "ESP", "r": ["}trAek@\\sE~AwEWy@p@uG~B{BC_K\\HdEuDbCl@Cm@t@i@`@rAzAw@TaDgAuF}@[KiBnBk@v@{C`FgAb@|Fr@z@bBIvA{Ax@x@bAOf@r@tA@z@|@n@sBr@jCbCz@dC[xBjCQzCq@hAX`AhDHvB_Ap@`C^FXiA\\ZH~JdD`AJlEjBd@x@pBtA|@X|C_@xAt@x@~@nJq@tBdApA{AdCR^`BHE|AzAr@{ANwBk@eBbBoDu@_@{AgBwA}A`@[pCkCj@wCyC[uByAgAoByD{A@q@t@}BkDyOuDoFEyDxAa@y@qEmAg@hBkChBcAD]t@c@c@uCIQeB"], "nuts": "Cataluña" }, { "id": "FR-65", "name": "Hautes-Pyrénées", "c": "FRA", "r": ["_qrA~K}A`EgIa@wAcEiB@sCqE_HsBy@eBsD^NnB}A}@uEvD_@i@c@eDpC}@|@eEjD_@|AoBxBuXpDjAtD|FpBqFlC~@y@uCtCmArD|D`@jD~HEu@`F~A|CqBrEpA~K_A~C{CrAT|A"], "nuts": "Occitanie" }, { "id": "FR-09", "name": "Ariège", "c": "FRA", "r": ["_qrAqx@y@`C{Db@eDsHqEIwBkGbC_FcA}A}AjCyBcIgCvCDgCdDeC[aBkCq@fBgFk@oCfD_@|CcMpG}A~@bBzBwApBpF~BiBNyHrC{D`@|IfD`C@nIsAlAmAdJNvCzAjAcFjDB~J_CzBYnI"], "nuts": "Occitanie" }, { "id": "AD-05", "name": "Ordino", "c": "AND", "r": ["qhrAm_Bt@kBn@CZbAh@POlBo@f@Mz@mA_@OwC"], "nuts": null }, { "id": "AD-02", "name": "Canillo", "c": "AND", "r": ["{frAybBVyFf@Pt@gBl@~AeAbAV|Fi@Q[cAo@B"], "nuts": null }, { "id": "FR-66", "name": "Pyrénées-Orientales", "c": "FRA", "r": ["warAijB_AyLgDgCFmJoBkGk@w@uERDuU_DmHxC}JrPKz@iDrDyAeAnN~BfN`AbBbAk@XdHmEzMXvGhC~FsDbDqBlL{AI"], "nuts": "Occitanie" }, { "id": "AD-03", "name": "Encamp", "c": "AND", "r": ["warAijBhARV`Au@`Ag@hDq@?W}FdAcA"], "nuts": null }, { "id": "AD-04", "name": "La Massana", "c": "AND", "r": ["eerAixA?gBn@g@NmBp@?bArEu@h@Bl@cCm@"], "nuts": null }, { "id": "ES-GI", "name": "Gerona", "c": "ESP", "r": ["{~qA_jBpBmLjCiAf@yAUkBsBsCYwGxAcH~@m@r@iCs@aAXcFcAj@aAcBKeEsBaHF_ElAoBG}DbAT|Aa@t@eGdDlBg@xDrAdBzCEnCwDdAb@lDgAhEbDE`AnGnJ`@xD`BzBw@`@}AM]f@[~B|@pGgDzEFrC}AxAqA[^eBoA}CkAj@yC}BkAp@QrB_BjBNrB{@v@l@lHa@|BsDrAeCa@o@|FVlCaFfAw@zC}A`@"], "nuts": "Cataluña" }, { "id": "AD-06", "name": "Sant Julià de Lòria", "c": "AND", "r": ["yzqAg}AWnC{Av@}@}Cx@WFwC~@Bn@`C"], "nuts": null }, { "id": "AD-08", "name": "Escaldes-Engordany", "c": "AND", "r": ["c_rAqfB~@`@XdC_ACGvCcBkCh@oCf@_@"], "nuts": null }, { "id": "FR-67", "name": "Bas-Rhin", "c": "FRA", "r": ["ww~Ay|M@}PvCwOlHzEdBnFzG~H~DE~EtCbCYvLpIClAiApC}AFmGfU{HmAm@vBiB{I_DiAy@dAmCiBcEbFxBhEaCLwBlFeHyErF_OD{L_EaD"], "nuts": "Grand Est" }, { "id": "FR-68", "name": "Haute-Rhin", "c": "FRA", "r": ["q~|A{xMjHmAnOxErFsCtAlEd@k@pAjAOhBfBNh@nIu@jC_Ep@cCnF{Eu@kDfJqAkBcFw@sTaOPeDxIcQ"], "nuts": "Grand Est" }, { "id": "FR-90", "name": "Territoire de Belfort", "c": "FRA", "r": ["cw{A{wL@`DhAc@p@fBuEf@y@~E_I~AiEyCvEkLzEt@lD_G|@PCnD"], "nuts": "Bourgogne-Franche-Comté" }, { "id": "FR-25", "name": "Doubs", "c": "FRA", "r": ["es{AupLpCnC[qGjAaAvNtTpBp@xCzLlJZhIpQjAKsBfDaAsAsAXuCwFwDjJ}FtCoArKmFeCqFfFsDoVsCsJoCwBTqM_BsAq@eLx@_FtEg@"], "nuts": "Bourgogne-Franche-Comté" }, { "id": "FR-01", "name": "Ain", "c": "FRA", "r": ["wnyAm}JjDx@bAdGbD?dAjGbI_@|JhC~DdGsM~OzDbGqApF^pK}BNeD~HkQcC_OgGG_LnBwH|AQdH{JeDsGjCsCBkHaHuJ|AwCjA^"], "nuts": "Auvergne-Rhône-Alpes" }, { "id": "FR-39", "name": "Jura", "c": "FRA", "r": ["{|yAs~JxG|CzGbJ@|HkCrCzChIkBZgEzHeA?gAcFoB~BaE}BkIrC{AwE}A~F{C~Cs@qBaB?uAaE{JkFn@aJpFgFxF|BbAkK|FuCvDkJtCvFrAY`ArArBgD"], "nuts": "Bourgogne-Franche-Comté" }, { "id": "ES-BA", "name": "Badajoz", "c": "ESP", "r": ["sljAjeMkAl@cDm@aDmFgA}DcBRyEyDiBX{@z@c@`BRvDcCTq@vCeAj@oA]H}AiBaBmAPk@{AAyA`C?@w@eCm@_AxAm@c@jB_IJsDrC}A~B`B~A}@ZqDk@i@`@uCv@{@g@s@T{Hk@gBhCMpB_Hv@s@aEqF`Cc@{AyBr@a@g@eCsA_BNsAjB{Ce@wCgAgAeBdAq@mClBcEIcAaC}B}DMZaIy@oBuBo@dAsAy@aFp@_CeDuJ~@]rC`AjAxAfGcEq@hHbAnAtBf@rB_A\\rAYxCbDaAn@aD~AJj@`DdG~Bp@dJ~AT~@tC~AdBBlBfCrBtDhHpDCbEaBvCf@pCxIcAn@}@uAs@j@JtFvBzCjBApB`Bn@lHnAhCyBxI}@^s@fBpAxBOlD}BxAk@pJ_CGgAnGdArIcE|BqHjHi@rAm@o@q@T{Bw@{B_B"], "nuts": "Extremadura" }, { "id": "PT-07", "name": "Évora", "c": "PRT", "r": ["{ujArbMv@vAp@ZdCNv@k@ZJ~ArAbBb@VRXWV@l@n@h@sAtEsEr@]f@y@`DoALSNf@?\\[h@oBt@}@fBcBr@IR~@~E~@Z~@xBjA|@BT]lIw@|BWxC{@hDk@j@UjAPrAe@~@Gd@@~DPFm@jAOzAw@zB_Be@m@|@[GkA\\gAjAENd@nB@x@m@hADZVGNNShBc@lAEx@mAXa@@gAiA{AeDq@o@e@A_@USDQ~A_A_BMyAk@}@IeAg@YD_CUc@|@uANsAh@]B]b@SL_@Yc@m@EQj@m@l@q@KMHm@fCQ\\OBu@e@u@E]OCc@{@eAS}@DuAp@Jd@UAKk@MIu@F[f@m@fAKBaAm@iAEk@lBoB^mA?qAQ_Ao@s@R}@Gg@LoA{@gAa@uB[GYRMk@PIXoAV_@vAW^k@`AS^[\\Ht@g@Zo@@k@G]}@sAO}ARq@LEh@@l@`@P@LO"], "nuts": "Alentejo" }, { "id": "PT-12", "name": "Portalegre", "c": "PRT", "r": ["uyjA`{LNzAv@x@p@zAMNQAm@a@i@AMDSp@N|A|@rADhA[n@u@f@]I_@ZaAR_@j@wAVW^YnAQJLh@XSZF`@tBz@fAMnAFf@S|@n@r@P~@AdB]x@mBnBDj@n@zAIv@cABk@v@DfAj@L@Je@Tq@KI\\DdAl@vAUvAQZuBfAi@tA_@?}AuA}@mBqBeDi@USY@y@Ok@aB{Ai@O{@mBq@g@K@_BvBuAi@q@i@_@}@h@wBV]iAqBqAyAKg@mAw@Sa@ToBo@gA[iADSdDoAvA_Br@cBz@e@R]`@}BRMvAHv@XvAIjCwCd@Xh@BdAk@p@wCd@WlAT^oA]gADgBn@mAb@[f@M`@LLUPClC`BjAvAf@[z@Fv@`B"], "nuts": "Alentejo" }, { "id": "ES-CA", "name": "Cádiz", "c": "ESP", "r": ["yqeAtlImAjD|@`@jDEpBxI}@b@{@tBe@tEcEpFKnFuDfCm@jBeCp@eIzFf@gBpAu@qAgBDxAaCTgA~Aq@~EcFjAwAmDqDOm@cAh@cHx@iB\\kLiC_BQ{FyA_BtAcDIsAw@kA}CWUo@f@yA~Aj@v@UeCsFdC}CQoA{AkB|CqBtBf@hApDyAhCPrAlAfAlBwApErA~ArExAjAhBxFt@sBy@qCFeBfDmCxEeAWsAnAo@f@hAnG~A"], "nuts": "Andalucía" }, { "id": "ES-OR", "name": "Orense", "c": "ESP", "r": ["{cqA|~NwD|@e@mAqCc@ZlCq@~@sBK{AnBeGl@BkAcDaGl@u@L_Gw@s@O{B~@iAnADnEoPL_EaBeFn@wAHyDpDcCiEgBwC_DNoDc@}Bv@eEzAOx@r@hCmEtAH~C~Bb@xDvF|Ff@Il@kBjC`@h@fCwAxEj@nAzBCl@h@hAxIfAdB}Ar@W|A`A|@JtB_@`@}@_@s@dFpA|IoBP|AlAD`B~AlBHdGmAEc@tAiARoGmG_AtAThB"], "nuts": "Galicia" }, { "id": "PT-16", "name": "Viana do Castelo", "c": "PRT", "r": ["siqAz`Op@c@tB?NYUiB`@eA\\Ob@BVTzArCvB~Ad@Bb@WReANOhABB`@xAlFJlEd@lALzAZThAPZZ`@El@b@k@hDXn@BfBf@pCCbA{@PeAC[gDq@}At@jGQ|@aAd@sCOw@LUGcD_FiAW}@_D}@c@g@s@EkBy@oCe@sHw@gBOuA_@{@"], "nuts": "Norte" }, { "id": "ES-CC", "name": "Cáceres", "c": "ESP", "r": ["mukAddMkCvC{FKa@|BcCfDwA~AkDpAHkVe@cI_Dw@y@LuBoCoBEuDyA{DvC{@nC_B\\yAu@u@yBCuBo@i@dAwBaAgNa@c@w@H{@sA_GgQ~CuHzAn@pCmIqAeBi@mCf@k@hABHaEzBeDj@_CGkBsA{BWiCrDL`BcAl@hAfLh@K_Cp@aAhCp@dAKJ_BqAeB?qAzAEdAo@vFlBfKwNx@`FeArAtBn@x@nB[`I|DLpB`BX~AcBpC?`Bf@|AdBeAfAfAd@vCkBzCOrArA~Af@dCs@`@zAxBaCb@`EpFw@r@qB~GiCLj@fBUzHf@r@w@z@a@tCj@h@[pD_B|@_CaBiD|BHrCkB~Hl@b@~@yAdCl@Av@aC?@xAj@zAlAQhB`BI|A"], "nuts": "Extremadura" }, { "id": "PT-05", "name": "Castelo Branco", "c": "PRT", "r": ["}rmAzpLx@rCxAt@~A]ZWJmARi@zDwC`Aj@vANZ\\h@EdAJx@p@V~@b@\\x@MdAf@n@Eh@Td@bIA|@Uj@FpBT~AO`MZhAn@fAUnBR`@lAv@Jf@pAxAeAf@wArAc@`AWbBkBFc@TQnBDh@bDx@jAQNxC{@`DYPmBFQMcADURUbAu@TcAe@[uBi@m@Qu@wBmBEe@SSGoA[KQ{@Bs@i@s@MgAe@Dc@_@UcB`@kAiAAIIH_A_@y@WGk@JkAjBe@T}Aq@W_BuAuDoAqANq@KcAY_@mAm@gAcBp@oAHm@OuAe@k@GeAFg@vBPr@V`Ax@TUX}BYyA?_BQg@]M]a@`AeA?yC|@oB"], "nuts": "Centro" }, { "id": "PT-09", "name": "Guarda", "c": "PRT", "r": ["mtmAtlLZDRb@?zA}@nB?xCaAdA\\`@\\LPf@?~AXxAOzAMn@QFaAy@s@WwBQGf@FdAd@j@NtAIl@q@nAfAbBlAl@X^JbAOp@nApAtAtDV~Ac@\\Uv@{Ao@u@cAm@p@yALW~@SLUSKa@_@SqAn@MSKqAqAmDg@yEi@FmBo@YYo@Ic@`@Uj@]RSUYCYNm@`AMBeAs@u@U]o@HeA|AyB?_@eBaA{ARIWJkAk@_Aa@Oc@@e@~@c@NSoAu@Fc@E{DcAI}CJgBSQo@_Bv@X\\aAp@Jt@YRUbAoDHwBd@HXRXCjBmBzB{@`@cAXIXFF`@rAEnAH`Dm@z@C`CfA`@C`A{@`@IpCvA~@Kx@m@p@cAn@b@fArB`@H"], "nuts": "Centro" }, { "id": "ES-SA", "name": "Salamanca", "c": "ESP", "r": ["mtmAtlLyCaDkBpB_AJqCwAeChAaCgA}Ep@cDCa@i@}HzFoAeAOmEyAmAcBSyEwEEgD_AaDl@_IdDaK_@g@V{CfAE^y@[y@j@m@k@_AkCM^aEw@sGfC_JQqDjAKz@qCMaAqBM]gA`C_G`Bt@`AIj@sAtAO|@z@lA_@|AdBtCb@lFlJtCbB^nEdAI?uC~Cz@V~AhAHMx@_BrA`B`EbCY`ChBNnBiACg@j@h@lCpAhAOnAaCxG{Ao@_DtH~FfQn@hApAD\\x@v@jMeAvB"], "nuts": "Castilla y León" }, { "id": "PT-04", "name": "Bragança", "c": "PRT", "r": ["mtoAbtK~@`DDfDdB|Al@XdA~A~@Bb@NlBhBCpDNf@IvBcAnDiAn@q@K]`Aw@Yn@~ARPKfBJnEObAqArAQz@o@WKu@cAEa@c@i@E[a@OeAUn@i@\\i@JaB?q@cBcBiAIw@OUeAd@mACgDaAmAq@g@k@k@@e@b@{AZ{@Gq@LYU]C}AF[m@Q_AxA{Do@uBl@}AFw@G{BUo@{@KF}@rAgAL{@CmCOcAi@[Lo@VY`@GtANLOPwAb@VbDn@t@`@t@[jAO^YJmAo@sAX}DZaBj@yArBcCpCrCRJh@EzAjAP?B|@Vt@f@??h@jA|@fAdB"], "nuts": "Norte" }, { "id": "ES-ZA", "name": "Zamora", "c": "ESP", "r": ["mtoAbtKsCmEg@?[sBkDqAqCsCsBbCgAzDY|Dn@rAKlAaDdA}FiB_@fBuAOy@`@n@|GiB`Ez@JTn@?rDg@jAkCa@eAzB{GaHO{CeAk@lAwDLiGl@eCo@eJvBwES}H~@qDo@}Bv@o@]cFn@WMcCg@Dx@mBt@?h@oCeAU@i@tDaBj@X`@}A_C_@S{AzB}Dn@l@fDFrBw@fB|EtD_CnBY`@eAbATdAyBfAtDr@d@lBc@dCLtDcAtBzA^]GgAzBVw@hEkAJPpDgC~Iv@rG_@`EbDXRr@m@x@\\l@_@x@gADWzC^f@eD`Km@~H"], "nuts": "Castilla y León" }, { "id": "PT-17", "name": "Vila Real", "c": "PRT", "r": ["otpAbvN_BoBEaBqAe@Kg@nBQ?_Ac@]WgEUw@n@yBBkB|@^RAJ_@KuBO]q@_@V}AZW`A[gAeBEkCe@mCq@sAp@M~ABv@Wd@c@j@Af@j@lAp@fD`AlABdAe@NTHv@bBhAp@bB`B?h@Kh@]To@NdAZ`@h@D`@b@bADJt@n@V`AjFDxEh@tAJfAGfAy@`BBf@p@hB_BMoA[Qb@m@^]HYIi@rAQLa@@_@`@c@QWBoA{@WDo@QW]@Wk@e@a@}@yAoAWCk@^Q^b@h@Jx@KdB]dBeCSQN]`ARpDgAaAuCgAY@"], "nuts": "Norte" }, { "id": "PT-03", "name": "Braga", "c": "PRT", "r": ["itpAd~NJkDMyAjDhAfA`ASqDb@kApCL\\eBJeBKy@c@i@P_@j@_@VBxAnA`@|@j@d@AVV\\n@PVEnAz@VC~@Zv@hADb@_@`ABTU~@g@dA]B_@h@[`Bx@dAd@zBQv@RnCSfBp@dCBhCUXi@Ja@u@YZOp@q@~@EdAg@bBAl@m@TgBPuCp@BcAg@qCCgBYo@j@iDm@c@a@D[[iAQ[UM{Ae@mAKmEyAmFCa@"], "nuts": "Norte" }, { "id": "ES-PO", "name": "Pontevedra", "c": "ESP", "r": ["siqAz`OfBxFdBnPdBvAtEbLcMZWgC{@f@yG{LmAEHv@hAp@lAzEFdDaB]Ns@yAFAuBcEiFbAlEDjDgBvAYlBw@{BVg@^XL}AqA[eCReA}AiEwBWuEw@}@BiGyAiBHcB{BYr@mAaAgFb@yFMiDxB\\fC}ElG|BNzBv@r@M~Fm@t@bD`GCjAdGm@zAoBrBJp@_A[mCpCb@d@lA"], "nuts": "Galicia" }, { "id": "ES-H", "name": "Huelva", "c": "ESP", "r": ["qsgAjnMuPlBaDvBwA]gAsAyDw@qFqG{FcAg@aFuAiA`@eEsJsDfAoG~BFj@qJ|ByANmDmAsA@{@jBqB~AwHtAaABoAtBf@tAm@J|CjCd@Ir@{@b@z@lJvC|Cr@Dv@qGx@LpGkDb@DXrA|A?h@f@`BqA~IZfBx@xCw@dBn@x@mA~DX@fAoH~E}KpW_Bp@_DaCxBzC?~@zBeAgBxIPr@PqAFbNj@hBY`A"], "nuts": "Andalucía" }, { "id": "PT-08", "name": "Faro", "c": "PRT", "r": ["ohhAttMbAmAb@MrBM|@a@~CO~@Q^Jj@IvA]h@[LNS^IxANtArBdFdF`K]bGTNU`At@[s@j@q@fA}@nCe@nCRbFg@nCTz@FvAUxAo@hBKtAJzBdAvA?zBh@dBHjA^j@Kf@lAdCe@hAJ\\sAWoBwAeBw@{@P_AsAyA[aA^q@_@q@w@qD}@f@}Ax@sA@oA\\sA[_@O}Ap@aCJuAWeAu@a@g@wEJq@~@YTW~AiDRgEiA_Da@RYIM[OqCMYWO{AkEs@}CJmD{@gBGiB", "ifgAfpNJgBKg@e@o@XM^p@Hr@MfBO?"], "nuts": "Algarve" }, { "id": "PT-02", "name": "Beja", "c": "PRT", "r": ["kriAlqLz@L`HbCDp@g@rCv@d@\\b@Np@IjA`@bBv@GbEjAlAt@xBvDh@b@z@Z|BZfArAf@BZZlA]FhBz@fBKlDr@|CzAjEVNLXNpCLZXH`@ShA~CSfE_BhDUV_AXKp@f@vEt@`@VdAKtAq@`CN|AZ^]rAAnAy@rAg@|AqASyAEo@Jy@l@YDaEw@QqAo@KNpBa@NmD_@`@g@O{@Ha@lBcBYg@`@eBWm@kAWeAy@[u@[sDLkCXaA{B{@qCK}@^OZOhAs@bAi@LeA]Fc@IQ}@UOg@Rq@EMs@OUUBeAm@e@i@oDw@Iq@NsAn@QG@{Eh@iAQsATkAj@k@z@iDVyCv@}B\\mICUkA}@_AyB_A[_A_FHSbBs@|@gBnBu@Zi@OeARYGqAOo@[YGcACw@NY"], "nuts": "Alentejo" }, { "id": "FR-83", "name": "Var", "c": "FRA", "r": ["o|sAipL~BpCC`FdCx@dCpFT_ElCXlBjPnBt@c@jJhAnAfAu@@tDgAoAMjEoBjDZzB`ByBb@pFs@hAw@y@qCtGeEqDwApCwCHU_EeCbCsCWwBvA{CgGuAtBs@q@`AwCo@uCxCcEaGoL`C{EsBqCY{JvCwGvCc@pBqG~C`AjAkB"], "nuts": "Provence-Alpes-Côte-d'Azur" }, { "id": "FR-13", "name": "Bouches-du-Rhône", "c": "FRA", "r": ["wisAoaJf@vBiBlDEbJkBk@iDtCf@fOsCNe@gHgBgBKjDqC|EpAf@pDsANlJnB?CaAp@xA_DbEyH|BvH_BxCyC[fMkCVs@dCGdReGmNiAn@aC_BKgGwI_A{BgGnJgY~CcTqBeNhAmAv@j@bBzEvBwArCVdCcCT~DjDObAkCdEpD"], "nuts": "Provence-Alpes-Côte-d'Azur" }, { "id": "FR-30", "name": "Gard", "c": "FRA", "r": ["g{sA{eGu@pCqC`AaDaDcBHmB~AoBxHkC`@?tFe@|@yAo@eAjEpEvHs@nCnAxAgBtE{EqEoC~HcDsDlByGGcEeCmBhByKgFqD}GjCgCeEjBoB|C?tAqKgBuDIwA`B_A}AmElBqGvD}BhEIHgBbDiCdGzKvI~@JfG`C~AhAo@dGlN"], "nuts": "Occitanie" }, { "id": "FR-34", "name": "Hérault", "c": "FRA", "r": ["_atAq_GVnHhItSzDxEE~F`CxGaElRmC|B`GbFaCfC^xC{BnBuAkAUp@{A{D_EpAgCg@\\mGwC{HDgEcGaAJgGqD}GfBuEoAyAr@oCqEwHdAkExAn@d@}@MyExC}@~BuI`EmAnB`D`AI"], "nuts": "Occitanie" }, { "id": "FR-11", "name": "Aude", "c": "FRA", "r": ["elsAwiE~JzIzJn@yC|J~ClHYpSp@vAlEWdCrHwDbFYbIgCtA_BgF{BvA_AcB}C`BqA]uDlMcCz@}CaAi@aDyC{@jA}UuBiBd@eRbE]x@mBu@cB`CgCaGcFlC}B`EmR"], "nuts": "Occitanie" }, { "id": "ES-B", "name": "Barcelona", "c": "ESP", "r": ["{ipAslDhJ`]rGjGfBlEdDfZ}@?UbB_BoAe@v@aCr@yBnDcBU{@zC[NiBcAAjA][YhAs@e@]cBwB~@iDIYaAp@iAP{CyBkCeCZcC{@c@cCm@HQ`B{@}@uAAg@s@cANy@y@wAzAcBHs@{@{@kKn@}FdC`@rDsA`@}Bm@mHz@w@OsB~AkBPsBjAq@xC|BjAk@nA|C_@dBj@`@nA]r@aAGsCfD{E}@qGZ_C\\g@|ALv@a@"], "nuts": "Cataluña" }, { "id": "ES-T", "name": "Tarragona", "c": "ESP", "r": ["omoAodBHhDbD`SzAxAWtC|@vEzNlQf@mBIa@]`@L}@dByDh@B~@n@`AvDxC|CVxBy@n@LmC]aAwAiA?dBz@jEzCnBm@fCsAjAqAxFk@`@{@WuBpFy@wBaBwAgCh@yDoAiA^o@zAyCd@kAgDaBg@s@}A{As@D}AoBWtAwCeAqAp@uB_AoJu@y@^yAY}CuA}@y@qBkBe@KmEeDaAGkMhBbAZOz@{CbBTxBoDzDoBjArATcB|@?"], "nuts": "Cataluña" }, { "id": "ES-CS", "name": "Castellón", "c": "ESP", "r": ["{cnAw_@`NxI`FbHxDvB|A|CxRfOcDlHrC|EqCxC~AhEoDj@_@dAdAj@Gn@cE~DoBCs@oBmAi@_AwGeAF}A_BkDs@RaBi@qDyA]wCqEmCjBaAgCkAr@wDGW`DsAB[}@TsA_AkCcBU}@w@@uAvA{CHwDx@c@m@qBU{F|AiCz@Vj@a@pAyFrAkAl@gC"], "nuts": "Valenciana" }, { "id": "ES-V", "name": "Valencia", "c": "ESP", "r": ["eqlAbKdB\\fHbF~FCbCg@vGkD^t@lD_A~FqDfCsDz@nKy@~C|BrEn@bJlAy@MaAf@s@`BvEuBdFVjDaAdB@`BY\\cAc@cCNwBbBXjH_@z@qD`EgAZuGaDeDSuCtMFnAsClC_F[cEcDaAaBXkC_@_AoBEoF_CwCFaA{BMaHl@yCh@c@tCOLiAq@iCxB{CeAk@^eAnDk@_BiEpCyCsC}EbDmH", "uomAhpA~CcCp@yE~@{Ah@A~AfIq@lGeDdAs@lAe@E@wFkBo@"], "nuts": "Valenciana" }, { "id": "ES-A", "name": "Alicante", "c": "ESP", "r": ["e}jA|@fBqJt@}@NZr@qBv@M`DnHz@Bd@vFnC~@XjEpBnHnBbC`Bd@t@~DdGK`@lDv@`AzAh@|FR`AjBzEfBk@zCoAbByJzGcI{BgB\\mAxDq@LoBCeCaCwDWaC`@GaCs@kBsBzAcA?DcD`AeBWkDtBeFaBwEg@r@L`AmAx@o@cJ}BsEx@_D{@oK"], "nuts": "Valenciana" }, { "id": "ES-MU", "name": "Murcia", "c": "ESP", "r": ["k|hApn@bB?u@t@hBn@v@vAtC{Ar@mBC}Al@E`@l@|AhKg@`BIbFj@~@t@[}ApGh@d@GzB~CdHjBr@|A`HqBrDMzDaL|IkGB{Cu@{@fK{@vBgEtEsI}FkEqIb@cBUeCqD}IRwBjAQ`@u@UoD{BkDeHh@mB_BcCg@}A}B^iAeBuD_@iCZkB~@]hBeD`Ca@dEZtC`CbCMp@cDjBs@vC`@vBrAnBCtIqGnAcBj@{C"], "nuts": "Murcia" }, { "id": "ES-AL", "name": "Almería", "c": "ESP", "r": ["i_hAreBzItItLxD|AKpApDxFbDlAnBAxCqC|Cu@|Cr@lLdDnArAdCJpCcA~BZt@cBbCFjLsAVoB}EsBvAgDcDeEf@_@uBoBo@k@uAoD{@CeBhA}Af@aEoCJeEo@sEoHaAgGsDb@SwBwCHcCmAiEFeBwCbBsMzCt@jGC`L}IL{DpBsD"], "nuts": "Andalucía" }, { "id": "ES-GR", "name": "Granada", "c": "ESP", "r": ["swfAnbE@rK`BhD?|Bq@jAPbA}@dBd@bGWzAcCQiBtBB`B}D~OsDxFiH|AsAaC}@NgDkAIkCmB}CBuCn@cBO{E_DaB}BiIgDoF`BwE[gDyBwDtAgGa@oAVgC_AMaAsCwEWsGoEyBkDVy@yAqCoBFe@mBtCeNrD{DdBvChEGbClAvCIRvBrDc@`AfGrEnHdEn@nCKg@`EiA|ABdBnDz@j@tAnBn@^tBdEg@fDbDrBwAnB|ErAW"], "nuts": "Andalucía" }, { "id": "ES-MA", "name": "Málaga", "c": "ESP", "r": ["_wfA`kF_@zBp@rFi@~DfAnIOdKtGpEL|BzBzBd@pC[fJbBtDnAfJnF~CoAn@VrAyEdAgDlCGdBx@pCu@rBiByFyAkA_BsEqEsAmBvAmAgAQsAxAiCiAqDuBg@}CpByEaMi@]mAbBJcDs@k@|@mCcAmBaBZ]_@HsE`Ac@TqBeC{D?yBzBWX{AdJaCvCaF|D_PCaBhBuBbCP"], "nuts": "Andalucía" }, { "id": "ES-SE", "name": "Sevilla", "c": "ESP", "r": ["magAndKy@iAt@~Gy@lAeBo@yCv@gBy@_J[aBpAi@g@}A?YsAc@EqGjDy@Mw@pGs@EwC}C{@mJz@c@Hs@kCe@K}CuAl@uBg@CnA{@^oAiCy@cIuBqA}AFiCwEI}Cj@{@b@Cb@jAnAW}AeEBsAd@@pCkDzBa@nAqBrCa@p@yAbBe@d@}@tC@?|Cn@n@zBcAWmE{AkDF{BsAyCFcBjEkCbDVp@gApGkDx@uBaAgBLe@zCcAh@IGdC\\^`B[bAlB}@lCr@j@KbDlAcBh@\\dIzQM|@yBnBhCdGw@T_Bk@g@xATn@|CVv@jAHrAuAbDxA~APzFhC~A]jL{A|F"], "nuts": "Andalucía" }, { "id": "PT-15", "name": "Setúbal", "c": "PRT", "r": ["e{hA`ePeBCo@Jq@^I`Ai@pAi@u@oDgBmCe@kBm@wIh@oAr@cBpBo@hAOv@Y_@Nk@p@iAj@gCXAAsAh@gEYcBKnBu@pCOPw@NcA_@GZWR[DUKC\\|@f@Hf@L?Bk@\\U^?NNKvAq@rCL`BpAxAHOb@pBR`Ed@jBM|@e@?eAqA}CKaFhCOe@OqDj@iAg@J]{BK?u@}@}AsCG]?Qv@GPc@]uBj@oBGo@_@]eA]yAy@d@uB]gALKlADVWToDXQ^Td@@p@n@zAdDfAhAnB[Dy@b@mARiBEMi@An@}AAy@e@oBDOfAkAjA]ZFl@}@~Ad@v@{BN{Al@kArAo@pAOVHp@~Dd@TCdATTr@NDLQ~@LXfA\\Gl@PHr@Rh@Mr@cANiAN[|@_@pCJzBz@Y`AMjCZrDZt@dAx@jAVVl@a@dBXf@mBbBI`@Nz@a@f@"], "nuts": "Lisbon" }, { "id": "PT-11", "name": "Lisboa", "c": "PRT", "r": ["ovjA|mPuBt@_@MBl@_Cr@mCuA}@s@i@eAM{Bw@oBP@j@r@PhA\\[vBxApCbArAhAV?j@i@x@WBf@", "sikAndPp@vANlDNXdDfClDlBpApA^LvCQn@\\f@tEI`Cx@hAcAdDBdCKf@iAMuAVk@?oAsAaD_AyBBiAVcB[mBmA}BaAkCSq@LA_Bo@eB@c@j@m@xBm@V_@_AqAeBwAOa@XqCn@W\\B\\iCQoAZOlAcBRZHpBN\\J?hByBZcAl@_@", "g|jA`tPEKL?\\J|@~@CL_Ae@_@g@"], "nuts": "Lisbon" }, { "id": "PT-14", "name": "Santarém", "c": "PRT", "r": ["}hkAjdPu@q@^t@m@^[bAiBxBK?O]IqBS[mAbB[NPnA]hC]Co@VcBPqAs@Ow@{BqAUYO{@IaCFaBM[UG{@PIG@cAaA_AyCl@k@mA]W_@Fs@r@iAD]U_@{AB{@eAeC]gB|Dw@u@{D?q@}@FHaB^KTcATSbAEPLd@?fAGXQz@aDOyCkAPcDy@Ei@PoBb@UjBGVcBb@aAvAsAdAg@hApBW\\i@vB^|@p@h@tAh@~AwBJAp@f@z@lBh@N`BzANj@Ax@RXh@TpBdD|@lB|AtA^?h@uAtBgAP[TwA^\\Bb@JHfAJt@d@NCP]l@gCLIp@Jl@m@Pk@l@DXb@M^c@RC\\i@\\OrA}@`BTVE~Bf@XHdAj@|@LxA~@~AIzAWVwACXpAi@fBBLxAx@dA\\^\\Fn@k@nB\\~ACh@MNeBVw@p@W?sAiAqCcAwByA]ZQiAk@s@QA"], "nuts": "Alentejo" }, { "id": "PT-10", "name": "Leiria", "c": "PRT", "r": ["wvkAfgQwAb@mAtAEURyAcBwDCi@Zk@QWs@n@gB}Am@}A}B{AiA?s@WkAK}UsIh@kBHaA_@{AHmCRaAr@gAIe@o@k@Ei@NYlBSPQk@q@cAuBE}@r@i@~@[\\NNV@]UqA}@eAFs@I]QCc@f@YBe@]y@uAP{@}@{@`@s@fB?fBqAT^`ABz@f@^hAh@l@PjBbAn@^II`B|@GDHEf@t@zD}Dv@\\fBdAdCCz@^zA\\ThAEr@s@^G\\Vj@lAxCm@`A~@AbAHFz@QTFLZG`BH`CNz@TXfB~@Z`@Ff@x@j@VFbBQ[zBFb@p@|@`BtAZh@W^yBl@k@l@Ab@n@dB@~A"], "nuts": "Centro" }, { "id": "PT-06", "name": "Coimbra", "c": "PRT", "r": ["}emAjkP{CcA[]XUJa@@oAM?i@|@Q|BQ`@[Tk@@sCuAmKcCaBUnDaFDaAs@Us@k@f@mAp@Lv@GLM_@yBvAe@h@L`Av@p@@LMFsBsBsB?y@w@g@^gBdA}B?Ke@WKuALsBuAwCa@kB}@yBy@o@eAoBGg@l@UTW^Dn@`ARMV_AxAMl@q@t@bAzAn@Tw@b@]|Ap@VIz@aA\\u@j@KVF^x@I~@HHhA@]x@?dAd@fAt@@LfAh@r@G`@TlAZJFnARRLr@d@b@WEUHi@g@gBpAa@Dw@M[RSf@|@z@Qz@x@tAd@\\XCb@g@XNEdA|@dATpAA\\OW]O_AZs@h@D|@bAtBj@p@QPmBROXDh@n@j@Hd@s@fAS`AIlC^zAI`Ai@jB"], "nuts": "Centro" }, { "id": "PT-01", "name": "Aveiro", "c": "PRT", "r": ["ucnAfdPqFkAEIv@?cAeAJg@u@JGST[ESo@g@e@n@UCWwBg@}@^dCMv@gA^qAkAi@Pz@NFNYHf@Z|Dn@xAn@TXiT_Em@?KiBNa@a@uB\\}@?UkAgA~@_ATs@w@BQs@Hg@s@_BYOx@wB^Mx@@t@uCCq@u@s@FSZ@bA~@l@N~Be@d@H@b@Sp@NpAAdBfASxAx@|AnB\\A`Aw@v@AXMd@mAVnAXX|Ac@~@}@|@zClAQrA~@|@Gv@f@?x@rBrBGrBYPe@EaAw@i@MwAd@^xBMLw@Fq@Mg@lAr@j@r@TE`AoD`F"], "nuts": "Norte, Centro" }, { "id": "PT-13", "name": "Porto", "c": "PRT", "r": ["qboA|{OaDVeAA[c@K?KjAuDdBYIcAX}@AcCnAqABaAU@m@f@cBDeAp@_ANq@X[`@t@h@KTYCiCq@eCRgBSoCPw@e@{By@eAZaB^i@\\Cf@eAT_ACU^aAEc@e@y@m@Y^a@`@APMh@sAXH\\Il@_@Pc@nAZ~ALh@vA~@rFE~FJ`Af@dCXNr@~AIf@Pr@v@CUr@_A~@jAfA?T]|@`@tBO`@JhB"], "nuts": "Norte" }, { "id": "ES-C", "name": "La Coruña", "c": "ESP", "r": ["_krAt`P|AjBqAlB`Cx@ObAd@`AV[\\~Av@Tf@|@WZeALc@jA_FqAgDgGmASOf@j@Hj@jA?bEdAf@B|@mBdAg@eAo@pAyBK}@xBj@?Yv@|A`BgAd@oDqAkAx@uB{BVw@mAcDDfEa@R}A_DJkDuAoAF}CSc@kApCsB{Hx@wAd@yD}@gETeAqCsIhAcAqBm@f@_CpCqB{C?q@eAUrDo@nAk@{Fe@Sf@fIeB_@Sq@cAh@QaD_DaHXeAgAj@{@]Q{C_BoCDw@xAcA?h@bAJZdABeBy@R?aBs@MeCkG`@St@v@nCXf@c@dEdCx@YxCdArAxAApBdCL~A~AjAQ`C`ArKmBhDz@dC`Ea@xG`AfFs@lAzBXIbB|AbC[vARvCt@p@MrAjAjD"], "nuts": "Galicia" }, { "id": "ES-LU", "name": "Lugo", "c": "ESP", "r": ["gltA~_Ni@mB~Bq@uAuCfB{I`D}B`@}AXZVYWeJ^}AtC`@`B~B?~AjAPVoArAOlAeBxBg@rAiDfANf@]@_AiAyBdAcAf@?p@hAb@vCrBtAp@k@}@i@zBwE~AQpA~@nBCfClCvAnE`Ce@n@z@|Db@~BpA|@~AhEfBqDbCIxDo@vA`BdFM~DoEnPoAE_AhAmG}BgC|EyB]MfAkB_CuBy@sDv@oAScEfAaCaAkAP_B_BeCM@qBsAyAyCeAy@XeEeCg@b@sBY"], "nuts": "Galicia" }, { "id": "ES-O", "name": "Asturias", "c": "ESP", "r": ["w|sAlwLqC{AQqBN_Ni@mB~@uGO}Ag@JJsHu@wDh@yAHyEc@yA?iFaB?GuAk@WX_B`D}D[Wj@g@?yNf@aAbAl@_AqB@qB`BsFz@uKYcAlB{KZyLd@AfAn@rAc@x@b@i@nB`AtFpCt@DpDcAt@[`BrBtHjClBd@~NbAp@HrCj@b@LbBu@fIrCrCFr@w@bF}BhCEtDhAtAYzCt@bAiAdGPv@pAr@XxBz@eAv@pBHlK~@zBk@`C_BPs@~@KxA{@hA|@\\q@j@sBuAuAaFmA^_@r@r@n@RxBg@\\gAOsAhDyBf@mAdBsANWnAkAQ?_BmBcC"], "nuts": "Asturias" }, { "id": "ES-S", "name": "Cantabria", "c": "ESP", "r": ["uwsAbyGd@_Ae@aBd@kB_@g@IsI_B_J\\_AmAqAg@aFb@sBbAtCh@o@y@_B\\u@cATyAsK`@BjA_G\\@MpAl@~@d@qAe@[pAwMz@wBfAA~@jBOlFpBvEd@ZdDi@eA~LdDjFNnChA`@`BbEpC~@j@mAoAaCD_Ad@]l@~BhALTg@i@kBzB]|AhHMdAkBDjBvALlAaBdEw@aBe@HP~CgEd@eAhFiBhBYhBt@pDN|I}BtAy@rBaDFOaEgCe@aAuF^}Bo@UsAb@mBm@"], "nuts": "Cantabria" }, { "id": "ES-BI", "name": "Bizkaia", "c": "ESP", "r": ["_usA|cEMyBzAcDmBh@qAqD[Lk@cJv@kBpBo@wA{@pAaJrAyCpA`Af@k@pApAH~@lFTb@lGVj@~As@F`Cs@hKaBzBeBi@sB|BvA~@^pCgA~Ag@tEvBhIeDh@e@[qBwENmF_@wAgBQ"], "nuts": "País Vasco" }, { "id": "FR-40", "name": "Landes", "c": "FRA", "r": ["e`tAr}A}TiGcc@cG{BwIr@}CpCUc@qTzE{FbB}F~CUTyGcCgAhA{BtCWdAoOvDtC~EYCpCoBn@nCjK~BmAjEZnElCrA_AbAjKmAr@`BjEo@zMxCbUsCbBlB`FRvFoApC"], "nuts": "Nouvelle-Aquitaine" }, { "id": "FR-33", "name": "Gironde", "c": "FRA", "r": ["gzuAdmAoDJwDeBi@aIyE|FlHnD}t@oFeDmCbCy@hJcP|JcBpGeHlEcAcDF_BpBt@kEiEbI}LdBq@eF~AeApA_GzDqA|BkLO}LxAa@jFxBdAs@bBvAbAuJkBuBn@qD|@rB~BaAF`CtAb@Q|DnAJ|AqBtGnJdGy@h@fEjCcB`BrE}@|CvBd@UxG_DTcB|F{EzFb@pTqCTs@|CzBvI"], "nuts": "Nouvelle-Aquitaine" }, { "id": "FR-17", "name": "Charente-Maritime", "c": "FRA", "r": ["sowAdk@aKlGaHbNcBdIcDa@]cCrDaJuDrGwBt@gA}CcFjAi@{BiFlESrB}B{@{@iCaDi@k@oFrASUmG`JwJpDqVfFyIj@~B~Cu@pB`BL~MtAzACuArFFhF_JnDVjAlBrBs@x@_JrAJj@{E~C@bAlBAhIiBnIwDdAqA~F}At@n@tF", "ovxAdkAxAuA|CdBwHlHyCt@dByHrBy@", "wcyA`oA_EdPxAoNxAkBJt@"], "nuts": "Nouvelle-Aquitaine" }, { "id": "FR-85", "name": "Vendée", "c": "FRA", "r": ["mmyA|dA]rBrA|BkCbGT|CaC~@m@`HkEdIjAJeEv@cMnQqCR{GsGjH}Op@sIm@cBqG|A]aBhEmB}@qCmCMoAyDzDqUfJiKbAX`IcEjKDlAuChCrKe@tKsARdBhH", "qwzAnhCv@mBpAZiFpGP_ElA?"], "nuts": "Pays de la Loire" }, { "id": "FR-44", "name": "Loire-Atlantique", "c": "FRA", "r": ["uzzAl{BqBlAcBdLs@wC_FYK_MtCqKyEtPLrGdCbGoAxDd@xCaAzDMsEwCnFcAaIyArBDuE_BaCp@kEwBiCwEy@gCwWqE}LtAeLhHyDtAkHzAlIhA{AXeIbEsAjCtXzCgDCmBzBcAxCfCfC_FeAnHnAxDlCL|@pCwD~@JnCpG}Al@bBq@rIkH|O"], "nuts": "Pays de la Loire" }, { "id": "FR-56", "name": "Morbihan", "c": "FRA", "r": ["yt{AxxCyAl@OoFMbOqAyAbBnE?hHkB|CLoIoCqBg@l@pAXqAhC|AbGgC~AlEu@{AnC|@zBm@`BpFkA?|AoFPsAvBwDeD[tCdAcAlB`CqAjGJuCg@tCwCuCbBfEd@e@R`EuEtDoBsHaDG}@pMiHbEkB_IrAaPwB}NtAiAOeDtCeHeAcE|DcAeBqDuCq@r@yMxByEfCxDpAeHdF]XqBzBjCx@wB|@~BrEoAzFxDo@`F|AjBJdF", "em{AtaERgBn@|@]`GmClAfBeH"], "nuts": "Bretagne" }, { "id": "FR-29", "name": "Finistère", "c": "FRA", "r": ["{h|Ad|Eu@pReEzExAtCiC|DlBi@ItC~@aAx@~@JtJoBq@aFnDcBbE]dKcAu@oA_YaD`@gAxCUrEbCnCwCScA|CEeBqBw@dB}@WqS[rGqAoBv@pJaEgIbDhRHpI}IE_BuA?aHeA|@@{Cw@bAaByLhAgAOaFqAg@J{E_BsDtCe@g@}B~AoAmBJ_B_Bv@wIzDKjC_CdCx@l@sAtBtBzEuDnDf@dBhIrAl@jFoEd@wL~@g@xBTnA|GpBC"], "nuts": "Bretagne" }, { "id": "FR-22", "name": "Côtes-d'Armor", "c": "FRA", "r": ["_b~AlbF?gCyAPKgBgBjBeBeCdAiF}BoJvCLeDiF`Bu@fC~A_CuBDsB`AbAh@yEbAZ~LqOiF_Lo@X?iEaBkCv@cApA~Ag@}CfCiAgCcInGoCgA}AxBo@`LpCd@bJ`EnCzAvEaBhDLdEtCp@dBpD}DbAdAbEuCdHNdDuAhAvB|NsA`P_EsA{EtDuBuBm@rAeCy@kC~ByCL"], "nuts": "Bretagne" }, { "id": "FR-35", "name": "Ille-et-Vilaine", "c": "FRA", "r": ["sx}AxxBaFxCyBkJnDKc@oN~I{GiCkJfAuJhJQdB~@pOyBpA|FhJdDuAdLpE|L|CbYkDh@g@{By@vB{BkCYpBeF\\qAdHgCyDyBxEsFiFwAaLoBy@sCf@uBuAaBnA"], "nuts": "Bretagne" }, { "id": "FR-50", "name": "Manche", "c": "FRA", "r": ["c_~AjbBAqMoEhKkE`BkDwB}DDGkAHjDsCZqAmAoCpAQ{BJxCqGrCw@hFgCD}CbCqDyAsBrE{AUrCoS{BkK^cHnCeAbCzC|GcGtBJR}BjCF|CcFWaElJaBpCnF?pClBc@vCxE|AkEDgHjD_IdDd@hEtEeA`WrCbI_ApDeHtD"], "nuts": "Normandie" }, { "id": "FR-14", "name": "Calvados", "c": "FRA", "r": ["ck_B|dAeB}AHgG`Ba`@|B_KuHa_@rFUvAmC|@pAhEkDxBJTpAnBoBbBFT`SrFhN{@rIv@dAyA~Dz@rNtAb@~AfGm@vKyBdE{BsEmBb@?qCqCoFmJ`BV`E}CbFkCG"], "nuts": "Normandie" }, { "id": "FR-27", "name": "Eure", "c": "FRA", "r": ["up_BkQuB_LjDcIWyGtBcF^vBz@]tBgHsDiHQwEmDmCByJx@eJ~HaCAtDpInCnA|IlE_B~H|Hz@hDw@vG`FhQqAjD_Ca@oEdHm@lK_Fy@oBnBUqAkBOwEnD}@qAwAlCsFT"], "nuts": "Normandie" }, { "id": "FR-76", "name": "Seine-Maritime", "c": "FRA", "r": ["kt_By]hApHiAvMqAt@oIyEsHuXoE_c@qEoKbJgR|EoC~CrCf@eB~@`BlG_Af@mBtDtDmBxPrExFB~DrDhHuBfH{@\\_@wBmBfENtHkDtI"], "nuts": "Normandie" }, { "id": "FR-80", "name": "Somme", "c": "FRA", "r": ["cx`BytAiHgHj@oHiDdGcE{@hAcDRyP`ADvDcIi@oR|@sBxAlDhB]kAuInBwFeBg@vAgBxA^}@iDfBgAoBuHdEsIvJnGbD{BErMxDxDKxD|AjBeAn@}CrRWd[aChEsFrCcJfR"], "nuts": "Hauts-de-France" }, { "id": "FR-62", "name": "Pas-de-Calais", "c": "FRA", "r": ["ikaBubB_AnA}GmBcG|A_FuA}Cp@uCiHkCyS~K}HdAuIbAlA|Ba@pAkFo@{Tr@}@h@tBfCf@dAkJ~BkDzBpB`CyB`BtAAaEvAgBzI`Du@bEtBbGiBv@|@hDyA_@wAfBdBf@oBvFjAtIiB\\yAmD}@rBh@nRwDbIaAESxPcAtB"], "nuts": "Hauts-de-France" }, { "id": "ES-PM", "name": "Baleares", "c": "ESP", "r": ["kpjAk~AYoAjA]FrB_A`ClAtCkC?uA_BvBmB`@oA", "ejkAkcBzBa@Pz@rDdDlA|DtBVuAnF`@l@u@tAiCA[eDaCNyA_CqAkIv@eD", "oulAupEbAmFrDf@hAfB|@GfCdDrGjChF~J{DjEYvIkDbBqAc@g@TgAzBKt@`AjDtB`BDt@gAn@SWi@t@XzBgBpAgAMiEgLqByBmEkJ_E{UZeApAhF`ABW_FlAf@j@xBtASlAoD?gCcA}B", "k~lA}kGtBcAi@bAbCDJfBoFtO?jH_Bg@cA~A{@e@SkMi@iBjBiAoAy@r@OhBkD|@MH`@NuA^I", "{nkAqyDbBl@C|@cA`@cAeCf@G"], "nuts": "Islas Baleares" }, { "id": "FR-2B", "name": "Haute-Corse", "c": "FRA", "r": ["{wqAsvO_BsDiHaB`@{CwAc@oBiNkCgCPmF~AmBsCeBsDhAsDkBuCXZiFvJe@`InAxCiD`Y_AbKxHxDLHpIyIJE`C{I`F}BvHiBd@yBrQ"], "nuts": "Corse" }, { "id": "FR-2A", "name": "Corse-du-Sud", "c": "FRA", "r": ["gwpAgjQrHKjDlBKlBv@X`@oCbBjDzBKh@vBpA?i@mAlBt@}@|F}@q@}ApAf@pA}DbNcDIoBqFmBvOsCcGk@bAyBkBu@pAf@xHmBh@oD}HgBzAyAtGi@cAeCxAmAwGy@fDsAOXxB_B?bCwRhBe@|BwHzIaFDaCxIKIqI"], "nuts": "Corse" }, { "id": "ES-Z", "name": "Zaragoza", "c": "ESP", "r": ["ihrAfbAI_A{Ae@}AqFfAHv@y@v@xAdJgAfAVx@uBr@MxElDb@KFm@aA}@FkBcCeAwARZuAxCOnAp@tIQz@bAq@hAPx@zAb@z@WnAwCT{FrByA~AcDnEgAdBwEjBiAhBkDYoCfFeDjEaASmBl@cAPmDiAm@e@eAFmBq@k@j@aEfAT`@kA~@WrAp@zAOr@|A`Bf@~@|ClBEK`Hv@~@Id@_DpBaDpMqAvA\\n@}@hCcDlDNjC~DkBj@NwDfD?v@nCER`@zAaA|CfDcBpBhCbBgAdDdBzB_DvGhApC]xCx@|@hAY`@^ShGbBlBvAQh@r@BdHkF`HeEbJZvEiAvDyGt@aBwAkBWG_CbBi@}@iDeJrAO_CuBwEwAw@iDrByB{@kBfA}D?RgDfA_CEaCzAeD@yG}GmEeC~CuDp@oDaAsBiBi@b@gAMqCiCy@V}@g@SwBwAcBU`@w@u@GiC"], "nuts": "Aragón" }, { "id": "ES-LO", "name": "La Rioja", "c": "ESP", "r": ["a_rAjuCL_G|AmD?cF\\k@X\\^[J}CnDcFt@KzB_IpCQBxG|CnChAStA{At@XdAjDiA`IgBBsArA{Ai@N~FaBnAAbFx@bEpANhCpB?dEm@nCmC_As@l@d@dB|Bt@l@rBOlAwBn@IvDwEzDsC_A}Cf@}@gBoCMmAbAkAYWxAsBkBaATJiIc@kCl@ARm@t@NCqAy@c@Aw@t@yAdBGp@iBIiAh@WYyBw@g@|@oARoB"], "nuts": "La Rioja" }, { "id": "ES-VI", "name": "Álava", "c": "ESP", "r": ["kfrAzoDeBj@wEdJW`A\\nC_B\\iCiAt@bDz@h@cB|B_CoB@sBt@q@RoBw@sEwAxB}@iBkArAfAnB_@~CyCm@u@|@cA}@f@kASyByAw@C}@lB_B|BVhAiBf@aFFaHiBf@W{EjBYn@lBv@Zd@wASo@l@gJbBkExBUnDhAj@pAbCu@p@lBk@xBdBfDd@IZkAm@y@Ng@zDHSnB}@nAv@f@XxBi@VRl@{@dCeBFu@xAdA|CQZ{@UJZ"], "nuts": "País Vasco" }, { "id": "ES-AB", "name": "Albacete", "c": "ESP", "r": ["}njAz~@iBdD_A\\[jB^hCdBtDSfBpA~AbCf@lB~AdHi@zBjDTnDa@t@kAPSvBpD|ITdCc@bBjEpIrI|Fm@|F_A`DuEkEmC]aB~AuDTy@dDsCBBhEaA`DqAP_A[{@oCsDeAeBjAcAdCkCXu@hAGnCe@TuFuC_DfAmGqFaBf@k@uFVsD[c@xEqG{Aq@Iw@pB_AkBqFZmFwDrALkCZNvAmAUmEn@iFoA}@eEwNhBqAGoAdCgMdD@xFvC`B@xEsFWqHjBkBvC[pBpAzCeBr@jBF`C"], "nuts": "Castilla-La Mancha" }, { "id": "ES-TE", "name": "Teruel", "c": "ESP", "r": ["gamApfAmAb@w@}CkAPaArBYfD_DbCjBn@AvF}AIAbEiDjFMtByABeClDuDwEwDk@\\cDq@yAmLS{BfCuCXG{He@]wAPoBaC^uF_Dm@VoDmAsBbDeHeBkCfAeDeCmA~AgC}CgD{A`ASa@oCD?w@nDgCIm@eEjBa@Y@aC~C_D|@iC]o@pAwA`DqM~CqBHe@w@_AJaHv@Un@{AvBWjCfAfCi@`BvAx@vBVKbApGy@b@IvD_BzEbAlAbBT~@jCUrAZ|@rACVaDvDFjAs@`AfClCkBvCpExA\\^~G`Df@|A~AdAG~@vGlAh@f@`BzBPpAsAr@lDYn@kCDi@b@m@xCL`H"], "nuts": "Aragón" }, { "id": "ES-CU", "name": "Cuenca", "c": "ESP", "r": ["ucmAtgAlAc@`AzBvCGnF~B`BCl@hAYjClAnBvDtCpBIbBf@n@a@hEzMnA|@o@hFTlEwAlA[OMjCvDsA[lFjBpFqB~@Hv@zAp@yEpGZb@WrDj@tF_D|AtArAFdB_@\\m@u@aDxBuIm@_DvDgFvBoA`CmBw@kB?BzA}Bt@c@Kq@}D_Cb@Ym@XcBkAJ_@k@dBiDoA}AWcBqB]wGL[kAn@}AoB_E~@oFk@Iu@`AkCJt@iBm@oBLcAi@OmAt@k@a@lA_Dm@u@aBKf@wDgAaBnCoHI_CfIsCdB{DtAqAxACLuBhDkF@cEbCNr@mApDuAd@}F[_D"], "nuts": "Castilla-La Mancha" }, { "id": "ES-TO", "name": "Toledo", "c": "ESP", "r": ["q{lAroI_Mw@U{@t@aIcCcHjAc@AiAgEuG_Bs@SsDhCmANmHoAaDkCsCvBq@v@yA_B{B]uB~@sAKwCfAsBpByKt@eAJkDr@uB|Bf@pD`Ht@|D~@_BqCuJo@K}@sEs@q@OcGV{@eAyI|Ds@C{AjB?lBv@nAaCfFwB~CwDtIl@r@|AIvDyApCh@rADxExB`AHnC`AlCx@LvA|CFtFp@tAo@rBbAzBCbAgAtDkBHYhEl@`As@nAqDw@HkAk@e@gA`@y@gAgA?TbDYdA|CbAf@`B}@pJl@`B}BfA@r@zD~CFtC~@vB_@XwAo@o@VkBxElAfAxFxAgKvNwFmBeAn@{AD?pApAdBK~AeAJiCq@q@`AJ~B"], "nuts": "Castilla-La Mancha" }, { "id": "ES-LE", "name": "León", "c": "ESP", "r": ["mmsAbqHbBcC`DGx@sB|BuAr@zB`GxCJbAtCFnAv@dAeB~H`ANs@vHl@LzBfALOiAbBVAdDx@FkAjCjArBAvBdBdAZvAi@fBRf@zIIRzAcCdEAh@dATi@nCu@?y@lBf@ELbCo@V\\bFy@dAp@fB_ApDNrIsB`En@dJm@dCSfHgAxCyAsAuAIiClEy@s@{ANw@dEb@|BOnDcFu@o@{@qBn@aBoCEiAsBcCcCEqA_Aj@aC_A{BImKw@qB{@dAYyBqAs@Qw@hAeGu@cAX{CiAuADuD|BiCt@cGyCgDt@gIMcBk@c@IsCcAq@e@_OkCmBwBiI"], "nuts": "Castilla y León" }, { "id": "ES-SO", "name": "Soria", "c": "ESP", "r": ["e}pAbsB`BKjBgAxBz@hDsBvAv@tBvEN~BdJsA|@hD{AZWlBdFnCxGu@hAwDpCVqAnCt@pAl@zEYvC^rB]jAqC|BD|Bk@Kg@z@{@c@s@rEq@z@HfFiBhBz@|BRpDg@jHmD`HiCEm@rCyAj@_@lDiAb@y@[b@gCkEeCCeAwAG{@sCoDJS[jAyCbAo@sD_EGsBmAc@Iq@mDsADyBm@sB_DeB`@aBzC|@l@oC?eEiCqBqAOy@cE@cF`BoAO_GzAh@rAsA|@Pp@i@dA}FiA{E"], "nuts": "Castilla y León" }, { "id": "ES-BU", "name": "Burgos", "c": "ESP", "r": ["ghrAhpDb@jCKhI`AUdBhBXsAvATlAcAnCLhAhBpCi@rC~@vE{DHwDvBo@Hj@lDrAHp@lAb@FrBrD~DcAn@kAxCRZnDKz@rCvAFBdAjEdCc@fCx@ZX|@JfExAjBnBBCpAsA^BbBeGbKkC@oAp@aBc@qAfBmAA_@uDwAk@i@uCaAIQd@dAzEe@FkBoBa@HNjEk@n@cC^MhD{A[aA|AwIdAIjB_BFg@y@FsBaDd@aApAMi@y@TWg@uBTy@c@Xk@wBeEXuAo@a@MmAkBwAjBELeA}AiH{B\\h@jBUf@iAMm@_Ce@\\E~@nA`C[dAeD{@}A_EiAa@OoCeDkFhAgKyBoJd@gF^SbA|@t@}@xCl@^_DgAoBjAsA|@hBvAyBv@rESnBu@p@ArB~BnBbB}B{@i@u@cDhChA~A]]oCVaA`GcK", "yqrA`kDjAcKlBrAx@eA[oAnAUKlF}B|Ku@x@sAiAS_D"], "nuts": "Castilla y León" }, { "id": "ES-AV", "name": "Ávila", "c": "ESP", "r": ["iomA|`Hg@xAuB^RhE~Ar@|DxFJdBkAx@vBxEJbBu@pGaBbAsDMVhCrAzBFjBaEvJaCiBcCXaBaE~AsALy@iAIW_B_D{@?tCeAH_@oEuCcBmFmJuCc@}AeBmA^}@{@uANk@rAaAHaBu@y@{F|B{GkA}Be@wD~BV`HkHjCc@xAZLqCpCsAjFq@y@cI}@b@K]VgElCl@XrBe@~AjAKnAdAdGJTzDbDbBc@|BxEr@~@`D"], "nuts": "Castilla y León" }, { "id": "PT-18", "name": "Viseu", "c": "PRT", "r": ["sloAxyMI}AaAiGbBqBNcAAq@zDbAb@Dt@GRnAb@Od@_Ab@A`@Nj@~@KjAHVzASdB`A?^}AxBIdA\\n@t@TdAr@LCl@aAXOXBRT\\STk@b@a@n@HXXlBn@h@Gf@xEpAlD`@lCdAnBx@n@|@xB`@jBtAvCMrBJtAd@V?JeA|B_@fB}@FsA_AmAP}@{C_A|@}Ab@YYWoAe@lAYLw@@aAv@]@}AoByAy@gAR@eBOqARq@Ac@e@I_Cd@m@OqAcASFALt@r@Bp@u@tCy@A_@Ly@vBs@gED_G_AsF{AaECg@x@aBFgAKgAi@uAB{B"], "nuts": "Centro" }, { "id": "FR-32", "name": "Gers", "c": "FRA", "r": ["i~sAoEu@|CqC|@bAnEe@jGeAn@oEmCkE[_ClAoCkKnBo@J_C_Cs@FeC_BmBf@wDwC_QdAeCWeJrAA|B|Cp@cFfGm@@qBvJ{M|CpG`IlBmBdLhElHuBrZqGvD"], "nuts": "Occitanie" }, { "id": "FR-87", "name": "Haute-Vienne", "c": "FRA", "r": ["_gxAkuBnGnSo@rFrGxJiAvFyAw@eDzGPlMuDdBa@dEmDuCKuCmFo@wAcF{DdFqCXM_AkD`AsB_KwCmCiAiPxBqE|FhBzBiE|BIrDiD|BzB\\yDlC_@UeG|B_F`Es@"], "nuts": "Nouvelle-Aquitaine" }, { "id": "FR-19", "name": "Corrèze", "c": "FRA", "r": ["gexAosBwDaJhDoNyBqKjAeA`FvBrEkBbDz@SpGdCFfFpH`CWvEfErBq@rBzU{DvHZlHiFzBk@hFqAOc@`BsAwAcAnAmDgD[jBoDOcB{FoBiAn@sFkF}LRuC"], "nuts": "Nouvelle-Aquitaine" }, { "id": "FR-82", "name": "Tarn-et-Garonne", "c": "FRA", "r": ["uguAqzBrClKg@lF`CoAhAb@nB`GpBz@dBzLz@sB|A~EsA`Dv@vOmFVkAxF}DoDRfDiAj@{CcCIkD}@j@wDuCoAvBcCaA[mKxCSbAwH~AEZwC_C{E`BwDwBMp@kCkC}M|AX`@kE~B|BpAiC"], "nuts": "Occitanie" }, { "id": "FR-81", "name": "Tarn", "c": "FRA", "r": ["cguA_zBaAkI|DmNbC}DvK{ExCkD^oMtA{@vCzH]lGfCf@~DqAjAnBUfUrB`A]rHoAjAuBe@^zDiHjOsAkAeL`JuCEoCcHkDlAf@mFaC{J"], "nuts": "Occitanie" }, { "id": "FR-38", "name": "Isère", "c": "FRA", "r": ["kowAkyHs@nA~AdJy@v@mFl@sE{EuAfCy@qM{CmF{BdD_C}@nAqG{DcGdJiKjO{JxAuHcDGWeBnDuKjCi@hCtBdEq@d@iEzFdAb@mEdGoAdAlTfC~BhBbHWxH}BpDYrEqPs@bA|DcAjLyHF_D|G"], "nuts": "Auvergne-Rhône-Alpes" }, { "id": "FR-26", "name": "Drôme", "c": "FRA", "r": ["_qwA{vHvByGlAPWkA~Ia@bAkLcA}DjQRrDaUrAfAZlGhDbBvBuALdJzBs@BjCxCiCb@cGlCqBvEX{@dCnBhGaDfEw@bKsCRlC|SeDpCMhEkN}BiDgCqFb@uIsFaIjCqJV_BeJ"], "nuts": "Auvergne-Rhône-Alpes" }, { "id": "FR-12", "name": "Aveyron", "c": "FRA", "r": ["iavAydCc@}BkBs@]cNmIsFgEyGnCqACkBlDaEfEMxGkHvEoBjI`@lCkFPaGjEfDpCcIxJ|MDnHxFl@EfEyBhFd@zE{DpFmH~BmFxGuDbMrAhIqAnCkDiBa@jEiCaA{FfCeEiMJ{C"], "nuts": "Occitanie" }, { "id": "FR-46", "name": "Lot", "c": "FRA", "r": ["{cvAyhCjGdVrGgC~CdOq@jCvBLaBvDzBjGc@tBsAGk@rG_Db@H~BsHdCaK{Q}B[{DuFiFLyAyD~E}NsAqP|JcEhDp@xCqC"], "nuts": "Occitanie" }, { "id": "FR-37", "name": "Indre-et-Loire", "c": "FRA", "r": ["cd{A}qAzCy@tDlFa@dDhAbE`KbBxB`CgAzEuJ|HkAfE`BA^jNoEf@YtE{ANgBxFa[}Ij@}GcBWV}AmDqKdA{KlCk@y@qDv@wCzHcDbG\\dAkGvDoD"], "nuts": "Centre-Val de Loire" }, { "id": "FR-36", "name": "Indre", "c": "FRA", "r": ["_}zAupAsBmBoBdAoAkKuB}CGoFjCeF`EvAPgN`CE~AeBrBZlAiB~BjB~BgA~A|ArDgFnDn@lC_ApBfB@fR_AvBjBbA`@vEaAlE|B~EyAhCPnIqAc@sDrBg@zEyC|EmGdAIeEeO{DEeImBkC"], "nuts": "Centre-Val de Loire" }, { "id": "FR-41", "name": "Loir-et-Cher", "c": "FRA", "r": ["ef{A}qBkCdFFnFtB|CnAjKwDnDeAjGcG]{HbDw@vCx@pDwCbAYhMcAEaCgGmFeAmAqBwCMqAzAgC_LbImKb@_HgAuKxB\\vBsAnAxAx@gAv@j@dA{HxDeDuBoChAuUrA]zB|Eb@mCjEwBv@ZIjFbGWDhKxBhADbC"], "nuts": "Centre-Val de Loire" }, { "id": "FR-23", "name": "Creuse", "c": "FRA", "r": ["_gxA_wB[`BeDD}B~ETdGmC^]xD}B{BsDhD}BH{BhEoEeBkAn@}B_F`AmEa@wEkBcA~@wB?mY`EkD`E}I|N_DhHhKjDwDzBxJkDfO~BpF"], "nuts": "Nouvelle-Aquitaine" }, { "id": "FR-53", "name": "Mayenne", "c": "FRA", "r": ["oj|AzVjAjAa@bDvAxFuCne@mHuCqA}FqOxBeB_AiJPEoLxByEaC}OVaHeCqErFuIrBQv@|DvFS`CzDtDC`AvEfDaBx@bExBCt@tBlA{B"], "nuts": "Pays de la Loire" }, { "id": "FR-72", "name": "Sarthe", "c": "FRA", "r": ["ch|AfYkAkAmAzBu@uByBBy@cEgD`BaAwEuDBaC{DyE\\_Ay@SqJaCwDu@yHl@{BhGwApIa^fDdFpA{AdCD~AxBlFdA`CfGfBH|A|LtA?eAlKv@dAiCnNb@nC{@jAcBWuA`M"], "nuts": "Pays de la Loire" }, { "id": "FR-84", "name": "Vaucluse", "c": "FRA", "r": ["gltAsfJ|B|L_DbToJfY_DyCwCvF{MfCLiEdDqCmC}SrCS~@sK~C}FtBDXqAvDfAjBaDjDvAa@_ClEaH", "ywuAguHxB}CfBdB?nEaFwC"], "nuts": "Provence-Alpes-Côte-d'Azur" }, { "id": "FR-52", "name": "Haute-Marne", "c": "FRA", "r": ["ib~AeoH?yF|D}CbEcP`D{EnD`@g@kCvGyKdFlB`J_NjFbKdFVVdOxCdCPbDqDpEx@jCoBtC^fBiDbBw@qBqAh@iCpCTzAwAW}AnB}@rEaDWOiFmDcA_HjAmFtJmCaAKeFqBPc@{C}@`DaB{D"], "nuts": "Grand Est" }, { "id": "FR-51", "name": "Marne", "c": "FRA", "r": ["ib~A_wH\\zJbAx@|@aDb@zCpBQPdOcDjKwDTNzMpIlMuAfGv@~CsCjCu@tEcDNgAnBiB[GmBmK}Kq@jDaEoA_AsFoAnCyDp@wA}KcAi@d@eIyA[V{G`FqLCeI`BwBAkTlCn@|H}ClCp@hA~CxDj@lBwCpBQ"], "nuts": "Grand Est" }, { "id": "FR-24", "name": "Dordogne", "c": "FRA", "r": ["yrvAXuK}CoBdA?`CsBk@oAsHuCuEaG_AeCqHaHeDwCmF`@eEtDeBQmMdD{GxAv@tAwHbBZZkBnBpCjATt@oA~AvAVaB~AA\\wEhF{B|@bAvEOlDlF|BZhBxFbEbE}BpEfAdGoDx@UfLnBlJaH|GgARoA{A]xCjBtBcAtJ"], "nuts": "Nouvelle-Aquitaine" }, { "id": "FR-69", "name": "Rhône", "c": "FRA", "r": ["wdyA{jHlL`BdD_I|BO]qJ~B|@|AkDlE|Gd@fLtAgCrEzE}ArEsDZG|GiC`F}DYy@hBaCcBwAvBmBJw@hCsAaBkAlBcDmDe@wDsC~AgC{@|@cJ{@qClEmB`@{C"], "nuts": "Auvergne-Rhône-Alpes" }, { "id": "FR-88", "name": "Vosges", "c": "FRA", "r": ["eq}AmmLoEsKl@wBrHrAtAkErT`ObFv@n@lBqFfNnAlDiBhIh@`GyC`HfC~FkAPzAjCq@nDaC^qCbGeFmBwGxKf@jCaB^mAaAeDeWj@wBbCv@pBmEGwG}A{@F{EcAu@vAmFuCuKpCqKm@_D"], "nuts": "Grand Est" }, { "id": "FR-07", "name": "Ardèche", "c": "FRA", "r": ["_nwAukHpJW`IkCtIrFpFc@hDfCdQ|BmBpG|AlEaB~@HvAfBtDuApK}C?}JrGwHnAcF}HSuFgDyB]cD}AIa@cC}DCLiC{Eo@KmGmCW{A{EMcBjCqA"], "nuts": "Auvergne-Rhône-Alpes" }, { "id": "FR-42", "name": "Loire", "c": "FRA", "r": ["gwwAohHzCShB~HlCV_A|MmFnBrAxXeHyCqQ~OaEeAaCbBwAoGgM`B}AmF|BWhA{DDqQgB}D`@eApBYd@vDbDlDjAmBrA`Bv@iClBKvAwB`CbBx@iB|DXhCaFF}GrD[|AsE"], "nuts": "Auvergne-Rhône-Alpes" }, { "id": "FR-63", "name": "Puy-de-Dôme", "c": "FRA", "r": ["mjyAorD`IaHrBuRw@sEhCe@C}F~A_E`CcBlE`AdQ{OtG`Du@`DfAxABpGgCjFKdJhGtSgD|D]hK}AdAgBjIcEhAaFwBeGvFqAiEiEyDiIv@RgDaEcDj@eD{BoB"], "nuts": "Auvergne-Rhône-Alpes" }, { "id": "FR-03", "name": "Allier", "c": "FRA", "r": ["k`yAq{DaI`HzBnBk@dD`EbDSfDmGxDgBjGaEjDaDkDeBiPoEnA{CaHd@uBwCqNfEgIg@kLxB{BqDuHvFeFbCAjD{MpGi@`EpMfN{@v@hF_B~DB|FiCd@v@rEsBtR"], "nuts": "Auvergne-Rhône-Alpes" }, { "id": "FR-45", "name": "Loiret", "c": "FRA", "r": ["mf|A}bBcAdBw@k@y@fA{CyAk@rAoA}@g@~AuAAqB{SgEgFuDa@{BcL`AsBQ}GvEeFdD|A{@s]j@cCdG}DzDtFdFDtAxHhJkGhCjHs@jDnAjBoD`F_BlSoBdCXrKgAxEtBnCyDdD{@xCx@z@"], "nuts": "Centre-Val de Loire" }, { "id": "FR-49", "name": "Maine-et-Loire", "c": "FRA", "r": ["w{{AbaAo@cBiBbIsBPeAhCwCItCoe@wAyFvBeRbBVz@kAfAuX`[|IElCfEbFwA|Br@`TbB|@hAdHe@tVkEtHyCgC{Aj@wDlHkCuXcErAYdIiAzAy@YLoE"], "nuts": "Pays de la Loire" }, { "id": "FR-10", "name": "Aube", "c": "FRA", "r": ["mc~AgeGNqFvDUbDkKE_HlC`AlFuJfBm@fE]|CbAAjErDt@TfFzApApApO_BtB`A\\`@zIW`FgBb@ObCi@u@{GzFo@lHkDc@aHxKaFUsD_IrCkCw@_DtAgGgGcIiBsJ"], "nuts": "Grand Est" }, { "id": "FR-75", "name": "Paris", "c": "FRA", "r": ["ck~AujCeC_ArA{KtAz@c@~K"], "nuts": "Île-de-France" }, { "id": "FR-92", "name": "Hauts-de-Seine", "c": "FRA", "r": ["io~AulC~AnAfAqElDx@_FjHmC}@yAmGpBfB"], "nuts": "Île-de-France" }, { "id": "FR-93", "name": "Seine-Saint-Denis", "c": "FRA", "r": ["io~AulCmC}C`@}DgBuFnKw@sDnKGxF"], "nuts": "Île-de-France" }, { "id": "FR-95", "name": "Val-d'Oise", "c": "FRA", "r": ["{r~A}oCnCbKmE_BKfEfB`BeCzAV`EkCnAh@nGgAhDgH{CrAmAh@iHwAsJ`BkIa@aD|DoOtCz@|A|CHtH"], "nuts": "Île-de-France" }, { "id": "FR-78", "name": "Yvelines", "c": "FRA", "r": ["uz~AgdBfAiDi@oGjCoAWaEdC{AgBaBRoEdEfBzEkEf@lEhCzCvE`@z@~CpEz@aAjGuCt@cHjJeB{@o@jAoCC}J|F}AaJ"], "nuts": "Île-de-France" }, { "id": "FR-16", "name": "Charente", "c": "FRA", "r": ["_lxAvKoBwC}Dl@wI_NxAaU_D{AdB_FkBwEFoD|Ca@~C}EfBbFxFx@?jCdIbK`HdDdCpH`G~@zCfFl@hGcBfAK|CsAKy@~IsBr@kAmBoDWiF~IsFGBtAkAm@s@gIv@gC"], "nuts": "Nouvelle-Aquitaine" }, { "id": "FR-18", "name": "Cher", "c": "FRA", "r": ["__{A{tBu@~EoDaCEcCyBiAEiKcGVHkFmCAsE`FgAsG`@uItA{G|C}DoAkBRiHtCcBlEpBxCkEjLuD~II|CtAvCpNe@tBrCxG|E_A~A`P`DjDAdFiCoBuBfAsCw@}C`Bq@lC_B}A_CfA_CkBmAhBgI~@B`I"], "nuts": "Centre-Val de Loire" }, { "id": "FR-28", "name": "Eure-et-Loir", "c": "FRA", "r": ["_u|AwjAaI`KdArJiB_DmAdFm@y@eF~AyAqG_C_CoMfIaFiQv@wGq@uCiIqI|JaFnBt@xGeJtCu@`AkGjF_DxFl@dFpFzAzRrB`@ZfR"], "nuts": "Centre-Val de Loire" }, { "id": "FR-43", "name": "Haute-Loire", "c": "FRA", "r": ["imwAoaEiCNgC{LJeJfCkFCqGgAyAnAyM}AiOdFeBvBwFbErAYbC|DB`@bC|AH\\bDfDxBRtFbF|HeDpLoAVfBfIqLlJqC_Ao@hBgG~Aa@dF"], "nuts": "Auvergne-Rhône-Alpes" }, { "id": "FR-15", "name": "Cantal", "c": "FRA", "r": ["sqwA_aEhCO`@eFfG_Bn@iBpC~@hDsCbDrKa@xBhN|F}AjBmDAmD`EBjBoC`BfEhGlIrFAvI|A|DyCpCiDq@}JbEc@qCsBp@wEgEaCVgFqHeCG\\cGoDmBvDkI\\iKfD}DaCyE"], "nuts": "Auvergne-Rhône-Alpes" }, { "id": "FR-47", "name": "Lot-et-Garonne", "c": "FRA", "r": ["ofuA`GuCVaBsEkCbBi@gEeGx@uGoJuBzBqAeAj@mCuAc@GaChFoFoBmJTgLnDy@gAeG|BqErA|CtHeCTfIjBZnAwBvDtC|@k@HjDpE~F}@lEnEv]sBp@wDuCeAnO"], "nuts": "Nouvelle-Aquitaine" }, { "id": "FR-48", "name": "Lozère", "c": "FRA", "r": ["syuAsxFfCdE|GkCfFpDiBxKdClBFbEkHtWkIa@mL~HiN}F`@yBiDeLlGgEgBgInAWdDqLhQsF"], "nuts": "Occitanie" }, { "id": "FR-58", "name": "Nièvre", "c": "FRA", "r": ["um{As_GpDe@HcCxAaAxAZpApHnDKp@zBnGwDx@jBbBOfDzMcBjCPzGvDbFwBtCn@vKiDxIcEsA_JHkLtDyCjE}EqBoDvCuAeNjB{AvAqKY{GcCG|D}DhBaGr@aEyAiBpBEe@cD`DcBu@qE"], "nuts": "Bourgogne-Franche-Comté" }, { "id": "FR-21", "name": "Côte-d'Or", "c": "FRA", "r": ["yg{AwbGI|@iIvBuNsJgCOqAcDcCv@EbB_Dq@qA{NcBmBMkErCyH~ALU{A`EuDpAjBhDcB_@gBnBuCy@kCpDqE}@mIpCyApDpDvDsDvCq@jDv@zLdN?hLvCpUeFdGyAbKsDzG_CQs@|B"], "nuts": "Bourgogne-Franche-Comté" }, { "id": "FR-60", "name": "Oise", "c": "FRA", "r": ["sa`B}aEjLGlB{Ab@hCfCx@z@tErBoBlAlB`AWf@oHvCpCRp\\}DnO`@`DaBjIvArJi@hHkBvAOsDyIbCuCgBUnBmG~@oAkBq@bBoBkC`CiEVe[|CsRdAo@}AkBJyDyDyDDsM"], "nuts": "Hauts-de-France" }, { "id": "FR-61", "name": "Orne", "c": "FRA", "r": ["kv}A|t@iEuEeDe@cCnE_BgGuAc@{@sNxA_Ew@eAz@sIsFiNl@cB{AaGN}E|Cs@JuIjEkHjCVpAkDnMgI~B~BjAfGrFuAv@nBoCfFYvGsBbFyFx@m@zBt@xH`CvDAbFsBPsFtIdCpEW`H`C|OyBxE"], "nuts": "Normandie" }, { "id": "FR-70", "name": "Haute-Saône", "c": "FRA", "r": ["wh{A_~IqAvEkCZkDlDsCkDsC`@EhE}B{A]}OeFWeJuNlA_@gC_GxCaHi@aGfBaHmAuEfFeLhExCdHgB`A|@HnJ~ArAa@pLzCvCrCrJ|Dt["], "nuts": "Bourgogne-Franche-Comté" }, { "id": "FR-71", "name": "Saône-et-Loire", "c": "FRA", "r": ["{ezAamFgD{McBNy@kBoGvDq@{ByD@gAgHrD{GxAcKdFeGcDsa@dGeMzAvEjIsC`E|B|BwBx@zEoBvHLjLvS|Ga@zC{EbDhAzA}@bJfCz@dBfDeAvWeCb@iBeFsGn@cDvMcC@wFdFYcFbBkC"], "nuts": "Bourgogne-Franche-Comté" }, { "id": "FR-79", "name": "Deux-Sèvres", "c": "FRA", "r": ["ubyA~c@sE|HoBJyBmK}AnCyKAcKlDyK`Mp@iNiAeHcB}@s@aT|@oCvLqGjA|AvCaAlEpAfA}AjDjBdEe@pEaDo@qEnG~BvAwDlBB^`IzEtG}DxHsCvS"], "nuts": "Nouvelle-Aquitaine" }, { "id": "FR-86", "name": "Vienne", "c": "FRA", "r": ["ibyAwp@GnDjBvEeB~EjAvAhAYErI}FbJoFeCgAr@t@pE{DvBeEd@kDkBgA|AmEqAwC`AkA}AkM~FyC_EDmCfByFzAOXuEnEg@_@kNaB@jAgEvMkMvFk@nDiLrDsBpAb@`IzVjDaAL~@"], "nuts": "Nouvelle-Aquitaine" }, { "id": "FR-89", "name": "Yonne", "c": "FRA", "r": ["ew{AmjEcAzEgBfAPvGyEjByAbDiAc@aAyGeFE{DuFeG|Do@`EsEkEgE[Q_RqAaB`HyKjDb@n@mHzG{Fh@t@NcCfBc@I}PaA]~AkC~Cp@AyAhB{@rB|CzCZlM`JjDkAr@nD_DdCd@bDqBDxAzB}CpL}D|DbCFDpM"], "nuts": "Bourgogne-Franche-Comté" }, { "id": "FR-91", "name": "Essonne", "c": "FRA", "r": ["{y}Ac|BaGwAqDeIxAaD@sLpBgCtAfB`Fv@~D{@tElGNlGaArBlBbMsAu@mG|CoDy@QiB"], "nuts": "Île-de-France" }, { "id": "FR-77", "name": "Seien-et-Marne", "c": "FRA", "r": ["sj}AmtCuEmG_Ez@mMmEsJLwClAuC{@O{a@pDeArH{QhAhCtBXz@mBbDOx@}CnDfG`FTpA`BP~QfEZrEjE~@t[eD}AuEtF"], "nuts": "Île-de-France" }, { "id": "FR-94", "name": "Val-de-Marne", "c": "FRA", "r": ["ul~AqyCfBmFdFf@qBtNgCU@}EuA{@"], "nuts": "Île-de-France" }, { "id": "ES-P", "name": "Palencia", "c": "ESP", "r": ["uorAj~Fn@`@SnBvAtBXt@Yj@d@^hCQVf@x@ULh@`AqA`De@AnCbB\\n@[GwAvIeA`A}AzAZLiDbC_@j@o@?yE|BrBd@GeA{EPe@`AHh@tCvAj@^tDlA@pAgBj@DKrBaAn@DhF~@nCQnDb@tAa@dBuBCl@~CaDnD|C`GcF~C`@tBe@j@h@hAq@b@_DyBsCk@sBHGfEwCOuBa@M}AcBWNhAgAMM{BqGm@e@?Or@_IaAeAdBoAw@uCGKcAaGyCs@{B_AiQ|ByCdAiFfEe@Q_Dd@Iv@`B`BeE"], "nuts": "Castilla y León" }, { "id": "ES-CR", "name": "Ciudad Real", "c": "ESP", "r": ["kxkAjjD`Bg@lGpF~CgAtFtCd@UFoCt@iAjCYbAeCjCiAlCbAz@nC~@ZpAQnCtFYnCvAbBiBvBz@vCy@rJxCjGOzBiAdA~AhBq@tIxAfFi@rU\\d@hA?@t@eBzHoCdDo@dCeDjFeApFcCn@EpCwAtDk@oB}FyB]sC_BKo@`DcD`AXyC]sAsB~@uBg@cAoAp@iHsBrBiDpAu@{AoB{@cBVGuC{D_DAs@|BgAm@aB|@qJg@aB}CcAXeAUcDfA?x@fAfAa@j@d@IjApDv@r@oAm@aAXiEjBIfAuDBcAcA{Bn@sBq@uAGuFwA}Cy@MaAmCIoCyBaAEyEi@sAxAqCHwDs@}A`DyBl@t@^]GeBuAsA~C}A", "gglA|nHhAoDpAaApCp@jA`Fq@~ByFyAmAgA"], "nuts": "Castilla-La Mancha" }, { "id": "ES-CO", "name": "Córdoba", "c": "ESP", "r": ["s`hA`yFCtClB|CAzBrDzA|@OrA`Cy@fB{BV?xBdCzDUpBaAb@AlAeElAMd@`AfBy@tBqGjDq@fAcDWkEjCGbBrAxCGzBzAjDVlE{BbAo@o@?}CuCAe@|@cBd@q@xAsC`@oApB{B`@qCjDe@AaA_BmB_@_BJaCvAqDBuDiHgCsBCmB_BeB_AuC_BU[iGvAuDDqCbCo@dAqFdDkFn@eCnCeDzBoLbBy@jBIjBsAvA?Pp@vFtDnAm@~Gl@xAiBtBUd@_BlCpAnDmEdBm@|@aBjBiA"], "nuts": "Andalucía" }, { "id": "ES-GU", "name": "Guadalajara", "c": "ESP", "r": ["ugnA|zBqCdIfA`Bg@vD`BJl@t@mA~C|@^`Bo@b@~D}@nAL`@dCSt@aAj@H_AnFnB~Do@|AZjAvGM|Bl@JrAnA|AeBhD^j@jAKEtB_F|@h@bDcH}AaBpBiCPy@vAJvAaA?y@`A_BOGhAgAbATxAg@p@w@e@kAJeAfBgDeBgGiAaCr@c@~AeCzBgBmGcBJEoIcAcBf@eFKkEeAoCL{@|AgAIgFp@{@r@sEz@b@f@{@j@JE}BpC}B\\kA_@sBXwCm@{Eu@qApAoCqCW[wEdEcJjFaHtCYzBgChD^zBg@hD`AMvEvDj@tDvEu@~AgIrCJhB"], "nuts": "Castilla-La Mancha" }, { "id": "ES-J", "name": "Jaén", "c": "ESP", "r": ["akiAd~Cd@lBnBGxApCWx@xBjDrGnEvEV`ArC~@LWfC`@nAuAfGxBvDZfDaBvEfDnF|BhI~C`BNzEo@bBkBhA}@`BeBl@oDlEmCqAe@~AuBTyAhB_Hm@oAl@wFuDQq@wA?kBrAkBHaBr@YbAiA?]e@h@sUyAgFp@uI_BiBhAeAN{ByCkGx@sJ{@wChBwBmAcANoDoCuF`AaDSwCRw@xCGn@{CtDUrA}AzCZtEjE"], "nuts": "Andalucía" }, { "id": "ES-M", "name": "Madrid", "c": "ESP", "r": ["{lmA`_EVX~Am@p@|@LjCk@l@tAtHWz@NbGtHfRaA~Bu@}DqDaHwAo@s@\\q@jGu@dAqBxKgArBJvC_ArA\\tB~AzBw@xAwBp@jCrCfAlCQxByCoAyAJZiCcDcBU{DeGKy@{@kBEn@wAg@gC_CYcDmCg@sEmFgAeB{A_AsEgHwIm@{CdC{Bb@_B`Cs@fGhAfDdBdAgBjAKv@d@f@q@UyAfAcAFiA~ANx@aA`A?KwAx@wAhCQ`BqBbH|Ai@cD~E}@"], "nuts": "Madrid" }, { "id": "ES-SG", "name": "Segovia", "c": "ESP", "r": ["}mnA`cGQrGjAl@p@bEkFp@qCrAMpCyA[kCb@aHjH_CWwFuFe@v@m@Sb@mA_@o@t@}BkFvA_AuESwH{ByMiCcAfAwD|AiBCcBrA_@BqAoBCyAkBe@eGhAc@^mDxAk@l@sChCDlDaHbAbBDnIbBKfBxEl@nElDlFlBvAjAdFdBzAlFfAX~DpD`D"], "nuts": "Castilla y León" }, { "id": "ES-VA", "name": "Valladolid", "c": "ESP", "r": ["afqA`xIbCeE~B^a@|Ak@YuD`B", "}epAxwFhCbAzBxMRvH~@tEjFwAu@|B^n@c@lAl@Rd@w@vFtFd@vDjA|B}BzGx@zFaC~Fd@nC_@\\uB{AuDbAeCMmBb@s@e@gAuDeAxBcAUa@dAoBXuD~BgB}EsBv@gDGo@m@{B|D{IHSg@h@gB[wAeBeA@wBkAsBjAkCy@GNgAlGp@FgErBIrCj@~CxBp@c@i@iAd@k@a@uBbF_D}CaG`DoDm@_DtBB`@eBc@uAPoD_AoCEiF`Ao@JsBt@\\nAq@jCA~AaB"], "nuts": "Castilla y León" }];

  // src/geo-countries.ts
  var COUNTRIES = [{ "id": "832", "name": "Jersey", "focus": false, "r": ["_d_Bb}BbBMXtAMlJuDc@dAqK"] }, { "id": "826", "name": "United Kingdom", "focus": false, "r": ["kycBxeDdDjRhHpRo@zOaJnSj@pTwD_H}CnQDfL|EzQ_D~LwHtCa@xBiFwIqKck@aGsMqLqIaChE_EoAgFvC_E]zEfc@iDuAsFsMgGqG{Hq[kA{VMoEpDeMoGfC}@iEpFeHIqIoAhIeIlHqCMeHiGoAvEgGMoB{FqLaAdBtQiTdXaEj@_L{FkGkK}AkMLb_@lIlXB`JgCjFnDlOoD|QvHxDoI|L}FfAGeF__@sVaE|AiEjI}Ic@mB}AQaNaFdOwEuAdGzFpAhIhEpGiJMkI}LhL`WxAfAxKaAvVrI|BrDiArFgOkDeJaJSdFaNSiKwCu^sTbM`\\y@fLaGpEw@bI{B_OqCgHcCtFaDgQ?dO?s{F?pRj]zc@lHjf@eAqY~CsMfFfFPfLhIzVcCvYzCgJ~Bcb@uC_L?{MvFk[xSy]|`@kMdS}JnKcb@`Wsc@`ErFzXgSaGhWVhW`A_V~LiYfG_H|IeD~NjR`EsMa@oEyGaJLa^bCgStGiPvCqB~KaAzVtJdGhN[dDzFuArAjDIrMzCxKnAeHtAy@tCfArEf\\e@oEdE}Hr@yKG{_@lJb@hG`UrFlDMtJrIpb@gBjXbBnc@gGjf@xCeDpClJj@d_@`EgCp@nCeApRjAdDsEpTS~LdDdXlRfJ`D`EX~EiIdXjEh`@bGnPrFvE`@vEeD`LjBtJ_DfAcCkDaBkM_Q}ZeNiRoK{BcBcMaIwEsAsTn@ck@k`@ak@jFxM", "c_bBnaAfEtJwCpRwEwNfDoN"] }, { "id": "788", "name": "Tunisia", "focus": false, "r": ["}x_A_nU`XbBtG?jF}C|Ex@zShi@lHtL~JjGhBjKvLbIt_@_HzHtAtW~RzHlVcrBt\\o\\pk@}VrFaG`EgLzVgb@jMoN[{IsMwHsDsHwPuIuF{TaCkFcDoKtCwN?eHnCkb@oEmH~GaFcIaGwCoC{HqEp@wBiNiK_SaHea@|@gH`EjBxC}A}AaCoCb@|A_SzILnI_HfDnAbBmFiH}HaKc]nKoCbGzHrNrIrI`PfH|A~P_FxN{XtQmA|DwC`b@xY|Wvb@tG|CfQmFpFeHbCgHw@eO~IUe@_J{DsB~BaG`KaCxBwEvBpBbC{Q", "c{bAy_UlCtHqGkGbCi@"] }, { "id": "756", "name": "Switzerland", "focus": false, "r": ["gy{AgrQrBiEhQxG|EGjBgUlCaAhD}NkGoLlDwEtMpBbF_A]zHoBvCh@|EfF|AhNsDBlDyFnElBtX}IfE[tFh@tAxJT|OnNtGuA|ArDmI~IcDmAaA~ImGnJoKfA~IlSxEw@bH`GzDxKsBpNdErXo@vCgOpP_FwAwGrB[tS`EdK~CoAxBnCpAjM_C?_C{FeEq@cBxBmJgE_HqNcK}A{C_L_N_QqC}AkBhE}DuHzBiLy@sHwDoCyAuFByq@aAcGaCtHkDqIlFcR]}QdHkT"] }, { "id": "ES", "name": "Spain", "focus": true, "r": ["_pjAqbBVj@WhIoAFqBaApByBTaEx@?", "{ulAqcE`AaEy@iEn@wE~BSxLpIrD|AhDvIcCxIa@hEq@x@gEp@_AtAYhCzChGkBtAQxBaAp@oA?aN{XkBkF{B_ONoAlA`A\\?`@aAz@Nn@~@|AZ", "cylAikGVb@gFbRWhEc@p@kDUYyKrAkInGaElBx@", "k_kAiyAvBfAg@lHs@fAkCaAQ{A_B?eB}AmAoLbAeB`BSrE`GZdB", "_xsAdoBdAG`BgApAcG^sHv@{BpAE`Bb@zCpBdAkBCqB{BiCnA[lA_FnCaNRyIxG_Jw@wPpGgO}@aNv@kBDsV}Ei@iAc@Os@bCqRbCkKDkDd@kB~D}C|ARjDSp@k@IkDyBsIvC}LfCqBH}AgCqIbDc[kBc@{B_MUuChAiNzBq@p@eBhBc@`AxGzDZfBoCv@[tGU`JhNvQlj@bHhI`AxBvDd_@jGp`@|MvRd@cDbD{DfA~@nBpG^zFlQlMhL~KvDfFpGdFjUvNjEDdU{FxDgCzCiEbC}JbCuA|B`C|EtJhHnSjFvGdFx@fB`E~HfAvGnCbDxBpBNbDiEbBhEd@n^zIpRrHzH|PxGrIvI|@vCuClFWdHr@~GrBnC`AlFw@dF_@hNF~E|AxI_AdH]pNfAv`@d@~BlChCrFxIHdOzCxMdBrBpGhEfE~@k@tALnAzCb@|AbI}BnJyDlHK|CaHbG{DpBeEnAmCDoAfFwDv@kFkDgBgC[wAHpEvCtCuFbE_NnWiBq@_AD`C`C`@|ASrKx@jMkX`E{GyBuBaCoFkDiEwEkAcI{GaCJfHgPxM_KqBcCG}EuH_D}C_DoAmCSeBzAu@bGuKhG}Fx@mC~EyFrDe@eDC}S}@eDkDyBsGaCiD[eAh@iD~Es@FoAc@oG{KeEvAmAc@sGGcA[wFb@gEh@eGnCiB}AyAoEwEkDqD{FmCcI{H}JiC~@oA`Cm@dDMlHaAZsI?kAb@y@vANjDy@bG`@~@IbI{@lFr@|AtBZ~@xB|@hGGvEgBfJb@zKWp@hCxIBpBMj@yCbB}@UwDcDi@LyDtCGjBdD`S`F|JZnCi@v@{HNoIeKStFeBGk@uAkBoAuBdDcGUoATlB~IO|AkC?oEaE}@U_@dFgBlD}EvEuB?qGsBcCuH_EmHb@yKe@cGmE_QqBFwAfAoA_AcFwNWoHuBsHjAqEWsDtAoEhEqGrAsKaAcIJoYo@wNP_HcBmMzBmJz@{TfB_LhDoc@@gL_BmQiA{Fl@eFsAsILcDxBqE~CkVgCaE_@oCrAuOhD{OHwGk@yK}BkK"] }, { "id": "PT", "name": "Portugal", "focus": true, "r": ["i|pAtcPaF}JeDaSFkBxDuCh@MvDbD|@TxCcBLk@CqBiCyIVq@c@{KfBgJFwE}@iG_AyBuB[s@}Az@mFHcIa@_Ax@cGOkDx@wAjAc@rI?`A[LmHl@eDnAaChC_AzH|JlCbIpDzFvEjDxAnEhB|AdGoCfEi@vFc@bAZrGFlAb@dEwAnGzKnAb@r@GhD_FdAi@hDZrG`CjDxB|@dDB|Sd@dDxFsDlC_F|Fy@tKiGt@cGdB{AlCR~CnA~C|C|EtHbCF~JpBfPyMKgHzG`CjAbIhEvEnFjDtB`CzGxBjXaETjDdIjT?pEmCjK{Ax[|AvGAvEvBrDa@xB{WmJaIDyGq@uGx@kDpBcMuCgFLcHfCj@gLyDhGHdFtCzOUx@sDUkF|A}@oCQkDcBoCsBuAeEp@}DaC_D_HVvCbBjDhJpGvDtAxA|LaAdFqF?wEuAqH[mGaCsDp@iBqBcAiCkFiEyb@qRiA\\s@fA_D]uTiEyAmAkE}A{Sq@eCZeG`CgP`CwDLyAkBMrDwBnAcCO{EgE"] }, { "id": "528", "name": "Netherlands", "focus": false, "r": ["}bbBouJQhNeDvEwE_FmGgCgCh@yA|JmDbGLjOeCfFwFfCbCnJkDrDhCrFkBhG|AlFxBk@R`AmD|UdAnJyArMmDnGmBeQvG_X]iGyFzO[_JoKrMoJqGwR_Xof@wP`AmFgByImGuQwIwIwEkTcC_z@dFmHxAkMtPLtTzH`@xPpEpBbCqBxAwNjAgAdFb@vBlAxF~NxALnBkDhCxBlD`WqB|JzCnL~ToNbMrFzCkBhFzOxF}JrHrB", "sjcBagG~CdBbE`P{C`SnAdHgGdDOuu@", "{sfBmpHlChEiAtCeH_J`F?", "u`dBuuFtD{Ff@rFaDvN{@oN"] }, { "id": "504", "name": "Morocco", "focus": false, "r": ["_qcAtiChGkDtLcT~GjBxGgFdErB~JeDrWLnLcDnNzAh`@kMpMcTdD}AfG~IhM[m@nkAnBzX`AfC~KlD`GhYtA`W~Dp@vKyBfItAfGaLbCFlBvC|@vPnL|SnMng@xQ`L~KzOxFra@Vt\\~HtA`DvC}A`^zF|N?dzQ?}gLkR{TwQmJeNuA}Dv@yO~LeGwA_c@q@{PiGqVoSk]gEmi@}l@sFgLuOcm@oSmh@mq@ea@e~@wYqA}QmE}Lv@mF|ArB|E?bGeDzSaYrCaLxAuQkFyf@fCuQw@uJkIsMhPiGp@we@"] }, { "id": "442", "name": "Luxembourg", "focus": false, "r": ["q{`Bk}JlDLjF{DjFwPrDFvEvEfH~@}AjIjBpIwDtLwEsDeItH}Ec@qNsM|AwG"] }, { "id": "438", "name": "Liechtenstein", "focus": false, "r": ["a|zAyuQIxD_LmAdIeDbBx@"] }, { "id": "380", "name": "Italy", "focus": false, "r": ["muxA{uL|AwEeEsXrBqN{DyKcHaGyEv@_JmSnKgAlGoJ`A_JbDlAlI_J}AsDuGtA}OoNyJUi@uAZuF|IgEmBuXhG_Ho@aCmMvEgF}Ai@}EnBwC\\{HcF~@sKkBpDw`@_IwGkA_FUa`@aEwWl@_ArCnCdBs@nMsMlJ{pApBj@zDpKtE`E`BuAfAaLrG~GfB?L}EnIZbBqGfHsHr@rHoAyB{GtHvBbI{BdOlG`J~If`@M`CyCoEA|AfEnLxKbBpKqInCcGtFrB|A|CeAvE|Ex@fQsBzKsDjMmQlYmu@lWaNt]{KvZg`@lRef@Iup@tAsKbDk@nBfApGzMxEZb[wcAplA?ij@?pVrSjPvG|ENxEwCzH_X`b@C|@fNpDvGhDrB`RZ~HlOhR|LB|S_EtCwGFmDsBsAsFgJ}CeGp@qBcBmD{OkJUeDhEsSjDuf@nSaCvE]dQsIrTkCh@iCqBuDfAmKlJhCpYcGmFeDnH?jOsBEgO|JsEzFkBj]p@xKaH|JwBtLm\\ta@wGzO}KpImGjT`AtHs@fAoA_D{C\\{O|UeGzD_AbK{MMkInC}G`GcTnC_EzBoCvG_DxRuLlZkEz_@rCfLl\\da@xE~^aERuLcKcDnAr@~RiKbY{IpB}KuJ}EfAyD~NgHnEaBFs@{BPmHoEyM{GiCoUhUqC]aFoL", "qurAuhS~Gq@aBjDd@rKqAh@qCwP", "wsiAol]dZjTlSjGtFc@rD_FhArBnHuFpLfJlHFk@|SqD`PyIpGgG|LDzMsVzl@wDpNm@nPwCfFiHrDqM_FcGuJdHqI_B_HwE_FR}JjB_AbHmXuBeOIq[sFyPZmSuG{Vp@iG|ApB", "cznA_yQzVyIlMbIvN_Cbt@~Gv@tCiE~YhK`A~CpBbBdD[rMoPjMcPb@aNcBQsDuEM}CvGoVaC}KlFmHjIwL]sAi@zCiNyBkMqUc`@~MaWhDxBbB}C", "whkA_qOdErBcG`C|@uF", "_doAydOrA|CiEyBEwCzBrB"] }, { "id": "372", "name": "Ireland", "focus": false, "r": ["irjBfbM`CzHfOxIhCnUpE{HvGnWrIeOfCaApCoNRqPuEqIyB|AsEeKzCaGdFwCbBuHrEFgAyTpA{FhAc@HlHhCnAxU{KbLNlZuFxJxGfKzAjKpNbEyGtBzMm@vLfBvEsDtCdDnAfCr_@nEhExAfLtFvL{BxT|DoC~CnCnLpv@_AjIxAjVmF{F{CuJ`Djd@cPu_@jEl]u@|NkCfAyNg\\Yd]oCgAuC_M|@oUqHhG_HaPgGct@wC`LpFnJe@`WfDfUcL}WiFuFcBhCmHcIyEeVwA`LVjV}D~EQvNgBeDa@tQcCoAmC`CoBwWgBtJiCM}CgSsC?\\|SkMsBd@|C_FtA~@fFmEgAcB{]PoNrDqI{C_HxAq[oE|C_EmHcCcNiGaE|@fSmCbRaLaWcGZ}FkFmA{_@}BZMaEjGwElHhEyCgJmKnAgBoLyB~BIqBzFyTbHdO"] }, { "id": "276", "name": "Germany", "focus": false, "r": ["gy{AgrQeHjT\\|QmFbRjDpI`CuH`AbGt@n^uAnUcCfAg]mD}\\}LsN{QmDLqDr_@sDbInAzXgCfAw@vE|AzHsMjKqB|JgH_AwEwEsDGuCrMkEdFoF`AqGiCiDuJmGj@kCbIsCsBuHhNsHsByF|JiF{O{CjBsJmF{C?sRhN{CoLpB}JmDaWiCyBoBjDyAMyF_O}IqB}BfCg@vLcCpBqEqBBuOySiIwRc@{D~GgJkBeEaEeAeq@bH}HvCrBl@qGcIkDvDcInF?aWaA_EyDnAiPi@kR`OsVxAkKyAlHcO`SgCzSuCnCgOEgB`Gd@jGoEGkC{QmCOyNjP}ERJsMpDyT}AuUtCcPrEcGxDMvE|H_@cP~CiCy@eHpFeV{BwPdEeBdErBrEjK|CwEYuJ~BoQoKwWo@wRuQa\\rBi[~FmFxGuQYiPjGaElIwAhD{HjAsMb_@uH|EtAvIlMlBTpMcWfFoEpI`CxE{FxGq@v@}ArNlHvKwGpEZnDaLjJeDzHjBfPjKgAnHuBU_D|CuAdMbA`CnEgFdKzq@jElFg@xB~EbKd@jIfDnCq@fJlAnLdLzOcG~GvAtArImFtK{QvHrFjPaNtUeh@pF}Eb@gH~GuL~A}AdJx@~B|EuBtJxL~EzH|\\`EpGpLeKnIrBl@qGtAk@`JnA_CxKaEnA{@jD`ArKaD`PdEr@fAf\\zH`Y|@~NIxBqFvE}@fZpJfClDtJiDc@{@hGmBNoBrDmCtLfBdM"] }, { "id": "FR", "name": "France", "focus": true, "r": ["irrAqoQbHr@tEoClWy@|@LtKfHfKLfBh@fBvAlItCtChCcGdQqClDoAk@oAcBaAOyBrIsA?cCoAmBb@IlF{@DeDkDgBFcC|EqBj@oAuAs@aCuB|A[xBkCoCuFwCqBiEkBkMmC{DDqBdAsDe@y@kBk@}A\\cGMqCaAIkBpA}A~Ic@", "q}{A_{MxAtFvDnCl@|C?vGoB`C?dDfAjDtBhC`Ak@PaCz@[lB|A`LrO|@j@zC~Kj@b@vIx@~GpNpHxDz@LbByBdEp@~BzF~B?PgAI}CyAeFyBoCcCbB[SyBsDgAqEMmHz@kKjATlBc@jAaA~EvAdHgJrDiCtBdDjBhG`Ab@nAE|@]nAuCpIkGfEwGfBnAzEfAn@`E~CvGQlHr@zB`BG|AsBhE{AjAaCn@qG|@kB|EgAv@j@VzAlIlFbDcBfAb@nBq@lBiCzGyTTkBiAsObDoAjFjDhEvE`ES`@jBg@p@Hb@`Ab@pCjKvLxRbCdH|ErB|BjDx@|C|@vJbCzJu@dD@|L_DpGcBtOgFjDGjKa@|A{CZ`@fH`AfCWfAHj@l@GH|CeD|Sm@lHo@zByBbBy@xBx@xGlEzFxOx_@|E`EjI~ExCLjN}AbIsFiAhNTtCzB~LjBb@cDb[fCpII|AgCpBwC|LkBgAe@?w@`AkAxK|AvC_E|Ce@jBEjDyFtZ@zDfHlAErVw@jB|@`NqGfOv@vPyG~ISxIoC`NmA~EoAZzBhCHp@kAjD{CqBaBc@qADw@zB_@rHqAbGaBfAeAFy@cI}FgHo[wGw`@iEiEoC{@{DoCvC`ErD}]kBkJoA{JgCnH_OdCyBxLwCvDwGeB~@kAzBmQrDeDpBkCrDeH~P{@x@mBZ@aEv@eD_CfAoFfAeWvA_@hIk@|CiIvWsIjGyFvGoB~@mBEiFoCsC`C[xBiAjBgEsDU}CrByP{DlM|@rVaAlHiCp@_AkBuB}AoAjB]nCZnLq@p@_CyBo@jBn@`Je@fEqCzDPnEw@`CBdFsA`CiDpWSpIjAtHWjDoB`CsDbBmCvN}AcBwAqNoAcB_BnEW~CuB~Bi@{A`@{FScIwApBg@zDDfSmDtAoDoA_D{JqDo\\VsK]_HkBqIaBoCu@aNbBeMxJgL~BiE}EiNF}UzBwCgBw@{BiCv@kBjAy@i@{ZyAnEwEdDyWb@_FvEaJtFoEpBoD[\\uOoA}Lv@wEbDLnE_ArE{DIgJ`AcKHiNtBgUeAmHmCgH}AqPo@q@RbIyAlHcBb@_HuC_I_ZaBcRmDaSsDcIkFwE}A}CqAtAyZy@_D_AcCyBsEaNwCi`@y@}CzAUzDaCvAj@fAc@xFcInA_DgC{O|AoCjCkBbGmAn@uA|@kPd@_AfGoAd@i@gAyBLsKZ{DvCaGlElA~AqBrALjB|Av@Ur@wL_@_JsA_FyDcBsB_Fb@uA`JnCxAcB|Fy@NqGpBmFvAsHlIeMs@yP~@_AZ}ChAsBPcBQaC}@uA[yBH{BrAoER_F|A}CtCmA|H}HLuA_BoCKuAv@wEfCgA_@eDZ}CkAwNbCwCn@kDdBiWjAiGlDMrNzQdUhGvFrDxD`AxBs@`E\\fGjBhETbCgAZeB", "_txAthAlDfA_D`CmCrDcDb@|AqEdEoE"] }, { "id": "203", "name": "Czechia", "focus": false, "r": ["mu_Boe`@rl@?lJzAsEnCwDbTpB~I_@jRyErMqG~r@hMfCn@pGfH`EC`g@sDxBuOlZDvEmVz_@BhEiDhGiSdQwHsFuKzQuKlFVeDtEoEeL{OmAoLp@gJgDoCe@kI_FcKf@yBkEmFeK{q@oEfFs@y@dAmO~C}CtBTnAwEmCgOaGSnBuOdHaElCkV`GkPuAaPbA}C|AsBpBnAvDpIrB{FpO}QmG_UaJrFC_Fpw@g@"] }, { "id": "056", "name": "Belgium", "focus": false, "r": ["sjcBagGx@eHSaAyBj@}AmFjBiGiCsFjDsDcCoJvFgCdCgFMkO~H{T|IvCvE~EdDwEPiNtHiNrCrBjCcIlGk@hDtJ|ErB}AvGpNrM|Eb@dIuHvD`CrAjRmIdMyErXwI|CaJoCc@tArB~ExDbBrA~ESvWwFuA_BpBmEmAwC`Go@~NlAhEsIxDmB`ScGlAiFzFfCzOiIbNwLnC_Ouj@s@{FfGeDoAeHzCaScEaP_DeB"] }, { "id": "040", "name": "Austria", "focus": false, "r": ["ki{AmrQgKcEsBhEgBeMlEwPxDyB^qEhDb@mDuJqJgC|@gZpFwEHyB}@_O{HaYgAg\\eEs@`DaPaAsKz@kD`EoA~ByKaJoAuAj@m@pGoIsBsJdKiDkBqKcb@yL_FnAyMyAyBeJy@tCyIrDyBBag@gHaEo@qGiMgCpG_s@xEsM^kRqB_JvDcTrEoCdLrD~QoGlV?z@lLqCbKvCpIbCuLpCgApDjB~AfJxFc@dBtAfEwChFnADrFzHnQtAxBvFb@aAjK`D~Rp@da@vKjT_Pj`C{@rDoMrMeBr@sCoCm@~@`EvWT``@jA~E~HvG{Cd_@{ExBi@hCjGnLiD|NmC`AaBlOcBy@eIdD"] }, { "id": "AD", "name": "Andorra", "focus": true, "r": ["m_rAqiBxBrIHjDq@j@kDR}AS}AwCjAyKv@aAd@?jBfA"] }, { "id": "012", "name": "Algeria", "focus": false, "r": ["scgAawOpEq@nCzH`GvC`FbIlH_Hjb@nEdHoCvN?nKuCjFbDzT`CtItFrHvPvHrDzIrMnNZfb@kMfL{V`GaE|VsFn\\qk@brBu\\dF`Lfa@oUdCwC?qI?x]?a~C?xig@?orA{F}NrBq[wDgF_IuAWu\\yFsa@_L{OyQaLoMog@oL}S}@wPmBwCcCGgG`LgIuAwKxB_Eq@uAaWaGiY_LmDaAgCoB{Xl@okAiMZgG_JeD|AqMbTi`@jMoN{AoLbDsWM_KdDeEsByGfF_HkBuLbTiGjDRcRoDaNm]gn@_Kq]v@sVkMsKeE{HuPeh@sC_QcDorAoJsVSea@iEeO?e|@nNq`@qLco@qCoJuE}CoA{H`DsDfDaUaBkRuF`A`AeMtK}\\cDsh@"] }];

  // src/map.tsx
  function decode(str) {
    const out = [];
    let i = 0, lat = 0, lng = 0;
    const next = () => {
      let r = 0, s = 0, b;
      do {
        b = str.charCodeAt(i++) - 63;
        r |= (b & 31) << s;
        s += 5;
      } while (b >= 32);
      return r & 1 ? ~(r >> 1) : r >> 1;
    };
    while (i < str.length) {
      lat += next();
      lng += next();
      out.push([lng / 1e3, lat / 1e3]);
    }
    return out;
  }
  var CACHE = {};
  var ringsOf = (key, r) => CACHE[key] || (CACHE[key] = r.map(decode));
  var M_PER_DEG = 111320;
  function projector(view, W, H) {
    const cos = Math.cos(view.lat * Math.PI / 180);
    const k = W / (view.span * cos);
    const p = (lat, lng) => [W / 2 + (lng - view.lng) * cos * k, H / 2 + (view.lat - lat) * k];
    const mpp = M_PER_DEG / k;
    return { p, k, mpp, cos };
  }
  var path = (pts, P2) => "M" + pts.map(([lng, lat]) => {
    const [x, y] = P2(lat, lng);
    return x.toFixed(1) + " " + y.toFixed(1);
  }).join("L") + "Z";
  var DOURO_N = [[41.1478, -8.676], [41.1452, -8.656], [41.1436, -8.642], [41.1424, -8.63], [41.1412, -8.621], [41.1405, -8.614], [41.1404, -8.609], [41.1409, -8.602], [41.1418, -8.594], [41.1436, -8.585], [41.1462, -8.576], [41.149, -8.566]];
  var DOURO_S = [[41.1438, -8.676], [41.1418, -8.656], [41.14, -8.642], [41.1388, -8.63], [41.138, -8.621], [41.1384, -8.614], [41.1385, -8.609], [41.1388, -8.602], [41.1396, -8.594], [41.1412, -8.585], [41.144, -8.576], [41.1468, -8.566]];
  var STREETS = [
    [[41.1412, -8.63], [41.142, -8.622], [41.1416, -8.616], [41.1411, -8.612], [41.1412, -8.606]],
    [[41.1411, -8.613], [41.144, -8.6118], [41.1468, -8.611], [41.15, -8.61]],
    [[41.1416, -8.616], [41.145, -8.617], [41.148, -8.619]],
    [[41.143, -8.623], [41.146, -8.626], [41.149, -8.628]],
    [[41.1404, -8.6094], [41.1385, -8.6094]],
    [[41.1379, -8.62], [41.1372, -8.612], [41.137, -8.604], [41.1362, -8.596]],
    [[41.1372, -8.612], [41.134, -8.611], [41.131, -8.61]],
    [[41.15, -8.62], [41.147, -8.605], [41.146, -8.598]]
  ];
  var riverLat = (lng, bank) => {
    for (let i = 0; i < bank.length - 1; i++) {
      const [la0, ln0] = bank[i], [la1, ln1] = bank[i + 1];
      if (lng >= ln0 && lng <= ln1) return la0 + (la1 - la0) * (lng - ln0) / (ln1 - ln0);
    }
    return bank[0][0];
  };
  var BLOCKS = (() => {
    const out = [];
    let seed = 11;
    const r = () => {
      seed = seed * 16807 % 2147483647;
      return seed / 2147483647;
    };
    for (let lng = -8.64; lng < -8.592; lng += 92e-5) for (let lat = 41.13; lat < 41.153; lat += 68e-5) {
      const n = riverLat(lng, DOURO_N), sth = riverLat(lng, DOURO_S);
      const w2 = 66e-5 + r() * 12e-5, hh = 46e-5 + r() * 1e-4;
      if (lat < n + 1e-4 && lat + hh > sth - 1e-4) continue;
      if (Math.abs(lng + 8.6127) < 5e-4 || Math.abs(lng + 8.6094) < 3e-4) continue;
      if (r() < 0.12) continue;
      out.push([lat, lng, lat + hh, lng + w2]);
    }
    return out;
  })();
  var TOWN_LABELS = [{ t: "Ribeira", lat: 41.1428, lng: -8.6122 }, { t: "Miragaia", lat: 41.1448, lng: -8.6215 }, { t: "Vila Nova de Gaia", lat: 41.1352, lng: -8.615 }, { t: "Sé", lat: 41.146, lng: -8.6085 }];
  function MapView(props) {
    const { view, width = 420, height = 360, offline, heat, samples = 0, refs = [], candidates = [], selected, rings = [], zones = [], cone, final, area, legend = true, scale = true, labels = true, inset, hoverRef, dimOthers, caption } = props;
    const T = useT();
    const stage = useDensity() === "stage";
    const uid = useId().replace(/:/g, "");
    const W = width, H = height;
    const { p, mpp } = projector(view, W, H);
    const base = props.base === "auto" || !props.base ? view.span < 0.2 ? "town" : "outline" : props.base;
    const s = stage ? 1.8 : 1;
    const L = [];
    L.push(h("rect", { key: "water", x: 0, y: 0, width: W, height: H, className: "aq-map-water" }));
    if (base === "outline") {
      for (const c of COUNTRIES) {
        const rs = ringsOf("c" + c.id + c.name, c.r);
        L.push(h("path", { key: "c" + c.name, d: rs.map((r) => path(r, p)).join(""), className: c.focus ? "aq-map-land" : "aq-map-land-out" }));
      }
      for (const r of REGIONS) {
        const rs = ringsOf("r" + r.id + r.name, r.r);
        L.push(h("path", { key: "r" + r.id + r.name, d: rs.map((q) => path(q, p)).join(""), className: "aq-map-region" }));
      }
      for (const c of COUNTRIES.filter((c2) => c2.focus)) {
        const rs = ringsOf("c" + c.id + c.name, c.r);
        L.push(h("path", { key: "cb" + c.name, d: rs.map((r) => path(r, p)).join(""), className: "aq-map-country" }));
      }
    } else {
      L.push(h("rect", { key: "land", x: 0, y: 0, width: W, height: H, className: "aq-map-land" }));
      const river = [...DOURO_N, ...[...DOURO_S].reverse()].map(([la, ln]) => p(la, ln));
      BLOCKS.forEach((b, i) => {
        const [x0, y0] = p(b[2], b[1]), [x1, y1] = p(b[0], b[3]);
        if (x1 < 0 || x0 > W || y1 < 0 || y0 > H) return;
        L.push(h("rect", { key: "bk" + i, x: x0, y: y0, width: x1 - x0, height: y1 - y0, className: "aq-map-block" }));
      });
      L.push(h("polygon", { key: "douro", points: river.map((q) => q.join(",")).join(" "), className: "aq-map-river" }));
      STREETS.forEach((st, i) => L.push(h("polyline", { key: "st" + i, points: st.map(([la, ln]) => p(la, ln).join(",")).join(" "), className: "aq-map-street", strokeWidth: (stage ? 6 : 3.5) * Math.min(1.6, 0.012 / view.span) })));
    }
    const step = view.span > 6 ? 2 : view.span > 1.5 ? 1 : view.span > 0.2 ? 0.1 : 5e-3;
    const latMin = view.lat - H / W * view.span, latMax = view.lat + H / W * view.span;
    for (let g = Math.ceil((view.lng - view.span) / step) * step; g < view.lng + view.span; g += step) {
      const [x] = p(view.lat, g);
      L.push(h("line", { key: "gx" + g.toFixed(4), x1: x, x2: x, y1: 0, y2: H, className: "aq-map-grat" }));
    }
    for (let g = Math.ceil(latMin / step) * step; g < latMax; g += step) {
      const [, y] = p(g, view.lng);
      L.push(h("line", { key: "gy" + g.toFixed(4), x1: 0, x2: W, y1: y, y2: y, className: "aq-map-grat" }));
    }
    if (heat && heat.length) {
      const cell = stage ? 22 : 12;
      const cells = [];
      for (let x = 0; x < W; x += cell) for (let y = 0; y < H; y += cell) {
        const lng = view.lng + (x + cell / 2 - W / 2) / (W / view.span);
        const lat = view.lat - (y + cell / 2 - H / 2) / (W / (view.span * Math.cos(view.lat * Math.PI / 180)));
        let v = 0;
        for (const b of heat) {
          const d2 = ((lat - b.lat) ** 2 + ((lng - b.lng) * Math.cos(view.lat * Math.PI / 180)) ** 2) / (b.s * b.s);
          v += b.w * Math.exp(-d2 / 2);
        }
        const stepN = Math.min(5, Math.floor(v * 5.5));
        if (stepN <= 0) continue;
        cells.push(h("rect", { key: x + "_" + y, x: x + 0.5, y: y + 0.5, width: cell - 1, height: cell - 1, fill: `var(--heat-${stepN})` }));
      }
      L.push(h("g", { key: "heat", className: cx("aq-map-heat", dimOthers && "is-dim") }, cells));
    }
    if (zones.length) {
      const defs = zones.map((z) => h("pattern", { key: z.key, id: `zh${uid}${z.key}`, width: (z.rest ? 12 : 7) * s, height: (z.rest ? 12 : 7) * s, patternUnits: "userSpaceOnUse", patternTransform: `rotate(${{ A: 45, B: -45, C: 0, D: 90 }[z.key]})` }, h("line", { x1: 0, y1: 0, x2: 0, y2: (z.rest ? 12 : 7) * s, className: `aq-zone-hatch is-${z.key.toLowerCase()}`, strokeWidth: (z.rest ? 1 : 1.5) * s })));
      L.push(h("defs", { key: "zdefs" }, defs));
      const shapes = zones.filter((z) => !z.rest).map((z) => {
        const d = z.region ? (() => {
          const r = REGIONS.find((q) => q.id === z.region);
          return ringsOf("r" + r.id + r.name, r.r).map((q) => path(q, p)).join("");
        })() : z.poly ? path(z.poly.map(([la, ln]) => [ln, la]), p) : "";
        return { z, d };
      });
      zones.forEach((z) => {
        const d = z.rest ? `M0 0H${W}V${H}H0Z` + shapes.map((x) => x.d).join("") : shapes.find((x) => x.z === z).d;
        L.push(h(
          "g",
          { key: "z" + z.key, className: cx("aq-zone", "is-" + z.key.toLowerCase(), z.rest && "is-rest", z.chosen && "is-chosen", z.dim && "is-dim") },
          h("path", { d, fill: `url(#zh${uid}${z.key})`, fillRule: "evenodd", className: "aq-zone-fill" }),
          z.rest ? null : h("path", { d, className: "aq-zone-line", strokeWidth: (z.chosen ? 3 : 1.75) * s })
        ));
      });
      zones.forEach((z) => {
        const zp = z.point ? p(z.point[0], z.point[1]) : null;
        const inView = zp && zp[0] > 8 && zp[0] < W - 30 && zp[1] > 8 && zp[1] < H - 30;
        if (z.point && inView) {
          const [x, y] = zp;
          L.push(h(
            "g",
            { key: "zp" + z.key, className: cx("aq-zone-pt", "is-" + z.key.toLowerCase()) },
            h("rect", { x: x - 11 * s, y: y - 11 * s, width: 22 * s, height: 22 * s, rx: 2, className: "aq-zone-key" }),
            h("text", { x, y: y + 4.5 * s, textAnchor: "middle", className: "aq-zone-letter", style: { fontSize: 13 * s } }, z.key),
            labels ? h(MapLabel, { x: x + 15 * s, y: y + 4 * s, text: (z.label || "").replace(/^[A-D] · /, "") }) : null
          ));
        } else if (z.rest) {
          L.push(h("g", { key: "zr", className: cx("aq-zone-pt", "is-" + z.key.toLowerCase()) }, h("rect", { x: 10, y: H - 40 * s, width: 22 * s, height: 22 * s, rx: 2, className: "aq-zone-key" }), h("text", { x: 10 + 11 * s, y: H - 40 * s + 15.5 * s, textAnchor: "middle", className: "aq-zone-letter", style: { fontSize: 13 * s } }, z.key), h(MapLabel, { x: 16 + 22 * s, y: H - 25 * s, text: (z.label || "Everywhere else").replace(/^[A-D] · /, "") })));
        }
      });
    }
    if (area) {
      const [x, y] = p(area.lat, area.lng);
      const r = area.r / mpp;
      L.push(h("g", { key: "area", className: "aq-map-area" }, h("circle", { cx: x, cy: y, r, strokeWidth: 2 * s }), labels ? h(MapLabel, { x: x + r + 4, y: y - r + 10, text: area.label }) : null));
    }
    if (cone) {
      const [x, y] = p(cone.lat, cone.lng);
      const a1 = (cone.bearing - cone.err) * Math.PI / 180, a2 = (cone.bearing + cone.err) * Math.PI / 180;
      const Lc = cone.len * s;
      L.push(h(
        "g",
        { key: "cone", className: "aq-map-cone" },
        h("path", { d: `M${x} ${y}L${x + Math.sin(a1) * Lc} ${y - Math.cos(a1) * Lc}A${Lc} ${Lc} 0 0 1 ${x + Math.sin(a2) * Lc} ${y - Math.cos(a2) * Lc}Z` }),
        h("line", { x1: x, y1: y, x2: x + Math.sin(cone.bearing * Math.PI / 180) * Lc, y2: y - Math.cos(cone.bearing * Math.PI / 180) * Lc }),
        cone.label && labels ? h(MapLabel, { x: x + Math.sin(cone.bearing * Math.PI / 180) * Lc * 0.6 + 6, y: y - Math.cos(cone.bearing * Math.PI / 180) * Lc * 0.6, text: cone.label }) : null
      ));
    }
    if (samples && heat) {
      const pts = [];
      let seed = 7;
      const rnd = () => {
        seed = seed * 16807 % 2147483647;
        return seed / 2147483647;
      };
      for (let i = 0; i < samples; i++) {
        const b = heat[Math.floor(rnd() * heat.length)];
        const u = rnd(), v2 = rnd();
        const rr = Math.sqrt(-2 * Math.log(u + 1e-9)) * b.s * 0.9;
        const th = 2 * Math.PI * v2;
        const [x, y] = p(b.lat + rr * Math.sin(th), b.lng + rr * Math.cos(th) / Math.cos(view.lat * Math.PI / 180));
        pts.push(h("circle", { key: i, cx: x, cy: y, r: 1.6 * s }));
      }
      L.push(h("g", { key: "samples", className: cx("aq-map-samples", dimOthers && "is-dim") }, pts));
    }
    let thumb = null;
    refs.forEach((r) => {
      const [x, y] = p(r.lat, r.lng);
      const hv = hoverRef === r.id;
      L.push(h("g", { key: "ref" + r.id, className: cx("aq-map-ref", r.accepted === false && "is-rejected", hv && "is-hover", dimOthers && "is-dim") }, h("rect", { x: x - 4 * s, y: y - 4 * s, width: 8 * s, height: 8 * s, strokeWidth: 1.5 * s })));
      if (hv) {
        const tx = x > W / 2 ? 12 : W - 136, ty = 28;
        thumb = h("g", { key: "thumb", className: "aq-map-thumb" }, h("line", { x1: x, y1: y, x2: x > W / 2 ? tx + 124 : tx, y2: ty + 76, className: "aq-map-thumb-ln" }), h("rect", { x: tx, y: ty, width: 124, height: 76, rx: 2 }), h("svg", { x: tx + 2, y: ty + 2, width: 120, height: 72, viewBox: "0 0 120 72" }, h(PerspScene, { sc: urbanScene(), cam: { pos: [-13, -7, 1.6], yaw: 52, fov: 62, w: 120, h: 72 } })), h(MapLabel, { x: tx, y: ty - 6, text: r.label || "reference photo" }));
      }
    });
    const ringEl = (key, lat, lng, r, label, tone = "solver") => {
      const [x, y] = p(lat, lng);
      if (r == null) {
        const R3 = 34 * s;
        return h("g", { key, className: "aq-ring is-unknown" }, h("circle", { cx: x, cy: y, r: R3, strokeWidth: 1.75 * s }), h("circle", { cx: x, cy: y, r: R3 * 0.55, strokeWidth: 1 * s, className: "aq-ring-inner" }), h("text", { x: x + R3 * 0.71 + 4, y: y - R3 * 0.71, className: "aq-ring-q", style: { fontSize: 14 * s } }, "?"), labels ? h(MapLabel, { x: x + R3 + 6, y: y + 4, text: label || "± unknown radius" }) : null);
      }
      const R2 = r / mpp;
      const tiny = R2 < 4;
      return h("g", { key, className: cx("aq-ring", "is-" + tone, tiny && "is-tiny") }, h("circle", { cx: x, cy: y, r: Math.max(R2, 4), strokeWidth: 1.75 * s }), labels ? h(MapLabel, { x: x + Math.max(R2, 4) + 5, y: y - Math.max(R2, 4) * 0.7, text: (label || `± ${fmtDist(r)}`) + (tiny ? " (smaller than a pixel here)" : "") }) : null);
    };
    rings.forEach((r, i) => L.push(ringEl("ring" + i, r.lat, r.lng, r.r, r.label, r.tone)));
    candidates.forEach((c) => {
      const [x, y] = p(c.lat, c.lng);
      const sel = selected === c.id;
      const R2 = 9 * s;
      L.push(h(
        "g",
        { key: "cand" + c.id, className: cx("aq-pin", sel && "is-sel", c.ruledOut && "is-out"), "data-link": c.id },
        h("circle", { cx: x, cy: y, r: R2 + 2, className: "aq-pin-halo" }),
        h("circle", { cx: x, cy: y, r: R2, className: "aq-pin-dot" }),
        c.ruledOut ? h("line", { x1: x - R2, y1: y + R2, x2: x + R2, y2: y - R2, className: "aq-pin-strike" }) : h("text", { x, y: y + 4 * s, textAnchor: "middle", className: "aq-pin-n", style: { fontSize: 11 * s } }, c.rank),
        sel ? h("circle", { cx: x, cy: y, r: R2 + 5 * s, className: "aq-pin-sel", strokeWidth: 2 * s }) : null,
        labels && c.name ? h(MapLabel, { x: x + R2 + 5, y: y + 4, text: c.name }) : null
      ));
    });
    if (final) {
      L.push(ringEl("fring", final.lat, final.lng, final.r, final.r == null ? void 0 : `± ${fmtDist(final.r)}`));
      const [x, y] = p(final.lat, final.lng);
      L.push(h(SurveyMark, { key: "final", x, y, size: 30 * s }));
    }
    if (thumb) L.push(thumb);
    let scaleEl = null;
    if (scale) {
      const target = 100 * s * mpp;
      const nice = [5, 10, 20, 25, 50, 100, 200, 250, 500, 1e3, 2e3, 5e3, 1e4, 2e4, 5e4, 1e5, 2e5];
      const m = nice.reduce((a, b) => Math.abs(b - target) < Math.abs(a - target) ? b : a);
      const px = m / mpp;
      scaleEl = h("g", { className: "aq-map-scale", transform: `translate(${W - px - 14}, ${H - 16 * s})` }, h("rect", { x: -6, y: -16 * s, width: px + 12, height: 22 * s, rx: 2, className: "aq-map-scale-bg" }), h("path", { d: `M0 0V-5H${px}V0M${px / 2} 0V-3`, strokeWidth: 1.5 * s, fill: "none" }), h("text", { x: px / 2, y: -7 * s, textAnchor: "middle", style: { fontSize: 10.5 * s } }, fmtDist(m)));
    }
    if (base === "town" && labels) TOWN_LABELS.forEach((l) => {
      const [x, y] = p(l.lat, l.lng);
      if (x > 0 && x < W && y > 0 && y < H) L.push(h("text", { key: "tl" + l.t, x, y, textAnchor: "middle", className: "aq-map-place", style: { fontSize: 11 * s } }, l.t));
    });
    if (base === "town" && labels) {
      const [x, y] = view.span < 0.012 ? p(41.13935, view.lng - view.span * 0.28) : p(41.1394, -8.6265);
      L.push(h("text", { key: "douro", x, y, textAnchor: "middle", className: "aq-map-waterlabel", style: { fontSize: 13 * s } }, "Douro"));
      if (view.span < 0.012) {
        const [qx, qy] = p(41.14072, view.lng + view.span * 0.33);
        L.push(h("text", { key: "cais", x: qx, y: qy, textAnchor: "middle", className: "aq-map-place", style: { fontSize: 10.5 * s } }, "Cais da Ribeira"));
      }
    }
    if (base === "outline" && labels) [{ t: "Portugal", lat: 39.6, lng: -8 }, { t: "España", lat: 40.2, lng: -3.7 }, { t: "France", lat: 46.6, lng: 2.4 }, { t: "Atlantic", lat: 41.5, lng: -11.4, water: true }].forEach((l) => {
      const [x, y] = p(l.lat, l.lng);
      if (x > 20 && x < W - 20 && y > 10 && y < H - 10) L.push(h("text", { key: "cl" + l.t, x, y, textAnchor: "middle", className: l.water ? "aq-map-waterlabel" : "aq-map-place is-country", style: { fontSize: (l.water ? 13 : 12) * s } }, l.t));
    });
    return h(
      "figure",
      { className: cx("aq-map", offline && "is-offline", base === "town" && "is-town"), style: { width: W } },
      h(
        "svg",
        { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img", "aria-label": caption || "Map" },
        h("clipPath", { id: "mc" + uid }, h("rect", { x: 0, y: 0, width: W, height: H })),
        h("g", { clipPath: `url(#mc${uid})` }, L, scaleEl)
      ),
      inset ? h(Inset, inset) : null,
      offline ? h("div", { className: cx("aq-map-offline", T.micro) }, h(Icon, { name: "offline" }), base === "town" ? "Tiles offline · bundled schematic streets" : "Tiles offline · bundled outlines of PT, ES, FR with district borders") : null,
      legend ? h(MapLegend, { items: legendItems(props) }) : null
    );
  }
  function legendItems(pr) {
    const it = [];
    if (pr.heat) it.push("heat");
    if (pr.samples) it.push("samples");
    if (pr.refs && pr.refs.length) it.push("refs");
    if (pr.candidates && pr.candidates.length) it.push("cand");
    if (pr.candidates && pr.candidates.some((c) => c.ruledOut)) it.push("out");
    if ((pr.rings || []).some((r) => r.r != null) || pr.final && pr.final.r != null) it.push("ring");
    if ((pr.rings || []).some((r) => r.r == null) || pr.final && pr.final.r == null) it.push("ringU");
    if (pr.final) it.push("final");
    if (pr.cone) it.push("cone");
    if (pr.zones && pr.zones.length) it.push("zones");
    return it;
  }
  function MapLabel({ x, y, text }) {
    return h("text", { x, y, className: "aq-map-label" }, text);
  }
  function SurveyMark({ x, y, size = 30 }) {
    const r = size / 2, t = r * 0.62;
    const tri = `M${x} ${y - t}L${x + t * 0.866} ${y + t * 0.5}L${x - t * 0.866} ${y + t * 0.5}Z`;
    return h(
      "g",
      { className: "aq-mark" },
      h("circle", { cx: x, cy: y, r: r + 2, className: "aq-mark-halo" }),
      h("circle", { cx: x, cy: y, r, className: "aq-mark-c" }),
      h("path", { d: tri, className: "aq-mark-t" }),
      h("circle", { cx: x, cy: y, r: Math.max(1.6, size * 0.07), className: "aq-mark-d" }),
      h("path", { d: `M${x - r - 6} ${y}h5M${x + r + 1} ${y}h5M${x} ${y - r - 6}v5M${x} ${y + r + 1}v5`, className: "aq-mark-ticks" })
    );
  }
  function UncertaintyRing({ r, source, size }) {
    const T = useT();
    const stage = useDensity() === "stage";
    const S = size || (stage ? 120 : 72);
    const c = S / 2;
    return h(
      "figure",
      { className: "aq-uring" },
      h(
        "svg",
        { viewBox: `0 0 ${S} ${S}`, width: S, height: S, "aria-hidden": true },
        r == null ? h(Fragment, null, h("circle", { cx: c, cy: c, r: c - 4, className: "aq-ring-shape is-unknown" }), h("circle", { cx: c, cy: c, r: (c - 4) * 0.55, className: "aq-ring-shape is-inner" }), h("text", { x: c, y: c + 5, textAnchor: "middle", className: "aq-ring-q2" }, "?")) : h(Fragment, null, h("circle", { cx: c, cy: c, r: c - 4, className: "aq-ring-shape" }), h("circle", { cx: c, cy: c, r: 2.5, className: "aq-ring-dot" }), h("line", { x1: c, y1: c, x2: S - 4, y2: c, className: "aq-ring-rad" }))
      ),
      h("figcaption", null, h("div", { className: T.data }, r == null ? "± unknown" : `± ${fmtDist(r)}`), h("div", { className: cx(T.micro, "aq-ink3") }, r == null ? "no bound yet · not zero" : source || ""))
    );
  }
  function Inset({ view, box, label }) {
    const W = 132, H = 112;
    const { p } = projector(view, W, H);
    const L = [h("rect", { key: "w", x: 0, y: 0, width: W, height: H, className: "aq-map-water" })];
    for (const c of COUNTRIES) {
      const rs = ringsOf("c" + c.id + c.name, c.r);
      L.push(h("path", { key: c.name, d: rs.map((r) => path(r, p)).join(""), className: c.focus ? "aq-map-land" : "aq-map-land-out" }));
    }
    if (box) {
      const [x0, y0] = p(box.lat + box.span * 0.4, box.lng - box.span / 2), [x1, y1] = p(box.lat - box.span * 0.4, box.lng + box.span / 2);
      L.push(h("rect", { key: "b", x: x0, y: y0, width: Math.max(4, x1 - x0), height: Math.max(4, y1 - y0), className: "aq-inset-box" }));
    }
    return h("div", { className: "aq-inset" }, h("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H }, L), label ? h("div", { className: "aq-inset-l console-micro" }, label) : null);
  }
  var LEG = {
    heat: ["heat", "Pixel-geolocation heat"],
    samples: ["samples", "Sampled points"],
    refs: ["refs", "Reference photos (GPS)"],
    cand: ["cand", "Candidates, by rank"],
    out: ["out", "Ruled out"],
    ring: ["ring", "Uncertainty, known radius"],
    ringU: ["ringU", "Uncertainty, radius unknown"],
    final: ["final", "Best estimate (surveyor’s mark)"],
    cone: ["cone", "Measured bearing ± error"],
    zones: ["zones", "Zones A–D · key = representative point, not a camera position"]
  };
  function MapLegend({ items }) {
    const T = useT();
    return h("ul", { className: cx("aq-legend", T.micro) }, items.map((k) => h("li", { key: k }, h("svg", { viewBox: "0 0 18 14", width: 18, height: 14, "aria-hidden": true }, legendSym(k)), LEG[k][1])));
  }
  function legendSym(k) {
    switch (k) {
      case "heat":
        return h(Fragment, null, [1, 3, 5].map((s, i) => h("rect", { key: i, x: i * 6, y: 3, width: 5, height: 8, fill: `var(--heat-${s})` })));
      case "samples":
        return h(Fragment, null, h("circle", { cx: 4, cy: 7, r: 1.6, className: "aq-lg-sample" }), h("circle", { cx: 10, cy: 4, r: 1.6, className: "aq-lg-sample" }), h("circle", { cx: 14, cy: 9, r: 1.6, className: "aq-lg-sample" }));
      case "refs":
        return h("rect", { x: 5, y: 3, width: 8, height: 8, className: "aq-lg-ref" });
      case "cand":
        return h(Fragment, null, h("circle", { cx: 9, cy: 7, r: 6, className: "aq-lg-cand" }), h("text", { x: 9, y: 10, textAnchor: "middle", className: "aq-lg-candn" }, "1"));
      case "out":
        return h(Fragment, null, h("circle", { cx: 9, cy: 7, r: 6, className: "aq-lg-out" }), h("line", { x1: 4, y1: 12, x2: 14, y2: 2, className: "aq-lg-outl" }));
      case "ring":
        return h("circle", { cx: 9, cy: 7, r: 5.5, className: "aq-lg-ring" });
      case "ringU":
        return h("circle", { cx: 9, cy: 7, r: 5.5, className: "aq-lg-ringu" });
      case "final":
        return h("path", { d: "M9 2l5 9H4z", className: "aq-lg-final" });
      case "cone":
        return h("path", { d: "M2 12L16 3V12Z", className: "aq-lg-cone" });
      default:
        return h(Fragment, null, h("rect", { x: 1, y: 3, width: 7, height: 8, className: "aq-lg-za" }), h("rect", { x: 10, y: 3, width: 7, height: 8, className: "aq-lg-zb" }));
    }
  }

  // src/human.tsx
  var human_exports = {};
  __export(human_exports, {
    AnswerReceipt: () => AnswerReceipt,
    CueComposer: () => CueComposer,
    QuestionCard: () => QuestionCard,
    QuestionOption: () => QuestionOption,
    checkCue: () => checkCue
  });
  function QuestionOption({ o, state = "open", evidence = [], cost = 0.95, hover, showLinks = true, brief }) {
    const T = useT();
    const k = o.key.toLowerCase();
    const chips = (o.chips || []).map((id) => evidence.find((e) => e.id === id)).filter(Boolean);
    const pt = o.point;
    return h(
      "div",
      { className: cx("aq-qopt", "is-" + k, "is-" + state, hover && "is-hover"), role: "radio", "aria-checked": state === "chosen", tabIndex: 0 },
      h("span", { className: cx("aq-qopt-key", T.data) }, o.key),
      h(
        "div",
        { className: "aq-qopt-b" },
        h("div", { className: cx(T.heading, "aq-qopt-l") }, o.label, state === "chosen" ? h(Badge, { tone: "team", icon: "team" }, "Team answer") : null),
        h("div", { className: cx(T.body, "aq-ink2") }, o.reason),
        chips.length ? h("div", { className: "aq-qopt-chips" }, chips.map((e) => h("span", { key: e.id, className: cx("aq-qchip", T.micro) }, h(Icon, { name: "support" }), h("span", { className: "aq-num" }, e.obs.length > 28 ? e.obs.slice(0, 27) + "…" : e.obs)))) : null,
        brief ? null : pt ? h(
          "div",
          { className: cx("aq-qopt-pt", T.micro) },
          h(Icon, { name: "crosshair" }),
          h("span", { className: cx(T.dataSm, "aq-ink2") }, fmtCoord(pt[0], pt[1])),
          h("span", { className: "aq-ink3" }, "not a camera position"),
          showLinks ? h("span", { className: "aq-qopt-links" }, ["OSM", "Google Maps", "Street View"].map((l) => h("a", { key: l, href: "#", onClick: (e) => e.preventDefault() }, l, h(Icon, { name: "link" })))) : null
        ) : o.none ? h("div", { className: cx("aq-qopt-pt", T.micro, "aq-ink3") }, "Exists only because the agent made it an option.") : null
      ),
      h("div", { className: "aq-qopt-act" }, state === "open" ? h(Fragment, null, h(KeyCap, null, String("ABCD".indexOf(o.key) + 1)), h(CostTag, { multiplier: cost })) : null)
    );
  }
  function QuestionCard({ q, evidence = [], state = "open", cueLine, hoverKey, number = 1, brief }) {
    const T = useT();
    return h(
      "section",
      { className: cx("aq-q", "is-" + state), "aria-label": `Question ${number}: ${q.text}` },
      h(
        "header",
        { className: "aq-q-h" },
        h("div", { className: "aq-q-meta" }, h("span", { className: cx(T.label, "aq-ink2") }, `Question ${number}`), h(ModelChip, { name: "chosen by the solver", actor: "solver", size: "sm" }), h(ModelChip, { name: `worded by ${q.wordedBy}`, actor: "model", size: "sm" })),
        h("nav", { className: cx("aq-crumbs", T.micro), "aria-label": "Scope" }, h("span", { className: "aq-ink3" }, "Scope"), q.scope.map((s, i) => h(Fragment, { key: i }, i ? h(Icon, { name: "chevronRight" }) : null, h("span", { className: i === q.scope.length - 1 ? "aq-ink1" : "aq-ink2" }, s)))),
        h("h3", { className: cx(T.title, "aq-q-t") }, q.text)
      ),
      state === "open" ? h(GainMeter, { gain: q.gain, breakEven: q.breakEven, cueLine }) : null,
      h("div", { className: "aq-q-opts", role: "radiogroup", "aria-label": "Options" }, q.options.map((o) => h(QuestionOption, {
        key: o.key,
        o,
        evidence,
        cost: q.cost,
        hover: hoverKey === o.key,
        state: state === "answered" ? q.answer === o.key ? "chosen" : "other" : state === "skipped" ? "skipped" : "open",
        showLinks: state === "open" && !brief,
        brief
      }))),
      state === "open" ? h(
        "footer",
        { className: "aq-q-f" },
        h("div", { className: "aq-q-cost" }, h(Icon, { name: "cost" }), h("span", { className: T.body }, "Any answer costs ", h("b", { className: "aq-c-cost aq-num" }, fmtMult(q.cost)), " on every guess after it, right or wrong.")),
        h(
          "div",
          { className: "aq-q-actions" },
          h(Button, { variant: "skip", icon: "skip", shortcut: "S" }, "Skip"),
          h("span", { className: cx(T.micro, "aq-ink3", "aq-q-skipnote") }, "Changes nothing. Not read as “no” or “none of these”."),
          brief ? null : h("span", { className: "aq-q-share" }, h(Button, { variant: "quiet", icon: "copy" }, "Copy all links"), h(Button, { variant: "quiet", icon: "qr" }, "QR for a phone"))
        )
      ) : null
    );
  }
  function AnswerReceipt({ kind, q, before, after, multiplierBefore, multiplierAfter, t }) {
    const T = useT();
    const opt = q.options.find((o) => o.key === q.answer);
    const rows = (after || before).map((r) => ({ name: r.name, v: r.v, before: (before.find((b) => b.id === r.id) || {}).v, other: r.other, note: r.keptNote }));
    return h(
      "section",
      { className: cx("aq-receipt", "is-" + kind), role: "status" },
      h(
        "header",
        { className: "aq-receipt-h" },
        kind === "answered" ? h(Fragment, null, h(ModelChip, { name: "Team", actor: "team", size: "sm" }), h("span", { className: T.heading }, `Answered ${q.answer} · ${opt == null ? void 0 : opt.label}`)) : h(Fragment, null, h(Icon, { name: "skip" }), h("span", { className: T.heading }, "Skipped · free")),
        t != null ? h("span", { className: cx(T.dataSm, "aq-ink3", "aq-receipt-t") }, fmtTime(t)) : null
      ),
      kind === "answered" ? h("div", { className: "aq-receipt-m" }, h("span", { className: cx(T.label, "aq-ink2") }, "Multiplier"), h("span", { className: cx(T.readout, "aq-ink3") }, fmtMult(multiplierBefore)), h(Icon, { name: "chevronRight" }), h("span", { className: cx(T.readout, "aq-c-cost") }, fmtMult(multiplierAfter)), h("span", { className: cx(T.micro, "aq-ink3") }, "applies to every guess produced from now on")) : h("div", { className: "aq-receipt-m" }, h("span", { className: cx(T.label, "aq-ink2") }, "Multiplier"), h("span", { className: T.readout }, fmtMult(multiplierBefore)), h("span", { className: cx(T.micro, "aq-ink2") }, "unchanged")),
      h(EstimateBars, { rows: kind === "answered" ? rows : rows.map((r) => ({ ...r, before: r.v })), mode: "beforeAfter", title: kind === "answered" ? "Estimates before (dashed) and after" : "Estimates — exactly as before", tone: "solver" }),
      kind === "skipped" ? h(
        "ul",
        { className: cx("aq-receipt-list", T.body) },
        h("li", null, h(Icon, { name: "done" }), "Beliefs unchanged; no candidate moved"),
        h("li", null, h(Icon, { name: "done" }), "Logged as “skipped” — not as “no” or “none of these”"),
        h("li", null, h(Icon, { name: "done" }), "No cost: multiplier stays ", h("span", { className: "aq-num" }, fmtMult(multiplierBefore)))
      ) : h("div", { className: cx(T.micro, "aq-ink3") }, "Ruled-down candidates stay in the list with a small estimate, in case the answer was wrong.")
    );
  }
  var GAZ = ["porto", "lisboa", "lisbon", "douro", "gaia", "ribeira", "alentejo", "évora", "evora", "nazaré", "nazare", "galicia", "madrid", "paris", "extremadura", "braga", "sintra"];
  var HINTS = [[/big[- ]wave surf/i, "hints at Nazaré"], [/port wine|cellars/i, "hints at Porto / Gaia"], [/tram 28/i, "hints at Lisbon"], [/camino|pilgrim/i, "hints at Santiago"]];
  var COORD = /-?\d{1,2}\.\d{2,}\s*,\s*-?\d{1,3}\.\d{2,}/;
  function checkCue(text) {
    const flags = [];
    for (const w2 of GAZ) {
      const m = new RegExp(`\\b${w2}\\b`, "i").exec(text);
      if (m) flags.push({ term: m[0], why: "names a place" });
    }
    for (const [re, why] of HINTS) {
      const m = re.exec(text);
      if (m) flags.push({ term: m[0], why });
    }
    const c = COORD.exec(text);
    if (c) flags.push({ term: c[0], why: "looks like coordinates" });
    return flags;
  }
  function CueComposer({ text: init = "", confirm, max = 1e3, sent }) {
    const T = useT();
    const [text, setText] = useState(init);
    const flags = checkCue(text);
    const n = text.length;
    const state = sent ? "sent" : flags.length ? "flagged" : n === 0 ? "empty" : confirm ? "confirm" : "ready";
    return h(
      "section",
      { className: cx("aq-cue", "is-" + state) },
      h("header", { className: "aq-cue-h" }, h(Icon, { name: "cue" }), h("span", { className: T.heading }, "Cue to the agent"), h(CostTag, { multiplier: 0.8 }), h("span", { className: cx(T.micro, "aq-ink3") }, "pays off only above +25% expected gain")),
      h(
        "div",
        { className: "aq-cue-field" },
        h("textarea", { className: T.body, value: text, maxLength: max, rows: 3, "aria-label": "Cue text", placeholder: "Describe what you see, without naming or hinting at a place. Example: “the wall tiles are glazed and mostly blue on white”.", onChange: (e) => setText(e.target.value) }),
        h("div", { className: cx("aq-cue-count", T.dataSm, n > max * 0.9 && "is-near") }, `${n} / ${max}`)
      ),
      flags.length ? h("ul", { className: cx("aq-cue-flags", T.body) }, flags.map((f, i) => h("li", { key: i }, h(Icon, { name: "warning" }), h("b", { className: "aq-num" }, `“${f.term}”`), ` ${f.why}. Cues must not name or hint at any place.`))) : n ? h("div", { className: cx("aq-cue-ok", T.micro) }, h(Icon, { name: "done" }), "No place names, hints or coordinates found") : null,
      state === "confirm" ? h("div", { className: "aq-cue-confirm", role: "alertdialog" }, h("span", { className: T.body }, "Send this cue? Every guess after it is multiplied by ", h("b", { className: "aq-c-cost aq-num" }, "×0.8"), "."), h(Button, { variant: "quiet" }, "Keep editing"), h(Button, { variant: "primary", cost: 0.8 }, "Send cue")) : sent ? h("div", { className: cx("aq-cue-ok", T.body) }, h(Icon, { name: "done" }), "Sent at 04:12 · logged · multiplier now ", h("b", { className: "aq-c-cost aq-num" }, "×0.76")) : h("div", { className: "aq-cue-a" }, h(Button, { variant: "secondary", icon: "cue", cost: 0.8, disabled: state !== "ready" }, "Review and send"))
    );
  }

  // src/output.tsx
  var output_exports = {};
  __export(output_exports, {
    AnswerSlots: () => AnswerSlots,
    ChoiceNote: () => ChoiceNote,
    CoordinateBlock: () => CoordinateBlock,
    EventLog: () => EventLog,
    ExportBar: () => ExportBar,
    ReplayScrubber: () => ReplayScrubber,
    ScoreCurve: () => ScoreCurve
  });
  function CoordinateBlock({ a, showCopy = true, size = "md" }) {
    const T = useT();
    return h(
      "div",
      { className: cx("aq-coord", size === "lg" && "is-lg") },
      h("div", { className: cx(T.micro, "aq-ink3") }, "Latitude, longitude · WGS84"),
      h("div", { className: "aq-coord-v" }, h("span", { className: size === "lg" ? T.readout : T.data }, fmtCoord(a.lat, a.lng)), h("span", { className: cx(T.data, "aq-coord-r") }, a.r == null ? "± unknown" : `± ${fmtDist(a.r)}`)),
      h(
        "dl",
        { className: cx("aq-coord-meta", T.micro) },
        h("dt", null, "source role"),
        h("dd", { className: "aq-num" }, a.role),
        h("dt", null, "method"),
        h("dd", { className: "aq-num" }, a.method),
        h("dt", null, "radius from"),
        h("dd", null, a.r == null ? "no bound yet" : a.rSource),
        h("dt", null, "multiplier when produced"),
        h("dd", { className: cx("aq-num", a.multiplier < 1 && "aq-c-cost") }, fmtMult(a.multiplier))
      ),
      showCopy ? h("div", { className: "aq-coord-a" }, h(Button, { icon: "copy" }, "Copy lat, lng"), h(Button, { variant: "quiet", icon: "copy" }, "Copy as JSON")) : null
    );
  }
  function AnswerSlots({ a, expanded: ex, special, producedAt = 340 }) {
    const T = useT();
    const [open, setOpen] = useState(!!ex);
    return h(
      "section",
      { className: cx("aq-slots", open && "is-open") },
      h("header", { className: "aq-slots-h" }, h("span", { className: T.heading }, "Answer slots"), h("span", { className: cx(T.micro, "aq-ink3") }, "Same coordinate in all 10 — our default: the one with the highest expected score")),
      h(
        "div",
        { className: "aq-slots-once" },
        h("span", { className: cx(T.data, "aq-slots-coord") }, fmtCoord(a.lat, a.lng)),
        h("span", { className: cx("aq-slots-x", T.readout) }, "×10"),
        h("span", { className: cx(T.micro, "aq-ink2") }, `each at ${fmtMult(a.multiplier)} · ${a.method}`)
      ),
      h("div", { className: "aq-slots-w", role: "img", "aria-label": "Rank weights 1.00 to 0.63" }, RANK_W.map((w2, i) => h("span", { key: i, className: "aq-slots-wi" }, h("i", { style: { height: `${w2 * 100}%` } }), h("b", { className: T.dataSm }, w2.toFixed(2))))),
      h("button", { type: "button", className: cx("aq-slots-toggle", T.label), "aria-expanded": open, onClick: () => setOpen(!open) }, h(Icon, { name: open ? "chevronDown" : "chevronRight" }), open ? "Hide the 10 rows" : "Show all 10 rows"),
      open ? h(
        "table",
        { className: cx("aq-slots-table", T.dataSm) },
        h("thead", null, h("tr", null, ["Slot", "Latitude, longitude", "Rank weight", "Penalty snapshot", "Produced"].map((x) => h("th", { key: x, className: T.micro }, x)))),
        h("tbody", null, RANK_W.map((w2, i) => h("tr", { key: i }, h("td", null, i + 1), h("td", null, fmtCoord(a.lat, a.lng)), h("td", null, w2.toFixed(2)), h("td", { className: a.multiplier < 1 ? "aq-c-cost" : "" }, fmtMult(a.multiplier)), h("td", { className: "aq-ink3" }, fmtTime(producedAt)))))
      ) : null
    );
  }
  function ChoiceNote({ a, mostLikelyName, mostLikelyExpected }) {
    const T = useT();
    return h(
      "div",
      { className: cx("aq-choice", a.mostLikely ? "is-same" : "is-diff") },
      h(Icon, { name: a.mostLikely ? "done" : "info" }),
      a.mostLikely ? h("div", { className: T.body }, `Chosen coordinate is the most likely candidate${mostLikelyName ? " (" + mostLikelyName + ")" : ""}.`) : h(
        "div",
        { className: "aq-choice-b" },
        h("div", { className: T.heading }, "Why not the most likely spot"),
        h("div", { className: cx(T.body, "aq-ink2") }, a.why),
        mostLikelyExpected ? h("div", { className: cx("aq-choice-cmp", T.data) }, h("span", null, `${mostLikelyName}: ≈ ${fmtInt(mostLikelyExpected)}`), h("span", { className: "aq-c-solver" }, `chosen: ≈ ${fmtInt(a.expected)}`)) : null
      )
    );
  }
  function ScoreCurve({ urban = "urban", band, expected, width, height, multiplier = 1 }) {
    const T = useT();
    const stage = useDensity() === "stage";
    const W = width || (stage ? 900 : 420), H = height || (stage ? 380 : 200);
    const m = { l: stage ? 70 : 40, r: 14, t: 14, b: stage ? 52 : 30 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const lx = (d) => m.l + (Math.log10(d) - 1) / 4 * iw;
    const ly = (k) => m.t + (1 - k) * ih;
    const curve = (u) => {
      const pts = [];
      for (let e = 1; e <= 5.0001; e += 0.02) {
        const d = Math.pow(10, e);
        pts.push(`${lx(d).toFixed(1)},${ly(theta(d, u) / 2).toFixed(1)}`);
      }
      return pts.join(" ");
    };
    const marks = [25, 100, 1e3, 5e3, 1e4];
    const showU = true, showN = true;
    const els = [];
    [0, 0.25, 0.5, 0.75, 1].forEach((k) => {
      els.push(h("line", { key: "g" + k, x1: m.l, x2: W - m.r, y1: ly(k), y2: ly(k), className: "aq-sc-grid" }));
      els.push(h("text", { key: "gt" + k, x: m.l - 6, y: ly(k) + 4, textAnchor: "end", className: "aq-sc-tick" }, `${k * 100}%`));
    });
    [10, 100, 1e3, 1e4, 1e5].forEach((d) => els.push(h("text", { key: "x" + d, x: lx(d), y: H - m.b + (stage ? 26 : 16), textAnchor: "middle", className: "aq-sc-tick" }, fmtDist(d))));
    marks.forEach((d) => els.push(h("line", { key: "m" + d, x1: lx(d), x2: lx(d), y1: m.t, y2: H - m.b, className: "aq-sc-mark" })));
    if (band) els.push(h("rect", { key: "band", x: lx(Math.max(10, band[0])), y: m.t, width: Math.max(3, lx(Math.max(10.5, band[1])) - lx(Math.max(10, band[0]))), height: ih, className: "aq-sc-band" }));
    if (showN) els.push(h("polyline", { key: "n", points: curve(false), className: cx("aq-sc-line is-n", urban === "urban" && "is-faint") }));
    if (showU) els.push(h("polyline", { key: "u", points: curve(true), className: cx("aq-sc-line is-u", urban === "non-urban" && "is-faint") }));
    if (showU) els.push(h("text", { key: "ul", x: lx(300) + 6, y: ly(theta(300, true) / 2) - 6, className: "aq-sc-lab" }, "Urban"));
    if (showN) els.push(h("text", { key: "nl", x: lx(3e4) + 6, y: ly(theta(3e4, false) / 2) - 6, className: "aq-sc-lab" }, "non-Urban"));
    els.push(h("line", { key: "ax", x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b, className: "aq-sc-axis" }));
    const exp = expected == null ? null : typeof expected === "number" ? h("div", { className: "aq-sc-exp" }, h("span", { className: cx(T.micro, "aq-ink3") }, "Expected score · estimate"), h("span", { className: cx(T.readout, "aq-c-solver") }, `≈ ${fmtInt(expected)}`), h("span", { className: cx(T.data, "aq-ink3") }, `of ${fmtInt(Math.floor(MAX_SCORE))}`), multiplier < 1 ? h("span", { className: cx(T.dataSm, "aq-c-cost") }, `includes ${fmtMult(multiplier)}`) : null) : h("div", { className: "aq-sc-exp" }, h("span", { className: cx(T.micro, "aq-ink3") }, "Urban label unknown · both scenarios"), h("span", { className: cx(T.readout, "aq-c-solver") }, `≈ ${fmtInt(expected.urban)}`), h("span", { className: cx(T.micro, "aq-ink2") }, "if Urban"), h("span", { className: cx(T.readout, "aq-c-solver") }, `≈ ${fmtInt(expected.nonUrban)}`), h("span", { className: cx(T.micro, "aq-ink2") }, "if non-Urban"));
    return h(
      "figure",
      { className: "aq-sc" },
      h("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img", "aria-label": "Share of the slot score kept against distance error" }, els),
      h("figcaption", { className: "aq-sc-cap" }, exp, h("span", { className: cx(T.micro, "aq-ink3") }, `Share of 1000 × θ kept per slot · band = current uncertainty${band ? ` (${fmtDist(band[0])}–${fmtDist(band[1])})` : ""} · under 10 m counts as 0`))
    );
  }
  var TYPE_ICON = { "run.started": "play", "run.finished": "done", "stage.started": "running", "stage.finished": "done", "stage.skipped": "skipped", "stage.failed": "failed", "stage.timed_out": "timeout", "evidence.added": "plus", "candidates.updated": "solver", "question.asked": "question", "question.answered": "team", "question.skipped": "skip", "cue.sent": "cue", "output.produced": "pin" };
  function EventLog({ events, filter = "all", json, height, current }) {
    const T = useT();
    const shown = events.filter((e) => filter === "all" || e.actor === filter);
    return h(
      "section",
      { className: "aq-log" },
      h(Tabs, { tabs: [{ id: "all", label: "All", count: events.length }, { id: "model", label: "Models", icon: "model" }, { id: "solver", label: "Solver", icon: "solver" }, { id: "team", label: "Team", icon: "team" }], value: filter, label: "Filter by actor" }),
      h("ol", { className: "aq-log-l", style: height ? { maxHeight: height } : void 0 }, shown.map((e, i) => h(
        "li",
        { key: i, className: cx("aq-log-r", "aq-actor-" + e.actor, current != null && e.t > current && "is-future", current != null && Math.abs(e.t - current) < 0.01 && "is-now") },
        h("span", { className: cx(T.dataSm, "aq-ink3") }, fmtTime(e.t)),
        h(Icon, { name: TYPE_ICON[e.type] || "info", className: "aq-log-i" }),
        h("span", { className: cx(T.dataSm, "aq-log-type") }, e.type),
        h("span", { className: cx(T.body, "aq-log-text") }, e.text),
        json === i ? h("pre", { className: cx("aq-log-json", T.dataSm) }, JSON.stringify({ run_id: "r-07", t: e.t, type: e.type, stage: e.stage, actor: e.actor, model: e.model, payload: { text: e.text } }, null, 1)) : null
      )))
    );
  }
  function ReplayScrubber({ events, t, duration, speed = 1, playing = false }) {
    const T = useT();
    const x = (s) => `${s / duration * 100}%`;
    return h(
      "div",
      { className: "aq-scrub" },
      h(
        "div",
        { className: "aq-scrub-ctl" },
        h(Button, { variant: "quiet", icon: "back", title: "Previous event" }, ""),
        h(Button, { variant: "secondary", icon: playing ? "pause" : "play", shortcut: "Space" }, playing ? "Pause" : "Play"),
        h(Button, { variant: "quiet", icon: "forward", title: "Next event" }, ""),
        h("div", { className: "aq-seg", role: "radiogroup", "aria-label": "Replay speed" }, [1, 2, 5].map((s) => h("button", { key: s, type: "button", role: "radio", "aria-checked": s === speed, className: cx("aq-seg-o", T.label, s === speed && "is-on") }, `${s}×`))),
        h("span", { className: cx("aq-sys is-replay", T.label) }, h(Icon, { name: "replay" }), `Replay ${speed}×`),
        h("span", { className: cx(T.data, "aq-scrub-time") }, fmtTime(t), h("span", { className: "aq-ink3" }, ` / ${fmtTime(duration)} · real timestamps`))
      ),
      h(
        "div",
        { className: "aq-scrub-track", role: "slider", "aria-valuemin": 0, "aria-valuemax": duration, "aria-valuenow": t, tabIndex: 0 },
        h("b", { style: { width: x(t) } }),
        events.map((e, i) => h("i", { key: i, className: cx("aq-scrub-tick", "is-" + e.actor), style: { left: x(e.t) }, title: `${fmtTime(e.t)} ${e.type}` })),
        h("span", { className: "aq-scrub-head", style: { left: x(t) } })
      ),
      h("div", { className: cx("aq-scrub-legend", T.micro) }, h("span", null, h("i", { className: "aq-scrub-tick is-model" }), "model"), h("span", null, h("i", { className: "aq-scrub-tick is-solver" }), "solver"), h("span", null, h("i", { className: "aq-scrub-tick is-team" }), "team"))
    );
  }
  function ExportBar({ confirm, submitted, a }) {
    const T = useT();
    return h(
      "div",
      { className: "aq-export" },
      h(
        "div",
        { className: "aq-export-row" },
        h(Button, { icon: "copy" }, "Copy lat, lng"),
        h(Button, { icon: "download" }, "Export JSON log"),
        submitted ? h(Badge, { tone: "team", icon: "submit", solid: true }, "Submitted 05:52") : h(Button, { variant: "primary", icon: "submit", shortcut: "⇧⏎" }, "Submit answer")
      ),
      confirm && a ? h(
        Dialog,
        { title: "Submit this answer?", inline: true, actions: h(Fragment, null, h(Button, { variant: "quiet" }, "Go back"), h(Button, { variant: "primary", icon: "submit" }, "Submit")) },
        h("div", { className: T.body }, "Sends 10 slots of ", h("span", { className: cx(T.data, "aq-ink1") }, fmtCoord(a.lat, a.lng)), ` (lat, lng), produced at ${fmtMult(a.multiplier)}.`),
        h("div", { className: T.body }, "After submitting, this case is locked; the log is exported with it.")
      ) : null
    );
  }

  // src/extra.tsx
  var extra_exports = {};
  __export(extra_exports, {
    DropZone: () => DropZone,
    FilenameParse: () => FilenameParse,
    LeaderLines: () => LeaderLines,
    MatchView: () => MatchView
  });
  var FN = /^IMG_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_(\d{2})_(\d{3})\.jpe?g$/i;
  function FilenameParse({ file, urban = "unknown", source = "unknown", special, size = [6080, 3040], status, message, editable = true }) {
    const T = useT();
    const m = FN.exec(file);
    const st = status || (!m ? "warning" : size[0] / size[1] !== 2 ? "error" : size[0] !== 6080 ? "warning" : "valid");
    return h(
      "div",
      { className: cx("aq-fn", "is-" + st) },
      h(
        "div",
        { className: "aq-fn-top" },
        h(Icon, { name: st === "valid" ? "file" : st === "warning" ? "warning" : "failed" }),
        m ? h("span", { className: cx("aq-fn-name", T.data) }, h("span", { className: "aq-ink3" }, "IMG_"), h("mark", null, m[1] + m[2] + m[3]), h("span", { className: "aq-ink3" }, "_"), h("mark", null, m[4] + m[5] + m[6]), h("span", { className: "aq-ink3" }, `_${m[7]}_`), h("mark", null, m[8]), h("span", { className: "aq-ink3" }, ".jpg")) : h("span", { className: cx("aq-fn-name", T.data) }, file),
        h("span", { className: cx(T.dataSm, size[0] / size[1] !== 2 ? "aq-c-contra" : size[0] !== 6080 ? "aq-c-cost" : "aq-ink3") }, `${size[0]}×${size[1]}`)
      ),
      h(
        "div",
        { className: "aq-fn-row" },
        m ? h(
          "dl",
          { className: cx("aq-fn-parts", T.micro) },
          h("div", null, h("dt", null, "Date"), h("dd", { className: T.data }, `${m[1]}-${m[2]}-${m[3]}`)),
          h("div", null, h("dt", null, "Time"), h("dd", { className: T.data }, `${m[4]}:${m[5]}:${m[6]} UTC`)),
          h("div", null, h("dt", null, "Shot"), h("dd", { className: T.data }, m[8]))
        ) : null,
        st !== "error" && editable ? h(
          "div",
          { className: "aq-fn-ctl" },
          h(Segmented, { label: "Urban label", value: urban, options: [{ id: "urban", label: "Urban" }, { id: "non-urban", label: "Non-urban" }, { id: "unknown", label: "Unknown" }] }),
          h(Badge, { tone: source === "official" ? "neutral" : "outline" }, `source: ${source}`),
          h(Toggle, { label: "Special One ×3", on: !!special, icon: "special" })
        ) : null
      ),
      message ? h("div", { className: cx("aq-fn-msg", T.body) }, message) : null
    );
  }
  function DropZone({ state = "empty", files = [], count = 6 }) {
    const T = useT();
    return h(
      "div",
      { className: cx("aq-drop", "is-" + state) },
      state === "empty" || state === "dragging" ? h(
        "div",
        { className: "aq-drop-target" },
        h(Icon, { name: "drop" }),
        h("div", { className: T.heading }, state === "dragging" ? `Release to add ${count} panoramas` : "Drop the panoramas here"),
        h("div", { className: cx(T.body, "aq-ink2") }, state === "dragging" ? "Each one becomes its own sealed case." : "One or several 360° JPGs, 2:1 equirectangular. Nothing else can be uploaded."),
        state === "empty" ? h(Button, { icon: "file" }, "Choose files") : null
      ) : h("div", { className: "aq-drop-list" }, files.map((f, i) => h(FilenameParse, { key: i, ...f })))
    );
  }
  function MatchView({ c, refIdx = 0, width = 560, height = 220, lines = 36, showRejected = true }) {
    const T = useT();
    const stage = useDensity() === "stage";
    const sc = sceneFor(c);
    const half = width / 2 - 4;
    const qCam = { pos: [0, 0, 1.7], yaw: 42, fov: 74, w: half, h: height };
    const refCams = [{ pos: [-13, -7, 1.6], yaw: 52, fov: 62, w: half, h: height }, { pos: [16, -6, 1.6], yaw: 18, fov: 66, w: half, h: height }, { pos: [-30, -24, 1.6], yaw: 50, fov: 50, w: half, h: height }];
    const rCam = refCams[refIdx] || refCams[0];
    const ref = c.spot.refs[refIdx];
    const kps = (sc.keypoints || []).filter((_, i) => i % 3 === 0);
    const pairs = [];
    for (const k of kps) {
      const a = perspPoint(k, qCam), b = perspPoint(k, rCam);
      if (a && b && a[0] > 2 && a[0] < half - 2 && b[0] > 2 && b[0] < half - 2 && a[1] > 2 && a[1] < height - 2 && b[1] > 2 && b[1] < height - 2) pairs.push([a, b]);
    }
    const nIn = Math.min(lines, pairs.length);
    const accepted = pairs.slice(0, nIn);
    const rejected = showRejected ? accepted.slice(0, 6).map((p, i) => [p[0], [Math.min(half - 4, Math.abs((p[1][0] + 70 * (i % 2 ? 1 : -1.3)) % half)), Math.min(height - 4, (p[1][1] + 40 + i * 13) % height)]]) : [];
    const lw = stage ? 2 : 1;
    return h(
      "figure",
      { className: "aq-match" },
      h(
        "div",
        { className: "aq-match-h" },
        h("span", { className: T.label }, "Query view"),
        h("span", { className: cx(T.micro, "aq-ink3") }, "from this panorama · yaw 42° · 74°"),
        h("span", { className: cx(T.label, "aq-match-rh") }, `Reference ${ref.id}`),
        h("span", { className: cx(T.micro, "aq-ink3") }, `geotagged · ${fmtDist(ref.dist)} from the candidate`)
      ),
      h(
        "svg",
        { viewBox: `0 0 ${width} ${height}`, width, height, role: "img", "aria-label": `Keypoint matches: ${ref.inliers} inliers of ${ref.matches}` },
        h("g", null, h(PerspScene, { sc, cam: qCam })),
        h("g", { transform: `translate(${half + 8},0)` }, h(PerspScene, { sc, cam: rCam })),
        h("rect", { x: half, y: 0, width: 8, height, className: "aq-match-gap" }),
        rejected.map((p, i) => h("line", { key: "r" + i, x1: p[0][0], y1: p[0][1], x2: p[1][0] + half + 8, y2: p[1][1], className: "aq-match-out", strokeWidth: lw })),
        accepted.map((p, i) => h("g", { key: "a" + i }, h("line", { x1: p[0][0], y1: p[0][1], x2: p[1][0] + half + 8, y2: p[1][1], className: "aq-match-in", strokeWidth: lw }), h("circle", { cx: p[0][0], cy: p[0][1], r: stage ? 3.5 : 2, className: "aq-match-kp" }), h("circle", { cx: p[1][0] + half + 8, cy: p[1][1], r: stage ? 3.5 : 2, className: "aq-match-kp" })))
      ),
      h(
        "figcaption",
        { className: "aq-match-cap" },
        h("span", { className: cx(T.readout, ref.accepted ? "aq-c-support" : "aq-c-contra") }, ref.inliers),
        h("span", { className: cx(T.body, "aq-ink2") }, `inliers of ${ref.matches} matches`),
        h("span", { className: cx("aq-match-k", T.micro) }, h("i", { className: "is-in" }), `accepted (sample of ${nIn})`),
        showRejected ? h("span", { className: cx("aq-match-k", T.micro) }, h("i", { className: "is-out" }), "rejected by geometry") : null,
        h(ModelChip, { name: "ALIKED + LightGlue", actor: "model", size: "sm" })
      )
    );
  }
  function LeaderLines({ links, children, className, style }) {
    const ref = useRef(null);
    const [lines, setLines] = useState([]);
    useEffect(() => {
      const el = ref.current;
      if (!el) return;
      const run = () => {
        const box = el.getBoundingClientRect();
        const out = [];
        for (const [a, b] of links) {
          const A2 = el.querySelector(`[data-leader="${a}"]`) || el.querySelector(`[data-link="${a}"]`), B2 = el.querySelector(`[data-leader="${b}"]`) || el.querySelectorAll(`[data-link="${b}"]`)[0];
          if (!A2 || !B2 || A2 === B2) continue;
          const ra = A2.getBoundingClientRect(), rb = B2.getBoundingClientRect();
          const ax = ra.right < rb.left ? ra.right : ra.left > rb.right ? ra.left : ra.left + ra.width / 2, ay = ra.top + ra.height / 2;
          const bx = rb.left > ra.right ? rb.left : rb.right < ra.left ? rb.right : rb.left + rb.width / 2, by = rb.top + rb.height / 2;
          out.push([ax - box.left, ay - box.top, bx - box.left, by - box.top]);
        }
        setLines(out);
      };
      const id = setTimeout(run, 60);
      window.addEventListener("resize", run);
      return () => {
        clearTimeout(id);
        window.removeEventListener("resize", run);
      };
    }, [JSON.stringify(links)]);
    return h(
      "div",
      { ref, className: cx("aq-leaders", className), style },
      children,
      h("svg", { className: "aq-leaders-svg", "aria-hidden": true }, lines.map((l, i) => {
        const mx = (l[0] + l[2]) / 2;
        return h("g", { key: i }, h("path", { d: `M${l[0]} ${l[1]}C${mx} ${l[1]} ${mx} ${l[3]} ${l[2]} ${l[3]}`, className: "aq-leader-halo" }), h("path", { d: `M${l[0]} ${l[1]}C${mx} ${l[1]} ${mx} ${l[3]} ${l[2]} ${l[3]}`, className: "aq-leader" }), h("circle", { cx: l[0], cy: l[1], r: 3, className: "aq-leader-end" }), h("circle", { cx: l[2], cy: l[3], r: 3, className: "aq-leader-end" }));
      }))
    );
  }

  // src/docs.tsx
  var docs_exports = {};
  __export(docs_exports, {
    Cell: () => Cell,
    Grid: () => Grid,
    Page: () => Page
  });
  function Cell({ label, children, wide, pad = true }) {
    return h("div", { className: cx("aq-spec-cell", wide && "is-wide", !pad && "no-pad") }, label ? h("div", { className: "aq-spec-l console-micro" }, label) : null, h("div", { className: "aq-spec-b" }, children));
  }
  function Grid({ cols = 3, children, gap }) {
    return h("div", { className: "aq-spec-grid", style: { gridTemplateColumns: typeof cols === "number" ? `repeat(${cols}, minmax(0, 1fr))` : cols, gap } }, children);
  }
  function Page({ children, theme, density = "console", pad = true, style }) {
    return h(Density, { value: density, theme, className: cx("aq-spec-page", !pad && "no-pad"), style }, children);
  }

  // src/samples.ts
  var samples_exports = {};
  __export(samples_exports, {
    CASE_A: () => CASE_A,
    CASE_B: () => CASE_B,
    LOG_A: () => LOG_A,
    QUEUE: () => QUEUE,
    ROSTER: () => ROSTER
  });
  var ROSTER = [
    { id: "yoloe", name: "YOLOE-26-L", role: "Open-vocabulary detector", stage: "detect", gb: 1.9, state: "idle" },
    { id: "sam3", name: "SAM 3", role: "Checks each detection box", stage: "detect", gb: 1.2, state: "idle" },
    { id: "ocr", name: "PP-OCRv6-medium", role: "Reads text (CPU)", stage: "read", gb: 0, cpu: true, state: "idle" },
    { id: "lid", name: "Language-ID ×3", role: "Votes pt / gl / es / ca / eu / fr (CPU)", stage: "read", gb: 0, cpu: true, state: "idle" },
    { id: "qwen", name: "Qwen3.5-9B", role: "Vision-language: checklist, landmark guesses, question wording", stage: "describe", gb: 7.4, state: "resident" },
    { id: "gemma", name: "Gemma 4 12B", role: "Fallback vision-language model", stage: "describe", gb: 0, state: "standby" },
    { id: "eomt", name: "EoMT-L", role: "Segmentation: sky, trees, buildings, water", stage: "measure", gb: 1.1, state: "idle" },
    { id: "pvlib", name: "pvlib", role: "Sun position to compass heading (code)", stage: "measure", gb: 0, cpu: true, state: "idle" },
    { id: "pecore", name: "PE-Core", role: "Image embeddings for retrieval and regions", stage: "geo", gb: 0.9, state: "resident" },
    { id: "pigeon", name: "mini-PIGEON", role: "Our region classifier (on PE-Core)", stage: "geo", gb: 0.2, state: "resident" },
    { id: "geoclip", name: "GeoCLIP", role: "Extra location generator", stage: "geo", gb: 0.6, state: "idle" },
    { id: "megaloc", name: "MegaLoc", role: "Place retrieval near candidates", stage: "spot", gb: 0.5, state: "resident" },
    { id: "lightglue", name: "ALIKED + LightGlue", role: "Keypoint matching", stage: "spot", gb: 0.4, state: "running" }
  ];
  var CASE_A_STAGES = [
    { id: "intake", name: "Intake", models: ["Filename parser"], status: "done", dur: 0.1, gb: 0 },
    { id: "views", name: "Views", models: ["py360convert"], status: "done", dur: 1.8, gb: 0 },
    { id: "detect", name: "Detect", optional: true, models: ["YOLOE-26-L", "SAM 3"], status: "done", dur: 6.2, gb: 3.1 },
    { id: "read", name: "Read", models: ["PP-OCRv6-medium", "Language-ID ×3"], status: "done", dur: 4.9, gb: 0, cpu: true },
    { id: "describe", name: "Describe", models: ["Qwen3.5-9B"], status: "done", dur: 22.4, gb: 7.4 },
    { id: "measure", name: "Measure", optional: true, models: ["EoMT-L", "pvlib"], status: "done", dur: 5.1, gb: 1.1 },
    { id: "geo", name: "Pixel geolocation", models: ["PE-Core", "mini-PIGEON", "GeoCLIP"], status: "done", dur: 9.8, gb: 1.7 },
    { id: "names", name: "Name lookup", models: ["OSM · Wikidata · GeoNames index"], status: "done", dur: 0.6, gb: 0 },
    { id: "fusion", name: "Fusion", models: ["Solver (code)"], status: "done", dur: 0.2, gb: 0, solver: true },
    { id: "ask", name: "Ask", models: ["Solver (code)", "Qwen3.5-9B"], status: "done", dur: 1.4, gb: 0, note: "Answered A · ×0.95" },
    { id: "spot", name: "Exact spot", optional: true, models: ["MegaLoc", "ALIKED + LightGlue"], status: "running", dur: 31, deadline: 60, gb: 2.6 },
    { id: "answer", name: "Answer", models: ["Solver (code)"], status: "queued", dur: null, gb: 0, solver: true }
  ];
  var CASE_A = {
    id: "A",
    label: "Case 3",
    file: "IMG_20260115_143012_00_204.jpg",
    date: "2026-01-15",
    time: "14:30:12",
    shot: 204,
    urban: "urban",
    urbanSource: "official",
    special: false,
    size: [6080, 3040],
    run: { used: 340, budget: 480, session: 1395, sessionBudget: 3600, gpu: 12.6, gpuMax: 16, multiplier: 0.95, expected: 12500, expectedRange: [10900, 13400] },
    multiplierHistory: [{ t: 0, m: 1, what: "Run started" }, { t: 212, m: 0.95, what: "Answered question 1 (A) · ×0.95" }],
    stages: CASE_A_STAGES,
    scene: "urban",
    yawToBearing: 64,
    yawToBearingErr: 12,
    detections: [
      { id: "d1", label: "shop sign", score: 0.88, yaw: 38, pitch: 6, w: 9, h: 3.2, kept: true },
      { id: "d2", label: "shop sign", score: 0.81, yaw: 212.5, pitch: -3.1, w: 6, h: 2.6, kept: true },
      { id: "d3", label: "balcony", score: 0.77, yaw: 300, pitch: 14, w: 7, h: 5, kept: true },
      { id: "d4", label: "azulejo panel", score: 0.74, yaw: 330, pitch: 8, w: 10, h: 12, kept: true },
      { id: "d5", label: "bollard", score: 0.69, yaw: 252, pitch: -14, w: 2, h: 5, kept: true },
      { id: "d6", label: "street lamp", score: 0.66, yaw: 96, pitch: 10, w: 2, h: 12, kept: true },
      { id: "d7", label: "licence plate", score: 0.31, sam: 0.02, yaw: 268, pitch: -12, w: 3, h: 1.4, kept: false },
      { id: "d8", label: "church", score: 0.28, sam: 0.04, yaw: 150, pitch: 4, w: 6, h: 8, kept: false },
      { id: "d9", label: "granary", score: 0.22, sam: 0.01, yaw: 70, pitch: -2, w: 5, h: 3, kept: false }
    ],
    detectSummary: { kept: 17, rejected: 3 },
    texts: [
      { id: "t1", text: "CAFÉ", conf: 0.97, yaw: 38, pitch: 6.5, w: 7, h: 2.6 },
      { id: "t2", text: "4050-253", conf: 0.94, yaw: 212.5, pitch: -3.1, w: 4.2, h: 1.6, kind: "postcode", country: "PT" },
      { id: "t3", text: "22• ••• •••", conf: 0.71, yaw: 289, pitch: 2, w: 5, h: 1.4, kind: "phone", country: "PT" }
    ],
    language: [{ id: "pt", v: 0.93 }, { id: "gl", v: 0.04 }, { id: "es", v: 0.02 }, { id: "ca", v: 0 }, { id: "eu", v: 0 }, { id: "fr", v: 0.01 }],
    checklist: [
      { item: "Granite masonry", answer: "yes" },
      { item: "Blue-and-white azulejo façade", answer: "yes" },
      { item: "Wrought-iron balconies", answer: "yes" },
      { item: "River visible", answer: "yes" },
      { item: "Calçada portuguesa pavement", answer: "not_visible" },
      { item: "Vegetation", answer: "not_visible" }
    ],
    shares: [{ id: "sky", v: 0.31 }, { id: "building", v: 0.44 }, { id: "road", v: 0.17 }, { id: "water", v: 0.05 }, { id: "tree", v: 0.03 }],
    sun: { azimuth: 205, elevation: 22, yaw: 141, bearingOfYaw0: 64, err: 12 },
    water: { bearing: 200 },
    regions: [{ name: "Porto", v: 0.47, lo: 0.36, hi: 0.58 }, { name: "Braga", v: 0.12, lo: 0.06, hi: 0.19 }, { name: "Lisboa", v: 0.11, lo: 0.05, hi: 0.18 }, { name: "Viana do Castelo", v: 0.06 }, { name: "Galicia (ES)", v: 0.05 }, { name: "Other", v: 0.19, other: true }],
    neighbours: [
      { id: "n1", place: "Porto · Cais da Ribeira", lat: 41.1405, lng: -8.6122, sim: 0.83 },
      { id: "n2", place: "Porto · Miragaia", lat: 41.1432, lng: -8.6203, sim: 0.79 },
      { id: "n3", place: "Vila Nova de Gaia · Cais", lat: 41.1372, lng: -8.6125, sim: 0.77 },
      { id: "n4", place: "Porto · Ribeira", lat: 41.1411, lng: -8.6141, sim: 0.74 },
      { id: "n5", place: "Lisboa · Alfama", lat: 38.7114, lng: -9.13, sim: 0.61 }
    ],
    // candidates after first fusion (before question)
    candidatesBefore: [
      { id: "ribeira", rank: 1, name: "Porto · Ribeira", level: "spot", v: 0.52, lo: 0.41, hi: 0.63, delta: 0.09, sup: 9, con: 0, lat: 41.1407, lng: -8.6131 },
      { id: "gaia", rank: 2, name: "Vila Nova de Gaia · riverside", level: "town", v: 0.21, lo: 0.13, hi: 0.3, delta: -0.02, sup: 6, con: 1, lat: 41.1372, lng: -8.6118 },
      { id: "miragaia", rank: 3, name: "Porto · Miragaia", level: "spot", v: 0.12, lo: 0.07, hi: 0.19, delta: 0.03, sup: 7, con: 1, lat: 41.1432, lng: -8.6203 },
      { id: "alfama", rank: 4, name: "Lisboa · Alfama", level: "spot", v: 0.05, lo: 0.02, hi: 0.09, delta: -0.06, sup: 2, con: 3, lat: 38.7114, lng: -9.13, contradictedBy: "postcode 4050-253" },
      { id: "other", rank: 5, name: "Other", level: "area", v: 0.1, lo: 0.05, hi: 0.17, other: true }
    ],
    candidatesAfter: [
      { id: "ribeira", rank: 1, name: "Porto · Ribeira", level: "spot", v: 0.69, lo: 0.58, hi: 0.78, delta: 0.17, sup: 10, con: 0, lat: 41.1407, lng: -8.6131 },
      { id: "miragaia", rank: 2, name: "Porto · Miragaia", level: "spot", v: 0.21, lo: 0.13, hi: 0.29, delta: 0.09, sup: 8, con: 1, lat: 41.1432, lng: -8.6203 },
      { id: "gaia", rank: 3, name: "Vila Nova de Gaia · riverside", level: "town", v: 0.03, lo: 0.01, hi: 0.07, delta: -0.18, sup: 6, con: 2, lat: 41.1372, lng: -8.6118, keptNote: "kept in case the answer was wrong" },
      { id: "other", rank: 4, name: "Other", level: "area", v: 0.07, lo: 0.03, hi: 0.12, other: true }
    ],
    ruledOut: [{ name: "Galicia (ES)", level: "region", reason: "Portuguese postcode format and Portuguese spelling", by: ["e2", "e4"] }],
    funnel: [
      { level: "Country", name: "Portugal", v: 0.95 },
      { level: "Region", name: "Norte · Porto district", v: 0.86 },
      { level: "Town", name: "Porto", v: 0.81 },
      { level: "Spot", name: "Ribeira", v: 0.69 }
    ],
    question: {
      id: "q1",
      text: "Which zone contains the camera?",
      gain: 0.19,
      breakEven: 0.0526,
      cost: 0.95,
      wordedBy: "Qwen3.5-9B",
      chosenBy: "Solver",
      scope: ["Portugal", "Porto district"],
      options: [
        { key: "A", label: "Porto riverfront, Ribeira to Miragaia", reason: "Postcode area 4050 and the river to the south-west", chips: ["e2", "e9"], point: [41.1415, -8.6165] },
        { key: "B", label: "Vila Nova de Gaia riverfront", reason: "Same river, same 22 phone prefix; postcode would be 4400", chips: ["e3", "e9"], point: [41.1368, -8.61] },
        { key: "C", label: "Rest of Porto district", reason: "Granite and the 22 prefix fit, the river view narrows it", chips: ["e6", "e3"], point: [41.18, -8.58] },
        { key: "D", label: "None of these (anywhere else in PT, ES or FR)", reason: "Covers everywhere outside A to C, so a wrong scope can be corrected", chips: [], point: null, none: true }
      ],
      answer: "A",
      answeredAt: 212
    },
    spot: {
      refs: [
        { id: "r1", inliers: 412, matches: 530, dist: 38, lat: 41.14094, lng: -8.6129, accepted: true },
        { id: "r2", inliers: 118, matches: 260, dist: 96, lat: 41.14051, lng: -8.61401, accepted: true },
        { id: "r3", inliers: 36, matches: 190, dist: 142, lat: 41.14152, lng: -8.61198, accepted: false, reason: "Inliers below 50" }
      ],
      camera: { lat: 41.14081, lng: -8.61315, r: 22, rSource: "source GPS plus viewpoint offset" },
      offset: 17
    },
    answer: { lat: 41.14081, lng: -8.61315, role: "camera", method: "reference_camera", r: 22, rSource: "estimated offset", multiplier: 0.95, expected: 12500, max: 16050.52, mostLikely: true }
  };
  CASE_A.evidence = [
    {
      id: "e2",
      kind: "text",
      stage: "read",
      actor: "model",
      model: "PP-OCRv6-medium",
      obs: "4050-253",
      conf: 0.94,
      ref: "t2",
      inference: "a Portuguese postcode; area 4050 is central Porto",
      estimate: { label: "Porto", v: 0.47 },
      pol: { ribeira: 1, miragaia: 1, gaia: -1, alfama: -1 },
      t: 41.2
    },
    {
      id: "e3",
      kind: "text",
      stage: "read",
      actor: "model",
      model: "PP-OCRv6-medium",
      obs: "22• ••• •••",
      conf: 0.71,
      ref: "t3",
      inference: "a Portuguese landline; prefix 22 is Porto and Gaia",
      pol: { ribeira: 1, miragaia: 1, gaia: 1, alfama: -1 },
      t: 41.9
    },
    {
      id: "e1",
      kind: "text",
      stage: "read",
      actor: "model",
      model: "PP-OCRv6-medium",
      obs: "CAFÉ",
      conf: 0.97,
      ref: "t1",
      inference: "the same word in pt, es and fr — no help on its own",
      pol: {},
      t: 40.8
    },
    {
      id: "e4",
      kind: "language",
      stage: "read",
      actor: "model",
      model: "Language-ID ×3",
      obs: "pt 0.93 · gl 0.04 · es 0.02 · fr 0.01",
      conf: 0.93,
      inference: "Portuguese spelling, not Galician",
      pol: { ribeira: 1, miragaia: 1, gaia: 1, alfama: 1 },
      t: 43
    },
    {
      id: "e5",
      kind: "object",
      stage: "detect",
      actor: "model",
      model: "YOLOE-26-L · SAM 3",
      obs: "17 boxes kept, 3 rejected",
      conf: null,
      inference: "signs, balconies, an azulejo panel; no licence plate after all",
      pol: {},
      t: 33.5
    },
    {
      id: "e6",
      kind: "checklist",
      stage: "describe",
      actor: "model",
      model: "Qwen3.5-9B",
      obs: "Granite masonry: yes",
      conf: null,
      inference: "granite is the northern building stone; Lisbon builds in limestone",
      pol: { ribeira: 1, miragaia: 1, gaia: 1, alfama: -1 },
      t: 66
    },
    {
      id: "e7",
      kind: "checklist",
      stage: "describe",
      actor: "model",
      model: "Qwen3.5-9B",
      obs: "Calçada portuguesa: not_visible",
      conf: null,
      inference: "pavement out of view; says nothing either way",
      pol: {},
      notVisible: true,
      t: 66.4
    },
    {
      id: "e9",
      kind: "checklist",
      stage: "describe",
      actor: "model",
      model: "Qwen3.5-9B",
      obs: "River visible: yes",
      conf: null,
      inference: "a riverfront; narrows to the banks of the Douro",
      pol: { ribeira: 1, miragaia: 1, gaia: 1, alfama: 0 },
      t: 66.8
    },
    {
      id: "e10",
      kind: "measure",
      stage: "measure",
      actor: "model",
      model: "EoMT-L",
      obs: "sky 31% · building 44% · road 17% · water 5% · tree 3%",
      conf: null,
      inference: "a dense waterside street; water at a bearing of ~200°",
      pol: { ribeira: 1, gaia: 0, miragaia: 1 },
      t: 72
    },
    {
      id: "e11",
      kind: "sun",
      stage: "measure",
      actor: "model",
      model: "pvlib · EoMT-L",
      obs: "sun at yaw 141°, elevation 22°",
      conf: null,
      inference: "with 14:30 UTC on 15 Jan, image yaw 0 points to bearing 64° ± 12°; the river lies south-west",
      pol: { ribeira: 1, gaia: -1, miragaia: 1 },
      t: 73.1
    },
    {
      id: "e12",
      kind: "neighbour",
      stage: "geo",
      actor: "model",
      model: "PE-Core · kNN",
      obs: "5 nearest reference photos: 4 Porto/Gaia, 1 Lisboa",
      conf: null,
      group: "pecore",
      inference: "the closest-looking photos were taken on the Porto riverfront",
      estimate: { label: "Porto", v: 0.62 },
      pol: { ribeira: 1, miragaia: 1, gaia: 1, alfama: 0 },
      t: 82
    },
    {
      id: "e13",
      kind: "region",
      stage: "geo",
      actor: "model",
      model: "mini-PIGEON (on PE-Core)",
      obs: "Porto 0.47 · Braga 0.12 · Lisboa 0.11",
      conf: null,
      group: "pecore",
      inference: "pixels alone point north, Porto first",
      estimate: { label: "Porto", v: 0.47 },
      pol: { ribeira: 1, miragaia: 1, gaia: 1, alfama: -1 },
      t: 83.4
    },
    {
      id: "e14",
      kind: "name",
      stage: "names",
      actor: "model",
      model: "OSM · Wikidata · GeoNames",
      obs: '"4050": postcode area · "Cais da Ribeira": landmark',
      conf: null,
      inference: "an area coordinate and a landmark coordinate, not a camera position",
      pol: { ribeira: 1 },
      sub: "local index, offline",
      t: 85
    },
    {
      id: "e15",
      kind: "contradiction",
      stage: "fusion",
      actor: "solver",
      model: "Solver (code)",
      obs: 'VLM landmark guess "Alfama" (0.18) vs postcode 4050-253',
      conf: null,
      inference: "the postcode outweighs a low-confidence landmark guess; Alfama stays, its range widens",
      pol: { alfama: -1 },
      between: ["e2", "e6"],
      t: 86.1
    }
  ];
  CASE_A.groups = [{ id: "pecore", label: "One voice: PE-Core encoder", members: ["e12", "e13"], cap: 0.35, note: "Neighbours and regions share one image encoder, so fusion caps their combined weight" }];
  CASE_A.matrix = {
    candidates: ["ribeira", "gaia", "miragaia", "alfama"],
    names: { ribeira: "Ribeira", gaia: "Gaia", miragaia: "Miragaia", alfama: "Alfama" }
  };
  var CASE_B = {
    id: "B",
    label: "Case 4",
    file: "IMG_20260512_110547_00_318.jpg",
    date: "2026-05-12",
    time: "11:05:47",
    shot: 318,
    urban: "non-urban",
    urbanSource: "official",
    special: false,
    size: [6080, 3040],
    run: { used: 298, budget: 480, session: 1880, sessionBudget: 3600, gpu: 11.8, gpuMax: 16, multiplier: 1, expected: 11300, expectedRange: [8200, 12900] },
    multiplierHistory: [{ t: 0, m: 1, what: "Run started" }, { t: 188, m: 1, what: "Skipped question 1 · free · nothing changed" }],
    scene: "rural",
    yawToBearing: 312,
    yawToBearingErr: 15,
    stages: [
      { id: "intake", name: "Intake", models: ["Filename parser"], status: "done", dur: 0.1 },
      { id: "views", name: "Views", models: ["py360convert"], status: "done", dur: 1.7 },
      { id: "detect", name: "Detect", optional: true, models: ["YOLOE-26-L", "SAM 3"], status: "skipped", note: "Dropped for non-urban scenes" },
      { id: "read", name: "Read", models: ["PP-OCRv6-medium", "Language-ID ×3"], status: "done", dur: 3.2, note: "No text found" },
      { id: "describe", name: "Describe", models: ["Qwen3.5-9B"], status: "done", dur: 19.6, gb: 7.4 },
      { id: "measure", name: "Measure", optional: true, models: ["EoMT-L", "pvlib"], status: "done", dur: 4.8, gb: 1.1 },
      { id: "geo", name: "Pixel geolocation", models: ["PE-Core", "mini-PIGEON", "GeoCLIP"], status: "done", dur: 10.2, gb: 1.7 },
      { id: "names", name: "Name lookup", models: ["OSM · Wikidata · GeoNames index"], status: "skipped", note: "Nothing to look up" },
      { id: "fusion", name: "Fusion", models: ["Solver (code)"], status: "done", dur: 0.2, solver: true },
      { id: "ask", name: "Ask", models: ["Solver (code)", "Qwen3.5-9B"], status: "done", dur: 1.1, note: "Skipped · free" },
      { id: "spot", name: "Exact spot", optional: true, models: ["MegaLoc", "ALIKED + LightGlue"], status: "skipped", note: "Not run for non-urban scenes" },
      { id: "answer", name: "Answer", models: ["Solver (code)"], status: "done", dur: 0.1, solver: true }
    ],
    texts: [],
    language: null,
    checklist: [
      { item: "Cork oak (stripped trunks, painted digit)", answer: "yes" },
      { item: "Holm oak", answer: "yes" },
      { item: "Unpaved track", answer: "yes" },
      { item: "Whitewashed farmhouse, blue trim (distant)", answer: "yes" },
      { item: "Red-brown soil", answer: "yes" },
      { item: "Terrain", answer: "gently rolling" },
      { item: "Road signs", answer: "not_visible" }
    ],
    shares: [{ id: "sky", v: 0.47 }, { id: "grass", v: 0.24 }, { id: "tree", v: 0.22 }, { id: "ground", v: 0.06 }, { id: "building", v: 0.01 }],
    sun: { azimuth: 130, elevation: 61, yaw: 178, bearingOfYaw0: 312, err: 15 },
    regions: [{ name: "Évora", v: 0.31, lo: 0.22, hi: 0.41 }, { name: "Beja", v: 0.24, lo: 0.16, hi: 0.33 }, { name: "Portalegre", v: 0.17, lo: 0.1, hi: 0.25 }, { name: "Extremadura (ES)", v: 0.12, lo: 0.06, hi: 0.2 }, { name: "Setúbal", v: 0.09 }, { name: "Other", v: 0.07, other: true }],
    candidates: [
      { id: "evora", rank: 1, name: "Alentejo Central (Évora)", level: "region", v: 0.33, lo: 0.22, hi: 0.44, delta: 0.02, sup: 6, con: 0, lat: 38.57, lng: -7.91 },
      { id: "beja", rank: 2, name: "Baixo Alentejo (Beja)", level: "region", v: 0.25, lo: 0.16, hi: 0.35, delta: 0.01, sup: 5, con: 0, lat: 37.95, lng: -7.87 },
      { id: "portalegre", rank: 3, name: "Alto Alentejo (Portalegre)", level: "region", v: 0.17, lo: 0.1, hi: 0.26, delta: 0, sup: 5, con: 0, lat: 39.2, lng: -7.6 },
      { id: "extremadura", rank: 4, name: "Extremadura (ES) · dehesa", level: "region", v: 0.13, lo: 0.06, hi: 0.22, delta: 0, sup: 5, con: 0, lat: 38.9, lng: -6.4, lookalike: true },
      { id: "other", rank: 5, name: "Other", level: "area", v: 0.12, lo: 0.06, hi: 0.19, other: true }
    ],
    ruledOut: [],
    lookalikes: [{ a: "Alentejo montado (PT)", b: "Extremadura dehesa (ES)", shared: ["cork oak", "holm oak", "red-brown soil", "rolling terrain", "whitewashed farmhouse"], differ: "Only text or a road sign would separate them; none is visible" }],
    question: {
      id: "q1",
      text: "Which zone contains the camera?",
      gain: 0.11,
      breakEven: 0.0526,
      cost: 0.95,
      wordedBy: "Qwen3.5-9B",
      chosenBy: "Solver",
      scope: ["Portugal · Spain · France", "Alentejo"],
      options: [
        { key: "A", label: "Alto Alentejo", reason: "Cork and holm oak on rolling ground; granite outcrops would fit", chips: ["b1", "b2"], point: [39.25, -7.55], region: "PT-12" },
        { key: "B", label: "Alentejo Central", reason: "Montado with red-brown soil; the highest region estimate", chips: ["b1", "b5"], point: [38.62, -7.85], region: "PT-07" },
        { key: "C", label: "Baixo Alentejo and Alentejo Litoral", reason: "Open montado, whitewash with blue trim", chips: ["b4", "b5"], point: [37.95, -7.95], region: "PT-02" },
        { key: "D", label: "Anywhere else in PT, ES or FR", reason: "Covers Extremadura dehesa, which looks the same", chips: ["b6"], point: null, none: true }
      ],
      answer: null,
      skippedAt: 188
    },
    answer: {
      lat: 38.6061,
      lng: -7.8412,
      role: "area",
      method: "geographic_cell",
      r: 4200,
      rSource: "geometric bound",
      multiplier: 1,
      expected: 11300,
      max: 16050.52,
      mostLikely: false,
      why: "The cell centre between Évora and Beja scores higher in expectation than Évora alone: on the non-Urban curve a 40 km miss still keeps 20%, so hedging toward the second candidate pays."
    }
  };
  CASE_B.evidence = [
    { id: "b0", kind: "text", stage: "read", actor: "model", model: "PP-OCRv6-medium", obs: "No text found", conf: null, inference: "no signs, plates or painted words in any of the 10 views", pol: {}, empty: true, t: 9 },
    { id: "b1", kind: "checklist", stage: "describe", actor: "model", model: "Qwen3.5-9B", obs: "Cork oak: yes (stripped trunks, painted digit)", conf: null, inference: "montado or dehesa: southern Portugal or western Spain", pol: { evora: 1, beja: 1, portalegre: 1, extremadura: 1 }, t: 28 },
    { id: "b2", kind: "checklist", stage: "describe", actor: "model", model: "Qwen3.5-9B", obs: "Holm oak: yes", conf: null, inference: "dry interior, either side of the border", pol: { evora: 1, beja: 1, portalegre: 1, extremadura: 1 }, t: 28.4 },
    { id: "b4", kind: "checklist", stage: "describe", actor: "model", model: "Qwen3.5-9B", obs: "Whitewashed farmhouse with blue trim: yes (distant)", conf: null, inference: "Alentejo vernacular, also found in Extremadura", pol: { evora: 1, beja: 1, portalegre: 1, extremadura: 0 }, t: 28.9 },
    { id: "b5", kind: "checklist", stage: "describe", actor: "model", model: "Qwen3.5-9B", obs: "Red-brown soil: yes", conf: null, inference: "common across the Alentejo plain", pol: { evora: 1, beja: 1, portalegre: 0, extremadura: 1 }, t: 29.2 },
    { id: "b6", kind: "checklist", stage: "describe", actor: "model", model: "Qwen3.5-9B", obs: "Road signs: not_visible", conf: null, inference: "can't tell the country from signage", pol: {}, notVisible: true, t: 29.6 },
    { id: "b7", kind: "sun", stage: "measure", actor: "model", model: "pvlib · EoMT-L", obs: "sun at yaw 178°, elevation 61°", conf: null, inference: "image yaw 0 points to bearing 312° ± 15°", pol: {}, t: 36 },
    { id: "b8", kind: "region", stage: "geo", actor: "model", model: "mini-PIGEON (on PE-Core)", obs: "Évora 0.31 · Beja 0.24 · Portalegre 0.17 · Extremadura 0.12", conf: null, group: "pecore", inference: "Alentejo first; Spain not excluded", estimate: { label: "Évora", v: 0.31 }, pol: { evora: 1, beja: 1, portalegre: 1, extremadura: 1 }, t: 47 }
  ];
  CASE_B.matrix = { candidates: ["evora", "beja", "portalegre", "extremadura"], names: { evora: "Évora", beja: "Beja", portalegre: "Portalegre", extremadura: "Extremadura" } };
  CASE_B.groups = [{ id: "pecore", label: "One voice: PE-Core encoder", members: ["b8"], cap: 0.35 }];
  var QUEUE = [
    { label: "Case 1", status: "submitted", multiplier: 1, expected: 13900, used: 262 },
    { label: "Case 2", status: "done", multiplier: 0.95, expected: 9800, used: 431 },
    { label: "Case 3", status: "needs-answer", multiplier: 1, expected: 9100, used: 205, current: true, gain: 0.19 },
    { label: "Case 4", status: "processing", stage: "Describe", elapsed: 64 },
    { label: "Case 5", status: "waiting" },
    { label: "Special One", status: "waiting", special: true }
  ];
  var LOG_A = [
    { t: 0, type: "run.started", actor: "solver", text: "New conversation · empty evidence · nothing carried over" },
    { t: 0.1, type: "stage.finished", stage: "intake", actor: "solver", text: "2026-01-15 14:30:12 UTC · shot 204 · Urban (official)" },
    { t: 1.9, type: "stage.finished", stage: "views", actor: "model", model: "py360convert", text: "8 views of 45°, sky, ground; photographer mask 18%" },
    { t: 27.3, type: "evidence.added", stage: "detect", actor: "model", model: "YOLOE-26-L", text: "20 boxes proposed" },
    { t: 33.5, type: "evidence.added", stage: "detect", actor: "model", model: "SAM 3", text: "3 boxes rejected (licence plate 0.31, SAM 0.02)" },
    { t: 40.8, type: "evidence.added", stage: "read", actor: "model", model: "PP-OCRv6-medium", text: '"CAFÉ" 0.97' },
    { t: 41.2, type: "evidence.added", stage: "read", actor: "model", model: "PP-OCRv6-medium", text: '"4050-253" 0.94 · postcode · PT' },
    { t: 43, type: "evidence.added", stage: "read", actor: "model", model: "Language-ID ×3", text: "pt 0.93 · gl 0.04 · es 0.02" },
    { t: 66, type: "evidence.added", stage: "describe", actor: "model", model: "Qwen3.5-9B", text: "Granite masonry: yes" },
    { t: 73.1, type: "evidence.added", stage: "measure", actor: "model", model: "pvlib", text: "Yaw 0 points to bearing 64° ± 12°" },
    { t: 83.4, type: "evidence.added", stage: "geo", actor: "model", model: "mini-PIGEON", text: "Porto 0.47 · Braga 0.12 · Lisboa 0.11" },
    { t: 86.3, type: "candidates.updated", stage: "fusion", actor: "solver", text: "Ribeira 0.52 · Gaia 0.21 · Miragaia 0.12 · Galicia ruled out" },
    { t: 86.4, type: "output.produced", stage: "answer", actor: "solver", text: "First answer 41.14070, −8.61310 · ± 180 m · ×1.00" },
    { t: 88, type: "question.asked", stage: "ask", actor: "solver", text: "Which zone contains the camera? · gain +19% vs 5.26%" },
    { t: 212, type: "question.answered", stage: "ask", actor: "team", text: "A · Porto riverfront · ×0.95" },
    { t: 212.6, type: "candidates.updated", stage: "fusion", actor: "solver", text: "Ribeira 0.69 · Miragaia 0.21 · Gaia 0.03" },
    { t: 309, type: "stage.started", stage: "spot", actor: "model", model: "MegaLoc", text: "3 reference photos within 150 m" },
    { t: 331.5, type: "evidence.added", stage: "spot", actor: "model", model: "ALIKED + LightGlue", text: "Inliers 412 / 118 / 36" },
    { t: 340, type: "output.produced", stage: "answer", actor: "solver", text: "41.14081, −8.61315 · ± 22 m · ×0.95" }
  ];
  CASE_A.heatCountry = [{ lat: 41.15, lng: -8.61, w: 0.95, s: 0.22 }, { lat: 41.55, lng: -8.42, w: 0.38, s: 0.2 }, { lat: 38.72, lng: -9.14, w: 0.36, s: 0.2 }, { lat: 41.7, lng: -8.8, w: 0.22, s: 0.18 }, { lat: 42.4, lng: -8.6, w: 0.22, s: 0.3 }];
  CASE_A.heatTown = [{ lat: 41.1409, lng: -8.6131, w: 0.95, s: 11e-4 }, { lat: 41.137, lng: -8.6118, w: 0.55, s: 12e-4 }, { lat: 41.1434, lng: -8.6205, w: 0.5, s: 1e-3 }];
  CASE_A.viewCountry = { lat: 40.4, lng: -5.2, span: 16 };
  CASE_A.viewTown = { lat: 41.1405, lng: -8.615, span: 0.03 };
  CASE_A.viewSpot = { lat: 41.1409, lng: -8.6132, span: 62e-4 };
  CASE_A.zones = [
    { key: "A", poly: [[41.1411, -8.6235], [41.1452, -8.6235], [41.145, -8.608], [41.1404, -8.608], [41.1404, -8.614], [41.141, -8.62]], point: [41.1415, -8.6165], label: "A · Porto riverfront" },
    { key: "B", poly: [[41.1381, -8.6235], [41.1384, -8.614], [41.1386, -8.608], [41.1352, -8.608], [41.1347, -8.6235]], point: [41.1368, -8.61], label: "B · Gaia riverfront" },
    { key: "C", rest: true, point: [41.1318, -8.6268], label: "C · rest of Porto district" }
  ];
  CASE_B.heat = [{ lat: 38.57, lng: -7.91, w: 0.8, s: 0.33 }, { lat: 37.95, lng: -7.87, w: 0.66, s: 0.33 }, { lat: 39.2, lng: -7.6, w: 0.5, s: 0.28 }, { lat: 38.9, lng: -6.4, w: 0.46, s: 0.38 }, { lat: 38.3, lng: -8.6, w: 0.3, s: 0.24 }];
  CASE_B.view = { lat: 38.55, lng: -7.4, span: 5.2 };
  CASE_B.zones = [
    { key: "A", region: "PT-12", point: [39.25, -7.55], label: "A · Alto Alentejo" },
    { key: "B", region: "PT-07", point: [38.62, -7.85], label: "B · Alentejo Central" },
    { key: "C", region: "PT-02", point: [37.92, -7.95], label: "C · Baixo Alentejo" },
    { key: "D", rest: true, point: null, label: "D · anywhere else in PT, ES or FR" }
  ];

  // src/screens.tsx
  var screens_exports = {};
  __export(screens_exports, {
    Concept: () => Concept,
    MotionAsk: () => MotionAsk,
    MotionDetect: () => MotionDetect,
    MotionExactSpot: () => MotionExactSpot,
    MotionFusion: () => MotionFusion,
    MotionPinpoint: () => MotionPinpoint,
    ScreenCaseReport: () => ScreenCaseReport,
    ScreenExactSpot: () => ScreenExactSpot,
    ScreenFinalAnswer: () => ScreenFinalAnswer,
    ScreenIntake: () => ScreenIntake,
    ScreenQuestion: () => ScreenQuestion,
    ScreenQuestionOutcomes: () => ScreenQuestionOutcomes,
    ScreenQueue: () => ScreenQueue,
    ScreenRunConsole: () => ScreenRunConsole,
    ScreenSystemStates: () => ScreenSystemStates,
    StageFinal: () => StageFinal,
    StageOpening: () => StageOpening,
    StageQuestion: () => StageQuestion,
    StageRun: () => StageRun
  });
  var A = CASE_A;
  var B = CASE_B;
  var KEYS_RUN = [{ k: "J/K", label: "next / previous evidence" }, { k: "L", label: "layers" }, { k: "V", label: "strip / 360° view" }, { k: "M", label: "map focus" }, { k: "C", label: "cue" }, { k: "⇧⏎", label: "submit" }];
  var KEYS_Q = [{ k: "1–4", label: "answer (×0.95)" }, { k: "S", label: "skip (free)" }, { k: "O", label: "copy all links" }, { k: "J/K", label: "move between options" }];
  var cands = (list) => list.filter((c) => !c.other).map((c) => ({ id: c.id, rank: c.rank, lat: c.lat, lng: c.lng, name: c.name.split(" · ")[1] || c.name }));
  var ev = (c, id) => c.evidence.find((e) => e.id === id);
  var Panel = ({ title, aside, children, className, style }) => h("section", { className: cx("aq-panel", className), style }, title ? h("header", { className: "aq-panel-h" }, h("span", { className: "console-title" }, title), aside || null) : null, children);
  function ScreenIntake() {
    const files = [
      { file: A.file, urban: "urban", source: "official" },
      { file: "IMG_20260512_110547_00_318.jpg", urban: "non-urban", source: "official" },
      { file: "IMG_20250125_144630_00_319.jpg", urban: "urban", source: "inferred" },
      { file: "IMG_20260911_125512_00_749.jpg", size: [5760, 2880], urban: "non-urban", source: "inferred", message: "Not 6080×3040 — accepted as 2:1, flagged in the log." },
      { file: "IMG_20260605_092457_00_064.jpg", urban: "unknown", source: "unknown", special: true },
      { file: "pano_final.jpg", urban: "unknown", source: "unknown", message: "Filename does not parse: date, time and shot unknown, so the sun cannot fix north." }
    ];
    return h(
      Density,
      { value: "console", className: "aq-screen", style: { width: 1440, height: 900 } },
      h(
        "header",
        { className: "aq-runbar" },
        h("div", { className: "aq-runbar-wm" }, h(Wordmark, { size: 22 })),
        h("span", { className: "console-heading" }, "New session"),
        h(Timer, { label: "Session", used: 0, budget: 3600, compact: true }),
        h(GpuMeter, { used: 9.4, compact: true }),
        h("div", { className: "aq-runbar-sys" }, h(SystemBadge, { kind: "worker-online" }), h(SystemBadge, { kind: "tiles-offline" }))
      ),
      h(
        "div",
        { className: "aq-intake" },
        h(
          "div",
          { className: "aq-intake-main" },
          h("div", { className: "aq-intake-title" }, h("h1", { className: "narrative-title" }, "Six panoramas, six sealed cases"), h("p", { className: "console-body aq-ink2" }, "Each file becomes its own case with a new model conversation and empty evidence. Mark the Special One; set the Urban label where it is known.")),
          h(DropZone, { state: "valid", files })
        ),
        h(
          "aside",
          { className: "aq-intake-side" },
          h(CleanStateCheck, { caseLabel: "every case", items: [{ label: "New model conversation per case", ok: true }, { label: "Evidence file starts empty", ok: true }, { label: "Nothing carried over between cases", ok: true }, { label: "Queue never groups by date", ok: true }] }),
          h(ModelRoster, { models: ROSTER, compact: true }),
          h("div", { className: "aq-intake-go" }, h("div", { className: "console-body aq-ink2" }, "6 files · 1 flagged size · 1 unparsed name · Special One: case 5"), h(Button, { variant: "primary", icon: "play", shortcut: "⏎" }, "Start the run"))
        )
      )
    );
  }
  function ScreenRunConsole() {
    const run = { ...A, run: A.run };
    const evidence = ["e2", "e3", "e6"].map((id) => ev(A, id));
    return h(
      Density,
      { value: "console", className: "aq-screen", style: { width: 1440, height: 900 } },
      h(RunBar, { c: run }),
      h(
        LeaderLines,
        { links: [["e2", "t2"], ["e2", "area-4050"]], className: "aq-console" },
        h(
          "div",
          { className: "aq-col-pano" },
          h(
            Panel,
            { title: "Panorama", aside: h("span", { className: "console-micro aq-ink3" }, `${A.file} · 6080×3040`) },
            h(PanoramaStrip, { c: A, width: 560, selected: "t2", ruler: "bearing", labelMode: "selected", layers: { boxes: true, text: true, mask: true, water: false } }),
            h(LayerToggles, { layers: { boxes: true, text: true, mask: true }, counts: { boxes: "17 · 3 rejected", text: "3" }, columns: 2 })
          ),
          h(
            "div",
            { className: "aq-pano-lower" },
            h(Viewer360, { c: A, yaw: 212, width: 368, height: 214, selected: "t2" }),
            h("div", { className: "aq-col" }, h(ZoomCrop, { c: A, target: "t2", width: 184, height: 96 }), h(CompassDial, { yawToBearing: 64, err: 12, sun: { azimuth: 205, elevation: 22 }, water: 200, size: 128 }))
          )
        ),
        h(
          "div",
          { className: "aq-col-reason" },
          h(Tabs, { value: "evidence", tabs: [{ id: "stages", label: "Stages", count: 12 }, { id: "evidence", label: "Evidence", count: 14 }, { id: "matrix", label: "Matrix" }, { id: "log", label: "Log", count: 19 }] }),
          h("ol", { className: "aq-timeline-l aq-nowline" }, h(StageRow, { stage: A.stages[10], pass: 2 })),
          h(
            "div",
            { className: "aq-feed" },
            h(EvidenceCard, { e: evidence[0], names: A.matrix.names, selected: true, crop: h("span", { "data-leader": "e2" }) }),
            h(CorrelationBracket, { label: A.groups[0].label, cap: A.groups[0].cap }, h(EvidenceCard, { e: ev(A, "e13"), names: A.matrix.names, compact: true }), h(EvidenceCard, { e: ev(A, "e12"), names: A.matrix.names, compact: true })),
            h(EvidenceCard, { e: evidence[1], names: A.matrix.names }),
            h(EvidenceCard, { e: evidence[2], names: A.matrix.names })
          )
        ),
        h(
          "div",
          { className: "aq-col-map" },
          h(MapView, { view: { lat: 41.1405, lng: -8.6145, span: 0.026 }, width: 424, height: 330, heat: A.heatTown, candidates: cands(A.candidatesAfter), selected: "ribeira", refs: A.neighbours.slice(0, 4).map((n) => ({ id: n.id, lat: n.lat, lng: n.lng })), area: { lat: 41.1432, lng: -8.615, r: 420, label: "postcode area 4050" }, labels: true }),
          h("span", { className: "aq-area-anchor", "data-leader": "area-4050" }),
          h("div", { className: "aq-pad" }, h(CandidateList, { candidates: A.candidatesAfter, selected: "ribeira", ruledOut: A.ruledOut, title: "Candidates" }))
        )
      ),
      h(ShortcutBar, { keys: KEYS_RUN })
    );
  }
  function ScreenQuestion() {
    const c = { ...A, run: { ...A.run, used: 208, session: 1263, multiplier: 1, expected: 9100 }, multiplierHistory: [A.multiplierHistory[0]] };
    return h(
      Density,
      { value: "console", className: "aq-screen", style: { width: 1440, height: 900 } },
      h(RunBar, { c }),
      h(
        "div",
        { className: "aq-qlayout" },
        h(
          "div",
          { className: "aq-col-pano" },
          h(Panel, { title: "Panorama" }, h(PanoramaStrip, { c: A, width: 456, ruler: "bearing", labelMode: "text", layers: { boxes: false, text: true } })),
          h(Panel, { title: "Candidates now" }, h(CandidateList, { candidates: A.candidatesBefore, selected: "ribeira", ruledOut: A.ruledOut, title: "", caption: "before the answer" }))
        ),
        h("div", { className: "aq-col-q" }, h(QuestionCard, { q: A.question, evidence: A.evidence, hoverKey: "A", cueLine: true })),
        h(
          "div",
          { className: "aq-col-map" },
          h(MapView, { view: A.viewTown, width: 448, height: 520, heat: A.heatTown, zones: A.zones, dimOthers: true, inset: { view: { lat: 40, lng: -6, span: 14 }, box: { lat: 41.2, lng: -8.4, span: 0.9 }, label: "D: everywhere outside" } }),
          h("div", { className: "aq-pad console-body aq-ink2" }, "Zones never overlap and together cover the current scope. A click picks a zone; the agent computes the coordinate from it. Option links open on teammates’ devices; nothing seen there goes back in except a click on an option.")
        )
      ),
      h(ShortcutBar, { keys: KEYS_Q })
    );
  }
  function ScreenQuestionOutcomes() {
    const zonesA = A.zones.map((z) => ({ ...z, chosen: z.key === "A", dim: z.key !== "A" }));
    return h(
      Density,
      { value: "console", className: "aq-screen", style: { width: 1440, height: 900 } },
      h(
        "div",
        { className: "aq-outcomes" },
        h(
          "section",
          { className: "aq-outcome" },
          h("header", { className: "aq-outcome-h" }, h("span", { className: "narrative-title" }, "Answered"), h("span", { className: "console-body aq-ink2" }, "Case 3 · the team picked A"), h(MultiplierChip, { value: 0.95, history: A.multiplierHistory })),
          h(AnswerReceipt, { kind: "answered", q: A.question, before: A.candidatesBefore, after: A.candidatesAfter, multiplierBefore: 1, multiplierAfter: 0.95, t: 212 }),
          h(MapView, { view: A.viewTown, width: 680, height: 470, heat: A.heatTown, zones: zonesA, candidates: cands(A.candidatesAfter), legend: false })
        ),
        h(
          "section",
          { className: "aq-outcome" },
          h("header", { className: "aq-outcome-h" }, h("span", { className: "narrative-title" }, "Skipped"), h("span", { className: "console-body aq-ink2" }, "Case 4 · free, and nothing moved"), h(MultiplierChip, { value: 1, history: B.multiplierHistory })),
          h(AnswerReceipt, { kind: "skipped", q: B.question, before: B.candidates, multiplierBefore: 1, t: 188 }),
          h(MapView, { view: B.view, width: 680, height: 470, heat: B.heat, zones: B.zones, legend: false, offline: false })
        )
      )
    );
  }
  function ScreenExactSpot() {
    const sp = A.spot;
    return h(
      Density,
      { value: "console", className: "aq-screen", style: { width: 1440, height: 900 } },
      h(RunBar, { c: A }),
      h(
        "div",
        { className: "aq-spot" },
        h(
          "div",
          { className: "aq-spot-main" },
          h(
            Panel,
            { title: "Exact spot", aside: h(Badge, { tone: "outline" }, "conditional · urban") },
            h(MatchView, { c: A, width: 860, height: 300, lines: 40 })
          ),
          h(
            Panel,
            { title: "Reference photos near the candidates" },
            h(
              "table",
              { className: "aq-table console-body" },
              h("thead", null, h("tr", null, ["", "Reference", "Distance", "Matches", "Inliers", "Verdict"].map((x) => h("th", { key: x, className: "console-micro" }, x)))),
              h("tbody", null, sp.refs.map((r) => h(
                "tr",
                { key: r.id, className: r.accepted ? "" : "is-out" },
                h("td", null, h(Icon, { name: r.accepted ? "done" : "failed", className: r.accepted ? "aq-c-support" : "aq-c-contra" })),
                h("td", { className: "console-data" }, r.id),
                h("td", { className: "console-data" }, `${r.dist} m`),
                h("td", { className: "console-data" }, r.matches),
                h("td", { className: "console-data" }, r.inliers),
                h("td", null, r.accepted ? "accepted · geometry consistent" : `rejected · ${r.reason.toLowerCase()}`)
              )))
            )
          ),
          h("div", { className: "aq-offset" }, h(Icon, { name: "info" }), h("div", null, h("div", { className: "console-heading" }, "A good image match is not a 10 m camera fix"), h("div", { className: "console-body aq-ink2" }, `412 inliers place the camera near r1’s viewpoint, but r1 was taken ${sp.refs[0].dist} m away and its GPS has its own error. Remaining offset ≈ ${sp.offset} m, so the ring is ± ${sp.camera.r} m (source GPS plus viewpoint offset), not ± 10 m.`)))
        ),
        h(
          "div",
          { className: "aq-spot-map" },
          h(MapView, {
            view: A.viewSpot,
            width: 500,
            height: 520,
            refs: sp.refs.map((r) => ({ id: r.id, lat: r.lat, lng: r.lng, accepted: r.accepted, label: `${r.id} · ${r.inliers} inliers` })),
            rings: [{ lat: 41.14094, lng: -8.6129, r: 35, label: "r1 ± 35 m", tone: "model" }, { lat: 41.14051, lng: -8.61401, r: 60, label: "r2 ± 60 m", tone: "model" }],
            cone: { lat: sp.camera.lat, lng: sp.camera.lng, bearing: 276, err: 12, len: 170, label: "276° ± 12°" },
            final: { lat: sp.camera.lat, lng: sp.camera.lng, r: sp.camera.r }
          }),
          h("div", { className: "aq-pad" }, h(CoordinateBlock, { a: { ...A.answer, rSource: sp.camera.rSource }, showCopy: false }))
        )
      ),
      h(ShortcutBar, { keys: [{ k: "←/→", label: "previous / next reference" }, { k: "R", label: "show rejected matches" }, { k: "M", label: "map focus" }] })
    );
  }
  function ScreenFinalAnswer() {
    return h(
      Density,
      { value: "console", className: "aq-screen", style: { width: 1440, height: 900 } },
      h(RunBar, { c: A }),
      h(
        "div",
        { className: "aq-final" },
        h(
          "div",
          { className: "aq-final-map" },
          h(MapView, { view: { lat: 41.1407, lng: -8.61315, span: 62e-4 }, width: 640, height: 640, final: { lat: A.answer.lat, lng: A.answer.lng, r: 22 }, refs: A.spot.refs.filter((r) => r.accepted).map((r) => ({ id: r.id, lat: r.lat, lng: r.lng })) }),
          h("div", { className: "aq-pad" }, h(ChoiceNote, { a: A.answer, mostLikelyName: "Porto · Ribeira 0.69" }))
        ),
        h(
          "div",
          { className: "aq-final-side" },
          h("div", { className: "aq-final-head" }, h("h1", { className: "narrative-title" }, "Best estimate"), h(Stamp, { kind: "estimate" })),
          h(CoordinateBlock, { a: A.answer, size: "lg" }),
          h(AnswerSlots, { a: A.answer }),
          h(ScoreCurve, { urban: "urban", band: [10, 44], expected: 12500, multiplier: 0.95, width: 500, height: 170 }),
          h(ExportBar, {})
        )
      ),
      h(ShortcutBar, { keys: [{ k: "C", label: "copy lat, lng" }, { k: "E", label: "export JSON log" }, { k: "⇧⏎", label: "submit (asks to confirm)" }, { k: "N", label: "next case" }] })
    );
  }
  function ScreenCaseReport() {
    return h(
      Density,
      { value: "console", theme: "light", className: "aq-screen aq-report", style: { width: 1440 } },
      h(
        "header",
        { className: "aq-report-h" },
        h(
          "div",
          { className: "aq-report-t" },
          h(Wordmark, { size: 26 }),
          h("h1", { className: "narrative-display" }, "Case 3: the Ribeira quay, Porto"),
          h("p", { className: "console-body aq-ink2" }, `${A.file} · taken 2026-01-15 14:30:12 UTC · shot 204 · Urban (official) · solved in ${fmtTime(A.run.used)} of 08:00`)
        ),
        h("div", { className: "aq-report-sum" }, h(Stamp, { kind: "estimate" }), h(CoordinateBlock, { a: A.answer, showCopy: false }), h(ScoreReadout, { expected: 12500, range: [10900, 13400] }))
      ),
      h("section", { className: "aq-report-sec" }, h("h2", { className: "narrative-title" }, "Replay"), h(ReplayScrubber, { events: LOG_A, t: 212, duration: 340, speed: 1 }), h(EventLog, { events: LOG_A, current: 212 })),
      h(
        "div",
        { className: "aq-report-2" },
        h("section", { className: "aq-report-sec" }, h("h2", { className: "narrative-title" }, "What supports what"), h(EvidenceMatrix, { evidence: A.evidence, candidates: A.matrix.candidates, names: A.matrix.names, groups: A.groups })),
        h(
          "div",
          { className: "aq-col", style: { gap: 28 } },
          h(
            "section",
            { className: "aq-report-sec" },
            h("h2", { className: "narrative-title" }, "Questions, answers and costs"),
            h(AnswerReceipt, { kind: "answered", q: A.question, before: A.candidatesBefore, after: A.candidatesAfter, multiplierBefore: 1, multiplierAfter: 0.95, t: 212 }),
            h("div", { className: "console-body aq-ink2" }, "Cues sent: none. Place names converted by a human: none (the app produced the coordinates).")
          ),
          h(
            "section",
            { className: "aq-report-sec" },
            h("h2", { className: "narrative-title" }, "Ruled out, and why"),
            h(RuledOutRow, { r: A.ruledOut[0], byLabels: { e2: "postcode 4050-253", e4: "pt 0.93" }, stamp: true }),
            h(CandidateRow, { c: A.candidatesBefore[3], max: 0.7, ghost: true })
          ),
          h(
            "section",
            { className: "aq-report-sec" },
            h("h2", { className: "narrative-title" }, "Far apart, alike"),
            h(
              "div",
              { className: "aq-lookalike" },
              h("div", null, h("div", { className: "console-heading" }, "Porto · Ribeira"), h("div", { className: "console-micro aq-ink3" }, "41.14, −8.61")),
              h(Icon, { name: "contradiction" }),
              h("div", null, h("div", { className: "console-heading" }, "Lisboa · Alfama"), h("div", { className: "console-micro aq-ink3" }, "38.71, −9.13 · 274 km south")),
              h("div", { className: "aq-lookalike-b console-body" }, h("span", { className: "aq-ink3" }, "Share: "), "azulejo façades, wrought-iron balconies, a river view, a steep old town. ", h("span", { className: "aq-ink3" }, "Separated by: "), "granite against limestone, postcode 4050, the 22 prefix.")
            ),
            h(
              "div",
              { className: "aq-lookalike" },
              h("div", null, h("div", { className: "console-heading" }, "Alentejo montado"), h("div", { className: "console-micro aq-ink3" }, "Case 4 · PT")),
              h(Icon, { name: "contradiction" }),
              h("div", null, h("div", { className: "console-heading" }, "Extremadura dehesa"), h("div", { className: "console-micro aq-ink3" }, "ES")),
              h("div", { className: "aq-lookalike-b console-body" }, h("span", { className: "aq-ink3" }, "Share: "), "cork and holm oak, red-brown soil, rolling ground, whitewash. ", h("span", { className: "aq-ink3" }, "Separated by: "), "nothing visible; with no text, Portugal against Spain stays open.")
            ),
            h("div", { className: "console-micro aq-ink3" }, "Look-alikes are listed per case from that case’s own evidence; cases never inform each other.")
          ),
          h("section", { className: "aq-report-actions" }, h(Button, { icon: "download" }, "Export JSON log"), h(Button, { icon: "file" }, "Export report (PDF)"), h(Button, { variant: "quiet", icon: "copy" }, "Copy lat, lng"))
        )
      )
    );
  }
  function ScreenQueue() {
    return h(
      Density,
      { value: "console", className: "aq-screen", style: { width: 1440, height: 900 } },
      h(
        "header",
        { className: "aq-runbar" },
        h("div", { className: "aq-runbar-wm" }, h(Wordmark, { size: 22 })),
        h("span", { className: "console-heading" }, "Queue"),
        h(Timer, { label: "Session", used: 1395, budget: 3600 }),
        h(ScoreReadout, { expected: 13900 + 9800 }),
        h(GpuMeter, { used: 11.8, compact: true }),
        h("div", { className: "aq-runbar-sys" }, h(SystemBadge, { kind: "worker-online" }))
      ),
      h(
        "div",
        { className: "aq-queue" },
        h("div", { className: "aq-queue-h" }, h("h1", { className: "narrative-title" }, "Five cases and the Special One"), h("p", { className: "console-body aq-ink2" }, "One GPU worker takes them in turn, each from a clean state; the case you open goes first. Only status crosses between cards: no images, no dates, no shared evidence.")),
        h("div", { className: "aq-queue-grid" }, QUEUE.map((q, i) => h(CaseCard, { key: i, ...q }))),
        h(
          "div",
          { className: "aq-queue-worker" },
          h(Icon, { name: "running" }),
          h("span", { className: "console-body" }, "Worker: Case 4 · Describe · 00:34 of 00:45 deadline"),
          h("span", { className: "console-micro aq-ink3" }, "next: Case 5, then the Special One"),
          h("span", { className: "aq-queue-sum console-data" }, "Submitted 1 · ready 1 · question waiting 1")
        )
      ),
      h(ShortcutBar, { keys: [{ k: "1–6", label: "open case" }, { k: "⏎", label: "open next needing an answer" }, { k: "P", label: "prioritise this case" }] })
    );
  }
  var stageBar = (c, speed = 1, extra) => h(
    "header",
    { className: "aq-runbar aq-stagebar" },
    h("div", { className: "aq-runbar-wm" }, h(Wordmark, { size: 36 })),
    h("span", { className: "stage-title" }, c.label),
    h(Badge, { tone: "outline" }, c.urban === "urban" ? "Urban" : "Non-urban"),
    h(Timer, { label: "This panorama", used: c.run.used, budget: c.run.budget }),
    h(MultiplierChip, { value: c.run.multiplier }),
    extra || null,
    h("div", { className: "aq-runbar-sys" }, h(SystemBadge, { kind: "replay", speed }))
  );
  function StageOpening() {
    const models = ROSTER.filter((m) => m.id !== "pvlib");
    return h(
      Density,
      { value: "stage", theme: "stage", className: "aq-screen aq-stage-screen aq-opening", style: { width: 1920, height: 1080 } },
      h(
        "div",
        { className: "aq-opening-l" },
        h(Wordmark, { size: 132 }),
        h("h1", { className: "narrative-display" }, "Where in the world could here be?"),
        h("p", { className: "stage-body aq-ink2" }, "One 360° photo. No metadata. Every claim traced back to pixels, every doubt left in view, every ruled-out place kept with its reason."),
        h("div", { className: "aq-opening-facts" }, h(Badge, { tone: "outline", icon: "gpu" }, "one laptop · 16 GB GPU"), h(Badge, { tone: "outline", icon: "offline" }, "no cloud APIs"), h(Badge, { tone: "outline", icon: "model" }, "open weights only"))
      ),
      h(
        "div",
        { className: "aq-opening-r" },
        h("div", { className: "stage-label aq-ink3" }, "The local models, and what each one does"),
        h(
          "ul",
          { className: "aq-opening-models" },
          models.map((m) => h("li", { key: m.id }, h(Icon, { name: "model", className: "aq-c-model" }), h("div", null, h("div", { className: "stage-body aq-strong" }, m.name), h("div", { className: "stage-label aq-ink2" }, m.role)))),
          h("li", null, h(Icon, { name: "solver", className: "aq-c-solver" }), h("div", null, h("div", { className: "stage-body aq-strong" }, "Solver"), h("div", { className: "stage-label aq-ink2" }, "Our code: combines the evidence. Not a model."))),
          h("li", null, h(Icon, { name: "team", className: "aq-c-team" }), h("div", null, h("div", { className: "stage-body aq-strong" }, "The team"), h("div", { className: "stage-label aq-ink2" }, "Answers the agent’s questions, when one is worth its cost.")))
        )
      )
    );
  }
  function StageRun() {
    return h(
      Density,
      { value: "stage", theme: "stage", className: "aq-screen aq-stage-screen", style: { width: 1920, height: 1080 } },
      stageBar({ ...A, run: { ...A.run, used: 41, multiplier: 1 } }, 2),
      h(
        LeaderLines,
        { links: [["crop-t2", "t2"]], className: "aq-stage-run" },
        h(
          "div",
          { className: "aq-stage-focus" },
          h("div", { "data-leader": "crop-t2" }, h(ZoomCrop, { c: A, target: "t2", width: 1180, height: 470, fov: 9, note: "full resolution · view 5 · yaw 212.5°" })),
          h(PanoramaStrip, { c: A, width: 1180, selected: "t2", crop: [42, -30], layers: { boxes: false, text: true, mask: false }, ruler: "yaw" })
        ),
        h(
          "aside",
          { className: "aq-stage-rail" },
          h(EvidenceCard, { e: ev(A, "e2"), names: A.matrix.names, selected: true }),
          h(LanguageVote, { votes: A.language }),
          h(EstimateBars, { rows: A.regions.slice(0, 4).concat([A.regions[5]]), tone: "model", title: "Pixels alone (mini-PIGEON)" })
        )
      ),
      h(CaptionBar, { headline: "Reading signs", caption: "A postcode in a format only Portugal uses: 4050 is central Porto", source: "PP-OCRv6-medium", t: 41.2, speed: 2 })
    );
  }
  function StageQuestion() {
    const c = { ...A, run: { ...A.run, used: 208, multiplier: 1 } };
    return h(
      Density,
      { value: "stage", theme: "stage", className: "aq-screen aq-stage-screen", style: { width: 1920, height: 1080 } },
      stageBar(c, 1),
      h(
        "div",
        { className: "aq-stage-q" },
        h(QuestionCard, { q: { ...A.question, options: A.question.options.map((o) => ({ ...o, chips: [] })) }, evidence: A.evidence, brief: true }),
        h(MapView, { view: { lat: 41.1405, lng: -8.615, span: 0.026 }, width: 860, height: 760, heat: A.heatTown, zones: A.zones, dimOthers: true, legend: false })
      ),
      h(CaptionBar, { headline: "Asking the team", caption: "One answer is worth more here than its ×0.95 cost: expected gain +19%", actor: "solver", source: "Solver", t: 88 })
    );
  }
  function StageFinal() {
    return h(
      Density,
      { value: "stage", theme: "stage", className: "aq-screen aq-stage-screen", style: { width: 1920, height: 1080 } },
      stageBar(A, 1),
      h(
        "div",
        { className: "aq-stage-final" },
        h(MapView, { view: { lat: 41.1407, lng: -8.61315, span: 56e-4 }, width: 980, height: 760, final: { lat: A.answer.lat, lng: A.answer.lng, r: 22 }, legend: false }),
        h(
          "div",
          { className: "aq-stage-final-r" },
          h("div", { className: "stage-label aq-ink3" }, "Best estimate · latitude, longitude"),
          h("div", { className: "stage-readout" }, fmtCoord(A.answer.lat, A.answer.lng)),
          h("div", { className: "stage-data aq-c-solver" }, "± 22 m · reference_camera · ×0.95"),
          h(ScoreReadout, { expected: 12500, size: "xl" }),
          h(AnswerSlots, { a: A.answer })
        )
      ),
      h(CaptionBar, { headline: "Pinpoint", caption: "Best estimate: the Ribeira quay, within about 22 metres", actor: "solver", source: "Solver", t: 340 })
    );
  }
  function ScreenSystemStates() {
    const failStages = [
      { id: "describe", name: "Describe", models: ["Qwen3.5-9B"], status: "failed", dur: 8.2, gb: 7.4, note: "Returned invalid JSON twice.", fallback: "Gemma 4 12B, closed checklist only" },
      { id: "measure", name: "Measure", optional: true, models: ["EoMT-L", "pvlib"], status: "timed_out", dur: 20, gb: 1.1, note: "No result in 20 s.", fallback: "scene shares skipped; north stays unknown" },
      { id: "geo", name: "Pixel geolocation", models: ["PE-Core", "mini-PIGEON", "GeoCLIP"], status: "done", dur: 9.6, gb: 1.7 }
    ];
    const lowCands = [{ id: "x1", rank: 1, name: "Centro region", level: "region", v: 0.21, lo: 0.11, hi: 0.32, delta: 0, sup: 2, con: 1 }, { id: "x2", rank: 2, name: "Castilla y León (ES)", level: "region", v: 0.18, lo: 0.08, hi: 0.3, delta: 0, sup: 2, con: 0 }, { id: "x3", rank: 3, name: "Norte region", level: "region", v: 0.16, lo: 0.07, hi: 0.27, delta: 0, sup: 1, con: 0 }, { id: "o", name: "Other", level: "area", v: 0.45, other: true }];
    const S = (title, note, body) => h("section", { className: "aq-state" }, h("header", null, h("h2", { className: "console-title" }, title), h("p", { className: "console-body aq-ink2" }, note)), body);
    return h(
      Density,
      { value: "console", className: "aq-screen aq-states", style: { width: 1440 } },
      S(
        "A stage failed or timed out",
        "Every stage has a deadline and a fallback; the run still produces an answer. The row says which fallback ran.",
        h("div", { className: "aq-col" }, h("ol", { className: "aq-timeline-l" }, failStages.map((s) => h(StageRow, { key: s.id, stage: s }))), h(Toast, { tone: "contra", title: "Measure timed out after 20 s", body: "Skipped scene shares; the bearing ruler stays on camera yaw.", action: "Show stage" }))
      ),
      S(
        "The VLM returned invalid JSON",
        "The raw reply is kept in the log; one retry with a stricter prompt, then the fallback model. Nothing from the bad reply becomes evidence.",
        h("div", { className: "aq-col" }, h("pre", { className: "aq-raw console-data-sm" }, '{"granite_masonry": "yes", "azulejo": yes,\n "river_visible": "yes" ...'), h("div", { className: "aq-row" }, h(Badge, { tone: "contra", icon: "failed" }, "parse error at char 38"), h(Badge, { tone: "neutral", icon: "replay" }, "retry 1 of 1 · failed"), h(Badge, { tone: "model", icon: "model" }, "Gemma 4 12B · answered 9 of 11")))
      ),
      S(
        "Map tiles offline",
        "Tiles are prefetched; if they fail, bundled outlines of PT, ES and FR with district borders take over — drawn on purpose, not as an error.",
        h(MapView, { view: { lat: 41, lng: -4.5, span: 15 }, width: 640, height: 300, offline: true, heat: A.heatCountry, candidates: [{ id: "p", rank: 1, lat: 41.15, lng: -8.61, name: "Porto" }] })
      ),
      S(
        "No text found",
        "An empty reading is evidence too. It says so in words, and the language vote is absent rather than zero.",
        h("div", { className: "aq-col" }, h(EvidenceCard, { e: B.evidence[0] }), h(EmptyState, { icon: "language", title: "No language vote", body: "Nothing to read, so the three voters did not run. Country comes from scene and pixels." }))
      ),
      S(
        "No candidate above the threshold",
        "When nothing clears 0.30, the answer falls back to the cell that maximises expected score and the ring widens; the map stays at region level.",
        h("div", { className: "aq-col" }, h(CandidateList, { candidates: lowCands, title: "Candidates", caption: "nothing above 0.30" }), h("div", { className: "aq-row" }, h(UncertaintyRing, { r: null }), h("span", { className: "console-body aq-ink2" }, "Radius unknown until a stage bounds it; drawn open and large, never as a point.")))
      ),
      S(
        "Urban label unknown",
        "The label picks the scoring curve. When nobody knows it, both curves and both expected scores stay on screen.",
        h("div", { className: "aq-col" }, h(FilenameParse, { file: "IMG_20260605_092457_00_064.jpg", urban: "unknown", source: "unknown", special: true }), h(ScoreCurve, { urban: "unknown", band: [1500, 8400], expected: { urban: 2900, nonUrban: 11300 }, width: 640, height: 170 }))
      )
    );
  }
  function Concept() {
    return h(
      Density,
      { value: "console", className: "aq-screen aq-concept", style: { width: 1440 } },
      h(
        "div",
        { className: "aq-concept-top" },
        h("div", { className: "aq-concept-wm" }, h(Wordmark, { size: 150 }), h("div", { className: "console-micro aq-ink3" }, "Newsreader outlines · the tittle is a point inside a broken uncertainty ring")),
        h(
          "div",
          { className: "aq-concept-text" },
          h("h1", { className: "narrative-title" }, "A cartographer’s case file, read by an instrument"),
          h("p", { className: "console-body" }, "Aqui is the opposite of the chatbot that names a new town with full confidence. Everything on screen is a record: what a model saw, what follows from it, what the solver estimates — three registers that never blur. The base is quiet Atlantic ink (limestone on paper); colour is spent only on meaning: azulejo cobalt for models, Pombaline ochre for the solver, jacaranda for the team, roof-tile terracotta for every point spent. The memorable thing is the panorama strip and its bearing ruler, which turns from camera yaw to true north the moment the sun is found."),
          h("p", { className: "console-body aq-ink2" }, "Three voices in type: Atkinson Hyperlegible Next for the interface (built to tell I, l and 1 apart — this app reads signs), Atkinson Hyperlegible Mono for every reading and number, Newsreader for the narrator: stage headlines, inference lines, the report.")
        )
      ),
      h(
        "div",
        { className: "aq-moods" },
        h("figure", { className: "aq-mood" }, h(PanoramaStrip, { c: B, width: 440, ruler: "bearing", crop: [40, -40], layers: { sun: true, skyline: true, boxes: false, text: false, mask: false }, label: false }), h("figcaption", { className: "console-body" }, h("b", null, "The ruler. "), "North arrives with the sun, with its error on the ruler.")),
        h("figure", { className: "aq-mood" }, h(Density, { value: "console", theme: "light", className: "aq-mood-paper" }, h("div", { className: "aq-mood-pad" }, h("div", { className: "aq-row", style: { justifyContent: "space-between" } }, h("span", { className: "narrative-title" }, "Ruled out, and why"), h(Stamp, { kind: "ruled-out" })), h(RuledOutRow, { r: A.ruledOut[0] }), h(EvidenceCard, { e: ev(A, "e2"), names: A.matrix.names, compact: true }))), h("figcaption", { className: "console-body" }, h("b", null, "The case file. "), "Ruled-out places stay, struck through, with the reason.")),
        h("figure", { className: "aq-mood" }, h(Density, { value: "stage", theme: "stage", className: "aq-mood-stage" }, h("div", { style: { zoom: 0.23 } }, h(CaptionBar, { headline: "Reading signs", caption: "A postcode in a format only Portugal uses", source: "PP-OCRv6-medium", t: 41.2, speed: 2 }), h(ZoomCrop, { c: A, target: "t2", width: 1900, height: 700, fov: 9 }))), h("figcaption", { className: "console-body" }, h("b", null, "The room. "), "One focus, one plain sentence, from the back row."))
      )
    );
  }
  var Frame = ({ n, t, title, children, notes }) => h("figure", { className: "aq-frame" }, h("div", { className: "aq-frame-h" }, h("span", { className: "console-data-sm aq-ink3" }, `F${n}`), h("span", { className: "console-label" }, title), h("span", { className: "console-data-sm aq-ink3 aq-frame-t" }, t)), h("div", { className: "aq-frame-b" }, children), h("figcaption", { className: "console-micro aq-ink2" }, notes));
  var Storyboard = ({ beat, event, frames, foot }) => h(
    Density,
    { value: "console", className: "aq-screen aq-story", style: { width: 1440 } },
    h("header", { className: "aq-story-h" }, h("h1", { className: "narrative-title" }, beat), h("span", { className: "console-data aq-ink2" }, event)),
    h("div", { className: "aq-frames" }, frames),
    foot ? h("p", { className: "console-micro aq-ink3" }, foot) : null
  );
  function MotionDetect() {
    const all = A.detections.map((d) => d.id), kept = A.detections.filter((d) => d.kept).map((d) => d.id);
    const W = 320;
    return h(Storyboard, { beat: "Beat 3 · Detect", event: "evidence.added (detect) ×20 → evidence.added (SAM 3 verdicts)", frames: [
      h(Frame, { key: 1, n: 1, t: "27.3 s", title: "Boxes proposed", notes: "Each box enters with its own event: corner brackets scale 0.92 → 1 and fade in, dur-quick 180 ms, ease-enter; stagger dur-stagger 40 ms, capped at 480 ms." }, h(PanoramaStrip, { c: A, width: W, ruler: false, layers: { text: false, mask: false }, label: false, visibleBoxes: all.slice(0, 5) })),
      h(Frame, { key: 2, n: 2, t: "27.8 s", title: "All 20 in view", notes: "Labels appear only after the box settles (dur-quick). No pulsing while waiting for SAM 3 — the stage row’s real clock carries the wait." }, h(PanoramaStrip, { c: A, width: W, ruler: false, layers: { text: false, mask: false }, label: false })),
      h(Frame, { key: 3, n: 3, t: "33.5 s", title: "SAM 3 rejects 3", notes: "Rejected boxes switch to dashed and get a strike (dur-quick), then fade to opacity-ghost over dur-standard 280 ms, ease-exit. They stay, struck, until the layer is toggled off." }, h(PanoramaStrip, { c: A, width: W, ruler: false, layers: { text: false, mask: false }, label: true, fadedBoxes: [] })),
      h(Frame, { key: 4, n: 4, t: "33.8 s", title: "Settled", notes: "The evidence card “17 kept, 3 rejected” lifts into the feed (dur-standard, ease-enter). Reduced motion: each step is a 180 ms cross-fade." }, h(PanoramaStrip, { c: A, width: W, ruler: false, layers: { text: false, mask: false }, label: false, showRejected: true }))
    ], foot: "Every frame corresponds to an event in the log; replay at 2× or 5× halves or fifths the waits between events, never the durations above." });
  }
  function MotionFusion() {
    const before = A.candidatesBefore.map((c) => ({ ...c, v: c.v * 0.35, lo: void 0, hi: void 0, delta: 0 }));
    return h(Storyboard, { beat: "Beat 8 · Fusion", event: "candidates.updated (fusion) at 86.3 s", frames: [
      h(Frame, { key: 1, n: 1, t: "86.1 s", title: "Evidence sends weight", notes: "Each supporting card ticks its ▲ chips in sequence (stagger 40 ms) while bars grow: dur-deliberate 520 ms, ease-move." }, h("div", { className: "aq-col" }, h(EvidenceCard, { e: ev(A, "e2"), names: A.matrix.names, compact: true }), before.slice(0, 3).map((c) => h(CandidateRow, { key: c.id, c, max: 0.7, showDelta: false })))),
      h(Frame, { key: 2, n: 2, t: "86.2 s", title: "Correlated sources merge", notes: "Neighbours and regions slide together under one bracket (dur-standard); the bracket’s cap badge appears last. One voice, one weight." }, h(CorrelationBracket, { label: "One voice: PE-Core", cap: 0.35 }, h(EvidenceCard, { e: ev(A, "e12"), names: A.matrix.names, compact: true }), h(EvidenceCard, { e: ev(A, "e13"), names: A.matrix.names, compact: true }))),
      h(Frame, { key: 3, n: 3, t: "86.2 s", title: "A contradiction pulses", notes: "The two sources outline in contra twice (2 × dur-quick, no loop); Alfama’s range widens over dur-deliberate. Confidence moves both ways." }, h("div", { className: "aq-col" }, h(EvidenceCard, { e: ev(A, "e15"), names: A.matrix.names, compact: true }), h(CandidateRow, { c: A.candidatesBefore[3], max: 0.7 }))),
      h(Frame, { key: 4, n: 4, t: "86.3 s", title: "Ruled out, ghosted", notes: "Galicia strikes through (dur-quick), then fades to opacity-ghost (dur-standard, ease-exit) with its reason. It never leaves the list." }, h("div", { className: "aq-col" }, A.candidatesBefore.slice(0, 3).map((c) => h(CandidateRow, { key: c.id, c, max: 0.7 })), h(RuledOutRow, { r: A.ruledOut[0] })))
    ] });
  }
  function MotionAsk() {
    const zonesA = A.zones.map((z) => ({ ...z, chosen: z.key === "A", dim: z.key !== "A" }));
    const W = 320, H = 210;
    return h(Storyboard, { beat: "Beat 10 · Ask", event: "question.asked 88.0 s → question.answered 212.0 s (or question.skipped)", frames: [
      h(Frame, { key: 1, n: 1, t: "88.0 s", title: "Zones draw", notes: "Outlines draw on A → D (stroke-dashoffset, dur-standard each, stagger 40 ms); hatch fades in after. Heat dims to opacity-dim." }, h(MapView, { view: A.viewTown, width: W, height: H, heat: A.heatTown, zones: A.zones.slice(0, 1), legend: false, labels: false, scale: false, dimOthers: true })),
      h(Frame, { key: 2, n: 2, t: "88.4 s", title: "Question open", notes: "The card rises (dur-standard, ease-enter). The gain bar fills to +19% once (dur-deliberate). Nothing else moves while the team decides." }, h(MapView, { view: A.viewTown, width: W, height: H, heat: A.heatTown, zones: A.zones, legend: false, labels: false, scale: false, dimOthers: true })),
      h(Frame, { key: 3, n: 3, t: "212.0 s", title: "Answered A", notes: "Chosen zone thickens, others dim (dur-quick). Multiplier ticks ×1.00 → ×0.95 in place (dur-deliberate, ease-move); bars resize after." }, h("div", { className: "aq-col" }, h(MapView, { view: A.viewTown, width: W, height: 150, heat: A.heatTown, zones: zonesA, legend: false, labels: false, scale: false }), h("div", { className: "aq-row" }, h(MultiplierChip, { value: 0.95 }), h(Badge, { tone: "team", icon: "team" }, "Answered A")))),
      h(Frame, { key: 4, n: 4, t: "188.0 s · Case 4", title: "Or: skipped", notes: "A skip moves nothing. The card collapses to a dashed receipt (dur-standard) reading “Skipped · free · nothing changed”. No tick, no bar motion." }, h("div", { className: "aq-col" }, h(MapView, { view: B.view, width: W, height: 150, heat: B.heat, zones: B.zones, legend: false, labels: false, scale: false }), h("div", { className: "aq-row" }, h(MultiplierChip, { value: 1 }), h(Badge, { tone: "outline", icon: "skip" }, "Skipped · nothing changed"))))
    ] });
  }
  function MotionExactSpot() {
    return h(Storyboard, { beat: "Beat 11 · Exact spot", event: "stage.started (spot) 309.0 s → evidence.added (matches) 331.5 s → output.produced 340.0 s", frames: [
      h(Frame, { key: 1, n: 1, t: "309.0 s", title: "Reference slides in", notes: "The reference photo slides in beside the query view from the right (dur-standard, ease-enter); its map square highlights." }, h(MatchView, { c: A, width: 320, height: 120, lines: 0, showRejected: false })),
      h(Frame, { key: 2, n: 2, t: "320.0 s", title: "Matches draw", notes: "Lines draw left to right in batches as LightGlue reports them (stagger 40 ms, cap 480 ms per batch). Rejected matches appear dashed, then fade." }, h(MatchView, { c: A, width: 320, height: 120, lines: 12 })),
      h(Frame, { key: 3, n: 3, t: "331.5 s", title: "Inliers counted", notes: "The inlier count climbs to 412 over dur-deliberate — a count-up of a known number, not a progress bar." }, h(MatchView, { c: A, width: 320, height: 120, lines: 36 })),
      h(Frame, { key: 4, n: 4, t: "340.0 s", title: "Ring contracts", notes: "The ring contracts from ± 180 m to ± 22 m (dur-deliberate, ease-move) and stops there — never tighter than the remaining offset." }, h(MapView, { view: A.viewSpot, width: 320, height: 150, final: { lat: A.answer.lat, lng: A.answer.lng, r: 22 }, legend: false, labels: true, scale: true }))
    ] });
  }
  function MotionPinpoint() {
    return h(Storyboard, { beat: "Beat 12 · Pinpoint", event: "output.produced 340.0 s", frames: [
      h(Frame, { key: 1, n: 1, t: "340.0 s", title: "The mark lands", notes: "The surveyor’s mark drops 12 px and settles with ease-spring over dur-deliberate — the only spring in the system." }, h(MapView, { view: { lat: 41.14081, lng: -8.61315, span: 4e-3 }, width: 320, height: 170, final: { lat: A.answer.lat, lng: A.answer.lng, r: null }, legend: false, labels: false })),
      h(Frame, { key: 2, n: 2, t: "340.2 s", title: "Ring settles", notes: "The ring settles at the final radius (dur-deliberate); its label “± 22 m” fades in after (dur-quick)." }, h(MapView, { view: { lat: 41.14081, lng: -8.61315, span: 4e-3 }, width: 320, height: 170, final: { lat: A.answer.lat, lng: A.answer.lng, r: 22 }, legend: false })),
      h(Frame, { key: 3, n: 3, t: "340.4 s", title: "Slots fill", notes: "The ten rank-weight bars fill left to right, stagger 40 ms (400 ms total), each at its weight 1.00 → 0.63." }, h(AnswerSlots, { a: A.answer })),
      h(Frame, { key: 4, n: 4, t: "340.9 s", title: "Expected score counts up", notes: "Counts 0 → ≈ 12,500 over dur-cinematic 1400 ms, ease-move, always labelled “estimate”. Reduced motion: the final number appears." }, h(ScoreReadout, { expected: 12500, range: [10900, 13400] }))
    ] });
  }

  // src/index.ts
  var NS = {
    ...base_exports,
    ...shell_exports,
    ...panorama_exports,
    ...reasoning_exports,
    ...beliefs_exports,
    ...charts_exports,
    ...map_exports,
    ...human_exports,
    ...output_exports,
    ...extra_exports,
    Docs: docs_exports,
    Samples: samples_exports,
    Screens: screens_exports,
    Icon,
    ICONS,
    fmt: { coord: fmtCoord, dist: fmtDist, time: fmtTime, est: fmtEst, mult: fmtMult, int: fmtInt },
    theta,
    RANK_W,
    MAX_SCORE
  };
  var w = window;
  w.Aqui = Object.assign(w.Aqui || {}, NS);
})();
