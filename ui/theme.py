"""Look and feel: colours, verdict styles, page CSS and small formatting helpers."""
from __future__ import annotations

# Chart colours: categorical slots from the dataviz reference palette; status colours are reserved for the verdict.
BLUE, ORANGE, AQUA, MUTED, RED = "#2a78d6", "#eb6834", "#1baf7a", "#898781", "#d03b3b"
CLASS_COLOURS = {"Standard": BLUE, "Plus": ORANGE, "Prime": AQUA}
VERDICTS = {
    "affordable": ("✅", "Affordable", "#0a7d32", "#0ca30c", "#ffffff"),
    "tight": ("⚠️", "Tight", "#c98500", "#fab219", "#0b0b0b"),
    "gap": ("⛔", "Cash gap", "#a32626", "#d03b3b", "#ffffff"),
    "ineligible": ("🚫", "Not eligible", "#5c5b57", "#898781", "#ffffff"),
}
FLAT_LABELS = {"2-room": "2-room Flexi", "3-room": "3-room", "4-room": "4-room", "5-room": "5-room", "3gen": "3Gen"}


def money(x: float) -> str:
    return f"${x:,.0f}"


def md(text: str) -> str:
    """Escape dollar signs: Streamlit markdown renders text between two $ as LaTeX."""
    return text.replace("$", r"\$")


def badge(text: str, colour: str | None = None) -> str:
    return (f'<span class="badge" style="background:{colour}">{text}</span>' if colour
            else f'<span class="badge soft">{text}</span>')


CSS = """
<style>
@keyframes drift {0% {background-position: 0% 50%} 50% {background-position: 100% 50%} 100% {background-position: 0% 50%}}
@keyframes pop {0% {transform: scale(.6); opacity: 0} 70% {transform: scale(1.12)} 100% {transform: scale(1); opacity: 1}}
@keyframes rise {from {transform: translateY(8px); opacity: 0} to {transform: none; opacity: 1}}
.hero {background: linear-gradient(120deg, #0d366b, #1c5cab, #2a78d6, #1baf7a, #1c5cab);
       background-size: 300% 300%; animation: drift 18s ease infinite;
       border-radius: 1.5rem; padding: 2.2rem 2.4rem 1.7rem; color: #fff; margin-bottom: 1.4rem;
       box-shadow: 0 18px 40px rgba(13, 54, 107, .28); position: relative; overflow: hidden;}
.hero::before {content: ""; position: absolute; width: 420px; height: 420px; right: -120px; top: -180px;
       background: radial-gradient(circle, rgba(255,255,255,.22), transparent 65%); border-radius: 50%;}
.hero::after {content: "🏠"; position: absolute; right: 2rem; bottom: .4rem; font-size: 7.5rem; opacity: .16;}
.hero h1 {color: #fff; margin: 0 0 .4rem; font-size: 2.6rem; line-height: 1.08; padding: 0; letter-spacing: -.02em;}
.hero p {color: rgba(255,255,255,.9); margin: 0 0 1.2rem; font-size: 1.08rem; max-width: 46rem;}
.stats {display: flex; gap: 2.2rem; flex-wrap: wrap; margin-bottom: 1rem;}
.stats div {line-height: 1.1;}
.stats b {display: block; font-size: 1.9rem; font-weight: 800; color: #fff;}
.stats span {font-size: .8rem; letter-spacing: .06em; text-transform: uppercase; color: rgba(255,255,255,.75);}
.chip {display: inline-block; background: rgba(255,255,255,.15); border: 1px solid rgba(255,255,255,.3);
       border-radius: 999px; padding: .22rem .8rem; margin: 0 .4rem .4rem 0; font-size: .8rem; color: #fff;
       backdrop-filter: blur(6px);}
.section {font-size: 1.45rem; font-weight: 800; margin: 1.2rem 0 .2rem; letter-spacing: -.01em;}
.section small {display: block; font-size: .92rem; font-weight: 400; opacity: .65; margin-top: .15rem;}
.verdict {border-radius: 1.2rem; padding: 1.3rem 1.5rem; margin-bottom: 1rem; animation: rise .45s ease;
          box-shadow: 0 12px 30px rgba(0,0,0,.14); position: relative; overflow: hidden;}
.verdict::after {content: ""; position: absolute; width: 260px; height: 260px; right: -80px; top: -120px;
          background: radial-gradient(circle, rgba(255,255,255,.25), transparent 65%); border-radius: 50%;}
.verdict .label {font-size: .78rem; letter-spacing: .08em; text-transform: uppercase; opacity: .85;}
.verdict .big {font-size: 2.2rem; font-weight: 800; line-height: 1.15; margin: .15rem 0 .35rem;}
.verdict .big .icon {display: inline-block; animation: pop .5s ease;}
.verdict .why {font-size: 1rem; opacity: .95;}
.step {font-weight: 700; font-size: 1.05rem; margin: .1rem 0 .5rem;}
.step span {display: inline-flex; align-items: center; justify-content: center; width: 1.7rem; height: 1.7rem;
            border-radius: 999px; background: linear-gradient(135deg, #2a78d6, #1baf7a); color: #fff;
            font-size: .85rem; margin-right: .55rem; box-shadow: 0 4px 10px rgba(42,120,214,.35);}
.badge {display: inline-block; border-radius: 999px; padding: .15rem .65rem; font-size: .75rem; font-weight: 700;
        margin: 0 .3rem .3rem 0; color: #fff;}
.badge.soft {background: rgba(137,135,129,.18); color: inherit; font-weight: 600;}
.pcard h3 {margin: .1rem 0 .1rem; padding: 0; font-size: 1.35rem;}
.pcard .meta {opacity: .7; font-size: .9rem; margin-bottom: .5rem;}
.basis {font-size: .82rem; opacity: .75; border-left: 3px solid #eb6834; padding-left: .6rem; margin: .4rem 0;}
.timeline {display: grid; grid-template-columns: 1fr 1fr; gap: .7rem; margin: .5rem 0 1rem;}
.tl {border-radius: 1rem; padding: .9rem 1rem; background: rgba(42,120,214,.08); border: 1px solid rgba(42,120,214,.18);
     position: relative; animation: rise .4s ease both;}
.tl:nth-child(2) {animation-delay: .06s} .tl:nth-child(3) {animation-delay: .12s} .tl:nth-child(4) {animation-delay: .18s}
.tl .n {font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; opacity: .65;}
.tl .t {font-weight: 700; margin: .15rem 0 .3rem;}
.tl .v {font-size: 1.35rem; font-weight: 800; color: #2a78d6;}
.tl .d {font-size: .8rem; opacity: .75; margin-top: .25rem;}
@media (max-width: 800px) {.hero h1 {font-size: 2rem;} .stats {gap: 1.2rem;}}
[class*="st-key-card"] {border-radius: 1.2rem !important; transition: box-shadow .2s ease, transform .2s ease;
       box-shadow: 0 2px 10px rgba(0,0,0,.04);}
[class*="st-key-card"]:hover {box-shadow: 0 10px 28px rgba(42,120,214,.14); transform: translateY(-2px);}
.legend {display: flex; flex-wrap: wrap; gap: .4rem 1.1rem; font-size: .8rem; opacity: .85; margin-top: -.3rem;}
.legend i {display: inline-block; width: .7rem; height: .7rem; border-radius: 50%; margin-right: .35rem;
           vertical-align: -1px;}
[class*="st-key-plain"] {background: linear-gradient(135deg, rgba(42,120,214,.08), rgba(27,175,122,.08));
       border: 1px solid rgba(42,120,214,.18); border-radius: 1.1rem; padding: .9rem 1.1rem .4rem; margin: .4rem 0 .6rem;
       animation: rise .45s ease;}
.demo {border-radius: 1rem; padding: .9rem 1.1rem; margin-bottom: .6rem; font-size: .92rem;
       background: linear-gradient(135deg, rgba(235,104,52,.10), rgba(42,120,214,.10));
       border: 1px solid rgba(235,104,52,.25);}
.foot {opacity: .7; font-size: .85rem; text-align: center; margin-top: 2.4rem;}
</style>
"""
