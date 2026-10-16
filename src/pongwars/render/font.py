"""@package pongwars.render.font
@brief Tiny 3x5 bitmap font (digits, Latin capitals and basic punctuation).
"""

import unicodedata

import pygame

from pongwars.render.palette import Color

GLYPH_W = 3
GLYPH_H = 5
_GLYPHS: dict[str, str] = {
    "0": "111101101101111",
    "1": "010110010010111",
    "2": "111001111100111",
    "3": "111001111001111",
    "4": "101101111001001",
    "5": "111100111001111",
    "6": "111100111101111",
    "7": "111001001001001",
    "8": "111101111101111",
    "9": "111101111001111",
    "A": "010101111101101",
    "B": "110101110101110",
    "C": "011100100100011",
    "D": "110101101101110",
    "E": "111100110100111",
    "F": "111100110100100",
    "G": "011100101101011",
    "H": "101101111101101",
    "I": "111010010010111",
    "J": "001001001101010",
    "K": "101101110101101",
    "L": "100100100100111",
    "M": "101111111101101",
    "N": "110101101101101",
    "O": "010101101101010",
    "P": "110101110100100",
    "Q": "010101101111011",
    "R": "110101110101101",
    "S": "011100010001110",
    "T": "111010010010010",
    "U": "101101101101111",
    "V": "101101101101010",
    "W": "101101111111101",
    "X": "101101010101101",
    "Y": "101101010010010",
    "Z": "111001010100111",
    "|": "010010010010010",
    ":": "000010000010000",
    "-": "000000111000000",
    ".": "000000000000010",
    "!": "010010010000010",
    "?": "110001010000010",
    "/": "001001010100100",
    ",": "000000000010100",
    "(": "010100100100010",
    ")": "010001001001010",
    "%": "101001010100101",
    "+": "000010111010000",
    "'": "010010000000000",
    "<": "001010100010001",
    ">": "100010001010100",
    "_": "000000000000111",
    " ": "000000000000000",
}

# Characters without a glyph that are dropped (inverted punctuation) or spelled differently.
_REPLACEMENTS = {"¿": "", "¡": "", "ß": "SS", "Æ": "AE", "Œ": "OE", "Ø": "O", "Ł": "L"}


def normalize(text: str) -> str:
    """@brief Reduce text to the font's charset: upper-case, accents removed.

    Works for every Latin-script language (e.g. "Año" becomes "ANO").
    @param text Text to normalise.
    @return Upper-case text made of glyph characters where possible.
    """
    out: list[str] = []
    for char in text.upper():
        char = _REPLACEMENTS.get(char, char)
        for part in unicodedata.normalize("NFD", char):
            if not unicodedata.combining(part):
                out.append(part)
    return "".join(out)


def unsupported_chars(text: str) -> set[str]:
    """@brief Characters of a text that still have no glyph after normalisation.
    @param text Text to check.
    @return The offending characters (empty when everything can be drawn).
    """
    return {char for char in normalize(text) if char not in _GLYPHS}


def text_width(text: str, scale: int = 1) -> int:
    """@brief Pixel width of a string.
    @param text Text to measure.
    @param scale Integer pixel scale.
    @return Width in pixels.
    """
    return max(0, len(normalize(text)) * (GLYPH_W + 1) * scale - scale)


def draw_text(
    surface: pygame.Surface, text: str, x: int, y: int, color: Color, scale: int = 1
) -> None:
    """@brief Draw upper-cased text; unknown characters render as blanks.
    @param surface Target surface.
    @param text Text to draw.
    @param x Left pixel.
    @param y Top pixel.
    @param color Text colour.
    @param scale Integer pixel scale.
    """
    cursor = x
    for char in normalize(text):
        bits = _GLYPHS.get(char, _GLYPHS[" "])
        for index, bit in enumerate(bits):
            if bit == "1":
                px = cursor + (index % GLYPH_W) * scale
                py = y + (index // GLYPH_W) * scale
                surface.fill(color, (px, py, scale, scale))
        cursor += (GLYPH_W + 1) * scale
