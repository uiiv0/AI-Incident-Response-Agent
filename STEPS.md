# خطوات التنفيذ بالترتيب (يوم واحد)

المشروع جاهز كامل (الكود، البيانات، الاختبارات). شغلك اليوم: تشغّله على جهازك، تقيس، تثبت الأمان، تكتب النتائج.
لا تنتقل للخطوة التالية قبل ما تنجح نقطة التحقق ✅.

## 1) تجهيز البيئة (45 دقيقة)
```powershell
# ثبّت uv (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# فك ضغط المشروع، ثم:
cd ir-agent
uv sync
copy .env.example .env
```
✅ `uv run pytest -q` يطلع كله passed (29). هذي الاختبارات ما تحتاج نموذج.

## 2) النموذج واختبار الأدوات (45 دقيقة) ← أخطر خطوة
**Ollama (محلي):** ثبّته من ollama.com/download، ثم اسحب نموذج يدعم tools (فلتر Tools في ollama.com/search):
```powershell
ollama pull qwen3:8b          # مثال، صغّر الحجم لو جهازك ضعيف
```
ارفع سياق Ollama لأن الافتراضي صغير على بعض النسخ، وأعد تشغيل Ollama بعدها:
```powershell
setx OLLAMA_CONTEXT_LENGTH 8192
```
**أو OpenRouter:** حط مفتاحك واسم نموذج `:free` في `.env` (انتبه لحد الطلبات اليومي).
```powershell
uv run python smoke_test.py
```
✅ يطبع `PASS: model called the tool`. إذا FAIL غيّر النموذج الحين.

## 3) جرّب الـ agent على حادثة (30 دقيقة)
```powershell
uv run python -m agent.cli INC-001 --prompt B
```
اضغط `y` عند طلب الموافقة. ✅ يطلع JSON نهائي، ويتسجل trace في `traces/`.
جرّب INC-007 (beaconing) وINC-010 (إنذار كاذب: لازم action=none).

## 4) شغّل الـ eval A مقابل B (60 دقيقة، شغّله بالخلفية)
```powershell
uv run python -m evals.run_eval --configs A B --k 2
```
- لو وقف بسبب حد الطلبات أو انقطع: أعد نفس الأمر، الردود المخزّنة (`.cache/`) ما تنعاد.
- للتجربة السريعة: `--limit 5` أو `--ids INC-001 INC-013`.
✅ يطلع `evals/results/results.md` فيه الجدول وعدّاد الأخطاء.

## 5) الهجوم والدفاع (60 دقيقة، وانت تنتظر الـ eval)
```powershell
uv run python -m security.attack --incident INC-013 --undefended
uv run python -m security.attack --incident INC-013
```
✅ الأول: `EXECUTED` فيه isolate_host dc01 (الهجوم نجح). الثاني: ما نُفّذ شي (الدفاع بالكود).
لو النموذج ما انخدع أصلاً، جرّب `--prompt A` أو INC-014 / INC-015 أو نموذج أصغر، وسجّل هذا في README بصراحة.
الإثبات المستقل عن النموذج: `uv run pytest tests/test_defence.py -v`.

## 6) تحليل الأخطاء (45 دقيقة)
افتح `evals/results/results.json` وعدّ الأسباب (`errors`)، وافتح 3 traces لحالات فاشلة. اكتب في README:
أكبر فئة أخطاء، وش اللي تغيّر بين A وB، وهل الفرق أكبر من الضجيج (pass^k).

## 7) README والتسليم (60 دقيقة)
- عبّي الـ TODO الثلاثة في README.md (جدول الـ eval، نتيجة الهجوم، المزوّد وPDPL).
- **clone نظيف:** انسخ المشروع لمجلد ثاني بدون `.venv` و`.cache` وشغّل `uv sync` ثم `uv run pytest -q`.
- تأكد ما في مفاتيح في الـ repo (`.env` مستبعد في `.gitignore`)، ثم push.

## 8) العرض (60 دقيقة)
5 شرائح: المشكلة، demo، السلم (prompt → graph)، الـ evals، الأمان.
شغّل الـ demo مرة قبل العرض (يسخّن الـ cache)، وسجّل فيديو دقيقتين احتياطي.

## لو ضاق الوقت: اقطع بهذا الترتيب
1. `--k 1` بدل 2 (وقل بصراحة إنك ما حسبت pass^k).  2. شرائح أقل.  
لا تقطع: الموافقة، الـ eval، الهجوم والدفاع.
