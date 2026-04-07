"""
Оптимизатор плана питания на основе линейного программирования (ЛП).

Математическая постановка задачи:
═══════════════════════════════════════════════════════════════

Пусть имеется N продуктов, каждый со следующими параметрами на 100г:
  c_i — калории, p_i — белки, f_i — жиры, u_i — углеводы

Переменные решения:
  x_i — масса i-го продукта в граммах (порция)

Вспомогательные переменные отклонений:
  δ_cal⁺, δ_cal⁻ — положительное и отрицательное отклонение по калориям
  δ_prot⁺, δ_prot⁻ — по белкам
  δ_fat⁺, δ_fat⁻ — по жирам  
  δ_carb⁺, δ_carb⁻ — по углеводам

Целевая функция (минимизация взвешенной суммы отклонений):
  min  w₁(δ_cal⁺ + δ_cal⁻) + w₂(δ_prot⁺ + δ_prot⁻) + 
       w₃(δ_fat⁺ + δ_fat⁻) + w₄(δ_carb⁺ + δ_carb⁻)

  где w₁..w₄ — весовые коэффициенты, нормирующие разные единицы измерения

Ограничения:
  1. Баланс калорий:   Σ(c_i · x_i/100) - δ_cal⁺ + δ_cal⁻ = T_cal
  2. Баланс белков:    Σ(p_i · x_i/100) - δ_prot⁺ + δ_prot⁻ = T_prot
  3. Баланс жиров:     Σ(f_i · x_i/100) - δ_fat⁺ + δ_fat⁻ = T_fat
  4. Баланс углеводов: Σ(u_i · x_i/100) - δ_carb⁺ + δ_carb⁻ = T_carb
  5. Порционные:       min_i ≤ x_i ≤ max_i  (если продукт выбран)
  6. Неотрицательность: x_i ≥ 0, δ⁺, δ⁻ ≥ 0

Метод решения: Симплекс-метод (scipy.optimize.linprog, method='highs')
═══════════════════════════════════════════════════════════════
"""

import logging
from typing import List, Optional
from scipy.optimize import linprog
import numpy as np

from src.core.models.mealplan.MealPlanModels import (
    FoodItem, MealPlanItem, MealPlanResult
)

logger = logging.getLogger(__name__)

# Категории приёмов пищи с предпочтительными категориями продуктов
MEAL_CATEGORIES = {
    'breakfast': ['breakfast', 'universal'],
    'lunch': ['lunch', 'universal'],
    'dinner': ['dinner', 'universal'],
    'snack': ['snack', 'universal'],
}

# Весовые коэффициенты для нормализации целевой функции
# Калории измеряются в сотнях, БЖУ — в десятках, поэтому нормализуем
WEIGHT_CALORIES = 1.0 / 100.0   # w₁: нормализуем калории
WEIGHT_PROTEIN = 1.0 / 10.0     # w₂: нормализуем белки
WEIGHT_FAT = 1.0 / 10.0         # w₃: нормализуем жиры
WEIGHT_CARBS = 1.0 / 10.0       # w₄: нормализуем углеводы


def optimize_meal_plan(
    food_items: List[FoodItem],
    target_calories: float,
    target_protein: float,
    target_fat: float,
    target_carbs: float,
    excluded_allergens: Optional[List[str]] = None,
    excluded_ingredients: Optional[List[str]] = None,
    already_eaten_calories: float = 0,
    already_eaten_protein: float = 0,
    already_eaten_fat: float = 0,
    already_eaten_carbs: float = 0,
) -> MealPlanResult:
    """
    Решает задачу линейного программирования для составления
    оптимального плана питания на день.
    
    Учитывает уже съеденную пищу (из дневника): вычитает из целей.
    Фильтрует продукты по аллергенам и ограничениям.
    """
    
    excluded_allergens = excluded_allergens or []
    excluded_ingredients = excluded_ingredients or []
    
    # Шаг 1: Фильтрация продуктов по противопоказаниям
    filtered_items = _filter_food_items(food_items, excluded_allergens, excluded_ingredients)
    
    if len(filtered_items) < 4:
        return _empty_result(target_calories, target_protein, target_fat, target_carbs, "infeasible_too_few_items")

    # Шаг 2: Корректируем цели с учётом уже съеденного
    remaining_cal = max(0, target_calories - already_eaten_calories)
    remaining_prot = max(0, target_protein - already_eaten_protein)
    remaining_fat = max(0, target_fat - already_eaten_fat)
    remaining_carbs = max(0, target_carbs - already_eaten_carbs)

    # Шаг 3: Распределяем продукты по приёмам пищи
    meal_assignments = _assign_meals(filtered_items)
    
    # Шаг 4: Формируем и решаем задачу ЛП
    result = _solve_lp(
        meal_assignments,
        remaining_cal, remaining_prot, remaining_fat, remaining_carbs,
        target_calories, target_protein, target_fat, target_carbs
    )
    
    return result


def _filter_food_items(
    items: List[FoodItem],
    excluded_allergens: List[str],
    excluded_ingredients: List[str],
) -> List[FoodItem]:
    """Исключает продукты с аллергенами и нежелательные ингредиенты"""
    filtered = []
    excluded_lower = {a.lower() for a in excluded_allergens}
    excluded_ingr_lower = {i.lower() for i in excluded_ingredients}
    
    for item in items:
        # Проверяем аллергены
        item_allergens = {a.lower() for a in item.allergens}
        if item_allergens & excluded_lower:
            continue
        
        # Проверяем нежелательные ингредиенты по тегам и имени
        item_tags = {t.lower() for t in item.tags}
        if item_tags & excluded_ingr_lower:
            continue
        if item.name.lower() in excluded_ingr_lower:
            continue
        
        filtered.append(item)
    
    return filtered


def _assign_meals(items: List[FoodItem]) -> dict:
    """
    Распределяет продукты по приёмам пищи.
    Каждый продукт может быть назначен на несколько приёмов,
    если его категория совпадает.
    """
    assignments = {meal: [] for meal in MEAL_CATEGORIES}
    
    for item in items:
        for meal, allowed_categories in MEAL_CATEGORIES.items():
            if item.category in allowed_categories:
                assignments[meal].append(item)
    
    return assignments


def _solve_lp(
    meal_assignments: dict,
    target_cal: float,
    target_prot: float,
    target_fat: float,
    target_carbs: float,
    original_target_cal: float,
    original_target_prot: float,
    original_target_fat: float,
    original_target_carbs: float,
) -> MealPlanResult:
    """
    Формирует и решает задачу линейного программирования.
    
    Структура вектора переменных x:
    [x_1, x_2, ..., x_N, δ_cal⁺, δ_cal⁻, δ_prot⁺, δ_prot⁻, δ_fat⁺, δ_fat⁻, δ_carb⁺, δ_carb⁻]
    
    где x_i — порция i-го продукта (г), δ — переменные отклонений
    """
    
    # Собираем уникальные продукты с информацией о приёме пищи
    all_items_with_meal = []
    seen_ids = set()
    
    for meal_type, items in meal_assignments.items():
        for item in items:
            key = (item.id or item.name, meal_type)
            if key not in seen_ids:
                seen_ids.add(key)
                all_items_with_meal.append((item, meal_type))
    
    N = len(all_items_with_meal)
    
    if N == 0:
        return _empty_result(original_target_cal, original_target_prot, 
                            original_target_fat, original_target_carbs, "infeasible_no_items")
    
    # Количество переменных: N порций + 8 переменных отклонений
    num_vars = N + 8
    
    # === Целевая функция c^T x → min ===
    # Минимизируем взвешенные отклонения, порции x_i имеют нулевой вес
    c = np.zeros(num_vars)
    # Индексы переменных отклонений
    idx_dcal_plus = N      # δ_cal⁺
    idx_dcal_minus = N + 1 # δ_cal⁻
    idx_dprot_plus = N + 2 # δ_prot⁺
    idx_dprot_minus = N + 3
    idx_dfat_plus = N + 4  # δ_fat⁺
    idx_dfat_minus = N + 5
    idx_dcarb_plus = N + 6 # δ_carb⁺
    idx_dcarb_minus = N + 7
    
    c[idx_dcal_plus] = WEIGHT_CALORIES
    c[idx_dcal_minus] = WEIGHT_CALORIES
    c[idx_dprot_plus] = WEIGHT_PROTEIN
    c[idx_dprot_minus] = WEIGHT_PROTEIN
    c[idx_dfat_plus] = WEIGHT_FAT
    c[idx_dfat_minus] = WEIGHT_FAT
    c[idx_dcarb_plus] = WEIGHT_CARBS
    c[idx_dcarb_minus] = WEIGHT_CARBS
    
    # === Ограничения-равенства A_eq · x = b_eq ===
    # 4 уравнения баланса:
    # Σ(c_i·x_i/100) - δ_cal⁺ + δ_cal⁻ = T_cal
    A_eq = np.zeros((4, num_vars))
    b_eq = np.zeros(4)
    
    for j, (item, _) in enumerate(all_items_with_meal):
        A_eq[0, j] = item.calories / 100.0   # калории
        A_eq[1, j] = item.protein / 100.0     # белки
        A_eq[2, j] = item.fat / 100.0         # жиры
        A_eq[3, j] = item.carbs / 100.0       # углеводы
    
    # δ⁺ и δ⁻ для каждого нутриента
    A_eq[0, idx_dcal_plus] = -1.0
    A_eq[0, idx_dcal_minus] = 1.0
    A_eq[1, idx_dprot_plus] = -1.0
    A_eq[1, idx_dprot_minus] = 1.0
    A_eq[2, idx_dfat_plus] = -1.0
    A_eq[2, idx_dfat_minus] = 1.0
    A_eq[3, idx_dcarb_plus] = -1.0
    A_eq[3, idx_dcarb_minus] = 1.0
    
    b_eq[0] = target_cal
    b_eq[1] = target_prot
    b_eq[2] = target_fat
    b_eq[3] = target_carbs
    
    # === Границы переменных ===
    bounds = []
    for j, (item, _) in enumerate(all_items_with_meal):
        # Порции: от 0 до max_portion (0 означает — не включать)
        bounds.append((0, item.max_portion))
    
    # Переменные отклонений ≥ 0
    for _ in range(8):
        bounds.append((0, None))
    
    # === Решаем задачу ЛП ===
    try:
        result = linprog(
            c,
            A_eq=A_eq,
            b_eq=b_eq,
            bounds=bounds,
            method='highs',
        )
    except Exception as e:
        logger.error(f"Ошибка решения ЛП: {e}")
        return _empty_result(original_target_cal, original_target_prot,
                            original_target_fat, original_target_carbs, f"solver_error: {e}")
    
    if not result.success:
        logger.warning(f"ЛП не нашла оптимальное решение: {result.message}")
        return _empty_result(original_target_cal, original_target_prot,
                            original_target_fat, original_target_carbs, f"infeasible: {result.message}")
    
    # === Извлекаем решение ===
    portions = result.x[:N]
    
    meals: List[MealPlanItem] = []
    total_cal = 0.0
    total_prot = 0.0
    total_fat = 0.0
    total_carbs = 0.0
    
    for j, (item, meal_type) in enumerate(all_items_with_meal):
        portion = portions[j]
        if portion < 10:  # Меньше 10г — не включаем (незначительно)
            continue
        
        portion = round(portion, 0)
        cal = round(item.calories * portion / 100, 1)
        prot = round(item.protein * portion / 100, 1)
        fat = round(item.fat * portion / 100, 1)
        carb = round(item.carbs * portion / 100, 1)
        
        meals.append(MealPlanItem(
            food_item=item,
            portion_grams=portion,
            meal_type=meal_type,
            calories=cal,
            protein=prot,
            fat=fat,
            carbs=carb,
        ))
        
        total_cal += cal
        total_prot += prot
        total_fat += fat
        total_carbs += carb
    
    # Сортируем: завтрак → обед → ужин → перекус
    meal_order = {'breakfast': 0, 'lunch': 1, 'dinner': 2, 'snack': 3}
    meals.sort(key=lambda m: meal_order.get(m.meal_type, 99))
    
    return MealPlanResult(
        meals=meals,
        total_calories=round(total_cal, 1),
        total_protein=round(total_prot, 1),
        total_fat=round(total_fat, 1),
        total_carbs=round(total_carbs, 1),
        target_calories=original_target_cal,
        target_protein=original_target_prot,
        target_fat=original_target_fat,
        target_carbs=original_target_carbs,
        deviation_calories=round(abs(total_cal - target_cal), 1),
        deviation_protein=round(abs(total_prot - target_prot), 1),
        deviation_fat=round(abs(total_fat - target_fat), 1),
        deviation_carbs=round(abs(total_carbs - target_carbs), 1),
        solver_status="optimal",
    )


def _empty_result(
    target_cal: float, target_prot: float,
    target_fat: float, target_carbs: float,
    status: str,
) -> MealPlanResult:
    """Возвращает пустой результат при невозможности оптимизации"""
    return MealPlanResult(
        meals=[],
        total_calories=0, total_protein=0, total_fat=0, total_carbs=0,
        target_calories=target_cal, target_protein=target_prot,
        target_fat=target_fat, target_carbs=target_carbs,
        deviation_calories=target_cal, deviation_protein=target_prot,
        deviation_fat=target_fat, deviation_carbs=target_carbs,
        solver_status=status,
    )
