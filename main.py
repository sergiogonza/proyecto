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

FORMATOS = f"{BASE}/formatos"
CADENA_CSV = f"{FORMATOS}/cadena.csv"
CONCEPTO_CSV = f"{FORMATOS}/concepto.csv"


llm = ChatOpenAI(
    model=MODEL,
    temperature=TEMPERATURE
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
            if archivo.lower().endswith(".pdf"):
                documentos.extend(
                    PyPDFLoader(os.path.join(carpeta, archivo)).load()
                )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200
    )

    chunks = splitter.split_documents(documentos)

    return FAISS.from_documents(
        chunks,
        OpenAIEmbeddings()
    )


db = cargar_corpus()


# ======================================================
# 📑 FORMATOS MGA (SOLO CONSULTA)
# ======================================================
def cargar_formatos_mga() -> str:
    bloques = []

    if os.path.exists(CADENA_CSV):
        df = pd.read_csv(CADENA_CSV)
        bloques.append(
            "FORMATO OFICIAL CADENA DE VALOR MGA (EJEMPLO REAL):\n"
            + df.to_csv(index=False)
        )

    if os.path.exists(CONCEPTO_CSV):
        df = pd.read_csv(CONCEPTO_CSV)
        bloques.append(
            "\nFORMATO OFICIAL CONCEPTO SECTORIAL MGA (EJEMPLO REAL):\n"
            + df.to_csv(index=False)
        )

    return "\n".join(bloques)


# ======================================================
# 🧠 IA – FORMULADOR MGA ROBUSTO
# ======================================================
def extraer_json_seguro(texto: str) -> dict:
    match = re.search(r"\{[\s\S]*\}", texto)
    if not match:
        raise ValueError("La IA no devolvió JSON válido")
    return json.loads(match.group())


def consultar_mga(descripcion: str) -> dict:
    contexto = db.similarity_search(descripcion, k=12)
    contexto_txt = "\n\n".join(c.page_content for c in contexto)

    formatos_txt = cargar_formatos_mga()

    prompt = f"""
Eres un FORMULADOR EXPERTO en Metodología General Ajustada (MGA) – Colombia.

REGLAS ABSOLUTAS:
- RESPETA EXACTAMENTE los formatos CSV MGA entregados
- NO inventes columnas
- NO cambies nombres
- NO expliques nada
- NO uses markdown
- NO agregues texto fuera del JSON
- Valores monetarios realistas en COP
- Lenguaje institucional MGA

RESPONDE SOLO CON JSON VÁLIDO:

{{
  "documento_tecnico": "",
  "cadena_valor": [{{}}],
  "concepto_sectorial": [{{}}],
  "mga_txt": ""
}}

FORMATOS MGA OBLIGATORIOS:
{formatos_txt}

DOCUMENTOS DE REFERENCIA:
{contexto_txt}

DESCRIPCIÓN DEL PROYECTO:
{descripcion}
"""

    respuesta = llm.invoke(prompt).content
    return extraer_json_seguro(respuesta)


# ======================================================
# 📄 GENERADORES DE ARCHIVOS (MEMORIA)
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
# 📦 ZIP FINAL
# ======================================================
def generar_zip(data: dict) -> bytes:
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr(
            "Documento_Tecnico_MGA.docx",
            generar_docx(data["documento_tecnico"])
        )
        zipf.writestr(
            "CADENA_VALOR.xlsx",
            generar_excel(data["cadena_valor"])
        )
        zipf.writestr(
            "CONCEPTO_SECTORIAL.xlsx",
            generar_excel(data["concepto_sectorial"])
        )
        zipf.writestr(
            "Proyecto_MGA.txt",
            generar_txt(data["mga_txt"])
        )

    buffer.seek(0)
    return buffer.read()


# ======================================================
# 🌐 WEB
# ======================================================
@app.get("/", response_class=HTMLResponse)
def home():
    return """<!DOCTYPE html>
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

body{
margin:0;
background:radial-gradient(circle,var(--bg),var(--deep));
color:white;
font-family:system-ui,sans-serif;
overflow-x:hidden;
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

.logo{
max-width:160px;
filter:drop-shadow(0 6px 18px rgba(0,0,0,.6));
}

.section{
min-height:100vh;
display:flex;
align-items:center;
justify-content:center;
text-align:center;
position:relative;
padding-top:140px;
}

.main-text{
font-size:clamp(2.6rem,6vw,3.8rem);
font-weight:800;
background:linear-gradient(45deg,var(--gold2),var(--gold));
-webkit-background-clip:text;
-webkit-text-fill-color:transparent;
z-index:2;
transition:.3s;
}

.reveal{
position:absolute;
inset:0;
display:flex;
align-items:center;
justify-content:center;
color:#141c1f;
font-size:clamp(2.6rem,6vw,3.6rem);
font-weight:800;
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
font-weight:700;
cursor:pointer;
background:linear-gradient(45deg,var(--gold2),var(--gold));
color:#141c1f;
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
padding:26px;
border-radius:22px;
width:90%;
max-width:520px;
}

textarea{
width:100%;
height:120px;
border-radius:14px;
padding:14px;
resize:none;
}

button{
width:100%;
margin-top:14px;
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
<div class="main-text">
Las comunidades tienen ideas.<br>
La IA las convierte en proyectos MGA.
</div>

<div class="reveal">
IA territorial que estructura,<br>
respalda y viabiliza proyectos reales.
</div>
</section>

<button class="cta" id="open">Generar Proyecto MGA</button>

<div class="overlay" id="overlay">
<div class="popup">
<h3>Generador MGA con IA</h3>
<p>Describe la idea. Nosotros estructuramos.</p>
<form method="post" action="/generar">
<textarea name="descripcion" required></textarea>
<button type="submit">Generar ZIP MGA</button>
</form>
</div>
</div>

<script>
const s=document.getElementById("hero");
const r=document.querySelector(".reveal");
const t=document.querySelector(".main-text");

s.addEventListener("mousemove",e=>{
const b=s.getBoundingClientRect();
gsap.to(r,{ "--x":e.clientX-b.left+"px","--y":e.clientY-b.top+"px","--r":"220px",duration:.35});
t.style.opacity=.15;
});

s.addEventListener("mouseleave",()=>{
gsap.to(r,{ "--r":"0px",duration:.4});
t.style.opacity=1;
});

document.getElementById("open").onclick=()=>overlay.style.display="flex";
</script>

</body>
</html>"""


# ======================================================
# 🚀 GENERACIÓN
# ======================================================
@app.post("/generar")
def generar(descripcion: str = Form(...)):
    data = consultar_mga(descripcion)
    zip_bytes = generar_zip(data)

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={
            "Content-Disposition":
            "attachment; filename=Proyecto_MGA_Completo.zip"
        }
    )
