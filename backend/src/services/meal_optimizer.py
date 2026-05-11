"""
Генератор meal plan на основе MILP.

Логика построена так:
1. Фильтруем блюда по аллергенам, жёстким запретам и диетическим ограничениям.
2. Формируем кандидатов "блюдо + приём пищи".
3. Решаем смешанно-целочисленную задачу:
   - x_j — количество шагов порции кандидата j;
   - один шаг равен PORTION_STEP граммам;
   - y_j — бинарная переменная выбора кандидата;
   - d — отклонения по калориям и БЖУ;
   - o_f — мягкий штраф за повторение одной и той же продуктовой семьи.
4. Если MILP-решатель недоступен или не находит решение, возвращается пустой план
   с соответствующим статусом.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from math import ceil, floor, inf
from typing import Dict, List, Optional, Sequence, Tuple

from src.core.models.mealplan.MealPlanModels import FoodItem, MealPlanItem, MealPlanResult

logger = logging.getLogger(__name__)


# ─── Константы ───────────────────────────────────────────────────────────────

# Допустимые категории блюд для каждого типа приёма пищи.
# Категории обрабатываются до запуска MILP: в сам решатель текстовые значения
# не передаются, туда попадают только числовые коэффициенты и ограничения.
MEAL_CATEGORIES: Dict[str, List[str]] = {
    "breakfast": ["breakfast", "universal"],
    "lunch": ["lunch", "universal"],
    "dinner": ["dinner", "universal"],
    "snack": ["snack", "universal"],
}

# Порядок сортировки приёмов пищи в итоговом плане.
MEAL_ORDER = {"breakfast": 0, "lunch": 1, "dinner": 2, "snack": 3}

# Максимальное число блюд на каждый приём пищи и суммарный лимит за день.
MEAL_ITEM_LIMITS = {"breakfast": 2, "lunch": 2, "dinner": 2, "snack": 2}
MAX_TOTAL_ITEMS = 5

# Шаг порции. Теперь MILP подбирает не произвольные граммы, а количество шагов.
# Например:
# x_j = 1 -> 50 г
# x_j = 2 -> 100 г
# x_j = 3 -> 150 г
PORTION_STEP = 50.0

# Порции ниже этого порога не включаются в итоговый план.
MIN_VISIBLE_PORTION = 50.0

GRAM_PENALTY = 0.00005         # штраф за каждый грамм, стимулирует компактность
FAMILY_OVERUSE_PENALTY = 0.05  # штраф за повторное использование одной продуктовой семьи
UNIVERSAL_ITEM_PENALTY = 0.006 # лёгкий штраф за блюда с категорией universal
SNACK_ITEM_PENALTY = 0.012     # лёгкий штраф за перекусы
BASE_SELECTION_PENALTY = 0.028 # базовый штраф за включение любого блюда в план
FAVORITE_MATCH_BONUS = 0.02    # снижение штрафа за совпадение с предпочтениями
DISLIKED_MATCH_PENALTY = 0.05  # дополнительный штраф за нежелательные ингредиенты


DIETARY_EXCLUSION_RULES: Dict[str, Tuple[str, ...]] = {
    "vegetarian": (
        "мяс", "куриц", "индейк", "говядин", "рыб", "лосос", "треск", "морепродукт",
        "свинин", "ветчин", "колбас", "сосиск", "бекон", "фарш", "шашлык", "шницел",
        "карбонар", "болоньез", "котлет",
        "пельмен", "манты", "хинкал", "тефтел", "фрикадел", "буженин", "паштет",
        "крылышк", "окорок", "грудинк", "салями", "прошутт", "полуфабрикат",
    ),
    "vegan": (
        "мяс", "куриц", "индейк", "говядин", "рыб", "лосос", "треск", "морепродукт",
        "свинин", "ветчин", "колбас", "сосиск", "бекон", "фарш", "шашлык", "шницел",
        "карбонар", "болоньез", "котлет",
        "пельмен", "манты", "хинкал", "тефтел", "фрикадел", "буженин", "паштет",
        "крылышк", "окорок", "грудинк", "салями", "прошутт", "полуфабрикат",
        "молоч", "сыр", "творог", "кефир", "йогурт", "яйц", "омлет", "сметан",
    ),
    "gluten_free": ("глютен",),
    "lactose_free": ("лактоз", "молоч", "сыр", "творог", "кефир", "йогурт", "сметан"),
    "nut_free": ("орех", "арахис"),
}


DIETARY_ALIASES: Dict[str, str] = {
    "вегетарианство": "vegetarian",
    "вегетарианец": "vegetarian",
    "вегетарианская": "vegetarian",
    "vegetarian": "vegetarian",
    "веган": "vegan",
    "веганство": "vegan",
    "vegan": "vegan",
    "без глютена": "gluten_free",
    "глютен фри": "gluten_free",
    "gluten free": "gluten_free",
    "без лактозы": "lactose_free",
    "lactose free": "lactose_free",
    "без орехов": "nut_free",
    "nut free": "nut_free",
}


FAMILY_KEYWORDS = (
    ("chicken", ("куриц",)),
    ("turkey", ("индейк",)),
    ("fish", ("рыб", "лосос", "треск", "морепродукт")),
    ("beef_meat", ("говядин", "мяс", "тефтел", "котлет", "фарш", "шашлык", "шницел", "болоньез")),
    ("pork", ("свинин", "ветчин", "колбас", "сосиск", "бекон", "карбонар")),
    ("eggs", ("яйц", "омлет")),
    ("dairy", ("молоч", "творог", "кефир", "йогурт", "сыр", "сметан", "сырник")),
    ("grains", ("овсян", "гречк", "рис", "макарон", "лапш", "круп")),
    ("vegetables", ("овощ", "брокколи", "морков", "салат", "рагу", "борщ", "картоф")),
    ("fruits", ("яблок", "банан", "авокад", "сухофрукт", "кураг")),
    ("nuts", ("орех", "арахис")),
    ("legumes", ("хумус", "бобов")),
    ("bread", ("хлеб", "тост", "блин")),
    ("soup", ("суп", "борщ")),
)


@dataclass(frozen=True)
class Candidate:
    item: FoodItem
    meal_type: str
    base_key: str
    family: str
    preference_penalty: float
    text: str


# ─── Публичный интерфейс ─────────────────────────────────────────────────────

def optimize_meal_plan(
    food_items: List[FoodItem],
    target_calories: float,
    target_protein: float,
    target_fat: float,
    target_carbs: float,
    excluded_allergens: Optional[List[str]] = None,
    excluded_ingredients: Optional[List[str]] = None,
    favorite_ingredients: Optional[List[str]] = None,
    favorite_cuisines: Optional[List[str]] = None,
    disliked_cuisines: Optional[List[str]] = None,
    dietary_restrictions: Optional[List[str]] = None,
    already_eaten_calories: float = 0,
    already_eaten_protein: float = 0,
    already_eaten_fat: float = 0,
    already_eaten_carbs: float = 0,
) -> MealPlanResult:
    """Основная точка входа. Строит план питания через MILP.

    Сначала из дневных целей вычитается уже съеденное. Затем каталог блюд
    фильтруется по ограничениям пользователя, формируются кандидаты
    "блюдо + приём пищи", после чего строится и решается MILP-задача.
    """
    excluded_allergens = excluded_allergens or []
    excluded_ingredients = excluded_ingredients or []
    favorite_ingredients = favorite_ingredients or []
    favorite_cuisines = favorite_cuisines or []
    disliked_cuisines = disliked_cuisines or []
    dietary_restrictions = dietary_restrictions or []

    daily_targets = {
        "calories": max(0.0, float(target_calories)),
        "protein": max(0.0, float(target_protein)),
        "fat": max(0.0, float(target_fat)),
        "carbs": max(0.0, float(target_carbs)),
    }

    already_eaten = {
        "calories": max(0.0, float(already_eaten_calories)),
        "protein": max(0.0, float(already_eaten_protein)),
        "fat": max(0.0, float(already_eaten_fat)),
        "carbs": max(0.0, float(already_eaten_carbs)),
    }

    # plan_targets — это не полная дневная норма, а остаток нормы.
    # Если пользователь уже превысил норму по какому-то показателю,
    # остаток принимается равным нулю.
    plan_targets = {
        "calories": max(0.0, daily_targets["calories"] - already_eaten["calories"]),
        "protein": max(0.0, daily_targets["protein"] - already_eaten["protein"]),
        "fat": max(0.0, daily_targets["fat"] - already_eaten["fat"]),
        "carbs": max(0.0, daily_targets["carbs"] - already_eaten["carbs"]),
    }

    if _targets_are_already_met(plan_targets):
        return _build_result(
            meals=[],
            plan_targets=plan_targets,
            daily_targets=daily_targets,
            already_eaten=already_eaten,
            solver_status="optimal_nothing_to_plan",
            solution_method="targets_already_met",
        )

    filtered_items = _filter_food_items(
        items=food_items,
        excluded_allergens=excluded_allergens,
        excluded_ingredients=excluded_ingredients,
        dietary_restrictions=dietary_restrictions,
    )

    if len(filtered_items) < 2:
        return _empty_result(
            plan_targets=plan_targets,
            daily_targets=daily_targets,
            already_eaten=already_eaten,
            status="infeasible_too_few_items",
        )

    candidates = _build_candidates(
        items=filtered_items,
        favorite_ingredients=favorite_ingredients,
        excluded_ingredients=excluded_ingredients,
        favorite_cuisines=favorite_cuisines,
        disliked_cuisines=disliked_cuisines,
    )

    if not candidates:
        return _empty_result(
            plan_targets=plan_targets,
            daily_targets=daily_targets,
            already_eaten=already_eaten,
            status="infeasible_no_candidates",
        )

    milp_result = _solve_milp(
        candidates=candidates,
        plan_targets=plan_targets,
        daily_targets=daily_targets,
        already_eaten=already_eaten,
    )

    if milp_result is not None:
        return milp_result

    return _empty_result(
        plan_targets=plan_targets,
        daily_targets=daily_targets,
        already_eaten=already_eaten,
        status="infeasible_milp_failed",
    )


def _targets_are_already_met(plan_targets: Dict[str, float]) -> bool:
    """Возвращает True, если оставшиеся цели по всем нутриентам уже закрыты."""
    return all(value <= 1.0 for value in plan_targets.values())


def _filter_food_items(
    items: Sequence[FoodItem],
    excluded_allergens: Sequence[str],
    excluded_ingredients: Sequence[str],
    dietary_restrictions: Sequence[str],
) -> List[FoodItem]:
    """Фильтрует каталог блюд по аллергенам, ингредиентам и диетическим ограничениям."""
    filtered: List[FoodItem] = []

    excluded_allergen_terms = [_normalize_text(value) for value in excluded_allergens if value]
    excluded_ingredient_terms = [_normalize_text(value) for value in excluded_ingredients if value]
    restriction_keys = [_normalize_dietary_restriction(value) for value in dietary_restrictions if value]

    for item in items:
        item_text = _item_text(item)
        allergen_texts = [_normalize_text(value) for value in item.allergens]

        if any(term and any(term in allergen for allergen in allergen_texts) for term in excluded_allergen_terms):
            continue

        if any(term and term in item_text for term in excluded_ingredient_terms):
            continue

        if _violates_dietary_restrictions(item_text, restriction_keys):
            continue

        filtered.append(item)

    return filtered


def _normalize_text(value: str) -> str:
    """Приводит строку к единому виду для поиска совпадений."""
    return " ".join(value.lower().replace("ё", "е").replace("_", " ").replace("-", " ").split())


def _normalize_dietary_restriction(value: str) -> str:
    """Переводит произвольное название диеты в стандартный ключ."""
    normalized = _normalize_text(value)
    return DIETARY_ALIASES.get(normalized, normalized)


def _violates_dietary_restrictions(item_text: str, restriction_keys: Sequence[str]) -> bool:
    """Проверяет, нарушает ли блюдо активные диетические ограничения."""
    for restriction in restriction_keys:
        keywords = DIETARY_EXCLUSION_RULES.get(restriction)
        if keywords and any(keyword in item_text for keyword in keywords):
            return True
    return False


def _item_text(item: FoodItem) -> str:
    """Собирает нормализованный текст блюда из названия, категории, тегов и аллергенов."""
    parts: List[str] = [item.name, item.category]
    parts.extend(item.tags)
    parts.extend(item.allergens)
    return _normalize_text(" ".join(parts))


def _build_candidates(
    items: Sequence[FoodItem],
    favorite_ingredients: Sequence[str],
    excluded_ingredients: Sequence[str],
    favorite_cuisines: Sequence[str],
    disliked_cuisines: Sequence[str],
) -> List[Candidate]:
    """Формирует список кандидатов "блюдо + приём пищи".

    В MILP-решатель текстовые категории не передаются. Они используются здесь,
    чтобы заранее создать только допустимые пары "блюдо + приём пищи".

    Если у блюда нет ни одной допустимой порции, кратной PORTION_STEP,
    оно не включается в кандидаты.
    """
    candidates: List[Candidate] = []

    favorite_terms = [_normalize_text(value) for value in favorite_ingredients if value]
    excluded_terms = [_normalize_text(value) for value in excluded_ingredients if value]
    favorite_cuisine_terms = [_normalize_text(value) for value in favorite_cuisines if value]
    disliked_cuisine_terms = [_normalize_text(value) for value in disliked_cuisines if value]

    for item in items:
        # Если у блюда нет допустимой порции, кратной 50 г,
        # оно не может использоваться в MILP-модели.
        if _portion_step_bounds(item) is None:
            continue

        text = _item_text(item)
        family = _detect_family(text, item.category)
        base_key = str(item.id) if item.id is not None else _normalize_text(item.name)

        for meal_type, allowed_categories in MEAL_CATEGORIES.items():
            if item.category not in allowed_categories:
                continue

            preference_penalty = BASE_SELECTION_PENALTY
            preference_penalty += SNACK_ITEM_PENALTY if meal_type == "snack" else 0.0
            preference_penalty += UNIVERSAL_ITEM_PENALTY if item.category == "universal" else 0.0
            preference_penalty -= FAVORITE_MATCH_BONUS * _count_matches(text, favorite_terms)
            preference_penalty -= FAVORITE_MATCH_BONUS * _count_matches(text, favorite_cuisine_terms)
            preference_penalty += DISLIKED_MATCH_PENALTY * _count_matches(text, excluded_terms)
            preference_penalty += DISLIKED_MATCH_PENALTY * _count_matches(text, disliked_cuisine_terms)

            candidates.append(
                Candidate(
                    item=item,
                    meal_type=meal_type,
                    base_key=base_key,
                    family=family,
                    preference_penalty=preference_penalty,
                    text=text,
                )
            )

    return candidates


def _count_matches(text: str, terms: Sequence[str]) -> int:
    """Считает количество терминов, встречающихся в тексте."""
    return sum(1 for term in terms if term and term in text)


def _detect_family(text: str, category: str) -> str:
    """Определяет продуктовую семью блюда по ключевым словам."""
    for family, keywords in FAMILY_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return family
    return f"category:{category}"


def _solve_milp(
    candidates: Sequence[Candidate],
    plan_targets: Dict[str, float],
    daily_targets: Dict[str, float],
    already_eaten: Dict[str, float],
) -> Optional[MealPlanResult]:
    """Решает задачу оптимизации рациона через scipy.optimize.milp.

    Структура вектора решения:
      [0 .. n-1]          — x_j: количество шагов PORTION_STEP для кандидата;
      [n .. 2n-1]         — y_j: выбран кандидат или нет;
      [2n .. 2n+7]        — отклонения по калориям, белкам, жирам и углеводам;
      [2n+8 .. конец]     — o_f: переменные повторения продуктовых семей.

    Значения этого вектора не передаются заранее. Они находятся MILP-решателем.
    """
    try:
        import numpy as np
        from scipy.optimize import Bounds, LinearConstraint, milp
    except Exception as exc:
        logger.warning("MILP недоступен: %s", exc)
        return None

    n = len(candidates)
    if n == 0:
        return None

    family_names = sorted({candidate.family for candidate in candidates})
    family_index = {name: idx for idx, name in enumerate(family_names)}

    x_start = 0
    y_start = n
    deviation_start = 2 * n
    family_overuse_start = deviation_start + 8
    num_vars = family_overuse_start + len(family_names)

    # objective — коэффициенты целевой функции.
    # Решатель минимизирует сумму objective[i] * variable[i].
    objective = [0.0] * num_vars

    # Нижние и верхние границы переменных.
    lower_bounds = [0.0] * num_vars
    upper_bounds = [inf] * num_vars

    # integrality показывает, какие переменные целочисленные.
    # Для x_j задаётся 1, чтобы количество шагов было целым.
    # Для y_j задаётся 1, а границы 0..1 делают их бинарными.
    integrality = [0] * num_vars

    for idx, candidate in enumerate(candidates):
        bounds = _portion_step_bounds(candidate.item)
        if bounds is None:
            return None

        min_steps, max_steps = bounds

        # x_j теперь означает количество шагов по PORTION_STEP,
        # поэтому штраф за граммовку умножается на PORTION_STEP.
        objective[x_start + idx] = GRAM_PENALTY * PORTION_STEP
        objective[y_start + idx] = candidate.preference_penalty

        lower_bounds[x_start + idx] = 0.0
        upper_bounds[x_start + idx] = float(max_steps)

        upper_bounds[y_start + idx] = 1.0

        # x_j — целое число шагов порции.
        integrality[x_start + idx] = 1

        # y_j — бинарная переменная выбора.
        integrality[y_start + idx] = 1

    weights = _deviation_weights(plan_targets)

    objective[deviation_start + 0] = weights["calories_over"]
    objective[deviation_start + 1] = weights["calories_under"]
    objective[deviation_start + 2] = weights["protein_over"]
    objective[deviation_start + 3] = weights["protein_under"]
    objective[deviation_start + 4] = weights["fat_over"]
    objective[deviation_start + 5] = weights["fat_under"]
    objective[deviation_start + 6] = weights["carbs_over"]
    objective[deviation_start + 7] = weights["carbs_under"]

    for family_name, idx in family_index.items():
        objective[family_overuse_start + idx] = FAMILY_OVERUSE_PENALTY
        lower_bounds[family_overuse_start + idx] = 0.0
        upper_bounds[family_overuse_start + idx] = inf

    rows: List[List[float]] = []
    lbs: List[float] = []
    ubs: List[float] = []

    # Баланс нутриентов:
    # сумма_нутриента - перебор + недобор = оставшаяся цель.
    #
    # Так как x_j теперь измеряется не в граммах, а в шагах по PORTION_STEP,
    # коэффициент нутриента на 1 г умножается на PORTION_STEP.
    nutrient_specs = (
        ("calories", deviation_start + 0, deviation_start + 1, lambda item: item.calories / 100.0),
        ("protein", deviation_start + 2, deviation_start + 3, lambda item: item.protein / 100.0),
        ("fat", deviation_start + 4, deviation_start + 5, lambda item: item.fat / 100.0),
        ("carbs", deviation_start + 6, deviation_start + 7, lambda item: item.carbs / 100.0),
    )

    for nutrient_name, over_idx, under_idx, getter in nutrient_specs:
        row = [0.0] * num_vars

        for candidate_idx, candidate in enumerate(candidates):
            row[x_start + candidate_idx] = getter(candidate.item) * PORTION_STEP

        row[over_idx] = -1.0
        row[under_idx] = 1.0

        rows.append(row)
        lbs.append(plan_targets[nutrient_name])
        ubs.append(plan_targets[nutrient_name])

    for candidate_idx, candidate in enumerate(candidates):
        x_idx = x_start + candidate_idx
        y_idx = y_start + candidate_idx

        bounds = _portion_step_bounds(candidate.item)
        if bounds is None:
            return None

        min_steps, max_steps = bounds

        # x_j <= max_steps_j * y_j.
        # Если y_j = 0, то x_j становится 0.
        # Если y_j = 1, то x_j может быть от min_steps до max_steps.
        upper_row = [0.0] * num_vars
        upper_row[x_idx] = 1.0
        upper_row[y_idx] = -float(max_steps)

        rows.append(upper_row)
        lbs.append(-inf)
        ubs.append(0.0)

        # x_j >= min_steps_j * y_j.
        # Если блюдо выбрано, количество шагов порции не может быть меньше min_steps.
        lower_row = [0.0] * num_vars
        lower_row[x_idx] = 1.0
        lower_row[y_idx] = -float(min_steps)

        rows.append(lower_row)
        lbs.append(0.0)
        ubs.append(inf)

    # Не больше заданного числа блюд на каждый приём пищи.
    for meal_type, limit in MEAL_ITEM_LIMITS.items():
        row = [0.0] * num_vars

        for candidate_idx, candidate in enumerate(candidates):
            if candidate.meal_type == meal_type:
                row[y_start + candidate_idx] = 1.0

        rows.append(row)
        lbs.append(0.0)
        ubs.append(float(limit))

    # Общее число блюд в плане: от 1 до MAX_TOTAL_ITEMS.
    total_items_row = [0.0] * num_vars
    for candidate_idx in range(n):
        total_items_row[y_start + candidate_idx] = 1.0

    rows.append(total_items_row)
    lbs.append(1.0)
    ubs.append(float(MAX_TOTAL_ITEMS))

    # Одно и то же исходное блюдо нельзя выбрать несколько раз
    # в разные приёмы пищи.
    grouped_by_item = _group_candidate_indices(candidates, key_getter=lambda candidate: candidate.base_key)
    for indices in grouped_by_item.values():
        row = [0.0] * num_vars

        for candidate_idx in indices:
            row[y_start + candidate_idx] = 1.0

        rows.append(row)
        lbs.append(0.0)
        ubs.append(1.0)

    # Мягкое ограничение на повторение продуктовой семьи:
    # если из одной семьи выбрано больше одного блюда, появляется переменная o_f,
    # которая затем штрафуется в целевой функции.
    grouped_by_family = _group_candidate_indices(candidates, key_getter=lambda candidate: candidate.family)
    for family_name, indices in grouped_by_family.items():
        row = [0.0] * num_vars

        for candidate_idx in indices:
            row[y_start + candidate_idx] = 1.0

        row[family_overuse_start + family_index[family_name]] = -1.0

        rows.append(row)
        lbs.append(-inf)
        ubs.append(1.0)

    try:
        result = milp(
            c=np.array(objective, dtype=float),
            integrality=np.array(integrality, dtype=int),
            bounds=Bounds(
                np.array(lower_bounds, dtype=float),
                np.array(upper_bounds, dtype=float),
            ),
            constraints=LinearConstraint(
                np.array(rows, dtype=float),
                np.array(lbs, dtype=float),
                np.array(ubs, dtype=float),
            ),
        )
    except Exception as exc:
        logger.warning("Ошибка MILP-решателя: %s", exc)
        return None

    if not result.success or result.x is None:
        logger.info("MILP не нашёл решение: %s", getattr(result, "message", "unknown"))
        return None

    selected_portions: Dict[int, float] = {}

    for idx, candidate in enumerate(candidates):
        portion_steps = round(float(result.x[x_start + idx]))
        portion = portion_steps * PORTION_STEP

        chosen = float(result.x[y_start + idx]) >= 0.5

        if not chosen or portion < MIN_VISIBLE_PORTION:
            continue

        selected_portions[idx] = _sanitize_portion(candidate.item, portion)

    if not selected_portions:
        return None

    meals = _selected_meals(candidates, selected_portions)

    return _build_result(
        meals=meals,
        plan_targets=plan_targets,
        daily_targets=daily_targets,
        already_eaten=already_eaten,
        solver_status="optimal_milp",
        solution_method="mixed_integer_programming",
    )


def _group_candidate_indices(candidates: Sequence[Candidate], key_getter) -> Dict[str, List[int]]:
    """Группирует индексы кандидатов по ключу."""
    grouped: Dict[str, List[int]] = {}

    for idx, candidate in enumerate(candidates):
        grouped.setdefault(key_getter(candidate), []).append(idx)

    return grouped


def _deviation_weights(plan_targets: Dict[str, float]) -> Dict[str, float]:
    """Вычисляет веса штрафов за отклонения от целей по нутриентам.

    Веса обратно пропорциональны целевым значениям. Это приводит калории,
    белки, жиры и углеводы к сопоставимому масштабу.
    """
    calories = max(plan_targets["calories"], 300.0)
    protein = max(plan_targets["protein"], 25.0)
    fat = max(plan_targets["fat"], 20.0)
    carbs = max(plan_targets["carbs"], 40.0)

    return {
        "calories_over": 1.0 / calories,
        "calories_under": 1.1 / calories,
        "protein_over": 0.9 / protein,
        "protein_under": 1.35 / protein,
        "fat_over": 0.9 / fat,
        "fat_under": 1.05 / fat,
        "carbs_over": 0.75 / carbs,
        "carbs_under": 0.9 / carbs,
    }


def _portion_step_bounds(item: FoodItem) -> Optional[Tuple[int, int]]:
    """Возвращает минимальное и максимальное количество шагов PORTION_STEP для блюда.

    Например, если PORTION_STEP = 50:
      1 шаг = 50 г;
      2 шага = 100 г;
      3 шага = 150 г.

    Минимальная порция округляется вверх, максимальная — вниз.
    Если между min_portion и max_portion нет ни одного значения, кратного PORTION_STEP,
    возвращается None, и блюдо не используется как кандидат.
    """
    min_portion = max(0.0, float(item.min_portion))
    max_portion = max(0.0, float(item.max_portion))

    if max_portion < PORTION_STEP:
        return None

    min_steps = max(1, int(ceil(min_portion / PORTION_STEP)))
    max_steps = int(floor(max_portion / PORTION_STEP))

    if max_steps < min_steps:
        return None

    return min_steps, max_steps


def _sanitize_portion(item: FoodItem, portion: float) -> float:
    """Возвращает порцию, кратную PORTION_STEP.

    Основное округление уже выполняется внутри MILP за счёт целочисленной
    переменной x_j. Эта функция оставлена как дополнительная защита.
    """
    bounds = _portion_step_bounds(item)
    if bounds is None:
        return 0.0

    min_steps, max_steps = bounds

    portion_steps = round(portion / PORTION_STEP)
    portion_steps = max(min_steps, min(max_steps, portion_steps))

    return portion_steps * PORTION_STEP


def _selected_meals(
    candidates: Sequence[Candidate],
    selected_portions: Dict[int, float],
) -> List[MealPlanItem]:
    """Преобразует найденные индексы кандидатов и порции в список MealPlanItem."""
    meals: List[MealPlanItem] = []

    for idx, portion in selected_portions.items():
        candidate = candidates[idx]

        if portion < MIN_VISIBLE_PORTION:
            continue

        portion = _sanitize_portion(candidate.item, portion)

        if portion <= 0:
            continue

        meals.append(
            MealPlanItem(
                food_item=candidate.item,
                portion_grams=portion,
                meal_type=candidate.meal_type,
                calories=round(candidate.item.calories * portion / 100.0, 1),
                protein=round(candidate.item.protein * portion / 100.0, 1),
                fat=round(candidate.item.fat * portion / 100.0, 1),
                carbs=round(candidate.item.carbs * portion / 100.0, 1),
            )
        )

    meals.sort(key=lambda meal: (MEAL_ORDER.get(meal.meal_type, 99), meal.food_item.name))
    return meals


def _build_result(
    meals: Sequence[MealPlanItem],
    plan_targets: Dict[str, float],
    daily_targets: Dict[str, float],
    already_eaten: Dict[str, float],
    solver_status: str,
    solution_method: str,
) -> MealPlanResult:
    """Собирает итоговый объект MealPlanResult."""
    total_calories = round(sum(meal.calories for meal in meals), 1)
    total_protein = round(sum(meal.protein for meal in meals), 1)
    total_fat = round(sum(meal.fat for meal in meals), 1)
    total_carbs = round(sum(meal.carbs for meal in meals), 1)

    return MealPlanResult(
        meals=list(meals),
        total_calories=total_calories,
        total_protein=total_protein,
        total_fat=total_fat,
        total_carbs=total_carbs,
        target_calories=round(plan_targets["calories"], 1),
        target_protein=round(plan_targets["protein"], 1),
        target_fat=round(plan_targets["fat"], 1),
        target_carbs=round(plan_targets["carbs"], 1),
        daily_target_calories=round(daily_targets["calories"], 1),
        daily_target_protein=round(daily_targets["protein"], 1),
        daily_target_fat=round(daily_targets["fat"], 1),
        daily_target_carbs=round(daily_targets["carbs"], 1),
        already_eaten_calories=round(already_eaten["calories"], 1),
        already_eaten_protein=round(already_eaten["protein"], 1),
        already_eaten_fat=round(already_eaten["fat"], 1),
        already_eaten_carbs=round(already_eaten["carbs"], 1),
        deviation_calories=round(abs(total_calories - plan_targets["calories"]), 1),
        deviation_protein=round(abs(total_protein - plan_targets["protein"]), 1),
        deviation_fat=round(abs(total_fat - plan_targets["fat"]), 1),
        deviation_carbs=round(abs(total_carbs - plan_targets["carbs"]), 1),
        solver_status=solver_status,
        solution_method=solution_method,
    )


def _empty_result(
    plan_targets: Dict[str, float],
    daily_targets: Dict[str, float],
    already_eaten: Dict[str, float],
    status: str,
) -> MealPlanResult:
    """Возвращает пустой план с указанным статусом."""
    return MealPlanResult(
        meals=[],
        total_calories=0.0,
        total_protein=0.0,
        total_fat=0.0,
        total_carbs=0.0,
        target_calories=round(plan_targets["calories"], 1),
        target_protein=round(plan_targets["protein"], 1),
        target_fat=round(plan_targets["fat"], 1),
        target_carbs=round(plan_targets["carbs"], 1),
        daily_target_calories=round(daily_targets["calories"], 1),
        daily_target_protein=round(daily_targets["protein"], 1),
        daily_target_fat=round(daily_targets["fat"], 1),
        daily_target_carbs=round(daily_targets["carbs"], 1),
        already_eaten_calories=round(already_eaten["calories"], 1),
        already_eaten_protein=round(already_eaten["protein"], 1),
        already_eaten_fat=round(already_eaten["fat"], 1),
        already_eaten_carbs=round(already_eaten["carbs"], 1),
        deviation_calories=round(plan_targets["calories"], 1),
        deviation_protein=round(plan_targets["protein"], 1),
        deviation_fat=round(plan_targets["fat"], 1),
        deviation_carbs=round(plan_targets["carbs"], 1),
        solver_status=status,
        solution_method="not_available",
    )