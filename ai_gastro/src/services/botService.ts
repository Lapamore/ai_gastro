import type { Recipe, ConversationState, BotServiceResponse, RecipeDetailsResponse } from '../types';

// Локальный тип для предпочтений рецептов (taste, cuisine, type)
interface RecipePreferences {
    taste: string | null;
    cuisine: string | null;
    type: string | null;
}

const getRandom = <T>(arr: T[]): T => arr[Math.floor(Math.random() * arr.length)];

const defaultResponses = {
    unknown: [
        "Хм, я не совсем понял. Можешь перефразировать?",
        "Прости, я еще учусь. Попробуй спросить по-другому.",
    ],
    askTaste: "Какой вкус предпочитаешь сегодня: сладкий, соленый, острый, кислый или что-то нейтральное/легкое?",
    askCuisine: "Отлично! А какую кухню выберем? Итальянская, азиатская (тайская, японская), русская, или что-то другое?",
    askType: "Понял! А что это будет: суп, основное блюдо, салат, закуска или десерт?",
    noResults: "К сожалению, по таким критериям я ничего не нашел. Попробуем изменить запрос или начать сначала?",
    confirmChoice: (name: string) => `Отличный выбор - ${name}! Приятного аппетита! 😋 Хочешь еще что-нибудь подобрать или начать сначала?`,
};

// Определяем типы для ключей в keywords
type TasteKeyword = "сладкое" | "соленое" | "острое" | "кислое" | "легкое";
type CuisineKeyword = "итальянская" | "тайская" | "японская" | "русская" | "любая";
type TypeKeyword = "суп" | "основное" | "салат" | "закуска" | "десерт" | "любой тип"; // Добавил "любой тип"

type KeywordCategory = "taste" | "cuisine" | "type" | "confirmation" | "rejection" | "restart" | "moreDetails";

const keywords: Record<KeywordCategory, Record<string, string[]> | string[]> = {
    taste: {
        сладкое: ["сладкое", "десерт", "пирожное", "торт", "конфеты"],
        соленое: ["соленое", "основное", "горячее", "сытное", "ужин", "обед"],
        острое: ["острое", "пикантное", "жгучее", "чили"],
        кислое: ["кислое", "лимон", "уксус"],
        легкое: ["легкое", "нейтральное", "перекус", "салат", "простое"],
    } as Record<TasteKeyword, string[]>,
    cuisine: {
        итальянская: ["итальянск", "паста", "пицца", "ризотто"],
        тайская: ["тайск", "том ям", "пад тай"],
        японская: ["японск", "суши", "роллы", "рамен"],
        русская: ["русск", "борщ", "пельмени", "блины", "сырники"],
        любая: ["любая", "все равно", "не важно", "удиви"],
    } as Record<CuisineKeyword, string[]>,
    type: {
        суп: ["суп", "борщ", "бульон", "похлебка"],
        основное: ["основное", "горячее", "главное блюдо", "второе"],
        салат: ["салат", "легкое", "закуска овощная"],
        закуска: ["закуска", "стартер", "аперитив"],
        десерт: ["десерт", "сладкое", "пирожное", "торт"],
        "любой тип": ["любой тип", "все равно какой тип"],
    } as Record<TypeKeyword, string[]>,
    confirmation: ["да", "хочу", "ага", "конечно", "отлично", "супер", "выбираю", "подходит"],
    rejection: ["нет", "не хочу", "другое", "не нравится", "не подходит"],
    restart: ["начать сначала", "сброс", "заново", "новый поиск"],
    moreDetails: ["подробнее", "расскажи", "детали"],
};

const parseKeyword = (text: string, category: Extract<KeywordCategory, "taste" | "cuisine" | "type">): string | null => {
    const lowerText = text.toLowerCase();
    const categoryKeywords = keywords[category] as Record<string, string[]>; // Утверждение типа
    for (const key in categoryKeywords) {
        if (categoryKeywords[key].some(kw => lowerText.includes(kw))) {
            return key;
        }
    }
    return null;
};

const checkKeywordList = (text: string, keywordList: string[]): boolean => {
    const lowerText = text.toLowerCase();
    return keywordList.some(kw => lowerText.includes(kw));
};


export const getInitialGreeting = (): BotServiceResponse => {
    return {
        text: "Привет! Я твой обновленный Гастро-Помощник 3.0! 🚀 Чем могу помочь сегодня?",
        suggestions: ["Хочу сладкое 🍰", "Посоветуй основное блюдо 🍲", "Ищу что-то из итальянской кухни 🇮🇹", "Удиви меня! ✨", "Начать сначала"],
        newState: { 
            stage: 'initial', 
            preferences: { taste: null, cuisine: null, type: null }, 
            suggestedRecipeIds: [], 
            currentRecipeId: null 
        }
    };
};

export const processUserMessage = (userInput: string, currentState: ConversationState, recipes: Recipe[]): BotServiceResponse => {
    let responseText = "";
    let responseSuggestions: string[] = [];
    let newState: ConversationState = JSON.parse(JSON.stringify(currentState)); // Глубокое копирование

    const lowerInput = userInput.toLowerCase();

    if (checkKeywordList(lowerInput, keywords.restart as string[])) {
        return getInitialGreeting();
    }
    
    if (checkKeywordList(lowerInput, keywords.moreDetails as string[]) && newState.currentRecipeId) {
        const recipe = recipes.find(r => r.id === newState.currentRecipeId);
        if (recipe) {
            const details = getRecipeDetails(recipe.id, recipes);
            return { 
                text: details.text, 
                suggestions: details.suggestions, 
                newState: { ...newState, stage: 'recipe_details' } 
            };
        }
    }

    if (newState.stage === 'recipe_details' && checkKeywordList(lowerInput, keywords.confirmation as string[])) {
         const recipe = recipes.find(r => r.id === newState.currentRecipeId);
         responseText = recipe ? defaultResponses.confirmChoice(recipe.name) : "Отличный выбор!";
         responseSuggestions = ["Подобрать еще что-нибудь", "Начать сначала"];
         const initialGreeting = getInitialGreeting();
         newState = initialGreeting.newState;
         return { text: responseText, suggestions: responseSuggestions, newState };
    }

    switch (newState.stage) {
        case 'initial':
        case 'asking_taste':
            const taste = parseKeyword(lowerInput, 'taste') as TasteKeyword | null;
            const cuisineFromInitial = parseKeyword(lowerInput, 'cuisine') as CuisineKeyword | null;

            if (taste) {
                newState.preferences.taste = taste;
                newState.stage = 'asking_cuisine';
                responseText = defaultResponses.askCuisine;
                responseSuggestions = ["Итальянская", "Тайская", "Японская", "Русская", "Любая кухня", "Назад (выбор вкуса)"];
            } else if (cuisineFromInitial) {
                 newState.preferences.cuisine = cuisineFromInitial;
                 newState.stage = 'asking_taste';
                 responseText = defaultResponses.askTaste;
                 responseSuggestions = ["Сладкое", "Соленое", "Острое", "Легкое", "Назад (выбор кухни)"];
            } else {
                responseText = defaultResponses.askTaste;
                newState.stage = 'asking_taste'; // Остаемся или переходим сюда явно
                responseSuggestions = ["Сладкое", "Соленое", "Острое", "Кислое", "Легкое"];
            }
            break;

        case 'asking_cuisine':
            if (lowerInput.includes("назад")) {
                newState.preferences.taste = null; // Сброс предыдущего выбора
                newState.stage = 'asking_taste';
                responseText = defaultResponses.askTaste;
                responseSuggestions = ["Сладкое", "Соленое", "Острое", "Кислое", "Легкое"];
                break;
            }
            const cuisine = parseKeyword(lowerInput, 'cuisine') as CuisineKeyword | null;
            if (cuisine) {
                newState.preferences.cuisine = cuisine;
                newState.stage = 'asking_type';
                responseText = defaultResponses.askType;
                responseSuggestions = ["Суп", "Основное блюдо", "Салат", "Закуска", "Десерт", "Любой тип", "Назад (выбор кухни)"];
            } else {
                responseText = "Не понял насчет кухни. " + defaultResponses.askCuisine;
                responseSuggestions = ["Итальянская", "Тайская", "Японская", "Русская", "Любая кухня", "Назад (выбор вкуса)"];
            }
            break;

        case 'asking_type':
             if (lowerInput.includes("назад")) {
                newState.preferences.cuisine = null;
                newState.stage = 'asking_cuisine';
                responseText = defaultResponses.askCuisine;
                responseSuggestions = ["Итальянская", "Тайская", "Японская", "Русская", "Любая кухня", "Назад (выбор вкуса)"];
                break;
            }
            const type = parseKeyword(lowerInput, 'type') as TypeKeyword | null;
            if (type) {
                newState.preferences.type = type === "любой тип" ? null : type;
                const filtered = filterRecipes(recipes, newState.preferences);
                if (filtered.length > 0) {
                    const suggested = filtered.slice(0, 3);
                    newState.suggestedRecipeIds = suggested.map(r => r.id);
                    newState.currentRecipeId = suggested.length > 0 ? suggested[0].id : null;
                    
                    responseText = `Вот что я нашел:\n${suggested.map(r => `\n- **${r.name}**`).join('')}`;
                    if (suggested.length > 0) {
                       responseText += `\n\nЧто-нибудь из этого нравится? Можно выбрать или попросить подробнее о первом.`;
                    }
                    responseSuggestions = suggested.map(r => r.name);
                    if (suggested.length > 0) {
                        const firstRecipeNamePart = suggested[0].name.split(" ")[0];
                        responseSuggestions.push(`Расскажи подробнее о "${firstRecipeNamePart}"`);
                    }
                    responseSuggestions.push("Другие варианты (изменить критерии)", "Начать сначала");
                    newState.stage = 'showing_suggestions';
                } else {
                    responseText = defaultResponses.noResults;
                    responseSuggestions = ["Изменить вкус", "Изменить кухню", "Изменить тип блюда", "Начать сначала"];
                    // newState.stage остается 'asking_type' для уточнения
                }
            } else {
                responseText = "Не понял тип блюда. " + defaultResponses.askType;
                responseSuggestions = ["Суп", "Основное блюдо", "Салат", "Закуска", "Десерт", "Любой тип", "Назад (выбор кухни)"];
            }
            break;

        case 'showing_suggestions':
            if (checkKeywordList(lowerInput, keywords.rejection as string[]) || lowerInput.includes("другие варианты")) {
                responseText = "Хорошо, давай попробуем подобрать что-то другое. Изменить вкус, кухню, тип блюда или начать сначала?";
                responseSuggestions = ["Изменить вкус", "Изменить кухню", "Изменить тип", "Начать сначала"];
                newState.stage = 'initial'; 
                newState.preferences = { taste: null, cuisine: null, type: null };
            } else {
                const chosenRecipe = recipes.find(r => 
                    newState.suggestedRecipeIds.includes(r.id) && 
                    r.name.toLowerCase().includes(lowerInput) // Простое совпадение по имени
                );
                if (chosenRecipe) {
                    newState.currentRecipeId = chosenRecipe.id;
                    const details = getRecipeDetails(chosenRecipe.id, recipes);
                    responseText = details.text;
                    responseSuggestions = details.suggestions;
                    newState.stage = 'recipe_details';
                } else if (lowerInput.startsWith("расскажи подробнее о ")) { // Уже обработано выше, но как fallback
                     const recipeNameFromUser = lowerInput.substring("расскажи подробнее о ".length).trim();
                     const recipeToDetail = recipes.find(r => r.name.toLowerCase().includes(recipeNameFromUser.toLowerCase()));
                     if (recipeToDetail) {
                        const details = getRecipeDetails(recipeToDetail.id, recipes);
                        responseText = details.text;
                        responseSuggestions = details.suggestions;
                        newState.currentRecipeId = recipeToDetail.id;
                        newState.stage = 'recipe_details';
                     } else {
                        responseText = "Не нашел такой рецепт для подробностей. Выбери из списка.";
                        responseSuggestions = newState.suggestedRecipeIds.map(id => recipes.find(r=>r.id === id)?.name).filter((n): n is string => !!n);
                     }
                } else {
                    responseText = "Не понял твой выбор. Пожалуйста, выбери из предложенных вариантов или попроси рассказать подробнее.";
                    responseSuggestions = newState.suggestedRecipeIds.map(id => recipes.find(r=>r.id === id)?.name).filter((n): n is string => !!n);
                    if (newState.currentRecipeId) {
                        const currentRecipeName = recipes.find(r=>r.id === newState.currentRecipeId)?.name.split(" ")[0];
                        if (currentRecipeName) responseSuggestions.push(`Расскажи подробнее о "${currentRecipeName}"`);
                    }
                    responseSuggestions.push("Другие варианты (изменить критерии)", "Начать сначала");
                }
            }
            break;
        
        case 'recipe_details':
            // Confirmation handled at the top
            if (checkKeywordList(lowerInput, keywords.rejection as string[]) || lowerInput.includes("другое")) {
                responseText = "Понял. Хочешь посмотреть другие рецепты по тем же критериям или изменить запрос?";
                // Попытка найти другие рецепты по тем же предпочтениям
                const currentPrefs = newState.preferences;
                const otherFilteredRecipes = filterRecipes(recipes, currentPrefs)
                    .filter(r => r.id !== newState.currentRecipeId) // исключаем текущий
                    .slice(0, 2); // Берем два других

                responseSuggestions = otherFilteredRecipes.map(r => r.name);
                responseSuggestions.push("Изменить критерии", "Начать сначала");
                
                if (otherFilteredRecipes.length > 0) {
                    responseText += `\n\nМожет быть, **${otherFilteredRecipes[0].name}**?`;
                    newState.currentRecipeId = otherFilteredRecipes[0].id; // Предлагаем детали для первого из новых
                } else {
                     responseText = defaultResponses.noResults + " Попробуем изменить критерии?";
                }
                newState.stage = 'showing_suggestions'; // Возвращаемся к показу предложений

            } else {
                responseText = "Выбери 'Да, подходит!' или 'Нет, другое блюдо'.";
                responseSuggestions = ["Да, подходит!", "Нет, другое блюдо", "Начать сначала"];
            }
            break;

        default:
            responseText = getRandom(defaultResponses.unknown);
            const initial = getInitialGreeting();
            newState = initial.newState;
            responseSuggestions = initial.suggestions;
    }

    if (!responseText && responseSuggestions.length === 0) { // Дополнительный fallback
        responseText = getRandom(defaultResponses.unknown);
        const initial = getInitialGreeting();
        newState = initial.newState;
        responseSuggestions = initial.suggestions;
    }
    
    return { text: responseText, suggestions: responseSuggestions, newState };
};

const filterRecipes = (allRecipes: Recipe[], prefs: RecipePreferences): Recipe[] => {
    return allRecipes.filter(recipe => {
        const tasteMatch = !prefs.taste || 
                           (Array.isArray(recipe.taste) ? recipe.taste.includes(prefs.taste) : recipe.taste === prefs.taste) ||
                           prefs.taste === 'любой'; // Добавим 'любой' если такое есть
        const cuisineMatch = !prefs.cuisine || recipe.cuisine.toLowerCase().includes(prefs.cuisine.toLowerCase()) || prefs.cuisine === 'любая';
        const typeMatch = !prefs.type || recipe.type.toLowerCase().includes(prefs.type.toLowerCase()) || prefs.type === 'любой тип';
        return tasteMatch && cuisineMatch && typeMatch;
    });
};

export const getRecipeDetails = (recipeId: string, recipes: Recipe[]): RecipeDetailsResponse => {
    const recipe = recipes.find(r => r.id === recipeId);
    if (!recipe) {
        return { text: "Ой, не могу найти детали этого рецепта.", suggestions: ["Выбрать другой", "Начать сначала"] };
    }
    let detailsText = `**${recipe.name}**\n\n`;
    detailsText += `*Кухня:* ${recipe.cuisine}\n`;
    detailsText += `*Вкус:* ${Array.isArray(recipe.taste) ? recipe.taste.join(', ') : recipe.taste}\n`;
    detailsText += `*Тип блюда:* ${recipe.type}\n`;
    if (recipe.difficulty) detailsText += `*Сложность:* ${recipe.difficulty}\n`;
    if (recipe.time) detailsText += `*Время приготовления:* ${recipe.time}\n\n`;
    detailsText += `${recipe.description}\n\n`;
    detailsText += `Тебе подходит этот вариант?`;

    return {
        text: detailsText,
        suggestions: ["Да, подходит!", "Нет, другое блюдо", "Назад к списку", "Начать сначала"]
    };
};