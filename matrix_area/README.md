# MATRIX — Project Mirror 🪞

النظام الذكي ذاتي التطور — **Phase 0 (The Mirror)** foundation.

نظام agent مستقل (autonomous) كيخدم المهام بوحدو داخل sandbox معزول، ونتا
(الـ Boss) كتراقب الـ "Thinking" ديالو وكتشوف شنو كيدير live من الـ Boss Panel.

---

## 🏗️ الهيكل (Architecture)

```
matrix_area/
├── backend/
│   ├── main.py        # FastAPI — Boss Panel API + SSE streaming
│   ├── engine.py      # محرك Gemini + حلقة agent بـ tool-use
│   ├── sandbox.py     # العالم المعزول (تنفيذ آمن + kill switch)
│   ├── memory.py      # الذاكرة المشتركة (SQLite) للـ clones
│   ├── monitor.py     # مراقب الموارد (CPU/RAM)
│   ├── clones.py      # نظام الاستنساخ (حد صلب: 10)
│   └── requirements.txt
├── frontend/
│   ├── index.html     # Dashboard (Boss Panel)
│   ├── styles.css     # ستايل غامق احترافي (Grok/ChatGPT)
│   └── app.js         # بث Thinking + Sandbox + Resources
├── sandbox_workspace/ # عالم الـ AI — هنا فقط كيقدر يخدم
├── Dockerfile
└── README.md
```

## 🔑 المفتاح (Gemini API Key)

النظام محتاج `GEMINI_API_KEY`. **ماتحطوش فالكود.** استعملو كـ env variable:

```bash
export GEMINI_API_KEY="your_key_here"
```

سير لـ https://aistudio.google.com/apikey باش تدير مفتاح مجاني.

## ▶️ التشغيل (Run)

### محلياً (Local)
```bash
cd matrix_area/backend
pip install -r requirements.txt
export GEMINI_API_KEY="your_key_here"
uvicorn main:app --reload --port 8000
```
ثم حل: http://localhost:8000

### بـ Docker (معزول — موصى به)
```bash
docker build -t matrix .
docker run -e GEMINI_API_KEY="your_key_here" -p 8000:8000 matrix
```

## 🛡️ الأمان (Safety — non-negotiable)

1. **العزل:** الـ AI كيخدم فقط داخل `sandbox_workspace/`. أي محاولة خروج = مرفوضة.
2. **Kill Switch:** زر `/kill` فالـ Boss Panel كيوقف كلشي فوراً، وهو **خارج تحكم الـ AI**.
3. **حد الاستنساخ:** أقصى 10 clones باش مايستنزفش الموارد.

## 🧩 الموديلات الجديدة (Phase 1)

| الملف | الوظيفة |
|---|---|
| `selfcode.py`  | **Source Code Injection** — كيحقن كود النظام لـ `self_source/` فالـ workspace باش الـ AI يكون واعي بكودو |
| `staging.py`   | **Staging Area + Self-Testing** — أي تعديل ذاتي كيتجرب فبيئة معزولة، وكيتطبق فقط إلا نجح الـ test |
| `webscout.py`  | **The Web Scout** — بحث فالويب (DuckDuckGo، بلا API key) |
| `prompts.py`   | **Recursive Prompt Optimization** — توليد system prompt مخصص لكل clone |

أدوات جديدة عند الـ agent: `web_search`, `read_own_source`, `propose_self_edit`.
endpoints جداد: `/clone_events` (بث thinking ديال clone)، `/best_clone` (Evolutionary Selection).

## 🗺️ خارطة الطريق (Roadmap)

- [x] **Phase 0 — The Mirror:** الهيكل، Gemini، Sandbox، Boss Panel ✅
- [x] **Phase 1 — The Fixer:** Source Injection + Staging/Self-Test + Web Scout ✅
- [x] **Phase 2 — The Architect:** Hot-Reload (محمي) + spawn_clone tool + Docker non-root ✅
- [ ] **Phase 3 — The Multi-Mind:** فريق clones (Dev/Design/QA) + بث live ديال كل clone فالـ UI
- [ ] **Phase 4 — Manus-Level:** استقلالية كاملة + Visual Self-Design

### أدوات الـ agent الكاملة
`run_shell`, `write_file`, `read_file`, `list_dir`, `remember`, `recall`,
`web_search`, `read_own_source`, `propose_self_edit`, `hot_reload`, `spawn_clone`, `finish`

### الموديل
الافتراضي: `gemini-2.5-flash` (يتبدل عبر `MATRIX_MODEL` فالـ `.env`).

### السر (الأمان)
المفتاح كيتقرا من `.env` (موجود فـ `.gitignore` — **مكيتدفعش أبداً**). نسخ `.env.example` لـ `.env` وحط مفتاحك.

> ملاحظة: الـ self-modification كيمر عبر Staging Area (الكود كيتجرب قبل ما يتطبق)،
> والـ live process + kill switch دايماً محميين خارج تحكم الـ AI.
