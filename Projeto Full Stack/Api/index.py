import os
from datetime import date, datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client

# Esse código tem como ideia principal ser um gerenciador para a gestão da 
# escola Bianca Ramos a ideia é que seja uma interface mais simples para que a escola 
# entenda seus dados e registre seus alunos tendo uma visão geral de faixa etária e público. 

# Config Supabase 
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Inicialização segura
supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Erro ao inicializar Supabase: {e}")

app = FastAPI(
    title="API Escola De Música Bianca Ramos",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos
class StudentCreate(BaseModel):
    name: str
    birth_date: str
    email: Optional[str] = None

class EnrollmentCreate(BaseModel):
    student_id: int
    class_id: int

# Data nacimento
def calculate_age(birthdate_str):
    try:
        birth = datetime.strptime(birthdate_str, "%Y-%m-%d")
        today = date.today()
        return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    except:
        return 0

def get_age_group(age):
    if age < 12: return "Criança (0-11)"
    if age < 18: return "Adolescente (12-17)"
    if age < 60: return "Adulto (18-59)"
    return "Sênior (60+)"

# Rotas

@app.get("/api/config")
def get_school_config():
    if not supabase: return {"logo_url": ""}
    try:
        response = supabase.table("school_config").select("value").eq("key", "logo_url").execute()
        if response.data:
            return {"logo_url": response.data[0]['value']}
        return {"logo_url": ""}
    except:
        return {"logo_url": ""}

@app.post("/api/alunos")
def create_student(student: StudentCreate):
    if not supabase: raise HTTPException(500, "Erro de conexão DB")
    try:
        response = supabase.table("students").insert(student.dict()).execute()
        return {"message": "Aluno cadastrado!", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/matriculas")
def enroll_student(enrollment: EnrollmentCreate):
    if not supabase: raise HTTPException(500, "Erro de conexão DB")
    try:
        response = supabase.table("enrollments").insert(enrollment.dict()).execute()
        return {"message": "Matrícula realizada!", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/dashboard")
def get_dashboard_metrics(data_limite: Optional[str] = None):
    if not supabase: raise HTTPException(500, "Erro de conexão DB")
    
    if not data_limite:
        data_limite = datetime.now().strftime("%Y-%m-%d")
    
    # Formato ISO para comparação no Supabase
    data_formatada = f"{data_limite}T23:59:59"

    try:
        # Busca professores e matrículas
        profs = supabase.table("professors").select("*, classes(id)").execute()
        
        # Filtra matrículas até a data limite usando created_at
        enrollments = supabase.table("enrollments")\
            .select("*, students(*), classes(professor_id)")\
            .lte("created_at", data_formatada)\
            .execute()

        prof_stats = {}
        age_groups = {
            "Criança (0-11)": 0, "Adolescente (12-17)": 0, 
            "Adulto (18-59)": 0, "Sênior (60+)": 0
        }

        # Processamento dos dados
        for entry in enrollments.data:
            # Contagem por professor
            if entry.get('classes'):
                prof_id = entry['classes']['professor_id']
                prof_stats[prof_id] = prof_stats.get(prof_id, 0) + 1

            # Contagem por idade
            if entry.get('students') and entry['students'].get('birth_date'):
                age = calculate_age(entry['students']['birth_date'])
                group = get_age_group(age)
                if group in age_groups:
                    age_groups[group] += 1

        professors_report = []
        for p in profs.data:
            count = prof_stats.get(p['id'], 0)
            professors_report.append({
                "professor": p['name'],
                "instrumento": p['instrument'],
                "total_alunos": count
            })

        return {
            "alunos_por_professor": professors_report,
            "faixa_etaria": age_groups,
            "data_referencia": data_limite
        }
    except Exception as e:
        print(f"Erro Dashboard: {e}")
        raise HTTPException(status_code=400, detail=str(e))