# Burkeanomics Simulator — Punchlist

## Now
- [ ] Test password reset flow end-to-end (local + Streamlit Cloud)
- [ ] Test cookie auth persistence on Streamlit Cloud
- [ ] Add `extra-streamlit-components` to Streamlit Cloud secrets (n/a — it's in requirements.txt)
- [ ] Streamline Account & My Universes sidebar UI (direction from David)
- [ ] Fix `use_container_width` deprecation warnings (low priority, cosmetic)

## Soon
- [ ] Bcon 304 — expand Electrons & Nucleons section
- [ ] Params panel redesign (prerequisite for subclasses)
- [ ] Supabase: explore Tables/Auth/Logs views (David)
- [ ] Set Supabase Site URL for Streamlit Cloud redirect (Auth → URL Configuration)

## Down the Road
- [ ] Subclasses — GovNuke subclasses first, then others
- [ ] Stripe integration + tier gating
- [ ] Contest mechanic (shared constants, leaderboard)
- [ ] Real PDF export (SaaS backend with Playwright)

## Done ✓
- [x] Electron PC IQ from Adults/Electron × Base IQ
- [x] Universe CRUD (save, load, delete) via Supabase
- [x] Auth — sign up, sign in, sign out, cookie persistence
- [x] Password reset flow
- [x] Email confirmation
- [x] Universe name/description/annotations
- [x] Per-constant notes & source URLs (clickable)
- [x] S$nnT tick format on BP charts
- [x] IQ Points axis labels on all Brains charts
- [x] Suppress 0 ticks globally
- [x] cCon slider suffixes
- [x] HTML fallback for PDF on Streamlit Cloud
- [x] Copyright footer updated
