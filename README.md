# 🍳 AI Gastro - Гастрономический AI-ассистент

Умный помощник для кулинарии с поддержкой персонализации, учёта аллергий и интеграцией с Mattermost.

## 📋 Функционал

### Основное приложение (Web)
- 🍳 **Рецепты** - поиск и рекомендации рецептов
- 📔 **Дневник питания** - отслеживание приёмов пищи
- ⚠️ **Аллергии** - учёт пищевых ограничений
- 🎯 **Персонализация** - рекомендации на основе предпочтений
- 📺 **YouTube видео** - кулинарные видео-рецепты
- 💬 **История чатов** - сохранение диалогов

### Mattermost бот
- 🤖 **Упрощённая версия** - только рецепты и аллергии
- 💬 **Интеграция** - работает в командах Mattermost
- 🔔 **Упоминания** - реагирует на @mentions

## 🚀 Быстрый старт с Docker

### Предварительные требования

- Docker 20.10+
- Docker Compose 2.0+
- AITunnel API ключ (или другой OpenAI-совместимый провайдер)

### 1. Клонировать репозиторий

```bash
git clone <repository-url>
cd ai_gastro
```

### 2. Настроить переменные окружения

```bash
# Создать .env файл из шаблона
cp backend/.env.example backend/.env

# Отредактировать backend/.env и заполнить:
# - AITUNNEL_API_KEY (API ключ для AI)
# - MYSQL_PASSWORD (пароль для базы данных)
# - YOUTUBE_API_KEY (для видео-рецептов)
# - MATTERMOST настройки (опционально)
```

### 3. Запустить приложение

```bash
# Собрать и запустить все сервисы
docker-compose up -d

# Проверить статус
docker-compose ps

# Посмотреть логи
docker-compose logs -f
```

### 4. Открыть приложение

- **Frontend**: http://localhost
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## 🛠️ Разработка

### Структура проекта

```
ai_gastro/
├── ai_gastro/          # Frontend (React + Vite)
│   ├── src/
│   ├── Dockerfile
│   └── nginx.conf
├── backend/            # Backend (FastAPI)
│   ├── src/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example    # Шаблон конфигурации
├── docker-compose.yaml
└── .gitignore
```

### Локальная разработка

#### Frontend

```bash
cd ai_gastro
npm install
npm run dev
# Откроется на http://localhost:5173
```

#### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn src.main:app --reload
# Запустится на http://localhost:8000
```

## 🐳 Docker команды

```bash
# Запуск
docker-compose up -d

# Остановка
docker-compose down

# Перезапуск сервиса
docker-compose restart backend

# Пересборка
docker-compose up -d --build

# Логи конкретного сервиса
docker-compose logs -f backend

# Очистка (удалить volumes)
docker-compose down -v
```

## 🤖 Настройка Mattermost бота

Подробная инструкция в [backend/MATTERMOST_SETUP.md](backend/MATTERMOST_SETUP.md)

Кратко:
1. Создайте бота в Mattermost
2. Получите токен и Team ID
3. Добавьте в `.env`:
   ```env
   MATTERMOST_URL=https://your-server.com
   MATTERMOST_BOT_TOKEN=your-token
   MATTERMOST_TEAM_ID=your-team-id
   MATTERMOST_ENABLED=true
   ```
4. Перезапустите: `docker-compose restart backend`

## 📊 Базы данных

### MongoDB
- **Порт**: 27017
- **Назначение**: Хранение аллергий, настроек пользователей
- **Подключение**: `mongodb://localhost:27017/ai_gastro`

### MySQL
- **Порт**: 3306
- **Назначение**: Основные данные пользователей, истории
- **Подключение**: через переменные из `.env`

## 🔧 Переменные окружения

| Переменная | Описание | Обязательна |
|------------|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API ключ | ✅ |
| `MYSQL_PASSWORD` | MySQL пароль | ✅ |
| `MATTERMOST_URL` | URL Mattermost сервера | ❌ |
| `MATTERMOST_BOT_TOKEN` | Токен бота | ❌ |
| `MATTERMOST_ENABLED` | Включить бота | ❌ |

## 🏗️ Архитектура

```
┌─────────────┐
│   Nginx     │ ← Frontend (React) + Reverse Proxy
│  (Port 80)  │
└──────┬──────┘
       │
       ├──→ /api/* ──→ ┌──────────────┐
       │                │   Backend    │ ← FastAPI
       │                │  (Port 8000) │
       │                └───────┬──────┘
       │                        │
       │                ┌───────┼───────┐
       │                ▼       ▼       ▼
       │           ┌────────┐ ┌─────┐ ┌────────────┐
       │           │MongoDB │ │MySQL│ │ Mattermost │
       │           └────────┘ └─────┘ └────────────┘
       │
       └──→ / ──→ Static files
```

## 🧪 Тестирование

```bash
# Backend тесты
cd backend
pytest

# Frontend тесты
cd ai_gastro
npm test
```

## 📝 API Документация

После запуска backend доступна по адресам:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🔒 Безопасность

- ✅ Не коммитить `.env` файлы
- ✅ Использовать сильные пароли для БД
- ✅ Ротация API ключей
- ✅ HTTPS в production
- ✅ Non-root пользователь в Docker контейнерах

## 📦 Production Deployment

### Рекомендации:

1. **Использовать внешние БД** - отдельные managed databases
2. **HTTPS** - настроить SSL сертификаты (Let's Encrypt)
3. **Environment** - использовать secrets management
4. **Мониторинг** - добавить Prometheus + Grafana
5. **Логирование** - централизованное с ELK/Loki
6. **Backup** - регулярные бэкапы БД

### Nginx с SSL (пример)

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # ... остальная конфигурация
}
```

## 🐛 Troubleshooting

### Backend не стартует
```bash
# Проверить логи
docker-compose logs backend

# Проверить подключение к БД
docker-compose exec backend python test_db.py
```

### Frontend не загружается
```bash
# Проверить nginx конфигурацию
docker-compose exec frontend nginx -t

# Перезапустить
docker-compose restart frontend
```

### Mattermost бот не отвечает
См. [MATTERMOST_SETUP.md](backend/MATTERMOST_SETUP.md)

## 📄 Лицензия

MIT

## 👥 Авторы

AI Gastro Team
