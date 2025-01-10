from fastapi import HTTPException, APIRouter
import psycopg2
from contextlib import contextmanager
import os

from models import *

router = APIRouter()

DB_PARAMS = {
    "host": os.environ['POSTGRES_HOST'],
    "port": os.environ['POSTGRES_PORT'],
    "dbname": os.environ['POSTGRES_DB'],
    "user": os.environ['POSTGRES_USER'],
    "password": os.environ['POSTGRES_PASSWORD']
}

@contextmanager
def get_db_connection():
    conn = psycopg2.connect(**DB_PARAMS)
    try:
        yield conn
    finally:
        conn.close()

@router.post("/university/")
def insert_university(university: University):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO university (uni_id, university_name, city, state)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (university.uni_id, university.university_name, university.city, university.state)
                )
                conn.commit()
                return {
                    "message": "University Added Successfully"
                }
            except psycopg2.Error as e:
                conn.rollback()
                raise HTTPException(status_code=400, detail=str(e))
            
@router.get("/universities/")
def get_universities():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM university")
            universities = cur.fetchall()
            return [
                {
                    "uni_id": univ[0],
                    "university_name": univ[1],
                    "city": univ[2],
                    "state": univ[3]
                }
                for univ in universities
            ]

@router.get("/universities/{uni_id}")
def get_university(uni_id: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM university WHERE uni_id = %s",
                (uni_id,)
            )
            univ = cur.fetchone()
            if univ is None:
                raise HTTPException(status_code=404, detail="University not found")
            return {
                "uni_id": univ[0],
                "university_name": univ[1],
                "city": univ[2],
                "state": univ[3]
            }
        
@router.delete("/universities/{uni_id}")
def delete_university(uni_id: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "DELETE FROM university WHERE uni_id = %s",
                    (uni_id,)
                )
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="University not found")
                conn.commit()
                return {"message": "University deleted successfully"}
            except psycopg2.Error as e:
                conn.rollback()
                raise HTTPException(status_code=400, detail=str(e))
            
@router.post("/fests/")
def create_fest(fest: Fest):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO fest (fest_id, fest_name, year, head_teamID, uni_id)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (fest.fest_id, fest.fest_name, fest.year, fest.head_teamID, fest.uni_id)
                )
                conn.commit()
                return {"message": "Fest created successfully"}
            except psycopg2.Error as e:
                conn.rollback()
                raise HTTPException(status_code=400, detail=str(e))

@router.get("/fests/{uni_id}")
def get_university_fests(uni_id: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM fest WHERE uni_id = %s", (uni_id,))
            fests = cur.fetchall()
            return [
                {
                    "fest_id": fest[0],
                    "fest_name": fest[1],
                    "year": fest[2],
                    "head_teamID": fest[3],
                    "uni_id": fest[4]
                }
                for fest in fests
            ]

@router.post("/teams/")
def create_team(team: Team):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO team (team_id, team_name, team_type, fest_id, uni_id)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (team.team_id, team.team_name, team.team_type, team.fest_id, team.uni_id)
                )
                conn.commit()
                return {"message": "Team created successfully"}
            except psycopg2.Error as e:
                conn.rollback()
                raise HTTPException(status_code=400, detail=str(e))

@router.post("/members/")
def create_member(member: Member):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO member (mem_id, mem_name, DOB, super_memID, team_id, uni_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (member.mem_id, member.mem_name, member.DOB, 
                     member.super_memID, member.team_id, member.uni_id)
                )
                conn.commit()
                return {"message": "Member created successfully"}
            except psycopg2.Error as e:
                conn.rollback()
                raise HTTPException(status_code=400, detail=str(e))

@router.post("/events/")
def create_event(event: Event):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO event (event_id, event_name, building, floor, 
                                     room_no, price, team_id, uni_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (event.event_id, event.event_name, event.building, 
                     event.floor, event.room_no, event.price, event.team_id, event.uni_id)
                )
                conn.commit()
                return {"message": "Event created successfully"}
            except psycopg2.Error as e:
                conn.rollback()
                raise HTTPException(status_code=400, detail=str(e))

@router.post("/event-conductions/")
def create_event_conduction(conduction: EventConduction):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO event_conduction (event_id, date_of_conduction, uni_id)
                    VALUES (%s, %s, %s)
                    """,
                    (conduction.event_id, conduction.date_of_conduction, conduction.uni_id)
                )
                conn.commit()
                return {"message": "Event conduction created successfully"}
            except psycopg2.Error as e:
                conn.rollback()
                raise HTTPException(status_code=400, detail=str(e))

@router.post("/participants/")
def create_participant(participant: Participant):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO participant (SRN, name, department, semester, gender, uni_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (participant.SRN, participant.name, participant.department,
                     participant.semester, participant.gender, participant.uni_id)
                )
                conn.commit()
                return {"message": "Participant created successfully"}
            except psycopg2.Error as e:
                conn.rollback()
                raise HTTPException(status_code=400, detail=str(e))

@router.post("/registrations/")
def create_registration(registration: Registration):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO registration (event_id, SRN, registration_id, uni_id)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (registration.event_id, registration.SRN, 
                     registration.registration_id, registration.uni_id)
                )
                conn.commit()
                return {"message": "Registration created successfully"}
            except psycopg2.Error as e:
                conn.rollback()
                raise HTTPException(status_code=400, detail=str(e))

@router.get("/events/{uni_id}/team/{team_id}")
def get_team_events(uni_id: str, team_id: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM event 
                WHERE uni_id = %s AND team_id = %s
                """, 
                (uni_id, team_id)
            )
            events = cur.fetchall()
            return [
                {
                    "event_id": event[0],
                    "event_name": event[1],
                    "building": event[2],
                    "floor": event[3],
                    "room_no": event[4],
                    "price": float(event[5]),
                    "team_id": event[6],
                    "uni_id": event[7]
                }
                for event in events
            ]

@router.get("/participants/{uni_id}/event/{event_id}")
def get_event_participants(uni_id: str, event_id: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.* FROM participant p
                JOIN registration r ON p.uni_id = r.uni_id AND p.SRN = r.SRN
                WHERE r.uni_id = %s AND r.event_id = %s
                """,
                (uni_id, event_id)
            )
            participants = cur.fetchall()
            return [
                {
                    "SRN": p[0],
                    "name": p[1],
                    "department": p[2],
                    "semester": p[3],
                    "gender": p[4],
                    "uni_id": p[5]
                }
                for p in participants
            ]