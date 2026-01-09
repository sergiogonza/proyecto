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
MODEL = "gpt-4.1"
TEMPERATURE = 0.2
BASE = "data"

PDF_MGA = f"{BASE}/pdf_mga_ejemplos"
DOC_BASE = f"{BASE}/documento_tecnico_base"
PDD = f"{BASE}/plan_desarrollo"

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
            path = os.path.join(carpeta, archivo)
            if archivo.lower().endswith(".pdf"):
                documentos.extend(PyPDFLoader(path).load())

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
    chunks = splitter.split_documents(documentos)
    return FAISS.from_documents(chunks, OpenAIEmbeddings())


db = cargar_corpus()


# ======================================================
# 🧰 CACHE DE INFORMACIÓN
# ======================================================
def generar_cache_completo():
    cache = {}

    for csv_file in ["gestion_social.csv", "mujer.csv"]:
        path_csv = os.path.join(BASE, csv_file)
        if os.path.exists(path_csv):
            df = pd.read_csv(path_csv)
            cache[csv_file] = df.to_dict(orient="records")

    for carpeta in [PDF_MGA, DOC_BASE, PDD]:
        if not os.path.exists(carpeta):
            continue
        for archivo in os.listdir(carpeta):
            path = os.path.join(carpeta, archivo)
            if archivo.lower().endswith(".pdf"):
                docs = PyPDFLoader(path).load()
                cache[archivo] = [d.page_content for d in docs]

    return cache


cache_proyecto = generar_cache_completo()


# ======================================================
# 🧠 UTILIDAD JSON SEGURA
# ======================================================
def extraer_json_seguro(respuesta: str) -> dict:
    if not respuesta:
        return {}

    texto = respuesta.replace("\n", " ").replace("\r", " ").strip()
    match = re.search(r"\{.*\}", texto, re.DOTALL)

    if not match:
        return {"mga_txt": texto}

    texto_json = match.group()
    texto_json = texto_json.replace("'", '"')
    texto_json = re.sub(r',\s*}', '}', texto_json)
    texto_json = re.sub(r',\s*]', ']', texto_json)

    try:
        return json.loads(texto_json)
    except json.JSONDecodeError:
        return {"mga_txt": texto}


# ======================================================
# 🧠 IA – GENERAR MGA BASE
# ======================================================
def consultar_mga(descripcion: str) -> dict:
    docs = db.similarity_search(descripcion, k=6)
    contexto = "\n\n".join([d.page_content for d in docs])

    prompt = f"""
Eres un FORMULADOR PROFESIONAL MGA – COLOMBIA.

Genera la ESTRUCTURA BASE DEL MGA para un proyecto real,
coherente con el aplicativo MGA Web del DNP.

DESCRIPCIÓN DEL PROYECTO:
{descripcion}

====================
CONTEXTO DOCUMENTAL:
{contexto[:6000]}

====================
RESPONDE EN JSON VÁLIDO:

{{
  "mga_txt": "Texto MGA completo",
  "cadena_valor": [
    {{
      "producto": "",
      "actividad": "",
      "indicador": "",
      "meta": ""
    }}
  ],
  "concepto_sectorial": [
    {{
      "sector": "",
      "justificacion": ""
    }}
  ]
}}
"""

    respuesta = llm.invoke(prompt).content
    data = extraer_json_seguro(respuesta)

    data.setdefault("cadena_valor", [])
    data.setdefault("concepto_sectorial", [])

    return data


# ======================================================
# 🧠 IA – DOCUMENTO TÉCNICO MGA
# ======================================================
def completar_documento_tecnico(mga_data: dict) -> str:
    mga_txt = mga_data.get("mga_txt", "")
    cadena_valor_txt = json.dumps(mga_data.get("cadena_valor", []), ensure_ascii=False, indent=2)
    concepto_sectorial_txt = json.dumps(mga_data.get("concepto_sectorial", []), ensure_ascii=False, indent=2)

    ejemplo_txt = ""
    for k, v in cache_proyecto.items():
        if "documento" in k.lower():
            ejemplo_txt += "\n".join(v[:30]) + "\n"

    pdd_txt = ""
    for k, v in cache_proyecto.items():
        if "plan" in k.lower() or "cauca" in k.lower():
            pdd_txt += "\n".join(v[:40]) + "\n"

    prompt = f"""
Eres un FORMULADOR PROFESIONAL MGA – COLOMBIA.

Redacta el DOCUMENTO TÉCNICO MGA COMPLETO,
listo para radicación.

MGA BASE:
{mga_txt}

CADENA DE VALOR:
{cadena_valor_txt}

CONCEPTO SECTORIAL:
{concepto_sectorial_txt}

DOCUMENTO EJEMPLO:
{ejemplo_txt[:5000]}

PLAN DE DESARROLLO:
{pdd_txt[:5000]}

RESPONDE SOLO CON EL TEXTO COMPLETO.
"""

    return llm.invoke(prompt).content


# ======================================================
# 📄 ARCHIVOS
# ======================================================
def generar_docx(texto):
    doc = Document()
    doc.add_heading("DOCUMENTO TÉCNICO MGA", 0)
    doc.add_paragraph(str(texto))
    b = io.BytesIO()
    doc.save(b)
    b.seek(0)
    return b.read()


def generar_csv(data):
    if not data:
        return b""
    df = pd.DataFrame(data)
    b = io.BytesIO()
    df.to_csv(b, index=False, encoding="utf-8-sig")
    b.seek(0)
    return b.read()


def generar_zip_completo(data):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Documento_Tecnico_MGA.docx", generar_docx(data.get("documento_tecnico", "")))
        z.writestr("Cadena_Valor.csv", generar_csv(data.get("cadena_valor", [])))
        z.writestr("Concepto_Sectorial.csv", generar_csv(data.get("concepto_sectorial", [])))
        z.writestr("MGA.txt", data.get("mga_txt", ""))
    b.seek(0)
    return b.read()


# ======================================================
# 🌐 INTERFAZ
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
# 🚀 ENDPOINT
# ======================================================
@app.post("/generar")
def generar(descripcion: str = Form(...)):
    data_mga = consultar_mga(descripcion)
    data_mga["documento_tecnico"] = completar_documento_tecnico(data_mga)

    zip_bytes = generar_zip_completo(data_mga)

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=Proyecto_MGA_Completo.zip"},
    )
