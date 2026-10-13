import streamlit as st
import io
import re
import base64
from pypdf import PdfReader

st.set_page_config(
    page_title="منصة DocuAudit AI",
    page_icon="⚖️",
    layout="wide"
)

st.title("⚖️ منصة تدقيق المستندات الذكية (DocuAudit AI)")
st.markdown("فحص وتدقيق بنود العقود والمستندات بدقة موثوقة مع تقييم المخاطر.")

if "document_store" not in st.session_state:
    st.session_state["document_store"] = []

# --- دالة تنقية الحروف العربية وتوحيدها ---
def normalize_ar(text: str) -> str:
    text = re.sub(r"[إأآا]", "ا", text)
    text = re.sub(r"ى", "ي", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"[ًٌٍَُِّْـ]", "", text)
    # إزالة علامات الترقيم والأقواس
    text = re.sub(r"[^\w\s]", " ", text)
    return text.lower().strip()

def extract_keywords(query: str):
    stop_words = {"في", "من", "على", "الى", "إلى", "عن", "مع", "او", "أو", "ثم", "كل", "أي", "شروط", "بنود"}
    raw_words = query.strip().split()
    clean_words = []
    for w in raw_words:
        nw = normalize_ar(w)
        # إزالة واو العطف الزائدة
        if nw.startswith("و") and len(nw) > 3:
            nw = nw[1:]
        # إزالة ال التعريف لمطابقة أدق (مثال: الجزائية -> جزائيه)
        if nw.startswith("ال") and len(nw) > 4:
            clean_words.append(nw[2:])
        if nw and nw not in stop_words and len(nw) > 1:
            clean_words.append(nw)
    return list(set(clean_words))

def process_pdf(file_bytes, filename):
    pdf_reader = PdfReader(io.BytesIO(file_bytes))
    store = []
    raw_full_text = ""

    for page_idx, page in enumerate(pdf_reader.pages, start=1):
        text = page.extract_text() or ""
        raw_full_text += f"\n--- صفحة {page_idx} ---\n" + text
        if not text.strip():
            continue
        
        # تقسيم بالفقرات أولاً، ثم بحجم 400 حرف لضمان عدم تشتيت البند
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 20]
        if not paragraphs:
            paragraphs = [text[i:i+400] for i in range(0, len(text), 300)]
            
        for chunk in paragraphs:
            store.append({
                "text": chunk,
                "norm_text": normalize_ar(chunk),
                # النسخة المعكوسة من النص لاكتشاف النصوص المعكوسة بـ PDF
                "reversed_norm": normalize_ar(chunk[::-1]),
                "page": page_idx,
                "filename": filename
            })
            
    return store, len(pdf_reader.pages), raw_full_text

def analyze_risk_and_summary(query, excerpt):
    norm_excerpt = normalize_ar(excerpt)
    risk_keywords_high = ["غرامه", "تعويض", "فسخ", "جزائي", "انهاء فوري", "مسؤوليه", "مصادره", "خسائر"]
    risk_keywords_medium = ["اشعار", "تاخير", "تعديل", "مهله", "ضمان", "سريه", "افصاح"]

    risk_level = "منخفضة"
    for kw in risk_keywords_high:
        if kw in norm_excerpt or kw in normalize_ar(excerpt[::-1]):
            risk_level = "عالية ⚠️"
            break
    if risk_level == "منخفضة":
        for kw in risk_keywords_medium:
            if kw in norm_excerpt or kw in normalize_ar(excerpt[::-1]):
                risk_level = "متوسطة ⚡"
                break

    recommendation = (
        f"تم رصد تطابق مع ({query}). "
        f"مستوى الحساسية القانونية والتشغيلية: {risk_level}. "
        "يُنصح بمراجعة التبعات المالية والالتزامات المتبادلة بدقة."
    )
    return risk_level, recommendation

# --- القائمة الجانبية ---
with st.sidebar:
    st.header("📄 رفع المستند")
    uploaded_file = st.file_uploader("اختر ملف PDF للعقد أو الوثيقة", type=["pdf"])
    
    if uploaded_file is not None:
        st.session_state["pdf_bytes"] = uploaded_file.getvalue()
        st.session_state["pdf_name"] = uploaded_file.name

        if st.button("بدء المعالجة والفهرسة", type="primary"):
            with st.spinner("جاري استخراج النصوص وتجهيز الفهرسة..."):
                store, pages_count, raw_text = process_pdf(uploaded_file.getvalue(), uploaded_file.name)
                st.session_state["document_store"] = store
                st.session_state["raw_text_preview"] = raw_text
                st.session_state["ready_for_audit"] = True
                st.success(f"✅ تمت فهرسة {pages_count} صفحة بنجاح ({len(store)} فقرة).")

# --- الواجهة الرئيسية ---
col_pdf, col_audit = st.columns([1, 1], gap="medium")

with col_pdf:
    st.subheader("📑 عارض الوثيقة الأصلية")
    if "pdf_bytes" in st.session_state:
        base64_pdf = base64.b64encode(st.session_state["pdf_bytes"]).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="650" type="application/pdf" style="border-radius: 8px; border: 1px solid #ddd;"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
    else:
        st.info("قم برفع ملف PDF من القائمة الجانبية ليظهر هنا.")

with col_audit:
    st.subheader("🔍 لوحة التدقيق وتحليل البنود")
    
    clause_query = st.text_input(
        "أدخل كلمة أو بنداً للتدقيق عنه:",
        placeholder="مثال: غرامة، جزائي، فسخ، سرية..."
    )

    quick_checks = [
        "-- بنود جاهزة للاختيار السريع --", 
        "غرامة التأخير والشرط الجزائي", 
        "فسخ العقد وإنهاء التعاقد", 
        "السرية وعدم الإفصاح",
        "الالتزامات ونطاق العمل"
    ]
    selected_quick = st.selectbox("أو اختر فحصاً سريعاً:", quick_checks)
    if selected_quick != "-- بنود جاهزة للاختيار السريع --":
        clause_query = selected_quick

    if st.button("🚀 فحص وتحليل البند", type="primary"):
        if not clause_query.strip():
            st.warning("يرجى كتابة نص أو اختيار بند للتدقيق.")
        elif not st.session_state.get("ready_for_audit", False):
            st.warning("يرجى الضغط على زر 'بدء المعالجة والفهرسة' في القائمة الجانبية أولاً.")
        else:
            with st.spinner("جاري مطابقة المقاطع وتقدير المخاطر..."):
                keywords = extract_keywords(clause_query)
                matches = []
                
                for item in st.session_state["document_store"]:
                    score = 0
                    for kw in keywords:
                        # مطابقة في النص العادي أو النص المعكوس (لحل مشكلة ترميز PDF العربي)
                        if kw in item["norm_text"] or kw in item["reversed_norm"]:
                            score += 1
                        elif len(kw) > 3 and (kw[:len(kw)-1] in item["norm_text"] or kw[:len(kw)-1] in item["reversed_norm"]):
                            score += 0.5
                    
                    if score > 0:
                        risk, rec = analyze_risk_and_summary(clause_query, item["text"])
                        matches.append({
                            "excerpt": item["text"],
                            "page": item["page"],
                            "similarity_score": round(min(score / max(len(keywords), 1), 1.0), 2),
                            "risk_level": risk,
                            "recommendation": rec
                        })
                
                matches.sort(key=lambda x: x["similarity_score"], reverse=True)
                st.session_state["latest_results"] = matches[:3]
                st.session_state["last_query"] = clause_query

    # عرض النتائج
    if "latest_results" in st.session_state:
        st.markdown("---")
        st.write(f"### نتائج فحص: **{st.session_state.get('last_query', '')}**")
        
        if not st.session_state["latest_results"]:
            st.warning("لم يتم العثور على فقرات مطابقة لنص البحث داخل الوثيقة.")
            # إظهار نافذة استكشافية للتأكد من قراءة النص
            if "raw_text_preview" in st.session_state:
                with st.expander("🛠️ معاينة النص المستخرج من الـ PDF للتأكد من سلامة القراءة:"):
                    st.text(st.session_state["raw_text_preview"][:1500])
        else:
            report_text = f"تقرير فحص منصة DocuAudit AI\nالبند: {st.session_state.get('last_query')}\n\n"

            for idx, item in enumerate(st.session_state["latest_results"], start=1):
                risk = item['risk_level']
                st.markdown(f"#### 📌 دليل #{idx} — **الصفحة: {item['page']}** | درجة الخطورة: `{risk}`")
                st.info(f"**التحليل والتوصية:** {item['recommendation']}")
                
                with st.expander("عرض النص المقتبس من الوثيقة:", expanded=True):
                    st.markdown(f"> *\"{item['excerpt']}\"*")

                report_text += f"دليل #{idx} (صفحة {item['page']}) - خطورة: {risk}\n"
                report_text += f"النص: {item['excerpt']}\n"
                report_text += f"التوصية: {item['recommendation']}\n"
                report_text += "-"*40 + "\n"

            st.download_button(
                label="📥 تحميل تقرير التدقيق (TXT)",
                data=report_text,
                file_name="Audit_Report.txt",
                mime="text/plain"
            )