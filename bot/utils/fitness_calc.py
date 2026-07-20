"""
Расчёт нормы калорий и макросов по формуле Миффлина-Сан Жеора.
Научная основа: Mifflin MD, St Jeor ST (1990).
"""
from dataclasses import dataclass
from enum import Enum


class ActivityLevel(str, Enum):
    sedentary   = "sedentary"    # сидячий
    light       = "light"        # лёгкая (1-3 раза/нед)
    moderate    = "moderate"     # средняя (3-5 раз/нед)
    active      = "active"       # высокая (6-7 раз/нед)
    very_active = "very_active"  # очень высокая (2x в день)


class FitnessPlan(str, Enum):
    cut_hard  = "cut_hard"   # активное похудение -20%
    cut_soft  = "cut_soft"   # мягкое похудение -10%
    maintain  = "maintain"   # поддержание
    bulk      = "bulk"       # набор массы +15%


ACTIVITY_MULTIPLIER = {
    ActivityLevel.sedentary:   1.2,
    ActivityLevel.light:       1.375,
    ActivityLevel.moderate:    1.55,
    ActivityLevel.active:      1.725,
    ActivityLevel.very_active: 1.9,
}

ACTIVITY_LABEL = {
    ActivityLevel.sedentary:   "🪑 Сидячий",
    ActivityLevel.light:       "🚶 Лёгкая",
    ActivityLevel.moderate:    "🏃 Средняя",
    ActivityLevel.active:      "💪 Высокая",
    ActivityLevel.very_active: "🔥 Очень высокая",
}

PLAN_LABEL = {
    FitnessPlan.cut_hard: "🔥 Активное похудение",
    FitnessPlan.cut_soft: "🌿 Мягкое похудение",
    FitnessPlan.maintain: "⚖️ Поддержание",
    FitnessPlan.bulk:     "💪 Набор массы",
}

PLAN_MULTIPLIER = {
    FitnessPlan.cut_hard: 0.80,
    FitnessPlan.cut_soft: 0.90,
    FitnessPlan.maintain: 1.00,
    FitnessPlan.bulk:     1.15,
}

# Соотношение макросов Б/Ж/У для каждого плана (в %)
PLAN_MACROS = {
    FitnessPlan.cut_hard: (0.35, 0.30, 0.35),  # больше белка при дефиците
    FitnessPlan.cut_soft: (0.30, 0.30, 0.40),
    FitnessPlan.maintain: (0.25, 0.30, 0.45),
    FitnessPlan.bulk:     (0.25, 0.25, 0.50),  # больше углей для роста
}


@dataclass
class FitnessProfile:
    weight: float   # кг
    height: int     # см
    age: int
    sex: str        # "male" / "female"
    activity: ActivityLevel
    plan: FitnessPlan

    @property
    def bmi(self) -> float:
        h_m = self.height / 100
        return round(self.weight / (h_m ** 2), 1)

    @property
    def bmi_category(self) -> str:
        b = self.bmi
        if b < 18.5:  return "Недостаточный вес"
        if b < 25.0:  return "Норма ✅"
        if b < 30.0:  return "Избыточный вес"
        return "Ожирение"

    @property
    def bmr(self) -> float:
        """Базовый обмен веществ (Mifflin-St Jeor)."""
        if self.sex == "male":
            return 10 * self.weight + 6.25 * self.height - 5 * self.age + 5
        return 10 * self.weight + 6.25 * self.height - 5 * self.age - 161

    @property
    def tdee(self) -> int:
        """Полный суточный расход энергии."""
        return round(self.bmr * ACTIVITY_MULTIPLIER[self.activity])

    @property
    def target_calories(self) -> int:
        return round(self.tdee * PLAN_MULTIPLIER[self.plan])

    @property
    def macros_g(self) -> dict:
        """Граммы Б/Ж/У."""
        p_pct, f_pct, c_pct = PLAN_MACROS[self.plan]
        cal = self.target_calories
        return {
            "protein": round(cal * p_pct / 4),   # 1г белка = 4 ккал
            "fat":     round(cal * f_pct / 9),   # 1г жира  = 9 ккал
            "carbs":   round(cal * c_pct / 4),   # 1г углей = 4 ккал
        }

    @property
    def ideal_weight_range(self) -> tuple[float, float]:
        """Диапазон нормального веса по ИМТ 18.5-24.9."""
        h_m = self.height / 100
        return (round(18.5 * h_m ** 2, 1), round(24.9 * h_m ** 2, 1))

    def summary(self) -> str:
        macros = self.macros_g
        ideal_lo, ideal_hi = self.ideal_weight_range
        diff = self.weight - ideal_hi if self.weight > ideal_hi else (self.weight - ideal_lo if self.weight < ideal_lo else 0)
        diff_str = ""
        if diff > 0:
            diff_str = f"\n📉 До нормы: -{diff:.1f} кг"
        elif diff < 0:
            diff_str = f"\n📈 До нормы: +{abs(diff):.1f} кг"

        return (
            f"📊 <b>Твой план: {PLAN_LABEL[self.plan]}</b>\n\n"
            f"⚖️ Вес: <b>{self.weight} кг</b>  |  Рост: <b>{self.height} см</b>\n"
            f"🧮 ИМТ: <b>{self.bmi}</b> — {self.bmi_category}"
            f"{diff_str}\n"
            f"🎯 Идеальный диапазон: <b>{ideal_lo}–{ideal_hi} кг</b>\n\n"
            f"🔥 Базовый обмен: <b>{round(self.bmr)} ккал</b>\n"
            f"⚡ Суточная норма (TDEE): <b>{self.tdee} ккал</b>\n"
            f"🍽 Цель по плану: <b>{self.target_calories} ккал/день</b>\n\n"
            f"<b>Макросы:</b>\n"
            f"🥩 Белки: <b>{macros['protein']} г</b>\n"
            f"🧈 Жиры: <b>{macros['fat']} г</b>\n"
            f"🍞 Углеводы: <b>{macros['carbs']} г</b>"
        )
