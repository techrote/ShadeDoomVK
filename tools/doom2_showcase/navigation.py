"""Local material-gallery page navigation; no engine or gameplay changes.

Use a repeatable player-use line with special 243 for NEXT and 244 for
PREVIOUS. MAPINFO next/secretnext supply their destinations. The shortcut's
private config may bind F1 to ``openmenu MaterialGalleryMenu``. KEYCONF adds
the action to Controls without replacing any existing user key binding.
"""

from __future__ import annotations

import re

NEXT_SPECIAL = 243  # src/playsim/p_lnspec.cpp: LS_Exit_Normal
PREVIOUS_SPECIAL = 244  # src/playsim/p_lnspec.cpp: LS_Exit_Secret
MENU_NAME = "MaterialGalleryMenu"
MENU_COMMAND = "openmenu " + MENU_NAME


def _quoted(value: str) -> str:
    return (
        '"'
        + value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
        .replace("\r", " ")
        + '"'
    )


def nav_members(mapnames: list[str], labels: list[str]) -> dict[str, bytes]:
    """Return MAPINFO/MENUDEF/KEYCONF for an ordinary cyclic map gallery.

    NEXT and PREVIOUS are ordinary map changes, with normal player spawn/setup.
    They do not teleport coordinates, force tics or alter simulation. There is
    no custom player class, event handler, renderer-mode command or HUD script.
    """
    if (
        not mapnames
        or len(mapnames) != len(labels)
        or len(set(mapnames)) != len(mapnames)
    ):
        raise ValueError("Each distinct gallery page requires exactly one label")
    if len(mapnames) > 1000:
        raise ValueError("Local gallery exceeds bounded navigation size")
    if any(not re.fullmatch(r"[A-Z][A-Z0-9]{0,7}", name) for name in mapnames):
        raise ValueError("Gallery map names must be 1-8 uppercase alphanumerics")
    mapinfo = ["// Local Doom II material gallery; ordinary map exits only."]
    for index, (name, label) in enumerate(zip(mapnames, labels)):
        mapinfo += [
            "map " + name + " " + _quoted(label),
            "{",
            "  levelnum = " + str(1000 + index),
            "  next = " + _quoted(mapnames[(index + 1) % len(mapnames)]),
            "  secretnext = " + _quoted(mapnames[(index - 1) % len(mapnames)]),
            "  nointermission",
            "}",
        ]
    menudef = [
        'OptionMenu "' + MENU_NAME + '"',
        "{",
        '  Title "Doom II Material Gallery"',
        '  StaticText "Pick a page; Esc returns to the room."',
        '  StaticText "Room signs: use NEXT / PREVIOUS."',
        '  StaticText "Comparisons all stay in hardware mode."',
        '  StaticText " "',
    ]
    for index, (name, label) in enumerate(zip(mapnames, labels), 1):
        menudef.append(
            "  Command "
            + _quoted(f"{index:02d}. {label}")
            + ", "
            + _quoted("map " + name)
        )
    menudef.append("}")
    keyconf = [
        'addkeysection "Material Gallery" "MaterialGallery"',
        'addmenukey "Open gallery page selector" "' + MENU_COMMAND + '"',
    ]
    return {
        "MAPINFO": ("\n".join(mapinfo) + "\n").encode("utf-8"),
        "MENUDEF": ("\n".join(menudef) + "\n").encode("utf-8"),
        "KEYCONF": ("\n".join(keyconf) + "\n").encode("utf-8"),
    }
