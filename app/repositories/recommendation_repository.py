from sqlalchemy.orm import Session
from app.models import Recommendation
from app.core import logger

class RecommendationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_recommendation(self, user_id: int, text: str) -> Recommendation | None:
        try:
            new_recommendation = Recommendation(rec_user_id=user_id, rec_text=text)
            self.db.add(new_recommendation)
            self.db.commit()
            self.db.refresh(new_recommendation)
            logger.info(f"Recomendación creada para el usuario {user_id}")
            return new_recommendation
        except Exception as e:
            logger.error(f"No se pudo crear la recomendación: {e}")
            self.db.rollback()
            return None
    
    def get_recommendations_by_user(self, user_id: int) -> list[Recommendation]:
        return self.db.query(Recommendation).filter(Recommendation.rec_user_id == user_id).order_by(Recommendation.rec_created_at.desc()).all()