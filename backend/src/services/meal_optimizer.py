"""
Улучшенный генератор meal plan.

Логика построена так:
1. Фильтруем блюда по аллергенам, жёстким запретам и диетическим ограничениям.
2. Формируем кандидатов "блюдо + приём пищи".
3. Пытаемся решить смешанно-целочисленную задачу:
   - x_{i,m} — граммовка блюда i в приёме пищи m
   - y_{i,m} — бинарная переменная выбора блюда
   - δ — отклонения по калориям и БЖУ
   - o_f — мягкий штраф за повторение одной и той же продуктовой семьи
4. Если MILP-решатель недоступен, используем жадный многокритериальный fallback,
   чтобы модуль не падал даже без SciPy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from math import inf
from typing import Dict, List, Optional, Sequence, Tuple

from src.core.models.mealplan.MealPlanModels import FoodItem, MealPlanItem, MealPlanResult

logger = logging.getLogger(__name__)

MEAL_CATEGORIES: Dict[str, List[str]] = {
    "breakfast": ["breakfast", "universal"],
    "lunch": ["lunch", "universal"],
    "dinner": ["dinner", "universal"],
    "snack": ["snack", "universal"],
}

MEAL_ORDER = {"breakfast": 0, "lunch": 1, "dinner": 2, "snack": 3}
MEAL_ITEM_LIMITS = {"breakfast": 2, "lunch": 2, "dinner": 2, "snack": 2}
MAX_TOTAL_ITEMS = 5
PORTION_GRID_SMALL = 10.0
PORTION_GRID_LARGE = 25.0
ROUND_PORTION_STEP = 5.0
MIN_VISIBLE_PORTION = 20.0
GRAM_PENALTY = 0.00005
FAMILY_OVERUSE_PENALTY = 0.05
UNIVERSAL_ITEM_PENALTY = 0.006
SNACK_ITEM_PENALTY = 0.012
BASE_SELECTION_PENALTY = 0.028
FAVORITE_MATCH_BONUS = 0.02
DISLIKED_MATCH_PENALTY = 0.05

DIETARY_EXCLUSION_RULES: Dict[str, Tuple[str, ...]] = {
    "vegetarian": ("мяс", "куриц", "индейк", "говядин", "рыб", "лосос", "треск", "морепродукт"),
    "vegan": ("мяс", "куриц", "индейк", "говядин", "рыб", "лосос", "треск", "морепродукт", "молоч", "сыр", "творог", "кефир", "йогурт", "яйц", "омлет", "сметан"),
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
    ("beef_meat", ("говядин", "мяс", "тефтел", "котлет")),
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

    logger.info("Переходим на жадный fallback для mealplan")
    greedy_result = _solve_greedy(
        candidates=candidates,
        plan_targets=plan_targets,
        daily_targets=daily_targets,
        already_eaten=already_eaten,
    )
    if greedy_result is not None:
        return greedy_result

    return _empty_result(
        plan_targets=plan_targets,
        daily_targets=daily_targets,
        already_eaten=already_eaten,
        status="infeasible_no_plan",
    )


def _targets_are_already_met(plan_targets: Dict[str, float]) -> bool:
    return all(value <= 1.0 for value in plan_targets.values())


def _filter_food_items(
    items: Sequence[FoodItem],
    excluded_allergens: Sequence[str],
    excluded_ingredients: Sequence[str],
    dietary_restrictions: Sequence[str],
) -> List[FoodItem]:
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
    return " ".join(value.lower().replace("ё", "е").replace("_", " ").replace("-", " ").split())


def _normalize_dietary_restriction(value: str) -> str:
    normalized = _normalize_text(value)
    return DIETARY_ALIASES.get(normalized, normalized)


def _violates_dietary_restrictions(item_text: str, restriction_keys: Sequence[str]) -> bool:
    for restriction in restriction_keys:
        keywords = DIETARY_EXCLUSION_RULES.get(restriction)
        if keywords and any(keyword in item_text for keyword in keywords):
            return True
    return False


def _item_text(item: FoodItem) -> str:
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
    candidates: List[Candidate] = []
    favorite_terms = [_normalize_text(value) for value in favorite_ingredients if value]
    excluded_terms = [_normalize_text(value) for value in excluded_ingredients if value]
    favorite_cuisine_terms = [_normalize_text(value) for value in favorite_cuisines if value]
    disliked_cuisine_terms = [_normalize_text(value) for value in disliked_cuisines if value]

    for item in items:
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
    return sum(1 for term in terms if term and term in text)


def _detect_family(text: str, category: str) -> str:
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
    try:
        import numpy as np
        from scipy.optimize import Bounds, LinearConstraint, milp
    except Exception as exc:
        logger.warning("MILP недоступен, используем fallback: %s", exc)
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

    objective = [0.0] * num_vars
    lower_bounds = [0.0] * num_vars
    upper_bounds = [inf] * num_vars
    integrality = [0] * num_vars

    for idx, candidate in enumerate(candidates):
        objective[x_start + idx] = GRAM_PENALTY
        objective[y_start + idx] = candidate.preference_penalty
        upper_bounds[x_start + idx] = float(candidate.item.max_portion)
        upper_bounds[y_start + idx] = 1.0
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

    nutrient_specs = (
        ("calories", deviation_start + 0, deviation_start + 1, lambda item: item.calories / 100.0),
        ("protein", deviation_start + 2, deviation_start + 3, lambda item: item.protein / 100.0),
        ("fat", deviation_start + 4, deviation_start + 5, lambda item: item.fat / 100.0),
        ("carbs", deviation_start + 6, deviation_start + 7, lambda item: item.carbs / 100.0),
    )

    for nutrient_name, over_idx, under_idx, getter in nutrient_specs:
        row = [0.0] * num_vars
        for candidate_idx, candidate in enumerate(candidates):
            row[x_start + candidate_idx] = getter(candidate.item)
        row[over_idx] = -1.0
        row[under_idx] = 1.0
        rows.append(row)
        lbs.append(plan_targets[nutrient_name])
        ubs.append(plan_targets[nutrient_name])

    for candidate_idx, candidate in enumerate(candidates):
        x_idx = x_start + candidate_idx
        y_idx = y_start + candidate_idx

        upper_row = [0.0] * num_vars
        upper_row[x_idx] = 1.0
        upper_row[y_idx] = -float(candidate.item.max_portion)
        rows.append(upper_row)
        lbs.append(-inf)
        ubs.append(0.0)

        min_portion = max(0.0, float(candidate.item.min_portion))
        if min_portion > 0:
            lower_row = [0.0] * num_vars
            lower_row[x_idx] = 1.0
            lower_row[y_idx] = -min_portion
            rows.append(lower_row)
            lbs.append(0.0)
            ubs.append(inf)

    for meal_type, limit in MEAL_ITEM_LIMITS.items():
        row = [0.0] * num_vars
        for candidate_idx, candidate in enumerate(candidates):
            if candidate.meal_type == meal_type:
                row[y_start + candidate_idx] = 1.0
        rows.append(row)
        lbs.append(0.0)
        ubs.append(float(limit))

    total_items_row = [0.0] * num_vars
    for candidate_idx in range(n):
        total_items_row[y_start + candidate_idx] = 1.0
    rows.append(total_items_row)
    lbs.append(1.0)
    ubs.append(float(MAX_TOTAL_ITEMS))

    grouped_by_item = _group_candidate_indices(candidates, key_getter=lambda candidate: candidate.base_key)
    for indices in grouped_by_item.values():
        row = [0.0] * num_vars
        for candidate_idx in indices:
            row[y_start + candidate_idx] = 1.0
        rows.append(row)
        lbs.append(0.0)
        ubs.append(1.0)

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
            bounds=Bounds(np.array(lower_bounds, dtype=float), np.array(upper_bounds, dtype=float)),
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
        portion = float(result.x[x_start + idx])
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
    grouped: Dict[str, List[int]] = {}
    for idx, candidate in enumerate(candidates):
        grouped.setdefault(key_getter(candidate), []).append(idx)
    return grouped


def _deviation_weights(plan_targets: Dict[str, float]) -> Dict[str, float]:
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


def _solve_greedy(
    candidates: Sequence[Candidate],
    plan_targets: Dict[str, float],
    daily_targets: Dict[str, float],
    already_eaten: Dict[str, float],
) -> Optional[MealPlanResult]:
    selected: Dict[int, float] = {}
    ordered_indices = sorted(range(len(candidates)), key=lambda idx: candidates[idx].preference_penalty)

    for _ in range(MAX_TOTAL_ITEMS):
        current_score = _score_selected_plan(candidates, selected, plan_targets)
        best_choice: Optional[Tuple[int, float, float]] = None

        for idx in ordered_indices:
            if idx in selected:
                continue
            if not _can_add_candidate(candidates, selected, idx):
                continue

            for portion in _portion_grid(candidates[idx].item):
                trial = dict(selected)
                trial[idx] = portion
                score = _score_selected_plan(candidates, trial, plan_targets)
                if best_choice is None or score < best_choice[2]:
                    best_choice = (idx, portion, score)

        if best_choice is None:
            break

        idx, portion, score = best_choice
        if score >= current_score and selected:
            break
        selected[idx] = portion

    if not selected:
        best_single = _best_single_candidate(candidates, plan_targets)
        if best_single is None:
            return None
        selected[best_single[0]] = best_single[1]

    selected = _prune_selection(candidates, selected, plan_targets)
    selected = _tune_portions(candidates, selected, plan_targets)
    if not selected:
        return None

    meals = _selected_meals(candidates, selected)
    return _build_result(
        meals=meals,
        plan_targets=plan_targets,
        daily_targets=daily_targets,
        already_eaten=already_eaten,
        solver_status="feasible_greedy",
        solution_method="greedy_fallback",
    )


def _best_single_candidate(
    candidates: Sequence[Candidate],
    plan_targets: Dict[str, float],
) -> Optional[Tuple[int, float]]:
    best: Optional[Tuple[int, float, float]] = None
    for idx, candidate in enumerate(candidates):
        for portion in _portion_grid(candidate.item):
            selected = {idx: portion}
            score = _score_selected_plan(candidates, selected, plan_targets)
            if best is None or score < best[2]:
                best = (idx, portion, score)
    if best is None:
        return None
    return best[0], best[1]


def _prune_selection(
    candidates: Sequence[Candidate],
    selected: Dict[int, float],
    plan_targets: Dict[str, float],
) -> Dict[int, float]:
    improved = True
    while improved and selected:
        improved = False
        current_score = _score_selected_plan(candidates, selected, plan_targets)
        for idx in list(selected):
            trial = dict(selected)
            trial.pop(idx)
            if not trial:
                continue
            score = _score_selected_plan(candidates, trial, plan_targets)
            if score < current_score:
                selected = trial
                improved = True
                break
    return selected


def _tune_portions(
    candidates: Sequence[Candidate],
    selected: Dict[int, float],
    plan_targets: Dict[str, float],
) -> Dict[int, float]:
    if not selected:
        return selected

    improved = True
    while improved:
        improved = False
        base_score = _score_selected_plan(candidates, selected, plan_targets)
        for idx in list(selected):
            best_portion = selected[idx]
            best_score = base_score
            for portion in _portion_grid(candidates[idx].item):
                if abs(portion - selected[idx]) < 1e-6:
                    continue
                trial = dict(selected)
                trial[idx] = portion
                score = _score_selected_plan(candidates, trial, plan_targets)
                if score < best_score:
                    best_score = score
                    best_portion = portion
            if best_portion != selected[idx]:
                selected[idx] = best_portion
                improved = True
                break
    return selected


def _can_add_candidate(candidates: Sequence[Candidate], selected: Dict[int, float], new_idx: int) -> bool:
    new_candidate = candidates[new_idx]
    if len(selected) >= MAX_TOTAL_ITEMS:
        return False

    meal_count = sum(1 for idx in selected if candidates[idx].meal_type == new_candidate.meal_type)
    if meal_count >= MEAL_ITEM_LIMITS.get(new_candidate.meal_type, MAX_TOTAL_ITEMS):
        return False

    if any(candidates[idx].base_key == new_candidate.base_key for idx in selected):
        return False

    return True


def _portion_grid(item: FoodItem) -> List[float]:
    minimum = max(1.0, float(item.min_portion))
    maximum = max(minimum, float(item.max_portion))
    step = PORTION_GRID_SMALL if maximum <= 120 else PORTION_GRID_LARGE

    portions = {minimum, maximum}
    current = minimum
    while current <= maximum:
        portions.add(round(current, 2))
        current += step

    midpoint = minimum + (maximum - minimum) / 2.0
    portions.add(round(midpoint, 2))
    return sorted(portions)


def _score_selected_plan(
    candidates: Sequence[Candidate],
    selected: Dict[int, float],
    plan_targets: Dict[str, float],
) -> float:
    totals = _totals_from_selection(candidates, selected)
    weights = _deviation_weights(plan_targets)
    score = 0.0

    calories_delta = totals["calories"] - plan_targets["calories"]
    protein_delta = totals["protein"] - plan_targets["protein"]
    fat_delta = totals["fat"] - plan_targets["fat"]
    carbs_delta = totals["carbs"] - plan_targets["carbs"]

    score += max(0.0, calories_delta) * weights["calories_over"] + max(0.0, -calories_delta) * weights["calories_under"]
    score += max(0.0, protein_delta) * weights["protein_over"] + max(0.0, -protein_delta) * weights["protein_under"]
    score += max(0.0, fat_delta) * weights["fat_over"] + max(0.0, -fat_delta) * weights["fat_under"]
    score += max(0.0, carbs_delta) * weights["carbs_over"] + max(0.0, -carbs_delta) * weights["carbs_under"]

    family_counts: Dict[str, int] = {}
    for idx, portion in selected.items():
        candidate = candidates[idx]
        score += candidate.preference_penalty
        score += portion * GRAM_PENALTY
        family_counts[candidate.family] = family_counts.get(candidate.family, 0) + 1

    for count in family_counts.values():
        score += max(0, count - 1) * FAMILY_OVERUSE_PENALTY

    return score


def _totals_from_selection(candidates: Sequence[Candidate], selected: Dict[int, float]) -> Dict[str, float]:
    totals = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    for idx, portion in selected.items():
        item = candidates[idx].item
        totals["calories"] += item.calories * portion / 100.0
        totals["protein"] += item.protein * portion / 100.0
        totals["fat"] += item.fat * portion / 100.0
        totals["carbs"] += item.carbs * portion / 100.0
    return totals


def _sanitize_portion(item: FoodItem, portion: float) -> float:
    portion = max(float(item.min_portion), min(float(item.max_portion), portion))
    portion = round(portion / ROUND_PORTION_STEP) * ROUND_PORTION_STEP
    return max(float(item.min_portion), min(float(item.max_portion), portion))


def _selected_meals(
    candidates: Sequence[Candidate],
    selected_portions: Dict[int, float],
) -> List[MealPlanItem]:
    meals: List[MealPlanItem] = []
    for idx, portion in selected_portions.items():
        candidate = candidates[idx]
        if portion < MIN_VISIBLE_PORTION:
            continue

        portion = _sanitize_portion(candidate.item, portion)
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
