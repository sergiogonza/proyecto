# ======================================================
# MGA IA WEB – SISTEMA COMPLETO (ZIP TEMPORAL)
# ======================================================
import os, json, re, io, zipfile
import pandas as pd
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from docx import Document

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ======================================================
# 🔐 CONFIGURACIÓN
# ======================================================
MODEL = "gpt-4.1"
TEMPERATURE = 0.2

BASE = "data"
PDF_MGA = f"{BASE}/pdf_mga_ejemplos"
DOC_BASE = f"{BASE}/documento_tecnico_base"
PDD = f"{BASE}/plan_desarrollo"

llm = ChatOpenAI(
    model=MODEL,
    temperature=TEMPERATURE,
)

# ======================================================
# 📚 CARGA DEL CORPUS (RAG)
# ======================================================
def cargar_corpus():
    documentos = []
    for carpeta in [PDF_MGA, DOC_BASE, PDD]:
        if not os.path.exists(carpeta):
            continue
        for archivo in os.listdir(carpeta):
            if archivo.endswith(".pdf"):
                documentos.extend(
                    PyPDFLoader(os.path.join(carpeta, archivo)).load()
                )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200
    )

    chunks = splitter.split_documents(documentos)
    return FAISS.from_documents(chunks, OpenAIEmbeddings())

db = cargar_corpus()

# ======================================================
# 🧠 IA – FORMULADOR MGA (ROBUSTO)
# ======================================================
def extraer_json_seguro(texto: str) -> dict:
    """
    Extrae el primer JSON válido aunque el modelo
    agregue texto antes o después.
    """
    match = re.search(r"\{[\s\S]*\}", texto)
    if not match:
        raise ValueError("No se encontró JSON en la respuesta")
    return json.loads(match.group())

def consultar_mga(descripcion: str) -> dict:
    contexto = db.similarity_search(descripcion, k=12)
    contexto_txt = "\n\n".join(c.page_content for c in contexto)

    prompt = f"""
Eres un FORMULADOR EXPERTO en Metodología General Ajustada (MGA) – Colombia.

USA EXCLUSIVAMENTE:
- Proyectos MGA en PDF
- Documento Técnico Base
- Plan de Desarrollo Departamental Cauca 2024–2027

REQUISITOS OBLIGATORIOS:
- Presupuesto ALTO y realista (incluye personal, capacitadores, operación)
- Costos en COP
- Lenguaje institucional MGA
- Estructura MGA completa
- NO inventes normas
- NO expliques nada
- NO uses markdown
- NO agregues texto fuera del JSON

RESPONDE ÚNICAMENTE CON JSON VÁLIDO:

{{
  "documento_tecnico": "texto completo",
  "cadena_valor": [
    {{"Actividad": "", "Producto": "", "Costo_COP": ""}}
  ],
  "concepto_sectorial": [
    {{"Sector": "", "Alineacion_PND": ""}}
  ],
  "mga_txt": "formulación MGA completa en texto plano"
}}

CONTEXTO:
{contexto_txt}

DESCRIPCIÓN DEL PROYECTO:
{descripcion}
"""

    respuesta = llm.invoke(prompt).content
    return extraer_json_seguro(respuesta)

# ======================================================
# 📄 GENERADORES EN MEMORIA
# ======================================================
def generar_docx(texto: str) -> bytes:
    doc = Document()
    doc.add_heading("DOCUMENTO TÉCNICO MGA", 0)
    for bloque in texto.split("\n\n"):
        doc.add_paragraph(bloque)
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.read()

def generar_excel(data: list) -> bytes:
    df = pd.DataFrame(data)
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer.read()

def generar_txt(texto: str) -> bytes:
    return texto.encode("utf-8")

# ======================================================
# 📦 ZIP TEMPORAL
# ======================================================
def generar_zip(data: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr("Documento_Tecnico_MGA.docx", generar_docx(data["documento_tecnico"]))
        zipf.writestr("CADENA_VALOR.xlsx", generar_excel(data["cadena_valor"]))
        zipf.writestr("CONCEPTO_SECTORIAL.xlsx", generar_excel(data["concepto_sectorial"]))
        zipf.writestr("Proyecto_MGA.txt", generar_txt(data["mga_txt"]))
    buffer.seek(0)
    return buffer.read()

# ======================================================
# 🌐 WEB APP
# ======================================================
app = FastAPI(title="MGA IA Web", version="1.0")

@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html>
<head>
  <title>MGA IA</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gradient-to-br from-indigo-50 to-blue-100 min-h-screen flex items-center justify-center">
<div class="bg-white p-10 rounded-2xl shadow-2xl w-2/3">
<h1 class="text-3xl font-bold mb-3">Generador de Proyectos MGA con IA</h1>
<p class="text-gray-600 mb-6">
Proyecto ejemplo: Textil para madres cabeza de hogar – Cauca
</p>
<form method="post" action="/generar">
<textarea name="descripcion" class="w-full h-48 p-4 border rounded-xl"
placeholder="Describe el proyecto MGA..."></textarea>
<button class="mt-6 bg-indigo-600 text-white px-8 py-3 rounded-xl hover:bg-indigo-700">
Generar y Descargar ZIP
</button>
</form>
</div>
</body>
</html>
"""

@app.post("/generar")
def generar(descripcion: str = Form(...)):
    data = consultar_mga(descripcion)
    zip_bytes = generar_zip(data)
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=Proyecto_MGA_Completo.zip"
        }
    )
