from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import re
from google import genai
from google.genai.errors import APIError
import os
from dotenv import load_dotenv

load_dotenv()
# ----------------------------------------------------
# تنظيف النص
# ----------------------------------------------------
ARABIC_DIACRITICS = re.compile(r"[\u064B-\u0652]")

def clean_text(text):
    if not text:
        return ""
    text = ARABIC_DIACRITICS.sub("", text)
    text = re.sub(r"[أإآٱ]", "ا", text)
    text = re.sub(r"[يى]", "ي", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"[^\w\s\u0600-\u06FF]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

# ----------------------------------------------------
# كلمات تعتبر سوالف وليست بحث عن معنى
# ----------------------------------------------------
SMALL_TALK_WORDS = [
    "السلام عليكم", "السلام", "هلا", "هلا والله", "مرحبا", "مرحبه",
    "اهلا", "اهلاً", "السلام عليكم ورحمة الله ", "عفوا", "السلام عليكم ورحمة الله وبركاته", "يا هلا", "كيف حالك", "كيفك", "وش الاخبار",
    "اخبارك", "ثانكيو", "اهلين", "سلام",
    "شكرا", "شكراً", "ثانكس", "شكرا لك", "يعطيك العافية", "هل انت",
    "العفو", "تمام", "بخير", "الحمد لله", "هاي", "hello", "hi"
]

def is_small_talk(text):
    cleaned = clean_text(text)
    return cleaned in [clean_text(w) for w in SMALL_TALK_WORDS]


# ----------------------------------------------------
# إعداد Flask
# ----------------------------------------------------
app = Flask(__name__)
CORS(app)


# ----------------------------------------------------
# تحميل القاموس
# ----------------------------------------------------
try:
    with open("dictionary.json", "r", encoding="utf-8") as f:
        DICT = json.load(f)
except:
    DICT = {}

# ----------------------------------------------------
# حالات المستخدم
# ----------------------------------------------------
STATE_AWAITING_WORD = "awaiting_word"
STATE_AWAITING_DIALECT = "awaiting_dialect"
STATE_AWAITING_AI_CONFIRMATION = "awaiting_ai_confirmation"

user_state = {}

# ----------------------------------------------------
# خيارات اللهجات
# ----------------------------------------------------
DIALECT_OPTIONS = {
    1: "وسطى",
    2: "جنوبية",
    3: "شرقية",
    4: "غربية",
    5: "شمالية",
    6: "اللغة الإنجليزية"
}

DIALECT_CHOICES_TEXT = "\n".join([f"{num}- {name}" for num, name in DIALECT_OPTIONS.items()])


# ----------------------------------------------------
# دالة البحث بالقاموس
# ----------------------------------------------------

def find_in_dictionary(user_input):
    """تحليل الجملة واستخراج الكلمة ومعرفة هل هي موجودة في القاموس."""

    cleaned_full = clean_text(user_input)

    # 1) البحث عن عبارة كاملة داخل الجملة (يسمح بالبحث عن مفاتيح تحتوي أكثر من كلمة)
    for key in DICT.keys():
        if clean_text(key) in cleaned_full:
            return key, DICT[key], "exact"

    # 2) استخراج الكلمات المهمة من الجملة (يحل مشكلة: ما معنى كلمة طريق)
    words = cleaned_full.split()

    COMMON = ["ما", "هو", "هي", "ايش", "وش", "معنى", "ماهو", "ما كلمة", "كلمة", "ابي", "ابغى", "اريد"]

    filtered = [w for w in words if w not in COMMON]

    if not filtered:
        filtered = words

    # نختار أطول كلمة لأنها الأقرب عادة للمفهوم
    candidate = max(filtered, key=len)

    # 3) البحث عن تطابق مباشر لكلمة واحدة
    for key in DICT.keys():
        if clean_text(key) == candidate:
            return key, DICT[key], "exact_word"

    # 4) فشل البحث
    return None, None, candidate

# ----------------------------------------------------
# تهيئة Gemini
# ----------------------------------------------------

API_KEY = os.getenv("API_KEY")
try:
    client = genai.Client(api_key=API_KEY)
    print("🤖 Gemini initialized successfully")
except:
    client = None
    print("❌ Gemini failed to initialize")

def ai_is_in_scope(user_text):
    """
    يطلب من الذكاء الاصطناعي تصنيف السؤال:
    هل يتعلق باللهجات/معنى الكلمات؟
    أم سؤال عام يجب رفضه؟
    """
    if not client:
        return True  # إذا ما فيه AI نخليه يكمل طبيعي

    prompt = (
        "أنت فلتر متخصص فقط في تصنيف الأسئلة.\n"
        "سأعطيك سؤال مستخدم.\n"
        "أجب فقط بكلمة واحدة:\n"
        "نعم = إذا كان السؤال يتعلق بمعنى كلمة، أو لهجة، أو ترجمة، أو كلمة يريد المستخدم شرحها.\n"
        "لا = إذا كان السؤال سؤالاً عاماً (دين، تاريخ، مدن، أخبار، معرفة، أشخاص...).\n"
        "لا تشرح.\n"
        f"السؤال: {user_text}"
    )

    try:
        res = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        answer = res.text.strip().lower()
        return answer == "نعم"
    
    except:
        return True  # fallback

# ----------------------------------------------------
# برومبت قوي باللهجات (الخيار A)
# ----------------------------------------------------
def get_ai_persona_prompt(user_question: str, chosen_dialect: str) -> str:

    base_instructions = (
        "أنت Gemini، المساعد الخارجي لشات بوت (نَبْرة) المتخصص في اللهجات السعودية.\n"
        "مهمتك: شرح معنى الكلمة باللهجة المطلوبة + إضافة مثال باللهجة + شرح الفصحى.\n"
        "التزم بـ:\n"
        "1) لهجة واضحة وقوية.\n"
        "2) مثال واحد فقط.\n"
        "3) أسلوب مختصر (1–2 أسطر).\n"
        "4) لا تستخدم مصادر خارجية.\n"
    )

    # اللهجات
    if "وسطى" in chosen_dialect:
        persona = (
            "اكتب باللهجة النجدية بشكل واضح.\n"
            "استخدم كلمات مثل: وش / وشلون / زين.\n"
        )

    elif "غربية" in chosen_dialect:
        persona = (
            "اكتب باللهجة الحجازية.\n"
            "استخدم كلمات: إيش / مرّة / كيف.\n"
        )

    elif "جنوبية" in chosen_dialect:
        persona = (
            "اكتب باللهجة الجنوبية.\n"
            "استخدم كلمات: وشّه / ذلحين / خابر.\n"
        )

    elif "شمالية" in chosen_dialect:
        persona = (
            "اكتب باللهجة الشمالية.\n"
            "استخدم كلمات: هاوش / شلون / وليد.\n"
        )

    elif "شرقية" in chosen_dialect:
        persona = (
            "اكتب باللهجة السعودية الشرقية بأسلوب بسيط وواضح.\n"
        )

    elif "اللغة الإنجليزية" in chosen_dialect or "اللغة الإنجليزية" in chosen_dialect:
        persona = (
            "اشرح المعنى باللغة الإنجليزية ثم وضّح المعنى بالعربية.\n"
        )

    else:
        persona = "اكتب بالعربية الفصحى."

    # البرومبت النهائي
    full_prompt = (
        f"{base_instructions}\n"
        f"اللهجة المطلوبة: {chosen_dialect}\n"
        f"الكلمة: {user_question}\n\n"
        f"{persona}"
    )

    return full_prompt


# ----------------------------------------------------
# دالة سؤال Gemini
# ----------------------------------------------------
def ask_ai(word, dialect):
    if not client:
        return "⚠️ خدمة المساعد الخارجي غير مفعّلة."

    try:
        prompt = get_ai_persona_prompt(word, dialect)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text.strip()

    except Exception as e:
        print("AI Error:", e)
        return "⚠️ حدث خطأ أثناء الاتصال بالمساعد الخارجي."


def ai_reply_formatted(word, dialect):
    ai_text = ask_ai(word, dialect)
    
    return (
        f"🤖 أنا Gemini المساعد الخارجي لنَبْرة.\n\n"
        f"📌 سؤالك / كلمتك: {word}\n"
        f"🌍 اللهجة المطلوبة: {dialect}\n\n"
        f"🔎 الجواب:\n{ai_text}\n\n"
        "⚠️ ملاحظة: أنا مُولَّد آليًا وقد تحتوي إجابتي على بعض الأخطاء.\n"
        "💬 اكتب كلمة أو جملة جديدة لو حاب تكمل."
    )


# ----------------------------------------------------
# دالة اختيار اللهجة
# ----------------------------------------------------
def handle_dialect(user_id, choice):

    state = user_state[user_id]
    word = state.get("pending_word")

    try:
        num = int(choice)
        dialect = DIALECT_OPTIONS.get(num)
    except:
        dialect = None

    if not dialect:
        return jsonify({
            "status": STATE_AWAITING_DIALECT,
            "reply": "⚠️ الرقم غير صحيح.\nاختر رقم لهجة من القائمة:\n\n" + DIALECT_CHOICES_TEXT
        })


    # ----------------------------------------------------
    # البحث عن الكلمة في القاموس
    found_key, translations, match_status = find_in_dictionary(word)


    # ----------------------------------------------------
    # 🔥 معالجة خاصة للهجة الإنجليزية (لا تعتبر لهجة)
    if dialect == "اللغة الإنجليزية" and translations:
        english_value = translations.get("اللغة الإنجليزية", "—")

        reply = (
            f"✨ أنا نبرة، يا سلام! لقيت لك معنى كلمة **{found_key}** "
            f"باللغة الإنجليزية.\n\n"
            f"📌 ترجمتها تكون: {english_value}\n"
        )

        # إضافة الفصحى إذا موجودة
        if "فصحى" in translations:
            reply += f"📖 بالفصحى: {translations['فصحى']}\n"

        # الإنجليزية ليست لهجة → لا ندخل وضع "عرض كل اللهجات"
        user_state[user_id] = {"state": STATE_AWAITING_WORD}

        return jsonify({"status": "success", "reply": reply})

    # ----------------------------------------------------
    # ✔ موجود في القاموس ولهجة سعودية
    if translations:
        meaning = translations.get(dialect, "لا يوجد معنى لهذه اللهجة.")

        reply = (
            f"✨انا نبرة. يا سلام! لقيت لك معنى كلمة {found_key} "
            f"باللهجة {dialect}.\n\n"
            f"🗣 مرادفها بهاللهجة يكون: {meaning}.\n"
        )

        if "فصحى" in translations:
            reply += f"📖 بالفصحى: {translations['فصحى']}\n"

        reply += "\n🔎 تبغاني أعرض لك الكلمة بكل اللهجات؟ (نعم / لا)"
        user_state[user_id]["state"] = "awaiting_show_all"
        user_state[user_id]["last_word"] = found_key
    
        return jsonify({"status": "success", "reply": reply})

    # ----------------------------------------------------
    # ❌ غير موجود في القاموس → روح لمسار الذكاء الاصطناعي
    else:
        user_state[user_id] = {
            "state": STATE_AWAITING_AI_CONFIRMATION,
            "pending_word": word,
            "dialect": dialect
        }
        
        reply = (
            "📖 انا نَبْرة. ما لقيت معنى للكلمة في قاموسي.\n"
            "تبيني أسأل المساعد الخارجي يساعدنا؟ (نعم/لا)"
        )

        return jsonify({
        "status": STATE_AWAITING_AI_CONFIRMATION,
        "reply": reply
    })

# ----------------------------------------------------
# /ask_dialect — استقبال رقم اللهجة
# ----------------------------------------------------
@app.route("/ask_dialect", methods=["POST"])
def ask_dialect():
    data = request.get_json()
    choice = data.get("choice", "")
    user_id = data.get("user_id", "default")

    return handle_dialect(user_id, choice)


# ----------------------------------------------------
# /ask — خطوة إدخال الكلمة
# ----------------------------------------------------
@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    word = data.get("text", "").strip()
    user_id = data.get("user_id", "default")
    
    # 🔥 فلتر التحيات والشكر والكلام العام (لا نبحث عنه في القاموس)
    if is_small_talk(word):
        return jsonify({
            "status": "neutral",
            "reply": "🤖 يا هلا! اكتب كلمة تبيني أشرح معناها أو أترجمها بلهجات المملكة."
        })

        # 🔥 فلتر الذكاء الاصطناعي للتخصص
    if not ai_is_in_scope(word):
        return jsonify({
            "status": "error",
            "reply": (
                "✨ سؤالك خارج نطاق معرفتي.\n"
                "أنا نَبْرة متخصص بشرح الكلمات وتحويله لمرادفاته باللهجات السعودية وترجمته باللغة الانجليزية.\n"
                "اكتب كلمة تبغى تعرف معناها ♥️"
            )
        })

    if not word:
        return jsonify({"status": "error", "reply": "📝 اكتب كلمة أو جملة."})

    user_state[user_id] = {
        "state": STATE_AWAITING_DIALECT,
        "pending_word": word
    }

    reply = (
        "📖:انا نَبْرة، تمام! حدد اللهجة اللي تبغاني أجاوبك فيها:\n\n" +
        DIALECT_CHOICES_TEXT +
        "\n\nاكتب رقم اللهجة:"
    )

    return jsonify({"status": STATE_AWAITING_DIALECT, "reply": reply})



# ----------------------------------------------------
# /ask_full — نعم / لا
# ----------------------------------------------------

@app.route("/ask_full", methods=["POST"])
def ask_full():
    data = request.get_json()
    answer = clean_text(data.get("answer", "").lower())
    user_id = data.get("user_id", "default")

    state = user_state.get(user_id, {})
    current_state = state.get("state")

    # ----------------------------------------------------
    # الحالة 1: عرض جميع اللهجات بعد الرد الرئيسي
    if current_state == "awaiting_show_all":
        word = state.get("last_word")

        if not word:
            user_state[user_id] = {"state": STATE_AWAITING_WORD}
            return jsonify({"status": "success", "reply": "⚠️ ما لقيت الكلمة السابقة.. حاول ترسلها من جديد."})

        translations = DICT.get(word, {})

        # نعم → عرض جميع اللهجات
        if answer in ["نعم", "ايه", "ايوه", "إيه", "يس", "yes"]:
            full = f" 📚 جميع اللهجات لكلمة {word}:\n\n"
            for dialect, meaning in translations.items():
                full += f"• {dialect}: {meaning}\n"

            user_state[user_id] = {"state": STATE_AWAITING_WORD}
            return jsonify({"status": "success", "reply": full + "\nاكتب كلمة جديدة لو تبي نكمل 🌿"})

        # لا → تجاهل وإكمال المحادثة
        elif answer in ["لا", "لأ", "no", "نو"]:
            user_state[user_id] = {"state": STATE_AWAITING_WORD}
            return jsonify({"status": "success", "reply": "تمام، اكتب كلمة جديدة ❤️"})

        else:
            return jsonify({"status": "success", "reply": "يرجى الإجابة بـ نعم أو لا."})


    # ----------------------------------------------------
    # الحالة 2: التأكيد على استخدام المساعد الخارجي (AI)
    if current_state != STATE_AWAITING_AI_CONFIRMATION:
        return jsonify({"status": "error", "reply": "اكتب كلمة جديدة."})

    if answer in ["نعم", "ايه", "أيوه", "إيه", "يس", "yes"]:
        word = state["pending_word"]
        dialect = state["dialect"]

        user_state[user_id] = {"state": STATE_AWAITING_WORD}
        return jsonify({
            "status": "ai_only_success",
            "reply": ai_reply_formatted(word, dialect)
        })

    elif answer in ["لا", "لأ", "no", "نو"]:
        user_state[user_id] = {"state": STATE_AWAITING_WORD}
        return jsonify({"status": "success", "reply": "تمام، اكتب كلمة جديدة."})

    else:
        return jsonify({"status": "success", "reply": "يرجى الإجابة بـ نعم أو لا."})

# ----------------------------------------------------
# الملفات الثابتة
# ----------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(".", path)

# ----------------------------------------------------
# تشغيل السيرفر
# ----------------------------------------------------
if __name__ == "__main__":
    app.run()
