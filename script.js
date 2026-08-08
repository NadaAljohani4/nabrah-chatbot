// ------------------------------
// صندوق عرض الرسائل
// ------------------------------
const chatBox = document.getElementById("chat-box");

// معرف المستخدم لتتبع الحالة
let userId = "user1";

// ------------------------------
// 💡 دالة تحديث تذييل الصفحة (Footer)
// ------------------------------
function updateFooter() {
    const footerElement = document.getElementById('app-footer');
    if (footerElement) {
        const date = new Date();
        const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        const formattedDate = date.toLocaleDateString('ar-SA', options); 
        
        footerElement.innerHTML = `<span>${formattedDate}</span>`;
    }
}

// ------------------------------
// دالة عرض الرسائل في الصندوق
// ------------------------------
function addMessage(text, sender) {
  const msg = document.createElement("div");
  msg.classList.add("message", sender);
  msg.innerHTML = text
    .replace(/\*\*/g, '')
    .replace(/\*/g, '')
    .replace(/\n/g, '<br>');

  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;
  return msg; 
}

// ------------------------------
// تنسيق رسالة البوت مع الأيقونة
// ------------------------------
function formatBotMessage(text) {
    const icon = '<img src="zz.png" alt="نبرة" style="height:20px;vertical-align:middle;margin-left:5px;">';
    return icon + text;
}

// ------------------------------
// دالة بدء المحادثة الترحيبية
// ------------------------------
function startGreetingConversation() {
  addMessage(formatBotMessage(": أهلاً بك! أنا نَبْرة، البوت اللي يحوّل لك الكلمة بمرادفاتها من لهجات السعودية."), "bot"); 
  
  setTimeout(() => {
    addMessage(formatBotMessage(": تفضل، اكتب أي شيء عشان نبدأ سوالف!"), "bot");
  }, 1000); 
}

// ------------------------------
// دالة إرسال الرسالة
// ------------------------------
async function sendMessage() {
  const input = document.getElementById("user-input");
  const text = input.value.trim();

  if (!text) return;

  addMessage(text, "user"); 
  input.value = "";         

  let loadingMsg = addMessage(formatBotMessage("ثواني..."), "bot");


// ------------------------------
// حالة اختيار رقم اللهجة
// ------------------------------
const dialectNumber = parseInt(text);

if (!isNaN(dialectNumber) && dialectNumber >= 1 && dialectNumber <= 6) {
    const res = await fetch("/ask_dialect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ choice: text, user_id: userId })
    });

    const data = await res.json();
    chatBox.removeChild(loadingMsg);
    addMessage(data.reply, "bot");
    return;
}

  // ------------------------------
  // حالة نعم / لا
  // ------------------------------
  const yesWords = ["نعم", "ايه", "أيوه", "إيه", "يس", "yes"];
  const noWords  = ["لا", "لأ", "نو", "no"];

  if (yesWords.includes(text.toLowerCase()) || noWords.includes(text.toLowerCase())) {
    try {
      const res = await fetch("/ask_full", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer: text, user_id: userId })
      });

      const data = await res.json();
      chatBox.removeChild(loadingMsg);

      if (data.reply) {
          addMessage(data.reply, "bot");
      } else if (data.message) {
          addMessage(data.message, "bot");
      } else {
          addMessage("⚠️ رد غير مفهوم من السيرفر.", "bot");
      }

      return;

    } catch (err) {
      chatBox.removeChild(loadingMsg);
      addMessage("⚠️ خطأ في الاتصال بالسيرفر. تأكد من تشغيله.", "bot");
      return;
    }
  }

  // ------------------------------
  // إرسال الكلمة الأساسية
  // ------------------------------
  try {
    const res = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, user_id: userId })
    });

    const data = await res.json();
    chatBox.removeChild(loadingMsg);

    // ⭐ أهم تعديل — عرض الرد مباشرة بدون شروط معقدة
    if (data.reply) {
        addMessage(data.reply, "bot");
    } else if (data.message) {
        addMessage(data.message, "bot");
    } else {
        addMessage("⚠️ رد غير مفهوم من السيرفر.", "bot");
    }

  } catch (err) {
    chatBox.removeChild(loadingMsg);
    addMessage("⚠️ خطأ في الاتصال بالسيرفر. تأكد من تشغيله.", "bot");
  }
}

// ------------------------------
// إرسال الرسالة بالضغط على Enter
// ------------------------------
document.getElementById("user-input").addEventListener("keypress", function(e) {
  if (e.key === "Enter") sendMessage();
});

// ------------------------------
// زر خدمة العملاء
// ------------------------------
function contactSupport() {
  const email = "smrkknr63@gmail.com";
  const phone = "0532123789";
  
  const messageText = 
      `📩 للتواصل مع خدمة العملاء:\n\n` +
      `البريد الإلكتروني: <a href="mailto:${email}" style="color:#f7a61a;">${email}</a>\n` +
      `رقم الهاتف: <a href="tel:${phone}" style="color:#f7a61a;">${phone}</a>`;

  addMessage(messageText, "bot");
}

// ------------------------------
// الخريطة التفاعلية
// ------------------------------
const map = document.getElementById('ksa-map');
const regions = document.querySelectorAll('.region');
const tooltip = document.getElementById('region-tooltip');

function hideTooltip() {
    tooltip.style.display = 'none';
}

regions.forEach(region => {
    region.addEventListener('mousemove', function(e) {
        tooltip.textContent = this.dataset.name;
        tooltip.style.display = 'block';
        tooltip.style.left = `${e.clientX + 10}px`;
        tooltip.style.top = `${e.clientY - 30}px`;
    });
    
    region.addEventListener('mouseout', hideTooltip);
});

map.addEventListener('click', function(event) {});

hideTooltip();

// ------------------------------
// الروبوت (العينين)
// ------------------------------
document.addEventListener('mousemove', (event) => {
    const leftPupil = document.getElementById('left-pupil');
    const rightPupil = document.getElementById('right-pupil');
    const robotContainer = document.getElementById('robot-container');

    if (!leftPupil || !rightPupil || !robotContainer) return; 

    const rect = robotContainer.getBoundingClientRect();
    const mouseX = event.clientX; 
    const mouseY = event.clientY;

    const LEFT_EYE_CX_SVG = 165; 
    const LEFT_EYE_CY_SVG = 140; 
    const RIGHT_EYE_CX_SVG = 235;
    const RIGHT_EYE_CY_SVG = 140;
    const maxMove = 8;

    const ratioX = rect.width / 400;
    const ratioY = rect.height / 500;
    
    const leftEye = { x: rect.left + LEFT_EYE_CX_SVG * ratioX, y: rect.top + LEFT_EYE_CY_SVG * ratioY };
    const rightEye = { x: rect.left + RIGHT_EYE_CX_SVG * ratioX, y: rect.top + RIGHT_EYE_CY_SVG * ratioY };
    
    function getMove(eyeCenter) {
        const dx = mouseX - eyeCenter.x;
        const dy = mouseY - eyeCenter.y;
        const angle = Math.atan2(dy, dx);
        const dist = Math.min(Math.sqrt(dx*dx + dy*dy), maxMove);
        return { x: Math.cos(angle) * dist, y: Math.sin(angle) * dist };
    }

    const m1 = getMove(leftEye);
    const m2 = getMove(rightEye);

    leftPupil.setAttribute('transform', `translate(${m1.x}, ${m1.y})`);
    rightPupil.setAttribute('transform', `translate(${m2.x}, ${m2.y})`);
});

// ------------------------------
// بدء النظام
// ------------------------------
window.onload = function() {
  startGreetingConversation();
  updateFooter();
};
