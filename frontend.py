import streamlit as st
import io
import base64
from pypdf import PdfReader

# ----------------------------------------------------
# 1. إعداد هوية الصفحة
# ----------------------------------------------------
st.set_page_config(
    page_title="منصة DocuAudit AI",
    page_icon="⚖️",
    layout="wide"
)

st.title("⚖️ منصة تدقيق المستندات الذكية (DocuAudit AI)")
st.markdown("فحص وتدقيق بنود العقود والمستندات بدقة لحظية موثوقة مع تقييم المخاطر.")

# ----------------------------------------------------
# 2. دوال المعالجة المباشرة والتدقيق (بدون الحاجة لسيرفر خارجي)
# ----------------------------------------------------
if "document_store" not in st.session_state:
    st.session_state["document_store"] = []

def process_pdf(file_bytes, filename):
    pdf_reader = PdfReader(io.BytesIO(file_bytes))
    store = []
    chunk_size = 500
    overlap = 100

    for page_idx, page in enumerate(pdf_reader.pages, start=1):
        text = page.extract_text() or ""
        if not text.strip():
            continue
        start = 0
        while start < len(text):
            chunk = text[start:start + chunk_size]
            store.append({
                "text": chunk,
                "page": page_idx,
                "filename": filename
            })
            start += (chunk_size - overlap)
            
    return store, len(pdf_reader.pages)

def analyze_risk_and_summary(query, excerpt):
    risk_keywords_high = ["غرامة", "تعويض", "فسخ", "جزائي", "إنهاء فوري", "مسؤولية كاملة", "فوائد"]
    risk_keywords_medium = ["إشعار", "تأخير", "تعديل", "مهلة", "ضمان", "سرية"]

    risk_level = "منخفضة"
    for kw in risk_keywords_high:
        if kw in excerpt:
            risk_level = "عالية ⚠️"
            break
    if risk_level == "منخفضة":
        for kw in risk_keywords_medium:
            if kw in excerpt:
                risk_level = "متوسطة ⚡"
                break

    recommendation = (
        f"يتعلق المقطع بـ ({query}). "
        f"مستوى الحساسية: {risk_level}. "
        "يُنصح بمراجعة المدد الزمنية والالتزامات المتبادلة بدقة."
    )
    return risk_level, recommendation

# ----------------------------------------------------
# 3. القائمة الجانبية: رفع المستند والمعالجة
# ----------------------------------------------------
with st.sidebar:
    st.header("📄 رفع المستند")
    uploaded_file = st.file_uploader("اختر ملف PDF للعقد أو الوثيقة", type=["pdf"])
    
    if uploaded_file is not None:
        st.session_state["pdf_bytes"] = uploaded_file.getvalue()
        st.session_state["pdf_name"] = uploaded_file.name

        if st.button("بدء المعالجة والفهرسة", type="primary"):
            with st.spinner("جاري استخراج النصوص وتجهيز الفهرسة محلياً..."):
                store, pages_count = process_pdf(uploaded_file.getvalue(), uploaded_file.name)
                st.session_state["document_store"] = store
                st.session_state["ready_for_audit"] = True
                st.success(f"✅ تمت معالجة وفهرسة {pages_count} صفحة بنجاح.")
                st.info(f"إجمالي الكتل المفهرسة: {len(store)}")

# ----------------------------------------------------
# 4. لوحة التدقيق وعارض الملفات
# ----------------------------------------------------
col_pdf, col_audit = st.columns([1, 1], gap="medium")

with col_pdf:
    st.subheader("📑 عارض الوثيقة")
    if "pdf_bytes" in st.session_state:
        base64_pdf = base64.b64encode(st.session_state["pdf_bytes"]).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf" style="border-radius: 8px; border: 1px solid #ddd;"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
    else:
        st.info("قم برفع ملف PDF من القائمة الجانبية ليظهر هنا.")

with col_audit:
    st.subheader("🔍 لوحة التدقيق وتحليل البنود")
    
    clause_query = st.text_input(
        "أدخل بنداً للتدقيق عنه:",
        placeholder="مثال: الشروط الجزائية، فسخ العقد، التعويضات..."
    )

    quick_checks = ["-- بنود جاهزة للاختيار --", "الشروط الجزائية وغرامات التأخير", "شروط إنهاء وفسخ التعاقد", "التزامات السرية وعدم الإفصاح"]
    selected_quick = st.selectbox("أو اختر فحصاً سريعاً:", quick_checks)
    if selected_quick != "-- بنود جاهزة للاختيار --":
        clause_query = selected_quick

    if st.button("🚀 فحص وتحليل البند", type="primary"):
        if not clause_query.strip():
            st.warning("يرجى كتابة نص أو اختيار بند للتدقيق.")
        elif not st.session_state.get("ready_for_audit", False):
            st.warning("يرجى الضغط على زر 'بدء المعالجة والفهرسة' في القائمة الجانبية أولاً.")
        else:
            with st.spinner("جاري مطابقة المقاطع وتقدير المخاطر..."):
                query_words = clause_query.strip().split()
                matches = []
                for item in st.session_state["document_store"]:
                    score = sum(1 for w in query_words if w in item["text"])
                    if score > 0:
                        risk, rec = analyze_risk_and_summary(clause_query, item["text"])
                        matches.append({
                            "excerpt": item["text"],
                            "page": item["page"],
                            "similarity_score": round(min(score / max(len(query_words), 1), 1.0), 2),
                            "risk_level": risk,
                            "recommendation": rec
                        })
                
                matches.sort(key=lambda x: x["similarity_score"], reverse=True)
                st.session_state["latest_results"] = matches[:3]
                st.session_state["last_query"] = clause_query

    # عرض نتائج التدقيق
    if "latest_results" in st.session_state:
        st.markdown("---")
        st.write(f"### نتائج فحص: **{st.session_state.get('last_query', '')}**")
        
        report_text = f"تقرير فحص منصة DocuAudit AI\nالبند: {st.session_state.get('last_query')}\n\n"

        if not st.session_state["latest_results"]:
            st.warning("لم يتم العثور على فقرات مطابقة لنص البحث داخل الوثيقة.")
        else:
            for idx, item in enumerate(st.session_state["latest_results"], start=1):
                risk = item['risk_level']
                st.markdown(f"#### 📌 دليل #{idx} — **الصفحة: {item['page']}** | درجة الخطورة: `{risk}`")
                st.info(f"**التحليل والتوصية:** {item['recommendation']}")
                
                with st.expander("عرض النص المقتبس من الوثيقة:", expanded=True):
                    st.markdown(f"> *\"{item['excerpt']}\"*")
                    st.caption(f"درجة التطابق: {int(item['similarity_score'] * 100)}%")

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