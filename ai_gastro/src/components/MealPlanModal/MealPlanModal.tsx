import { useState } from 'react';
import type { AxiosInstance } from 'axios';
import './MealPlanModal.css';

interface MealItem {
    name: string;
    portion_grams: number;
    meal_type: string;
    calories: number;
    protein: number;
    fat: number;
    carbs: number;
    category: string;
}

interface MealPlanData {
    meals: MealItem[];
    total_calories: number;
    total_protein: number;
    total_fat: number;
    total_carbs: number;
    target_calories: number;
    target_protein: number;
    target_fat: number;
    target_carbs: number;
    daily_target_calories: number;
    daily_target_protein: number;
    daily_target_fat: number;
    daily_target_carbs: number;
    already_eaten_calories: number;
    already_eaten_protein: number;
    already_eaten_fat: number;
    already_eaten_carbs: number;
    deviation_calories: number;
    deviation_protein: number;
    deviation_fat: number;
    deviation_carbs: number;
    solver_status: string;
    solution_method: string;
}

interface MealPlanModalProps {
    isOpen: boolean;
    onClose: () => void;
    api: AxiosInstance;
}

const mealLabels: Record<string, string> = {
    breakfast: '🌅 Завтрак',
    lunch: '☀️ Обед',
    dinner: '🌙 Ужин',
    snack: '🍿 Перекус',
};

function MealPlanModal({ isOpen, onClose, api }: MealPlanModalProps) {
    const [plan, setPlan] = useState<MealPlanData | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const [considerDiary, setConsiderDiary] = useState(true);
    const [maxItems, setMaxItems] = useState(5);

    const generatePlan = async () => {
        setIsLoading(true);
        setError('');
        setPlan(null);
        try {
            const res = await api.post('/mealplan/generate', {
                consider_diary: considerDiary,
                max_total_items: maxItems,
            });
            setPlan(res.data);
        } catch (err: any) {
            setError(err?.response?.data?.detail || 'Ошибка генерации плана');
        } finally {
            setIsLoading(false);
        }
    };

    if (!isOpen) return null;

    // Группируем блюда по приёмам пищи
    const groupedMeals: Record<string, MealItem[]> = {};
    if (plan) {
        for (const meal of plan.meals) {
            if (!groupedMeals[meal.meal_type]) groupedMeals[meal.meal_type] = [];
            groupedMeals[meal.meal_type].push(meal);
        }
    }

    const deviationPercent = (deviation: number, target: number) => {
        if (target === 0) return 0;
        return Math.round((deviation / target) * 100);
    };

    const isSuccessfulPlan = Boolean(
        plan && (plan.solver_status.startsWith('optimal') || plan.solver_status.startsWith('feasible'))
    );

    return (
        <div className="mealplan-overlay" onClick={onClose}>
            <div className="mealplan-modal" onClick={e => e.stopPropagation()}>
                <div className="mealplan-header">
                    <h2>🧮 Оптимальный план питания</h2>
                    <button className="mealplan-close" onClick={onClose}>×</button>
                </div>

                <div className="mealplan-body">
                    <div className="mealplan-info">
                        <p>
                            Планировщик подбирает блюда так, чтобы попасть в калории и БЖУ,
                            не повторять одно и то же без необходимости и по возможности учитывать ваши предпочтения.
                        </p>
                    </div>

                    <div className="mealplan-controls">
                        <label className="mealplan-checkbox">
                            <input
                                type="checkbox"
                                checked={considerDiary}
                                onChange={e => setConsiderDiary(e.target.checked)}
                            />
                            Учесть уже съеденное сегодня
                        </label>
                        <div className="mealplan-items-control">
                            <label htmlFor="mealplan-max-items">Количество блюд:</label>
                            <input
                                id="mealplan-max-items"
                                type="number"
                                min={3}
                                max={8}
                                value={maxItems}
                                onChange={e => setMaxItems(Math.max(3, Math.min(8, Number(e.target.value))))}
                                className="mealplan-items-input"
                            />
                        </div>
                        <button
                            className="mealplan-generate-btn"
                            onClick={generatePlan}
                            disabled={isLoading}
                        >
                            {isLoading ? 'Оптимизация...' : '⚡ Рассчитать план'}
                        </button>
                    </div>

                    {error && <div className="mealplan-error">{error}</div>}

                    {plan && isSuccessfulPlan && (
                        <div className="mealplan-result">
                            {/* Сводка отклонений */}
                            <div className="mealplan-summary">
                                <h3>📊 {plan.already_eaten_calories > 0 ? 'План на оставшуюся часть дня' : 'План на день'}</h3>
                                {plan.already_eaten_calories > 0 && (
                                    <p>
                                        Уже съедено: {plan.already_eaten_calories} ккал, Б {plan.already_eaten_protein}г, Ж {plan.already_eaten_fat}г, У {plan.already_eaten_carbs}г.
                                    </p>
                                )}
                                <div className="mealplan-targets">
                                    <div className="mealplan-target-item">
                                        <span className="target-label">Калории</span>
                                        <span className="target-value">{plan.total_calories} / {plan.target_calories} ккал</span>
                                        <span className={`target-deviation ${deviationPercent(plan.deviation_calories, plan.target_calories) < 5 ? 'good' : 'warn'}`}>
                                            ±{plan.deviation_calories} ({deviationPercent(plan.deviation_calories, plan.target_calories)}%)
                                        </span>
                                    </div>
                                    <div className="mealplan-target-item">
                                        <span className="target-label">Белки</span>
                                        <span className="target-value">{plan.total_protein} / {plan.target_protein}г</span>
                                        <span className={`target-deviation ${deviationPercent(plan.deviation_protein, plan.target_protein) < 10 ? 'good' : 'warn'}`}>
                                            ±{plan.deviation_protein}г
                                        </span>
                                    </div>
                                    <div className="mealplan-target-item">
                                        <span className="target-label">Жиры</span>
                                        <span className="target-value">{plan.total_fat} / {plan.target_fat}г</span>
                                        <span className={`target-deviation ${deviationPercent(plan.deviation_fat, plan.target_fat) < 10 ? 'good' : 'warn'}`}>
                                            ±{plan.deviation_fat}г
                                        </span>
                                    </div>
                                    <div className="mealplan-target-item">
                                        <span className="target-label">Углеводы</span>
                                        <span className="target-value">{plan.total_carbs} / {plan.target_carbs}г</span>
                                        <span className={`target-deviation ${deviationPercent(plan.deviation_carbs, plan.target_carbs) < 10 ? 'good' : 'warn'}`}>
                                            ±{plan.deviation_carbs}г
                                        </span>
                                    </div>
                                </div>
                            </div>

                            {/* Меню по приёмам пищи */}
                            <div className="mealplan-meals">
                                {['breakfast', 'lunch', 'dinner', 'snack'].map(mealType => {
                                    const items = groupedMeals[mealType];
                                    if (!items || items.length === 0) return null;
                                    return (
                                        <div key={mealType} className="mealplan-meal-group">
                                            <h4>{mealLabels[mealType]}</h4>
                                            {items.map((item, idx) => (
                                                <div key={idx} className="mealplan-meal-item">
                                                    <div className="meal-item-main">
                                                        <span className="meal-item-name">{item.name}</span>
                                                        <span className="meal-item-portion">{item.portion_grams}г</span>
                                                    </div>
                                                    <div className="meal-item-macros">
                                                        <span>{item.calories} ккал</span>
                                                        <span>Б:{item.protein}г</span>
                                                        <span>Ж:{item.fat}г</span>
                                                        <span>У:{item.carbs}г</span>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    );
                                })}
                            </div>

                            <div className="mealplan-method">
                                <details>
                                    <summary>📐 О методе оптимизации</summary>
                                    <p>
                                        Основной режим использует <strong>смешанно-целочисленную оптимизацию</strong>:
                                        отдельно выбираются блюда и отдельно подбираются их порции.
                                    </p>
                                    <p>
                                        Алгоритм учитывает минимальные и максимальные порции, запрет повторов одного блюда
                                        в нескольких приёмах пищи, мягкий штраф за однообразие и отклонения от целей по БЖУ.
                                    </p>
                                    <p>
                                        Текущий метод решения: <code>{plan.solution_method}</code>.
                                    </p>
                                </details>
                            </div>
                        </div>
                    )}

                    {plan && !isSuccessfulPlan && (
                        <div className="mealplan-error">
                            Не удалось найти оптимальное решение ({plan.solver_status}). 
                            Попробуйте изменить параметры профиля или снять ограничения.
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

export default MealPlanModal;
