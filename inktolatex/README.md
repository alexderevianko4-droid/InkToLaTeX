# ✏️ InkToLaTeX

**Word-плагін для розпізнавання рукописних математичних формул і вставки у документ як LaTeX або рідна формула Word**

InkToLaTeX — це повнофункціональний Office Add-in (Office.js) для Microsoft Word, який дозволяє малювати рукописні формули й текст мишкою або стилусом у бічній панелі (Task Pane), миттєво розпізнавати їх за допомогою нейромереж, переглядати формули через KaTeX та вставляти в документ як текст із LaTeX (`$...$`, `$$...$$`) або як повноцінну рідну формулу Word (OMML/OOXML).

---

## 🏗️ Архітектура та потік даних

```
┌────────────────────────────────────────────────────────────┐
│                    Microsoft Word                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │               Task Pane (Add-in)                     │  │
│  │  ┌──────────────┐  ┌───────────┐  ┌──────────────┐  │  │
│  │  │  HTML5 Canvas │  │  KaTeX    │  │  Вставка     │  │  │
│  │  │  (Pointer Ev) │→ │  превʼю   │→ │  в Word      │  │  │
│  │  └──────┬───────┘  └───────────┘  └──────┬───────┘  │  │
│  └─────────┼────────────────────────────────┼───────────┘  │
│            │ POST /recognize (base64 PNG)   │ POST /to-ooxml│
│            ▼                                ▼              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           FastAPI Backend (localhost:8000)             │  │
│  │  ┌────────────┐  ┌─────────────────────────────────┐ │  │
│  │  │ /recognize │  │  Recognizer (змінний модуль)    │ │  │
│  │  │ /to-ooxml  │→ │  • pix2tex (офлайн, активний)   │ │  │
│  │  │ /health    │  │  • Mathpix API                  │ │  │
│  │  │            │  │  • Vision LLM (OpenAI/Gemini)   │ │  │
│  │  │            │  │  • mock (тестовий офлайн)       │ │  │
│  │  │            │  ├─────────────────────────────────┤ │  │
│  │  │            │  │  LaTeX → MathML → OMML (XSLT)   │ │  │
│  │  └────────────┘  └─────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

---

## 📦 Склад системи

| Компонент | Технології | Призначення |
|---|---|---|
| **Плагін** | Office.js, TypeScript / ES6, HTML5 Canvas, KaTeX | Бічна панель (Task Pane) у Word |
| **Малювання** | Pointer Events, High-DPI Canvas, Undo-стек (50 кроків), авто-обрізка PNG | Зручне поле малювання мишкою/стилусом |
| **Бекенд** | Python 3.10+, FastAPI, Uvicorn | REST API на `localhost:8000` з CORS |
| **Розпізнавання** | Модульний інтерфейс `Recognizer` | pix2tex (активний, офлайн), Mathpix, Vision LLM, Mock |
| **Формули Word** | `latex2mathml` + `MML2OMML.XSL` + Word `insertOoxml` | Генерація рідних формул Word |

---

## 🚀 Швидкий запуск

### 1. Бекенд (FastAPI)

```powershell
cd backend
python -m pip install -r requirements.txt
python main.py
```

Сервер запуститься на `http://localhost:8000`. Перевірка стану: [http://localhost:8000/health](http://localhost:8000/health)

> За замовчуванням увімкнено `RECOGNIZER=pix2tex` (локальна модель, без API-ключів). Перший запуск завантажить ваги моделі. Для тестів без моделі лишається `RECOGNIZER=mock`.

### 2. Запуск плагіна (Task Pane)

#### Варіант A: Швидкий запуск через Python (без Node.js)
```powershell
cd addin
python serve.py
```
Сервер відкриється на `http://localhost:3000/taskpane.html` (або `https://localhost:3000/taskpane.html`).

#### Варіант B: Стандартний через Node.js / Webpack
```powershell
cd addin
npm install
npx office-addin-dev-certs install
npm start
```

### 3. Завантаження плагіна у Word (Sideloading)

#### Windows (Word Desktop):
1. Скопіюйте файл `addin/manifest.xml` у будь-яку локальну папку (наприклад `C:\WordManifests`).
2. Відкрийте спільний доступ до цієї папки: **Властивості папки → Доступ → Спільний доступ**.
3. У Word відкрийте: **Файл → Параметри → Центр керування безпекою → Настройки центру керування безпекою → Довірені каталоги надбудов**.
4. Вставте мережевий шлях (наприклад `\\localhost\WordManifests`) і натисніть **Додати каталог**. Позначте прапорець **Показувати в меню**.
5. Перезапустіть Word. На вкладці **Вставка → Мої надбудови → Спільна папка** виберіть **InkToLaTeX**.
6. На вкладці **Основне** з'явиться кнопка **InkToLaTeX**, яка відкриває бічну панель!

#### Word Online:
1. Відкрийте документ на [Office.com](https://www.office.com).
2. **Вставка → Надбудови Office → Завантажити мою надбудову**.
3. Оберіть файл `manifest.xml`.

---

## 🔄 Налаштування розпізнавача (`backend/.env`)

У файлі `backend/.env` встановіть потрібний режим:

```env
# Режими: pix2tex, mock, mathpix, llm
RECOGNIZER=pix2tex

# Mathpix API (альтернатива, краще читає рукопис):
MATHPIX_APP_ID=your_app_id
MATHPIX_APP_KEY=your_app_key

# Або Vision LLM (OpenAI / Gemini / Claude через OpenAI-сумісний ендпоінт):
LLM_API_KEY=your_key
LLM_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-4o
```

---

## 🧪 Запуск автоматичних тестів

У проєкті реалізовано 15 юніт-тестів, що покривають критерії розпізнавання, API-ендпоінти та конвертацію у формули Word:

```powershell
cd backend
python -m unittest discover -s . -p "test_*.py" -v
```

Тестові сценарії:
- `x² + y² = z²` → перетворення в OMML/Word Equation
- Дроби, квадратні корені, суми з межами $\sum_{i=1}^{n}$, інтеграли $\int_{0}^{\infty}$, матриці 2×2
- Змішаний текст: «Нехай ... тоді ...» (збереження кирилиці та правильна вставка формул)
- Ендпоінти `/health`, `/recognize`, `/to-ooxml`

---

## 📁 Структура каталогу

```
inktolatex/
├── addin/
│   ├── manifest.xml           # Маніфест плагіна для Word
│   ├── package.json           # npm конфігурація
│   ├── tsconfig.json          # TypeScript конфігурація
│   ├── webpack.config.js      # Webpack збірка
│   ├── serve.py               # Легкий Python dev-сервер (порт 3000)
│   ├── assets/                # Іконки (16x16, 32x32, 64x64, 80x80)
│   ├── dist/                  # Зібраний дистрибутив (HTML, JS, CSS, Assets)
│   └── src/taskpane/
│       ├── taskpane.html      # Інтерфейс бічної панелі
│       ├── taskpane.css       # Стилі інтерфейсу
│       ├── taskpane.ts        # Контролер TypeScript
│       ├── taskpane.js        # Скомпільований ES6 бандл
│       ├── canvas.ts          # Модуль малювання InkCanvas
│       ├── api.ts             # Клієнт бекенду
│       └── insert.ts          # Вставка тексту та формул у Word
├── backend/
│   ├── main.py                # FastAPI додаток (CORS, endpoints)
│   ├── omml.py                # Конвертер LaTeX → MathML → OMML/OOXML
│   ├── MML2OMML.XSL           # XSLT таблиця трансформації в OMML
│   ├── requirements.txt       # Python бібліотеки
│   ├── .env                   # Активна конфігурація
│   ├── .env.example           # Шаблон конфігурації
│   ├── test_api.py            # Набір автотестів
│   └── recognizers/
│       ├── base.py            # Абстрактний клас Recognizer
│       ├── mathpix.py         # Реалізація Mathpix API
│       ├── llm.py             # Реалізація Vision-LLM
│       ├── pix2tex.py         # Локальна LaTeX-OCR
│       └── mock.py            # Тестовий локальний розпізнавач
└── README.md
```

---

## 📄 Ліцензія

MIT
