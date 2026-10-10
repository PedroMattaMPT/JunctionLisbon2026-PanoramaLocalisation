// Aqui — Tailwind preset generated from tokens.json. Every value points at a CSS custom property from tokens.css,
// so the three themes ([data-theme="dark" | "light" | "stage"]) switch without rebuilding.
// Use: module.exports = { presets: [require('./aqui.tailwind.preset.js')], content: ['./src/**/*.{ts,tsx}'] }
module.exports = {
  "darkMode": [
    "selector",
    "[data-theme=\"dark\"]"
  ],
  "theme": {
    "colors": {
      "transparent": "transparent",
      "current": "currentColor",
      "surface-0": "var(--surface-0)",
      "surface-1": "var(--surface-1)",
      "surface-2": "var(--surface-2)",
      "surface-3": "var(--surface-3)",
      "line-1": "var(--line-1)",
      "line-2": "var(--line-2)",
      "ink-1": "var(--ink-1)",
      "ink-2": "var(--ink-2)",
      "ink-3": "var(--ink-3)",
      "ink-disabled": "var(--ink-disabled)",
      "model": "var(--model)",
      "model-soft": "var(--model-soft)",
      "on-model": "var(--on-model)",
      "solver": "var(--solver)",
      "solver-soft": "var(--solver-soft)",
      "on-solver": "var(--on-solver)",
      "team": "var(--team)",
      "team-soft": "var(--team-soft)",
      "on-team": "var(--on-team)",
      "cost": "var(--cost)",
      "cost-soft": "var(--cost-soft)",
      "on-cost": "var(--on-cost)",
      "support": "var(--support)",
      "support-soft": "var(--support-soft)",
      "contra": "var(--contra)",
      "contra-soft": "var(--contra-soft)",
      "on-contra": "var(--on-contra)",
      "neutral": "var(--neutral)",
      "opt-a": "var(--opt-a)",
      "opt-a-soft": "var(--opt-a-soft)",
      "on-opt-a": "var(--on-opt-a)",
      "opt-b": "var(--opt-b)",
      "opt-b-soft": "var(--opt-b-soft)",
      "on-opt-b": "var(--on-opt-b)",
      "opt-c": "var(--opt-c)",
      "opt-c-soft": "var(--opt-c-soft)",
      "on-opt-c": "var(--on-opt-c)",
      "opt-d": "var(--opt-d)",
      "opt-d-soft": "var(--opt-d-soft)",
      "on-opt-d": "var(--on-opt-d)",
      "conf-high": "var(--conf-high)",
      "conf-med": "var(--conf-med)",
      "conf-low": "var(--conf-low)",
      "conf-unknown": "var(--conf-unknown)",
      "status-queued": "var(--status-queued)",
      "status-running": "var(--status-running)",
      "status-done": "var(--status-done)",
      "status-skipped": "var(--status-skipped)",
      "status-failed": "var(--status-failed)",
      "status-timeout": "var(--status-timeout)",
      "seg-sky": "var(--seg-sky)",
      "seg-building": "var(--seg-building)",
      "seg-grass": "var(--seg-grass)",
      "seg-tree": "var(--seg-tree)",
      "seg-road": "var(--seg-road)",
      "seg-water": "var(--seg-water)",
      "seg-ground": "var(--seg-ground)",
      "seg-masked": "var(--seg-masked)",
      "heat-0": "var(--heat-0)",
      "heat-1": "var(--heat-1)",
      "heat-2": "var(--heat-2)",
      "heat-3": "var(--heat-3)",
      "heat-4": "var(--heat-4)",
      "heat-5": "var(--heat-5)",
      "map-water": "var(--map-water)",
      "map-land": "var(--map-land)",
      "map-land-out": "var(--map-land-out)",
      "map-border": "var(--map-border)",
      "map-border-country": "var(--map-border-country)",
      "map-graticule": "var(--map-graticule)",
      "map-label": "var(--map-label)",
      "focus": "var(--focus)",
      "select": "var(--select)",
      "photo-halo": "var(--photo-halo)",
      "on-photo": "var(--on-photo)",
      "mask-hatch": "var(--mask-hatch)",
      "scrim": "var(--scrim)"
    },
    "fontFamily": {
      "sans": [
        "var(--font-sans)"
      ],
      "mono": [
        "var(--font-mono)"
      ],
      "serif": [
        "var(--font-serif)"
      ]
    },
    "fontSize": {
      "console-title": [
        "18px",
        {
          "lineHeight": "24px",
          "fontWeight": "700"
        }
      ],
      "console-heading": [
        "15px",
        {
          "lineHeight": "20px",
          "fontWeight": "700"
        }
      ],
      "console-body": [
        "13px",
        {
          "lineHeight": "18px",
          "fontWeight": "400"
        }
      ],
      "console-label": [
        "12px",
        {
          "lineHeight": "16px",
          "fontWeight": "600"
        }
      ],
      "console-micro": [
        "11px",
        {
          "lineHeight": "14px",
          "fontWeight": "500"
        }
      ],
      "console-data": [
        "13px",
        {
          "lineHeight": "18px",
          "fontWeight": "450"
        }
      ],
      "console-data-sm": [
        "11px",
        {
          "lineHeight": "14px",
          "fontWeight": "500"
        }
      ],
      "console-readout": [
        "20px",
        {
          "lineHeight": "24px",
          "fontWeight": "500"
        }
      ],
      "stage-title": [
        "36px",
        {
          "lineHeight": "44px",
          "fontWeight": "700"
        }
      ],
      "stage-body": [
        "24px",
        {
          "lineHeight": "32px",
          "fontWeight": "400"
        }
      ],
      "stage-label": [
        "20px",
        {
          "lineHeight": "26px",
          "fontWeight": "600"
        }
      ],
      "stage-caption": [
        "30px",
        {
          "lineHeight": "40px",
          "fontWeight": "500"
        }
      ],
      "stage-data": [
        "24px",
        {
          "lineHeight": "30px",
          "fontWeight": "500"
        }
      ],
      "stage-readout": [
        "40px",
        {
          "lineHeight": "44px",
          "fontWeight": "500"
        }
      ],
      "stage-score": [
        "88px",
        {
          "lineHeight": "88px",
          "fontWeight": "500",
          "letterSpacing": "-0.02em"
        }
      ],
      "narrative-display": [
        "64px",
        {
          "lineHeight": "64px",
          "fontWeight": "500",
          "letterSpacing": "-0.01em"
        }
      ],
      "narrative-headline": [
        "44px",
        {
          "lineHeight": "48px",
          "fontWeight": "500"
        }
      ],
      "narrative-title": [
        "26px",
        {
          "lineHeight": "32px",
          "fontWeight": "500"
        }
      ],
      "inference": [
        "14px",
        {
          "lineHeight": "19px",
          "fontWeight": "400"
        }
      ],
      "stage-inference": [
        "28px",
        {
          "lineHeight": "36px",
          "fontWeight": "400"
        }
      ],
      "stamp": [
        "12px",
        {
          "lineHeight": "14px",
          "fontWeight": "800",
          "letterSpacing": "0.14em"
        }
      ],
      "stage-stamp": [
        "24px",
        {
          "lineHeight": "28px",
          "fontWeight": "800",
          "letterSpacing": "0.14em"
        }
      ]
    },
    "spacing": {
      "0": "0px",
      "1": "var(--space-1)",
      "2": "var(--space-2)",
      "3": "var(--space-3)",
      "4": "var(--space-4)",
      "5": "var(--space-5)",
      "6": "var(--space-6)",
      "8": "var(--space-8)",
      "12": "var(--space-12)",
      "16": "var(--space-16)",
      "half": "var(--space-half)"
    },
    "borderRadius": {
      "0": "var(--radius-0)",
      "1": "var(--radius-1)",
      "2": "var(--radius-2)",
      "3": "var(--radius-3)",
      "pill": "var(--radius-pill)"
    },
    "borderWidth": {
      "DEFAULT": "var(--border-hair)",
      "hair": "var(--border-hair)",
      "rule": "var(--border-rule)",
      "heavy": "var(--border-heavy)"
    },
    "boxShadow": {
      "float": "var(--shadow-float)",
      "dialog": "var(--shadow-dialog)",
      "focus": "var(--focus-ring)",
      "none": "none"
    },
    "zIndex": {
      "base": "var(--z-base)",
      "overlay": "var(--z-overlay)",
      "leader": "var(--z-leader)",
      "runbar": "var(--z-runbar)",
      "popover": "var(--z-popover)",
      "caption": "var(--z-caption)",
      "toast": "var(--z-toast)",
      "dialog": "var(--z-dialog)"
    },
    "opacity": {
      "0": "0",
      "100": "1",
      "ghost": "var(--opacity-ghost)",
      "dim": "var(--opacity-dim)",
      "zone": "var(--opacity-zone)"
    },
    "extend": {
      "transitionDuration": {
        "instant": "var(--dur-instant)",
        "quick": "var(--dur-quick)",
        "standard": "var(--dur-standard)",
        "deliberate": "var(--dur-deliberate)",
        "cinematic": "var(--dur-cinematic)",
        "stagger": "var(--dur-stagger)",
        "stagger-cap": "var(--dur-stagger-cap)"
      },
      "transitionTimingFunction": {
        "enter": "var(--ease-enter)",
        "exit": "var(--ease-exit)",
        "move": "var(--ease-move)",
        "spring": "var(--ease-spring)"
      },
      "height": {
        "control-sm": "var(--size-control-sm)",
        "control": "var(--size-control)",
        "control-stage": "var(--size-control-stage)",
        "runbar": "var(--size-runbar)",
        "ruler": "var(--size-ruler)",
        "caption": "var(--size-caption)",
        "mark": "var(--size-mark)"
      },
      "minHeight": {
        "control-sm": "var(--size-control-sm)",
        "control": "var(--size-control)",
        "control-stage": "var(--size-control-stage)",
        "runbar": "var(--size-runbar)",
        "ruler": "var(--size-ruler)",
        "caption": "var(--size-caption)",
        "mark": "var(--size-mark)"
      }
    }
  }
};
