# ======================================================
# MGA IA WEB – SISTEMA COMPLETO (FORMULADOR SERIO)
# Fundación Almagua
# ======================================================

import os, json, re, io, zipfile
import pandas as pd

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from docx import Document

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter


# ======================================================
# 🌐 APP
# ======================================================
app = FastAPI(title="MGA IA – Fundación Almagua", version="1.0")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")


# ======================================================
# 🔐 CONFIGURACIÓN
# ======================================================
MODEL = "gpt-4.1"  # ⚡ usar estándar, no long-context
TEMPERATURE = 0.2
BASE = "data"

PDF_MGA = f"{BASE}/pdf_mga_ejemplos"
DOC_BASE = f"{BASE}/documento_tecnico_base"
PDD = f"{BASE}/plan_desarrollo"

FORMATOS = f"{BASE}/formatos"
CADENA_CSV = f"{FORMATOS}/cadena.csv"
CONCEPTO_CSV = f"{FORMATOS}/concepto.csv"

PLANES = f"{BASE}/planes_indicativos"
GESTION_SOCIAL_CSV = f"{PLANES}/gestion_social.csv"
MUJER_CSV = f"{PLANES}/mujer.csv"

llm = ChatOpenAI(model=MODEL, temperature=TEMPERATURE)


# ======================================================
# 📚 CORPUS RAG (PDFs)
# ======================================================
def cargar_corpus():
    documentos = []

    for carpeta in [PDF_MGA, DOC_BASE, PDD]:
        if not os.path.exists(carpeta):
            continue
        for archivo in os.listdir(carpeta):
            if archivo.lower().endswith(".pdf"):
                documentos.extend(PyPDFLoader(os.path.join(carpeta, archivo)).load())

    # ⚡ Reducir tamaño de chunks para menos tokens
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
    chunks = splitter.split_documents(documentos)

    return FAISS.from_documents(chunks, OpenAIEmbeddings())


db = cargar_corpus()


# ======================================================
# 📑 FORMATOS MGA (CSV)
# ======================================================
def cargar_formatos_mga():
    bloques = []

    if os.path.exists(CADENA_CSV):
        df = pd.read_csv(CADENA_CSV).head(20)  # ⚡ limitar filas
        bloques.append("FORMATO CADENA DE VALOR MGA:\n" + df.to_csv(index=False))

    if os.path.exists(CONCEPTO_CSV):
        df = pd.read_csv(CONCEPTO_CSV).head(20)
        bloques.append("\nFORMATO CONCEPTO SECTORIAL MGA:\n" + df.to_csv(index=False))

    return "\n".join(bloques)


# ======================================================
# 📊 PLANES INDICATIVOS (CSV)
# ======================================================
def cargar_planes_indicativos_csv():
    bloques = []

    if os.path.exists(GESTION_SOCIAL_CSV):
        df = pd.read_csv(GESTION_SOCIAL_CSV).head(20)
        bloques.append("PLAN INDICATIVO 2024–2027 – GESTIÓN SOCIAL:\n" + df.to_csv(index=False))

    if os.path.exists(MUJER_CSV):
        df = pd.read_csv(MUJER_CSV).head(20)
        bloques.append("\nPLAN INDICATIVO 2024–2027 – MUJER:\n" + df.to_csv(index=False))

    return "\n".join(bloques)


# ======================================================
# 🧠 IA MGA
# ======================================================
def extraer_json_seguro(texto: str) -> dict:
    match = re.search(r"\{[\s\S]*\}", texto)
    if not match:
        raise ValueError("La IA no devolvió JSON válido")
    return json.loads(match.group())


def consultar_mga(descripcion: str) -> dict:
    # ⚡ reducir k para menos tokens
    contexto = db.similarity_search(descripcion, k=5)
    contexto_txt = "\n\n".join(c.page_content for c in contexto)

    # ⚡ limitar longitud
    if len(contexto_txt) > 150_000:
        contexto_txt = contexto_txt[-150_000:]

    prompt = f"""
Eres un FORMULADOR EXPERTO MGA – Colombia.

REGLAS ABSOLUTAS:
- Usa únicamente información suministrada
- No inventes metas, productos o indicadores
- Alinea el proyecto a los Planes Indicativos 2024–2027
- Usa SOLO metas existentes en los CSV oficiales
- Respeta exactamente los formatos MGA
- No expliques nada
- Responde SOLO JSON válido

FORMATO DE RESPUESTA:
{{
  "documento_tecnico":"",
  "cadena_valor":[{{}}],
  "concepto_sectorial":[{{}}],
  "mga_txt":""
}}

FORMATOS MGA OFICIALES:
{cargar_formatos_mga()}

PLANES INDICATIVOS OFICIALES (CSV):
{cargar_planes_indicativos_csv()}

DOCUMENTOS DE REFERENCIA (RAG):
{contexto_txt}

DESCRIPCIÓN DEL PROYECTO:
{descripcion}
"""
    return extraer_json_seguro(llm.invoke(prompt).content)


# ======================================================
# 📄 GENERADORES DE ARCHIVOS
# ======================================================
def generar_docx(texto: str):
    doc = Document()
    doc.add_heading("DOCUMENTO TÉCNICO MGA", 0)
    for p in texto.split("\n\n"):
        doc.add_paragraph(p)
    b = io.BytesIO()
    doc.save(b)
    b.seek(0)
    return b.read()


def generar_excel(data):
    df = pd.DataFrame(data)
    b = io.BytesIO()
    df.to_excel(b, index=False)
    b.seek(0)
    return b.read()


# ======================================================
# 📦 ZIP FINAL
# ======================================================
def generar_zip(data):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Documento_Tecnico_MGA.docx", generar_docx(data["documento_tecnico"]))
        z.writestr("CADENA_VALOR.xlsx", generar_excel(data["cadena_valor"]))
        z.writestr("CONCEPTO_SECTORIAL.xlsx", generar_excel(data["concepto_sectorial"]))
        z.writestr("Proyecto_MGA.txt", data["mga_txt"])
    b.seek(0)
    return b.read()


# ======================================================
# 🌐 WEB
# ======================================================
@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>MGA IA – Fundación Almagua</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js"></script>
<style>
:root{
--bg:#1f2a2e;
--deep:#141c1f;
--gold:#d4af37;
--gold2:#f6e27a;
}
*{box-sizing:border-box}
body{
margin:0;
background:radial-gradient(circle,var(--bg),var(--deep));
color:white;
font-family:system-ui;
}
header{
position:fixed;
top:0;
width:100%;
padding:16px;
text-align:center;
background:rgba(20,28,31,.85);
backdrop-filter:blur(8px);
z-index:1000;
}
.logo{max-width:160px}
.section{
min-height:100vh;
display:flex;
align-items:center;
justify-content:center;
text-align:center;
padding-top:140px;
position:relative;
}
.main-text{
font-size:clamp(2.6rem,6vw,3.8rem);
font-weight:800;
background:linear-gradient(45deg,var(--gold2),var(--gold));
-webkit-background-clip:text;
-webkit-text-fill-color:transparent;
transition:.3s;
}
.reveal{
position:absolute;
inset:0;
display:flex;
align-items:center;
justify-content:center;
font-size:clamp(2.6rem,6vw,3.6rem);
font-weight:800;
color:#141c1f;
background:linear-gradient(180deg,var(--gold2),#8fb7c8);
mask-image:radial-gradient(circle at var(--x,50%) var(--y,50%),black var(--r,0),transparent 0);
-webkit-mask-image:radial-gradient(circle at var(--x,50%) var(--y,50%),black var(--r,0),transparent 0);
pointer-events:none;
}
.cta{
position:fixed;
bottom:30px;
right:30px;
padding:16px 28px;
border-radius:40px;
border:none;
background:linear-gradient(45deg,var(--gold2),var(--gold));
font-weight:700;
cursor:pointer;
}
.overlay{
position:fixed;
inset:0;
display:none;
align-items:center;
justify-content:center;
background:rgba(0,0,0,.65);
backdrop-filter:blur(8px);
z-index:2000;
}
.popup{
background:white;
color:#1f2a2e;
padding:32px;
border-radius:22px;
width:92%;
max-width:520px;
display:grid;
grid-template-rows:auto auto 1fr auto;
gap:18px;
}
.popup-header{
display:flex;
justify-content:space-between;
align-items:center;
}
.popup-header h3{margin:0}
.popup-header button{
background:none;
border:none;
font-size:1.4rem;
cursor:pointer;
opacity:.6;
}
.popup p{margin:0;font-size:.95rem;opacity:.85}
.popup form{
display:grid;
gap:16px;
}
textarea{
width:100%;
min-height:140px;
padding:16px;
border-radius:14px;
border:1px solid #ccc;
resize:none;
font-family:system-ui;
}
textarea:focus{
outline:none;
border-color:var(--gold);
}
button.submit{
padding:14px;
border-radius:30px;
border:none;
background:linear-gradient(45deg,var(--gold2),var(--gold));
font-weight:700;
cursor:pointer;
}
</style>
</head>
<body>
<header>
<img src="/assets/logo.png" class="logo" alt="Fundación Almagua">
</header>
<section class="section" id="hero">
<div class="main-text">Las comunidades tienen ideas.<br>La IA las convierte en MGA.</div>
<div class="reveal">IA territorial para proyectos reales.</div>
</section>
<button class="cta" id="openBtn">Generar Proyecto MGA</button>
<div class="overlay" id="overlay">
<div class="popup" id="popup">
<div class="popup-header">
<h3>Generador MGA</h3>
<button id="closeBtn">✕</button>
</div>
<p>Describe la idea del proyecto. La IA estructurará el MGA completo.</p>
<form method="post" action="/generar">
<textarea name="descripcion" required></textarea>
<button class="submit" type="submit">Generar ZIP MGA</button>
</form>
</div>
</div>
<script>
const hero = document.getElementById("hero");
const reveal = document.querySelector(".reveal");
const text = document.querySelector(".main-text");
hero.addEventListener("mousemove", e => {
  const b = hero.getBoundingClientRect();
  gsap.to(reveal,{ "--x": e.clientX - b.left + "px", "--y": e.clientY - b.top + "px", "--r": "220px", duration:.25 });
  text.style.opacity = .15;
});
hero.addEventListener("mouseleave", () => {
  gsap.to(reveal,{ "--r":"0px", duration:.35 });
  text.style.opacity = 1;
});
const overlay = document.getElementById("overlay");
const popup = document.getElementById("popup");
const openBtn = document.getElementById("openBtn");
const closeBtn = document.getElementById("closeBtn");
openBtn.addEventListener("click", () => {
  overlay.style.display = "flex";
  gsap.fromTo(popup,{scale:.9, opacity:0},{scale:1, opacity:1, duration:.35, ease:"power3.out"});
});
closeBtn.addEventListener("click", () => {
  gsap.to(popup,{scale:.9, opacity:0, duration:.25, onComplete:()=> overlay.style.display="none"});
});
// ⚡ cerrar al click afuera
overlay.addEventListener("click", e => { if(e.target === overlay) closeBtn.click(); });
</script>
</body>
</html>
"""


# ======================================================
# 🚀 GENERAR MGA
# ======================================================
@app.post("/generar")
def generar(descripcion: str = Form(...)):
    data = consultar_mga(descripcion)
    zip_bytes = generar_zip(data)
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=Proyecto_MGA_Completo.zip"}
    )
