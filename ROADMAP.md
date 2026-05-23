# Burkeanomics Simulator — Roadmap

```mermaid
mindmap
  root((Burkeanomics Sim))
    SaaS

      Streamline account UI
      Stripe & Tiers
        Free vs Pro feature split
        Stripe Checkout
        Webhook → Supabase tier update
      Contests
        Shared constants
        Competing scenarios
        Leaderboard
    Sim Features
      Universe description & annotations ✓
      Subclasses
        Requires new params UI first
        GovNuke subclasses first
        Then Providers, SinSayers, Electrons
      Params UI redesign
        Full-width panel or tabs
        Scales for subclass depth
    Charts & UI
      use_container_width deprecation
      Dark mode
    Universe 3D → 4D
      3D via Three.js WebGL component (st.components.html)
        Electron (Nemo) fixed at center
        Background Electrons at depth, low opacity
        Nucleons in 3D space at N/E-ratio counts
        Bubble size = per-capita Power
      4D = Brownian Motion animation
        Each nucleon has velocity vector (vx, vy, vz)
        Soft spring attraction back to orbital band
        Light inter-nucleon repulsion (no clumping)
        requestAnimationFrame at 60fps
    PDF Export
      HTML fallback on Streamlit Cloud ✓
      Real PDF deferred to SaaS backend
    Bcon Content
      304 Human Dualities — E&N expansion
  
```
