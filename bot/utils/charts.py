"""
Генератор тёмных карточек для Telegram-бота.
Использует Pillow для создания PNG-изображений.
"""
from io import BytesIO
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

# ─── Палитра тёмной темы ──────────────────────────────────────────────────────
BG       = (11, 12, 16)        # Darkest gray/black
CARD     = (25, 30, 40)        # Dark slate
CARD2    = (35, 42, 55)        # Lighter slate
ACCENT   = (255, 0, 127)       # Neon Pink
GREEN    = (57, 255, 20)       # Neon Green (Matrix)
RED      = (255, 0, 85)        # Hot Red/Pink
YELLOW   = (15, 240, 252)      # Neon Cyan
BLUE     = (15, 240, 252)      # Neon Cyan
PROTEIN  = (255, 0, 127)       # Neon Pink
FAT      = (15, 240, 252)      # Neon Cyan
CARBS    = (57, 255, 20)       # Neon Green
WHITE    = (255, 255, 255)     # Bright White
GRAY     = (197, 198, 199)     # Silver
DIVIDER  = (69, 162, 158)      # Teal

W, H = 800, 420  # размер карточки


def _get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Возвращает системный шрифт нужного размера."""
    try:
        # Windows
        path = "C:/Windows/Fonts/arial.ttf" if not bold else "C:/Windows/Fonts/arialbd.ttf"
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _bar(draw: ImageDraw.Draw, x: int, y: int, width: int, height: int,
         filled: float, color: tuple, bg: tuple = CARD2, radius: int = 6):
    """Рисует прогресс-бар с закруглёнными углами."""
    draw.rounded_rectangle([x, y, x + width, y + height], radius, fill=bg)
    filled_w = max(radius * 2, int(width * min(filled, 1.0)))
    if filled_w > 0:
        draw.rounded_rectangle([x, y, x + filled_w, y + height], radius, fill=color)


def _card_base(title: str, subtitle: str = "") -> tuple[Image.Image, ImageDraw.Draw]:
    """Создаёт базовую тёмную карточку с заголовком."""
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Фоновый прямоугольник
    draw.rounded_rectangle([16, 16, W - 16, H - 16], 10, fill=CARD, outline=GREEN, width=2)
    
    # "Терминал" хедер
    font_term = _get_font(14)
    draw.text((25, 20), "root@uffnv:~# ./life_manager.sh", fill=GREEN, font=font_term)

    # Заголовок
    font_title = _get_font(28, bold=True)
    font_sub = _get_font(18)
    draw.text((40, 46), f"// {title.upper()}", fill=WHITE, font=font_title)
    if subtitle:
        draw.text((40, 82), f"> {subtitle}", fill=YELLOW, font=font_sub)

    # Разделитель
    y_div = 110 if subtitle else 90
    draw.line([(40, y_div), (W - 40, y_div)], fill=DIVIDER, width=1)

    return img, draw


def _to_bytes(img: Image.Image) -> BytesIO:
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ─── Финансовая карточка ──────────────────────────────────────────────────────

def generate_finance_card(
    income: float,
    expense: float,
    period_label: str,
    top_cats: list[tuple[str, float]],  # [(name, amount), ...]
    budget_total: float = 0,
) -> BytesIO:
    from datetime import date
    month_name = {
        1:"Январь",2:"Февраль",3:"Март",4:"Апрель",
        5:"Май",6:"Июнь",7:"Июль",8:"Август",
        9:"Сентябрь",10:"Октябрь",11:"Ноябрь",12:"Декабрь"
    }[date.today().month]

    img, draw = _card_base("Финансы", f"{month_name} — {period_label}")

    f_big   = _get_font(32, bold=True)
    f_med   = _get_font(20, bold=True)
    f_small = _get_font(17)
    f_label = _get_font(15)

    balance = income - expense

    # ─ Блок баланса ─
    bal_color = GREEN if balance >= 0 else RED
    draw.text((40, 128), "Баланс", fill=GRAY, font=f_small)
    bal_sign = "+" if balance >= 0 else ""
    draw.text((40, 150), f"{bal_sign}{balance:,.0f} ₽", fill=bal_color, font=f_big)

    # ─ Доходы / Расходы ─
    draw.rounded_rectangle([40, 205, 270, 265], 12, fill=CARD2)
    draw.text((56, 215), "Доходы", fill=GRAY, font=f_label)
    draw.text((56, 236), f"+{income:,.0f} ₽", fill=GREEN, font=f_med)

    draw.rounded_rectangle([285, 205, 515, 265], 12, fill=CARD2)
    draw.text((301, 215), "Расходы", fill=GRAY, font=f_label)
    draw.text((301, 236), f"-{expense:,.0f} ₽", fill=RED, font=f_med)

    # ─ Топ расходов ─
    if top_cats and expense > 0:
        draw.text((40, 285), "Куда уходят деньги", fill=GRAY, font=f_label)
        cat_colors = [RED, YELLOW, ACCENT]
        for i, (name, amount) in enumerate(top_cats[:3]):
            y = 308 + i * 34
            pct = min(amount / expense, 1.0)
            # Название + сумма
            label = f"{name[:18]}"
            draw.text((40, y + 3), label, fill=WHITE, font=f_label)
            draw.text((530, y + 3), f"{amount:,.0f} ₽", fill=GRAY, font=f_label)
            # Прогресс-бар
            _bar(draw, 230, y + 5, 290, 14, pct, cat_colors[i])
            draw.text((532, y + 3), f"  {pct*100:.0f}%", fill=GRAY, font=f_label)
    else:
        draw.text((40, 300), "Трат в этом периоде нет", fill=GRAY, font=f_small)

    # ─ Правый акцент ─
    draw.rounded_rectangle([W - 175, 128, W - 40, 195], 14, fill=CARD2)
    draw.text((W - 163, 135), "Доход/Расход", fill=GRAY, font=f_label)
    ratio = income / max(expense, 1)
    ratio_color = GREEN if ratio >= 1 else RED
    draw.text((W - 163, 158), f"×{ratio:.1f}", fill=ratio_color, font=f_med)

    return _to_bytes(img)


# ─── Карточка питания ─────────────────────────────────────────────────────────

def generate_fitness_card(
    calories: int,
    protein: float,
    fat: float,
    carbs: float,
    goal_calories: Optional[int],
    current_weight: Optional[float],
    target_weight: Optional[float],
) -> BytesIO:
    img, draw = _card_base("Питание и активность", "Сегодняшний прогресс")

    f_big   = _get_font(36, bold=True)
    f_med   = _get_font(22, bold=True)
    f_small = _get_font(17)
    f_label = _get_font(15)

    # ─ Калории ─
    draw.text((40, 128), "Калорий сегодня", fill=GRAY, font=f_label)
    draw.text((40, 150), f"{calories:,}", fill=WHITE, font=f_big)
    draw.text((40 + len(str(calories)) * 22, 170), " ккал", fill=GRAY, font=f_small)

    # Прогресс-бар калорий
    if goal_calories:
        pct = calories / goal_calories
        pct_color = GREEN if pct <= 1.0 else RED
        _bar(draw, 40, 205, W - 80, 18, pct, pct_color)
        remaining = goal_calories - calories
        status = f"Осталось {remaining} ккал" if remaining >= 0 else f"Перебор на {abs(remaining)} ккал"
        status_color = GRAY if remaining >= 0 else RED
        draw.text((40, 230), f"Цель: {goal_calories} ккал  ·  {status}", fill=status_color, font=f_label)
    else:
        _bar(draw, 40, 205, W - 80, 18, 0.5, ACCENT)
        draw.text((40, 230), "Установи цель в разделе «Мои цели»", fill=GRAY, font=f_label)

    # ─ КБЖУ блоки ─
    macros = [
        ("Белки", protein, PROTEIN, "г"),
        ("Жиры",  fat,     FAT,     "г"),
        ("Углев.",carbs,   CARBS,   "г"),
    ]
    block_w = (W - 80 - 24) // 3
    for i, (label, val, color, unit) in enumerate(macros):
        x = 40 + i * (block_w + 12)
        draw.rounded_rectangle([x, 262, x + block_w, 340], 12, fill=CARD2)
        draw.text((x + 14, 272), label, fill=GRAY, font=f_label)
        draw.text((x + 14, 295), f"{val:.1f}{unit}", fill=color, font=f_med)

    # ─ Вес ─
    if current_weight:
        draw.rounded_rectangle([40, 355, W - 40, 405], 12, fill=CARD2)
        draw.text((56, 365), "Текущий вес", fill=GRAY, font=f_label)
        draw.text((220, 365), f"{current_weight:.1f} кг", fill=WHITE, font=f_med)
        if target_weight:
            diff = current_weight - target_weight
            diff_color = RED if diff > 0 else GREEN
            diff_str = f"до цели: {abs(diff):.1f} кг {'↓' if diff > 0 else '↑'}"
            draw.text((420, 368), diff_str, fill=diff_color, font=f_small)

    return _to_bytes(img)


# ─── Карточка задач ───────────────────────────────────────────────────────────

def generate_tasks_card(
    tasks_today: list[tuple[str, str, bool]],  # (title, priority, is_done)
    done_count: int,
    total_count: int,
) -> BytesIO:
    img, draw = _card_base("Задачи", "На сегодня")

    f_med   = _get_font(22, bold=True)
    f_small = _get_font(17)
    f_label = _get_font(15)

    PRIO_COLOR = {"high": RED, "medium": YELLOW, "low": GREEN}

    # ─ Прогресс ─
    pct = done_count / max(total_count, 1)
    _bar(draw, 40, 125, W - 80, 22, pct, GREEN)
    draw.text((40, 153),
        f"Выполнено {done_count} из {total_count} задач  ·  {pct*100:.0f}%",
        fill=GRAY, font=f_label)

    if not tasks_today:
        draw.rounded_rectangle([40, 185, W - 40, 260], 14, fill=CARD2)
        draw.text((60, 210), "Задач на сегодня нет — можно расслабиться", fill=GRAY, font=f_small)
    else:
        for i, (title, priority, is_done) in enumerate(tasks_today[:5]):
            y = 185 + i * 42
            prio_color = PRIO_COLOR.get(priority, GRAY)
            row_bg = CARD2 if not is_done else (28, 40, 30)
            draw.rounded_rectangle([40, y, W - 40, y + 34], 10, fill=row_bg)
            # Цветная точка приоритета
            draw.ellipse([56, y + 10, 68, y + 22], fill=prio_color)
            # Текст
            title_text = ("✓ " if is_done else "") + title[:48]
            text_color = GRAY if is_done else WHITE
            draw.text((80, y + 8), title_text, fill=text_color, font=f_label)

    # ─ Мотивация ─
    if total_count > 0 and pct == 1.0:
        draw.text((40, H - 50), "Все задачи выполнены! Так держать!", fill=GREEN, font=f_small)
    elif total_count == 0:
        draw.text((40, H - 50), "Добавь первую задачу", fill=ACCENT, font=f_small)

    return _to_bytes(img)


# ─── Главная карточка ─────────────────────────────────────────────────────────

def generate_main_card(first_name: str) -> BytesIO:
    from datetime import datetime
    import pytz
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Фоновый градиент (Neon)
    for i in range(H):
        ratio = i / H
        r = int(11 + ratio * 20)
        g = int(12 + ratio * 15)
        b = int(16 + ratio * 25)
        draw.line([(0, i), (W, i)], fill=(r, g, b))

    # Акцентный блок
    draw.rounded_rectangle([16, 16, W - 16, H - 16], 10, outline=ACCENT, width=3)
    draw.rounded_rectangle([18, 18, W - 18, H - 18], 8, fill=CARD)

    f_huge  = _get_font(38, bold=True)
    f_big   = _get_font(26, bold=True)
    f_med   = _get_font(20)
    f_small = _get_font(16)
    
    # "Терминал" хедер
    font_term = _get_font(14)
    draw.text((25, 20), "root@uffnv:~# ./life_manager.sh", fill=ACCENT, font=font_term)

    # Приветствие
    hour = datetime.now().hour
    greeting = "INIT_SEQ: Утро" if 5 <= hour < 12 else \
               "INIT_SEQ: День" if 12 <= hour < 18 else \
               "INIT_SEQ: Вечер" if 18 <= hour < 23 else "INIT_SEQ: Ночь"
    draw.text((40, 50), f"{greeting}", fill=YELLOW, font=f_med)
    draw.text((40, 75), f"> SYSTEM ONLINE: {first_name.upper()}_", fill=GREEN, font=f_huge)

    # Разделитель
    draw.line([(40, 130), (W - 40, 130)], fill=DIVIDER, width=2)

    # Модули
    modules = [
        ("", "Финансы",          "доходы, расходы, бюджет",     ACCENT),
        ("", "Питание и физа",   "КБЖУ, вес, цели",             GREEN),
        ("", "Задачи",           "планирование, напоминания",    YELLOW),
    ]
    for i, (icon, title, desc, color) in enumerate(modules):
        x = 40 + i * 247
        # Карточка модуля
        draw.rounded_rectangle([x, 150, x + 227, 360], 12, fill=CARD2, outline=color, width=2)
        
        # ASCII Иконка или текст
        draw.text((x + 20, 170), f"[{i+1}]", fill=color, font=f_med)
        
        # Название и описание
        draw.text((x + 20, 220), title.upper(), fill=WHITE, font=f_med)
        
        # Разбиваем описание на 2 строки для аккуратности
        words = desc.split(", ")
        desc_line1 = ", ".join(words[:2])
        desc_line2 = ", ".join(words[2:]) if len(words) > 2 else ""
        
        draw.text((x + 20, 260), f"> {desc_line1}", fill=GRAY, font=f_small)
        if desc_line2:
            draw.text((x + 20, 280), f"  {desc_line2}", fill=GRAY, font=f_small)
        
        # Декоративный "загрузочный" бар
        _bar(draw, x + 20, 320, 187, 8, 0.7 + i*0.1, color, CARD)

    return _to_bytes(img)
