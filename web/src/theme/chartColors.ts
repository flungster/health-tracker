/** Theme-aware colors for recharts.

 * SVG presentation attributes (stroke, fill) do not resolve CSS variables, so
 * the chart parts that are colored by a token take explicit hex values here —
 * mirroring index.css's @theme / .dark palettes. Charts that only need "the
 * accent line" can keep using the raw value; this module exists for everything
 * that must flip with the theme.
 */

export type ChartPalette = {
  /** Gridline color (token: line). */
  grid: string;
  /** Axis tick text (token: ink-muted). */
  tick: string;
  /** Tooltip box background + border (tokens: surface / line). */
  tooltipBackground: string;
  tooltipBorder: string;
  /** Tooltip text (token: ink). */
  tooltipText: string;
  /** Hover cursor band behind bars (token: canvas). */
  cursorFill: string;
  /** The accent line/bar color (token: accent — lighter in dark for contrast). */
  accent: string;
  /** Heart-rate zone ramp, zones 1→5 (same hue family, lifted in dark). */
  zoneColors: readonly [string, string, string, string, string];
};

const LIGHT: ChartPalette = {
  grid: "#e3e1dc", // line
  tick: "#6f6d68", // ink-muted
  tooltipBackground: "#ffffff", // surface
  tooltipBorder: "#e3e1dc", // line
  tooltipText: "#292826", // ink
  cursorFill: "#f5f4f1", // canvas
  accent: "#2f6f6a", // accent
  zoneColors: ["#a8c4c1", "#7fa8a4", "#5d948f", "#3d7c76", "#2f6f6a"],
};

const DARK: ChartPalette = {
  grid: "#34322f", // line
  tick: "#a3a098", // ink-muted
  tooltipBackground: "#232220", // surface
  tooltipBorder: "#34322f", // line
  tooltipText: "#e8e6e1", // ink
  cursorFill: "#1b1a18", // canvas
  accent: "#4d9a93", // accent (dark)
  zoneColors: ["#c9dedb", "#93bbb5", "#62a098", "#478d85", "#3b766f"],
};

/** The palette for the resolved theme ("system" is already resolved to dark/light by useTheme). */
export function chartPalette(dark: boolean): ChartPalette {
  return dark ? DARK : LIGHT;
}

/** recharts <Tooltip contentStyle> for the palette (recharts' default box is white). */
export function tooltipStyle(palette: ChartPalette): {
  background: string;
  border: string;
  color: string;
  borderRadius: number;
  fontSize: number;
} {
  return {
    background: palette.tooltipBackground,
    border: `1px solid ${palette.tooltipBorder}`,
    color: palette.tooltipText,
    borderRadius: 8,
    fontSize: 12,
  };
}
