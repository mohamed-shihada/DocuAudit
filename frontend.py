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

# --- دالة توحيد وتجريد الحروف العربية ---
def normalize_ar(text: str) -> str:
    text = re.sub(r"[إأآا]", "ا", text)
    text = re.sub(r"ى", "ي", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"[ًٌٍَُِّْـ]", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return text.lower().strip()

def get_search_tokens(query: str):
    """استخراج الجذور والكلمات الأساسية للبحث بمرونة كاملة"""
    norm = normalize_ar(query)
    tokens = []
    
    # حالات خاصة للبند الحرج
    if "سر" in norm or "افصاح" in norm:
        tokens.extend(["سر", "افصاح", "كتمان"])
    if "جزا" in norm or "غرام" in norm:
        tokens.extend(["جزا", "غرام", "تاخير", "تعويض"])
    if "فسخ" in norm or "انها" in norm:
        tokens.extend(["فسخ", "انها", "اخلال"])
    if "التزام" in norm or "نطاق" in norm or "عمل" in norm:
        tokens.extend(["التزام", "تسليم", "نطاق"])
        
    # إضافة باقي الكلمات المنفصلة
    for word in norm.split():
        w = word.strip()
        if w.startswith("و") and len(w) > 3:
            w = w[1:]
        if w.startswith("ال") and len(w) > 4:
            w = w[2:]
        if len(w) >= 3 and w not in ["شروط", "بنود", "عدم", "علي", "في"]:
            tokens.append(w)
            
    return list(set(tokens))

def process_pdf(file_bytes, filename):
    pdf_reader = PdfReader(io.BytesIO(file_bytes))
    store = []
    full_text_debug = ""

    for page_idx, page in enumerate(pdf_reader.pages, start=1):
        text = page.extract_text() or ""
        full_text_debug += f"\n--- صفحة {page_idx} ---\n" + text
        
        # تنظيف الفواصل المزدوجة وتقطيع النص بنظام النافذة المتداخلة لضمان عدم ضياع أي بند
        clean_page_text = " ".join(text.split())
        if not clean_page_text:
            continue
            
        chunk_len = 350
        step = 180
        
        for i in range(0, max(len(clean_page_text), 1), step):
            chunk = clean_page_text[i:i + chunk_len]
            if len(chunk.strip()) > 15:
                store.append({
                    "text": chunk,
                    "norm_text": normalize_ar(chunk),
                    "reversed_norm": normalize_ar(chunk[::-1]),
                    "page": page_idx,
                    "filename": filename
                })
                
    return store, len(pdf_reader.pages), full_text_debug

def analyze_risk_and_summary(query, excerpt):
    norm_excerpt = normalize_ar(excerpt) + " " + normalize_ar(excerpt[::-1])
    
    risk_keywords_high = ["غرام", "تعويض", "فسخ", "جزا", "انهاء فوري", "مسؤول", "مصادر", "خسائر"]
    risk_keywords_medium = ["اشعار", "تاخير", "تعديل", "مهل", "ضمان", "سر", "افصاح"]

    risk_level = "منخفضة"
    for kw in risk_keywords_high:
        if kw in norm_excerpt:
            risk_level = "عالية ⚠️"
            break
            
    if risk_level == "منخفضة":
        for kw in risk_keywords_medium:
            if kw in norm_excerpt:
                risk_level = "متوسطة ⚡"
                break

    recommendation = (
        f"تم رصد تطابق مع ({query}). "
        f"مستوى الحساسية القانونية والتشغيلية: {risk_level}. "
        "يُنصح بمراجعة التبعات التشغيلية والالتزامات التعاقدية المرتبطة بهذا النص بدقة."
    )
    return risk_level, recommendation

# --- القائمة الجانبية: رفع المستند ---
with st.sidebar:
    st.header("📄 رفع المستند")
    uploaded_file = st.file_uploader("اختر ملف PDF للعقد أو الوثيقة", type=["pdf"])
    
    if uploaded_file is not None:
        st.session_state["pdf_bytes"] = uploaded_file.getvalue()
        st.session_state["pdf_name"] = uploaded_file.name

        if st.button("بدء المعالجة والفهرسة", type="primary"):
            with st.spinner("جاري استخراج النصوص وتجهيز الفهرسة..."):
                store, pages_count, debug_txt = process_pdf(uploaded_file.getvalue(), uploaded_file.name)
                st.session_state["document_store"] = store
                st.session_state["debug_txt"] = debug_txt
                st.session_state["ready_for_audit"] = True
                st.success(f"✅ تمت فهرسة {pages_count} صفحة بنجاح ({len(store)} كتلة نصية).")

# --- الواجهة الرئيسية: تقسيم الشاشة ---
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
        placeholder="مثال: غرامة، فسخ، سرية..."
    )

    quick_checks = [
        "-- بنود جاهزة للاختيار السريع --", 
        "الشروط الجزائية وغرامات التأخير", 
        "شروط إنهاء وفسخ التعاقد", 
        "التزامات السرية وعدم الإفصاح",
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
            with st.spinner("جاري فحص وتدقيق البند المستهدف..."):
                tokens = get_search_tokens(clause_query)
                matches = []
                
                for item in st.session_state["document_store"]:
                    score = 0
                    combined_norm = item["norm_text"] + " " + item["reversed_norm"]
                    for tok in tokens:
                        if tok in combined_norm:
                            score += 1
                    
                    if score > 0:
                        risk, rec = analyze_risk_and_summary(clause_query, item["text"])
                        matches.append({
                            "excerpt": item["text"],
                            "page": item["page"],
                            "similarity_score": round(min(score / max(len(tokens), 1), 1.0), 2),
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
        else:
            report_text = f"تقرير فحص منصة DocuAudit AI\nالبند المطلوب: {st.session_state.get('last_query')}\n\n"

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
