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

# --- CONFIGURAÇÃO ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MODELOS


class StudentCreate(BaseModel):
    name: str
    birth_date: str
    email: Optional[str] = None

# UTILITÁRIOS


def calculate_age(birthdate_str):
    try:
        # Tenta converter string YYYY-MM-DD para data
        birth = datetime.strptime(birthdate_str, "%Y-%m-%d")
        today = date.today()
        return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    except:
        return 0


def get_age_group(age):
    if age < 12:
        return "Criança (0-11)"
    if age < 18:
        return "Adolescente (12-17)"
    if age < 60:
        return "Adulto (18-59)"
    return "Sênior (60+)"

# ROTAS


@app.get("/api/config")
def get_school_config():
    if not supabase:
        return {"logo_url": ""}
    try:
        response = supabase.table("school_config").select(
            "value").eq("key", "logo_url").execute()
        if response.data:
            return {"logo_url": response.data[0]['value']}
        return {"logo_url": ""}
    except:
        return {"logo_url": ""}


@app.post("/api/alunos")
def create_student(student: StudentCreate):
    if not supabase:
        raise HTTPException(500, "Erro de conexão DB")
    try:
        # Insere direto na tabela students
        response = supabase.table("students").insert(student.dict()).execute()
        return {"message": "Aluno cadastrado!", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/dashboard")
def get_dashboard_metrics(data_limite: Optional[str] = None):
    #  Verificação de Segurança
    if not supabase:
        print("Erro: Cliente Supabase não inicializado.")
        raise HTTPException(500, "Erro de conexão DB")

    #  Define data limite (hoje ou a escolhida pelo usuário)
    if not data_limite:
        data_limite = datetime.now().strftime("%Y-%m-%d")

    # Formato para comparar com o banco de dados (fim do dia)
    data_formatada = f"{data_limite}T23:59:59"

    try:
        # BUSCA INTELIGENTE
        # Tenta buscar alunos filtrando pela data de criação.
        # Se a coluna 'created_at' não existir ou der erro, ele busca TODOS os alunos como fallback.

        try:
            # Tenta filtrar
            response = supabase.table("students")\
                .select("*")\
                .lte("created_at", data_formatada)\
                .execute()
            students_data = response.data
        except Exception as filter_error:
            print(
                f"Aviso: Erro ao filtrar por data ({filter_error}). Buscando todos os alunos.")
            # Fallback: Busca tudo sem filtro
            response = supabase.table("students").select("*").execute()
            students_data = response.data

        # 4. Processamento dos Dados
        age_groups = {
            "Criança (0-11)": 0,
            "Adolescente (12-17)": 0,
            "Adulto (18-59)": 0,
            "Sênior (60+)": 0
        }

        if students_data:
            for student in students_data:
                # Pega a data de nascimento com validação
                birth_date = student.get('birth_date')

                if birth_date:
                    age = calculate_age(birth_date)
                    group = get_age_group(age)

                    # Só conta se o grupo existir na nossa lista
                    if group in age_groups:
                        age_groups[group] += 1

        # 5. Retorno
        return {
            "faixa_etaria": age_groups,
            "data_referencia": data_limite,
            "total_alunos": len(students_data) if students_data else 0
        }

    except Exception as e:
        print(f"ERRO CRÍTICO DASHBOARD: {str(e)}")
        return {
            "faixa_etaria": {},
            "data_referencia": data_limite,
            "aviso": "Erro ao processar dados."
        }