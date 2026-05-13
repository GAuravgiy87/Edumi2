---
name: Mission Critical Intelligence
colors:
  surface: '#10131a'
  surface-dim: '#10131a'
  surface-bright: '#363941'
  surface-container-lowest: '#0b0e15'
  surface-container-low: '#191b23'
  surface-container: '#1d2027'
  surface-container-high: '#272a31'
  surface-container-highest: '#32353c'
  on-surface: '#e1e2ec'
  on-surface-variant: '#c2c6d6'
  inverse-surface: '#e1e2ec'
  inverse-on-surface: '#2e3038'
  outline: '#8c909f'
  outline-variant: '#424754'
  surface-tint: '#adc6ff'
  primary: '#adc6ff'
  on-primary: '#002e6a'
  primary-container: '#4d8eff'
  on-primary-container: '#00285d'
  inverse-primary: '#005ac2'
  secondary: '#4edea3'
  on-secondary: '#003824'
  secondary-container: '#00a572'
  on-secondary-container: '#00311f'
  tertiary: '#ffb95f'
  on-tertiary: '#472a00'
  tertiary-container: '#ca8100'
  on-tertiary-container: '#3e2400'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#d8e2ff'
  primary-fixed-dim: '#adc6ff'
  on-primary-fixed: '#001a42'
  on-primary-fixed-variant: '#004395'
  secondary-fixed: '#6ffbbe'
  secondary-fixed-dim: '#4edea3'
  on-secondary-fixed: '#002113'
  on-secondary-fixed-variant: '#005236'
  tertiary-fixed: '#ffddb8'
  tertiary-fixed-dim: '#ffb95f'
  on-tertiary-fixed: '#2a1700'
  on-tertiary-fixed-variant: '#653e00'
  background: '#10131a'
  on-background: '#e1e2ec'
  surface-variant: '#32353c'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 36px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
    letterSpacing: -0.01em
  body-base:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.4'
    letterSpacing: 0em
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: '1'
    letterSpacing: 0.05em
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '700'
    lineHeight: '1'
    letterSpacing: 0.1em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 16px
  margin-mobile: 16px
  margin-desktop: 32px
  card-padding: 1.25rem
---

## Brand & Style

This design system establishes a high-performance "Command Center" aesthetic tailored for a mission-critical AI educational ecosystem. The brand personality is authoritative, precise, and sophisticated, evoking the feeling of a high-tech flight deck or a cybersecurity monitoring hub.

The visual style leverages **Modern Glassmorphism** blended with **Minimalist Data Visualization**. It prioritizes density and low-latency information retrieval, ensuring users feel in complete control of a powerful, secure AI engine. The emotional response is one of calm confidence in the face of complex data.

## Colors

The palette is anchored in deep, nocturnal tones to reduce eye strain during long-duration monitoring. 

- **Primary Canvas:** Deep Slate (#0f172a) provides the foundation for the environment.
- **Surface Layers:** Charcoal (#1e293b) defines functional zones and interactive containers.
- **Tech Accents:** Vibrant Blue (#3b82f6) is used exclusively for primary actions, active states, and data highlights.
- **Semantic Status:** Emerald (#10b981) represents "Active" or "Optimal" states, while Amber (#f59e0b) is reserved for "Alerts" or "Required Attention."

## Typography

The system utilizes **Inter** for its exceptional legibility in dense UI environments. A secondary monospaced font, **JetBrains Mono**, is introduced for data-rich displays, timestamps, and AI-generated logs to reinforce the technical nature of the ecosystem.

Hierarchy is strictly enforced through weight and letter spacing rather than excessive size shifts. Large headers use tighter tracking for a compact look, while small labels use increased tracking and all-caps styling for maximum scannability in secondary dashboard regions.

## Layout & Spacing

The layout follows a **Fluid 12-Column Grid** designed for high information density. 

- **Density:** The spacing rhythm is based on a 4px baseline, favoring compact layouts that minimize vertical scrolling.
- **Responsiveness:** On desktop, the dashboard uses a fixed sidebar for navigation with fluid content panels. On mobile, panels stack vertically, and margins reduce from 32px to 16px.
- **Alignment:** All elements must align to the grid to maintain the "engineered" aesthetic. Use 16px gutters to provide clear visual separation between dense data modules.

## Elevation & Depth

This design system eschews traditional soft shadows in favor of **Tonal Layers** and **Glassmorphism**.

1.  **Base Layer:** The Deep Slate background (#0f172a) acts as the foundation.
2.  **Surface Tier:** Components sit on Charcoal (#1e293b) surfaces with 1px subtle borders (20% white) to define boundaries.
3.  **Overlay Tier:** Modals, tooltips, and floating menus use a 60% transparent Charcoal background with a 12px backdrop blur (Glassmorphism), creating a sense of physical depth without blocking the data underneath.
4.  **Indicators:** Active states are highlighted with "Glow" effects—subtle, colored outer glows using the primary blue or emerald, simulating a backlit hardware display.

## Shapes

The shape language is **Soft-Technical**. A base radius of 0.25rem (4px) is applied to most components to maintain a crisp, professional appearance while avoiding the harshness of sharp corners. Larger containers like cards may use a 0.5rem (8px) radius to distinguish them from smaller UI inputs. Progress bars and status tags utilize pill-shaped caps (full round) to differentiate "dynamic" elements from structural ones.

## Components

- **Compact Cards:** Use a 1px border (#ffffff15) with no shadow. Headers within cards should use the `label-caps` typography for clear categorization.
- **Primary Buttons:** Solid Tech-Blue (#3b82f6) with white text. High-contrast and minimal padding for a utilitarian feel.
- **Status Indicators:** "Pulsing" 8px dots indicate real-time AI activity. Emerald for "Online/Syncing" and Amber for "Processing/Attention Needed."
- **Data Visualizations:** Line charts should use 2px strokes with a subtle gradient fill below the line. Use monochromatic blue scales to maintain the low-latency visual vibe.
- **Input Fields:** Darker than the surface background (#0b1120) with a 1px border. On focus, the border transitions to Tech-Blue with a 2px outer glow.
- **Real-time Progress:** Sleek, thin (4px) progress bars. Use a "shimmer" animation to indicate active data transfer or AI computation.
- **Icons:** Use Lucide-style 2px stroke icons. Icons should always be accompanied by text labels or tooltips to ensure mission-critical clarity.