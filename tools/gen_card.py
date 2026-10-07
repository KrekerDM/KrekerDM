"""Собирает assets/card.svg и README.md: карточку профиля.

Фон: облачный шум, как make_backdrop во Frostpane, сдвинутый в зелёный.
Стекло: 12% белого поверх фона, размытого на 50px и насыщенного на 180%.
Текст векторный, лежит поверх картинки.

Версии, беты и число сборок для Windows берутся из релизов GitHub, число
твиков из описания репозитория. Новый релиз попадает на карточку сам:
.github/workflows/card.yml запускает скрипт раз в сутки. Если текст не
изменился, файлы не трогаются.

    pip install pillow numpy
    python tools/gen_card.py            # обновить, если изменился текст
    python tools/gen_card.py --force    # пересобрать и фон

Выход 1, если GitHub не ответил или контраст ниже 4.5:1. Старая карточка
в этом случае остаётся как была.
"""

import base64
import html
import io
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CARD = ROOT / "assets" / "card.svg"
README = ROOT / "README.md"

OWNER = "KrekerDM"
LABEL_LEFT = "Норвегия · на GitHub с мая 2026"
LABEL_RIGHT = "klondaik.uk"

# Строки карточки по порядку. Факт пишется так, чтобы не устареть, или
# берёт число из описания репозитория: count — регулярка, forms — формы
# слова для 1, 2 и 5, fallback — текст, если числа в описании не нашлось.
PROJECTS = [
    {
        "repo": "klondaik-tweaker",
        "fact": "{n} {word}, каждый откатывается отдельно",
        "count": r"(\d+)\s+твик",
        "forms": ("твик", "твика", "твиков"),
        "fallback": "твики Windows, каждый откатывается отдельно",
        "ru_en": True,
    },
    {"repo": "BaritoneBots", "fact": "клиент без окна, около 1 ГБ RAM на бота", "ru_en": True},
    {"repo": "RadioSetLink-RSL", "fact": "FPV-пульт как геймпад Xbox 360 по CRSF", "ru_en": True},
    {"repo": "handwriting-recognition", "fact": "CNN на PyTorch показывает свои активации", "ru_en": True},
    {"repo": "cluumsy", "fact": "задержка и потеря своих пакетов через WinDivert"},
    {"repo": "sv.autoclick", "fact": "ищет цель по картинке, а не по координатам", "ru_en": True},
    {"repo": "discord-webhook-sender", "fact": "предпросмотр как в Discord, до 10 embeds"},
    {"repo": "shorts-blocker", "fact": "убирает Shorts, один файл без зависимостей"},
]

# --- Размеры: координаты SVG в 1x, растр в 2x для ретины ---------------
W = 840
SCALE = 2
ROW = 40
PANE_TOP = 196
SEED = 7

# --- Фон: те же параметры, что в make_backdrop из Frostpane ------------
KNEE, SLOPE, LIFT = 118, 0.34, 13
TOP, BOTTOM = 128, 78
OCTAVES = [(6, 1.0), (14, 0.5), (32, 0.25), (70, 0.12)]

# --- Токены: Frostpane, сдвинутый в зелёный ----------------------------
GROUND = (7, 16, 12)
VEIL = (0.36, 0.38, 0.44)           # верх, середина, низ
SURFACE_WHITE = 0.12
BLUR_PX = 50
SATURATE = 1.8
TOKENS = {
    "text": "#FFFFFF",
    "text-soft": "#F4F8F6",
    "text-dim": "#EBF2EE",
    "accent-text": "#E3F6EB",
}
AA = 4.5


# --- Данные -------------------------------------------------------------

def api(path):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "gen_card"},
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def plural(n, forms):
    """forms — формы для 1, 2 и 5: («программа», «программы», «программ»)."""
    if n % 10 == 1 and n % 100 != 11:
        return forms[0]
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return forms[1]
    return forms[2]


def is_windows_build(name):
    name = name.lower()
    return name.endswith(".exe") or (name.endswith(".zip") and "win" in name)


def collect():
    rows = []
    for p in PROJECTS:
        repo = api(f"/repos/{OWNER}/{p['repo']}")
        releases = api(f"/repos/{OWNER}/{p['repo']}/releases?per_page=1")
        latest = releases[0] if releases else None

        fact = p["fact"]
        if "count" in p:
            m = re.search(p["count"], repo.get("description") or "")
            if m:
                n = int(m.group(1))
                fact = fact.format(n=n, word=plural(n, p["forms"]))
            else:
                fact = p["fallback"]

        tag = latest["tag_name"].removeprefix("v") if latest else "без релиза"
        rows.append({
            "name": p["repo"],
            "fact": fact,
            "version": tag,
            "beta": bool(latest) and (latest["prerelease"] or tag.startswith("0.")),
            "windows": bool(latest) and any(is_windows_build(a["name"]) for a in latest["assets"]),
            "ru_en": p.get("ru_en", False),
        })
    return rows


def texts(rows):
    win = sum(r["windows"] for r in rows)
    ru_en = sum(r["ru_en"] for r in rows)
    total = len(rows)
    betas = [r["name"] for r in rows if r["beta"]]

    lead = [
        f"{win} {plural(win, ('программа', 'программы', 'программ'))} для Windows "
        "с готовой сборкой, бот для Minecraft",
        f"и юзерскрипт для YouTube. У {ru_en} {plural(ru_en, ('проекта', 'проектов', 'проектов'))} "
        f"из {total} интерфейс на RU и EN.",
    ]
    footer = "Версии берутся из релизов GitHub раз в сутки."
    if betas:
        footer = f"Бета сейчас: {', '.join(betas)}. " + footer
    return lead, footer


# --- Разметка -----------------------------------------------------------

def layout(n_rows):
    pane = (32, PANE_TOP, 808, PANE_TOP + 24 + ROW * n_rows)
    footer_y = pane[3] + 32
    return pane, footer_y, footer_y + 24


def text_layer(rows, lead, footer):
    pane, footer_y, _ = layout(len(rows))
    e = html.escape
    out = [
        '  <g filter="url(#on-photo)">',
        f'    <text class="sans label dim" x="32" y="52">{e(LABEL_LEFT)}</text>',
        f'    <text class="sans label dim" x="808" y="52" text-anchor="end">{e(LABEL_RIGHT)}</text>',
        '    <text class="sans h1 text" x="30" y="104">KrekerDM</text>',
        f'    <text class="sans lead soft" x="32" y="140">{e(lead[0])}</text>',
        f'    <text class="sans lead soft" x="32" y="168">{e(lead[1])}</text>',
        '  </g>',
        '  <g>',
    ]
    for i, r in enumerate(rows):
        top = pane[1] + 12 + ROW * i
        base = top + 25
        if i:
            out.append(f'    <rect class="hairline" x="56" y="{top}" width="728" height="1"/>')
        out.append(f'    <text class="mono name" x="56" y="{base}">{e(r["name"])}</text>')
        out.append(f'    <text class="sans body soft" x="264" y="{base}">{e(r["fact"])}</text>')
        out.append(f'    <text class="mono small dim" x="784" y="{base}" text-anchor="end">{e(r["version"])}</text>')
    out += [
        '  </g>',
        '  <g filter="url(#on-photo)">',
        f'    <text class="sans small dim" x="32" y="{footer_y}">{e(footer)}</text>',
        '  </g>',
    ]
    return "\n".join(out)


def svg(rows, lead, footer, jpeg_b64):
    _, _, h = layout(len(rows))
    desc = html.escape(f"{LABEL_LEFT}. {lead[0]} {lead[1]}")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" role="img" aria-labelledby="t d">
  <title id="t">KrekerDM</title>
  <desc id="d">{desc}</desc>
  <defs>
    <filter id="on-photo" x="-5%" y="-40%" width="110%" height="180%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="9" result="b1"/>
      <feOffset in="b1" dy="2" result="o1"/>
      <feFlood flood-color="#050C09" flood-opacity="0.75"/>
      <feComposite in2="o1" operator="in" result="s1"/>
      <feGaussianBlur in="SourceAlpha" stdDeviation="1.5" result="b2"/>
      <feOffset in="b2" dy="1" result="o2"/>
      <feFlood flood-color="#050C09" flood-opacity="0.6"/>
      <feComposite in2="o2" operator="in" result="s2"/>
      <feMerge><feMergeNode in="s1"/><feMergeNode in="s2"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <style>
      .sans {{ font-family: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif; }}
      .mono {{ font-family: "IBM Plex Mono", "Cascadia Code", "SFMono-Regular", Menlo, monospace; }}
      .text {{ fill: {TOKENS["text"]}; }}
      .soft {{ fill: {TOKENS["text-soft"]}; }}
      .dim  {{ fill: {TOKENS["text-dim"]}; }}
      .h1    {{ font-size: 48px; font-weight: 600; letter-spacing: -0.96px; }}
      .lead  {{ font-size: 18px; }}
      .body  {{ font-size: 16px; }}
      .small {{ font-size: 14px; }}
      .label {{ font-size: 13px; font-weight: 500; }}
      .name  {{ font-size: 14px; font-weight: 500; fill: {TOKENS["accent-text"]}; }}
      .hairline {{ fill: #FFFFFF; fill-opacity: 0.15; }}
    </style>
  </defs>

  <image width="{W}" height="{h}" preserveAspectRatio="none" href="data:image/jpeg;base64,{jpeg_b64}"/>

<!-- text -->
{text_layer(rows, lead, footer)}
<!-- /text -->
</svg>
'''


def readme(rows, lead, footer):
    items = " ".join(f"{r['name']} {r['version']}: {r['fact']}." for r in rows)
    alt = html.escape(f"KrekerDM. {LABEL_LEFT}, сайт {LABEL_RIGHT}. {lead[0]} {lead[1]} {items} {footer}")
    return f'<img src="assets/card.svg" width="100%" alt="{alt}">\n'


# --- Фон и стекло -------------------------------------------------------

def render_backdrop(h1x, pane):
    import numpy as np
    from PIL import Image, ImageEnhance, ImageFilter

    w, h = W * SCALE, h1x * SCALE
    rng = np.random.default_rng(SEED)

    def noise(cells):
        small = Image.fromarray(
            rng.integers(0, 256, (int(cells * h / w) + 1, cells), dtype=np.uint8)
        )
        big = small.resize((w, h), Image.BICUBIC)
        return np.asarray(big.filter(ImageFilter.GaussianBlur(w / cells * 0.5)), float)

    total = sum(a for _, a in OCTAVES)
    clouds = sum(noise(c) * a / total for c, a in OCTAVES)
    # Второй крупный шум сдвигает оттенок: бирюза <-> салатовый.
    tint = np.clip((noise(4) - 128) / 64, -1, 1)

    t = np.linspace(0, 1, h)[:, None]
    v = TOP - (TOP - BOTTOM) * t + (clouds - 128) * 0.45
    v = np.where(v > KNEE, KNEE + (v - KNEE) * SLOPE, v)
    v = v * 0.95 + LIFT

    r = v * (0.58 + 0.10 * tint - 0.04 * t)
    g = v * (1.06 + 0.02 * tint)
    b = v * (0.78 - 0.14 * tint + 0.12 * t)
    img = np.clip(np.stack([r, g, b], -1), 0, 255)

    # Вуаль: сильнее внизу, как --veil.
    alpha = np.interp(t[:, 0], [0, 0.45, 1], VEIL)[:, None, None]
    img = img * (1 - alpha) + np.array(GROUND) * alpha

    # Виньетка: эллипс 95% x 70% с центром в 50% 28%.
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt(((xx - w * 0.5) / (w * 0.95)) ** 2 + ((yy - h * 0.28) / (h * 0.70)) ** 2)
    va = np.interp(d, [0, 0.68, 1.0], [0, 0.14, 0.32])[..., None]
    img = img * (1 - va) + np.array(GROUND) * va
    img = Image.fromarray(img.astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2 * SCALE))

    # Стекло: backdrop-filter blur(50px) saturate(180%), потом 12% белого.
    x0, y0, x1, y1 = (c * SCALE for c in pane)
    blurred = ImageEnhance.Color(img.filter(ImageFilter.GaussianBlur(BLUR_PX * SCALE))).enhance(SATURATE)
    region = np.asarray(blurred.crop((x0, y0, x1, y1)), float)
    region = region * (1 - SURFACE_WHITE) + 255 * SURFACE_WHITE
    img.paste(Image.fromarray(region.astype(np.uint8)), (x0, y0))
    return img


def measure(img, pane, footer_y):
    """Самые светлые 5% каждой зоны, как в tools/contrast.py Frostpane."""
    import numpy as np

    def lum(c):
        c = np.asarray(c, float) / 255
        c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
        return 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]

    zones = {
        "на фото, шапка": (32, 32, 808, 176),
        "стекло": pane,
        "на фото, подвал": (32, footer_y - 20, 808, footer_y + 8),
    }
    worst = 99.0
    for name, box in zones.items():
        x0, y0, x1, y1 = (c * SCALE for c in box)
        band = np.asarray(img.crop((x0, y0, x1, y1)).resize((200, 60)), float).reshape(-1, 3)
        bg = lum(band[np.argsort(lum(band))[int(len(band) * 0.95)]])
        ratios = []
        for value in TOKENS.values():
            fg = lum(tuple(int(value[i:i + 2], 16) for i in (1, 3, 5)))
            ratios.append((max(fg, bg) + 0.05) / (min(fg, bg) + 0.05))
        worst = min(worst, *ratios)
        print(f"  {name:16} " + "  ".join(f"{k} {r:.2f}" for k, r in zip(TOKENS, ratios)))
    print(f"  худшее {worst:.2f}:1, порог {AA}:1")
    return worst


def main(force):
    try:
        rows = collect()
    except OSError as err:
        print(f"GitHub не ответил: {err}. Карточка не тронута.")
        return 1

    lead, footer = texts(rows)
    pane, footer_y, h = layout(len(rows))
    layer = text_layer(rows, lead, footer)

    old = CARD.read_text(encoding="utf-8") if CARD.exists() else ""
    same_text = f"<!-- text -->\n{layer}\n<!-- /text -->" in old
    same_size = f'viewBox="0 0 {W} {h}"' in old
    new_readme = readme(rows, lead, footer)
    same_readme = README.exists() and README.read_text(encoding="utf-8") == new_readme

    if same_text and same_size and same_readme and not force:
        print("Без изменений.")
        return 0

    if same_size and not force:
        jpeg = re.search(r'href="data:image/jpeg;base64,([^"]+)"', old).group(1)
    else:
        img = render_backdrop(h, pane)
        if measure(img, pane, footer_y) < AA:
            print("Контраст ниже порога. Карточка не тронута.")
            return 1
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=84, optimize=True, progressive=True)
        jpeg = base64.b64encode(buf.getvalue()).decode()

    CARD.write_text(svg(rows, lead, footer, jpeg), encoding="utf-8", newline="\n")
    README.write_text(new_readme, encoding="utf-8", newline="\n")
    for r in rows:
        print(f"  {r['name']:24} {r['version']:14} {r['fact']}")
    print(f"  {lead[0]} {lead[1]}\n  {footer}")
    return 0


if __name__ == "__main__":
    sys.exit(main("--force" in sys.argv[1:]))
