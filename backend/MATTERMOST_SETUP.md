# 🤖 Настройка Mattermost бота "Гастро-помощник"

## Описание

Mattermost бот "Гастро-помощник" - это упрощённая версия основного AI-ассистента, которая работает только с:
- 🍳 **Рецептами** - поиск и рекомендации рецептов
- ⚠️ **Аллергиями** - учёт пищевых аллергий пользователя

## Шаг 1: Создание бота в Mattermost

### 1.1 Через System Console (рекомендуется)

1. Войдите в Mattermost как администратор
2. Перейдите в **System Console** → **Integrations** → **Bot Accounts**
3. Убедитесь, что опция **Enable Bot Account Creation** включена
4. Перейдите в **Integrations** → **Bot Accounts** → **Add Bot Account**
5. Заполните поля:
   - **Username**: `gastro-helper` (или любое другое)
   - **Display Name**: `Гастро-помощник 🍳`
   - **Description**: `AI-ассистент для рецептов и учёта аллергий`
   - **Role**: `Member`
6. Нажмите **Create Bot Account**
7. **Скопируйте и сохраните токен!** Он показывается только один раз

### 1.2 Через Personal Access Token

1. Создайте обычного пользователя для бота
2. Войдите под этим пользователем
3. Перейдите в **Account Settings** → **Security** → **Personal Access Tokens**
4. Нажмите **Create Token**
5. Введите описание и создайте токен
6. Скопируйте токен

## Шаг 2: Получение Team ID

### Способ 1: Через URL
1. Откройте ваш Mattermost
2. Team ID можно найти в URL: `https://mattermost.example.com/team-name/channels/town-square`
3. Используйте API для получения ID: `GET /api/v4/teams/name/{team_name}`

### Способ 2: Через System Console
1. **System Console** → **Teams**
2. Нажмите на нужную команду
3. Team ID будет в URL

### Способ 3: Через API
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://your-mattermost.com/api/v4/teams
```

## Шаг 3: Настройка .env

Добавьте в файл `.env`:

```env
# Mattermost Configuration
MATTERMOST_URL=https://your-mattermost-server.com
MATTERMOST_BOT_TOKEN=your-bot-token-here
MATTERMOST_TEAM_ID=your-team-id
MATTERMOST_ENABLED=true
```

## Шаг 4: Запуск

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn src.main:app --reload
```

При успешном подключении в консоли появится:
```
✅ Mattermost bot connected successfully
🤖 Bot user: gastro-helper
📋 Listening in team: your-team-name
```

## Использование бота

### Команды

Бот реагирует на упоминания (`@gastro-helper`) и прямые сообщения.

#### Примеры запросов:

**Рецепты:**
- `@gastro-helper подскажи рецепт борща`
- `@gastro-helper что приготовить из курицы и риса?`
- `@gastro-helper простой рецепт завтрака`

**Аллергии:**
- `@gastro-helper у меня аллергия на орехи и молоко`
- `@gastro-helper мои аллергии: глютен, яйца`
- `@gastro-helper какие у меня аллергии?`

**Рецепты с учётом аллергий:**
- `@gastro-helper рецепт торта (у меня аллергия на глютен)`
- После установки аллергий, бот автоматически их учитывает

### Примеры диалогов

```
Пользователь: @gastro-helper привет! у меня аллергия на молоко и орехи
Бот: Привет! 👋 Я запомнил твои аллергии:
     • Молоко 🥛
     • Орехи 🥜
     Теперь я буду учитывать их при подборе рецептов!

Пользователь: @gastro-helper что приготовить на ужин?
Бот: С учётом твоих аллергий (молоко, орехи), могу предложить:
     🍗 Запечённая курица с овощами
     🐟 Рыба на пару с рисом
     🥗 Овощное рагу
     Хочешь подробный рецепт какого-то блюда?
```

## Архитектура

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│   Mattermost    │────▶│  FastAPI Backend │────▶│   OpenAI    │
│    Server       │◀────│                  │◀────│     API     │
└─────────────────┘     └──────────────────┘     └─────────────┘
                               │
                               ▼
                        ┌─────────────┐
                        │   MongoDB   │
                        │ (allergies) │
                        └─────────────┘
```

## API Endpoints

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/mattermost/webhook` | POST | Webhook для входящих сообщений |
| `/api/mattermost/status` | GET | Статус подключения бота |
| `/api/mattermost/health` | GET | Health check |

## Хранение данных

Аллергии пользователей хранятся в MongoDB:

```json
{
  "mattermost_user_id": "abc123",
  "username": "john.doe",
  "allergies": ["молоко", "орехи", "глютен"],
  "updated_at": "2026-02-02T10:30:00Z"
}
```

## Troubleshooting

### Бот не отвечает
1. Проверьте, что `MATTERMOST_ENABLED=true`
2. Убедитесь, что токен валидный
3. Проверьте логи: `docker logs backend` или консоль

### Ошибка подключения
1. Проверьте URL (без trailing slash)
2. Убедитесь, что сервер доступен
3. Проверьте настройки firewall

### Бот не видит сообщения
1. Добавьте бота в нужный канал
2. Проверьте права бота
3. Убедитесь, что упоминаете бота правильно

## Безопасность

⚠️ **Важно:**
- Никогда не коммитьте `.env` файл с токенами
- Используйте отдельного бота для production
- Регулярно ротируйте токены
- Ограничьте доступ бота только нужными каналами

## Отличия от основного бота

| Функция | Основной бот | Mattermost бот |
|---------|--------------|----------------|
| Рецепты | ✅ | ✅ |
| Аллергии | ✅ | ✅ |
| Дневник питания | ✅ | ❌ |
| Персонализация | ✅ | ❌ |
| YouTube видео | ✅ | ❌ |
| История чатов | ✅ | ❌ |
