import io
from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel
from pypdf import PdfReader

app = FastAPI(
    title="DocuAudit AI Engine",
    description="محرك التدقيق الذكي وتقييم المخاطر"
)

# تخزين المقاطع وبيانات المستند
document_store = []


@app.post("/upload_and_index")
async def upload_and_index(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="يرجى رفع ملف PDF فقط.")

    try:
        content = await file.read()
        pdf_reader = PdfReader(io.BytesIO(content))
        
        global document_store
        document_store = []

        chunk_size = 500
        overlap = 100

        for page_idx, page in enumerate(pdf_reader.pages, start=1):
            page_text = page.extract_text() or ""
            if not page_text.strip():
                continue
            
            start = 0
            while start < len(page_text):
                chunk = page_text[start:start + chunk_size]
                document_store.append({
                    "text": chunk,
                    "page": page_idx,
                    "filename": file.filename
                })
                start += (chunk_size - overlap)

        if not document_store:
            raise HTTPException(status_code=400, detail="لم يتم العثور على نصوص قابلة للقراءة.")

        return {
            "status": "success",
            "message": f"تمت معالجة وفهرسة {len(pdf_reader.pages)} صفحة بنجاح.",
            "total_chunks": len(document_store),
            "pages_count": len(pdf_reader.pages)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AuditRequest(BaseModel):
    query: str
    num_results: int = 3


def analyze_risk_and_summary(query: str, excerpt: str):
    """
    محرك استدلال وتقييم للمخاطر وتوليد ملخص تنفيذي للبند المسترجع
    """
    risk_keywords_high = ["غرامة", "تعويض", "فسخ", "جزائي", "إنهاء فوري", "مسؤولية كاملة", "فوائد"]
    risk_keywords_medium = ["إشعار", "تأخير", "تعديل", "مهلة", "ضمان", "سرية"]

    risk_level = "منخفضة"
    risk_color = "green"

    for kw in risk_keywords_high:
        if kw in excerpt:
            risk_level = "عالية ⚠️"
            risk_color = "red"
            break

    if risk_level == "منخفضة":
        for kw in risk_keywords_medium:
            if kw in excerpt:
                risk_level = "متوسطة ⚡"
                risk_color = "orange"
                break

    # صياغة التوصية التحليلية
    recommendation = (
        f"يتعلق المقطع بـ ({query}). "
        f"مستوى الحساسية القانونية/التشغيلية: {risk_level}. "
        "يُنصح بالتحقق من المدد الزمنية المذكورة والتوافق بين الطرفين قبل الاعتماد النهائي."
    )

    return {
        "risk_level": risk_level,
        "recommendation": recommendation
    }


@app.post("/audit_clause")
async def audit_clause(request: AuditRequest):
    try:
        query_words = request.query.strip().split()
        matches = []

        for item in document_store:
            score = sum(1 for word in query_words if word in item["text"])
            if score > 0:
                analysis = analyze_risk_and_summary(request.query, item["text"])
                matches.append({
                    "excerpt": item["text"],
                    "page": item["page"],
                    "similarity_score": round(min(score / max(len(query_words), 1), 1.0), 2),
                    "risk_level": analysis["risk_level"],
                    "recommendation": analysis["recommendation"]
                })

        matches.sort(key=lambda x: x["similarity_score"], reverse=True)
        top_results = matches[:request.num_results]

        return {
            "query": request.query,
            "evidence": top_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))