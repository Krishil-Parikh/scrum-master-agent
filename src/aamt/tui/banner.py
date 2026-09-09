"""ASCII art for the dashboard: the AGENT.OS wordmark, a globe, a mountain range."""

from __future__ import annotations

_WORDMARK = r"""
 █████╗  ██████╗ ███████╗███╗   ██╗████████╗   ██████╗ ███████╗
██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝  ██╔═══██╗██╔════╝
███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║     ██║   ██║███████╗
██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║     ██║   ██║╚════██║
██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║  ██╗╚██████╔╝███████║
╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
""".strip("\n")

_ASCII_FALLBACK = r"""
   _   ___ ___ _  _ _____    ___  ___
  /_\ / __| __| \| |_   _|  / _ \/ __|
 / _ \ (_ | _|| .` | | |   | (_) \__ \
/_/ \_\___|___|_|\_| |_| (_)\___/|___/
""".strip("\n")


def wordmark(ascii_only: bool = False) -> str:
    return _ASCII_FALLBACK if ascii_only else _WORDMARK


GLOBE = r"""
     ___
   //   \\
  |=======|
  | \   / |
   \\___//
     ===
""".strip("\n")


MOUNTAINS = r"""
              /\
       /\    /  \      /\
      /  \  /    \    /  \   /\
   /\/    \/      \  /    \_/  \
  /   .    .   ..   \/  .        \
""".strip("\n")


TAGLINE = "> THINK. PLAN. BUILD. AUTOMATE. <"
SUBQUOTE = '"A better you, through better tools."'
CENTER_QUOTE = '"Automate the trivial. Augment the hard. Focus on what matters."'
