# app/services/recommendation_service.py (NUEVO)

from sqlalchemy.orm import Session
from app.repositories import RecommendationRepository
from app.schemas import RecommendationResponse
from app.core import logger

def get_recommendations_by_user_service(db: Session, user_id: int) -> list[RecommendationResponse]:
    """
    Obtiene todas las recomendaciones para un usuario específico.
    """
    rec_repo = RecommendationRepository(db)
    recommendations = rec_repo.get_recommendations_by_user(user_id)
    logger.info(f"Se obtuvieron {len(recommendations)} recomendaciones para el usuario {user_id}")
    return [RecommendationResponse.model_validate(rec) for rec in recommendations]

# La lógica para CREAR recomendaciones (ej. con IA) la añadiremos
# cuando tengamos los datos de consumo históricos en Redis.