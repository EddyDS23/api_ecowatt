# app/services/recommendation_service.py 

import google.generativeai as genai
from sqlalchemy.orm import Session
from app.repositories import RecommendationRepository
from app.schemas import RecommendationResponse
from app.core import logger, settings

def get_recommendations_by_user_service(db: Session, user_id: int) -> list[RecommendationResponse]:
    rec_repo = RecommendationRepository(db)
    recommendations = rec_repo.get_recommendations_by_user(user_id)
    logger.info(f"Se obtuvieron {len(recommendations)} recomendaciones para el usuario {user_id}")
    return [RecommendationResponse.model_validate(rec) for rec in recommendations]

def generate_recommendation_with_gemini(db: Session, user_id: int, alert_type: str, device_name: str, value: str):
    """
    Genera una recomendación personalizada usando Google Gemini AI.
    Las respuestas son concisas (máximo 3 oraciones) y accionables.
    """
    try:
        genai.configure(api_key=settings.GEMINIS_API_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')

        # Crear el prompt según el tipo de alerta
        prompt = _create_prompt_for_gemini(alert_type, device_name, value)
        if not prompt:
            logger.warning(f"No se pudo crear un prompt para el tipo de alerta: {alert_type}")
            return

        logger.info("Enviando prompt a la API de Gemini...")
        response = model.generate_content(prompt)
        
        recommendation_text = response.text.strip()
        if not recommendation_text:
             logger.warning(f"Gemini devolvió una respuesta vacía para alerta tipo {alert_type}.")
             return

        logger.info(f"Respuesta de Gemini recibida: '{recommendation_text[:100]}...'")

        # Guardar recomendación en BD
        rec_repo = RecommendationRepository(db)
        rec_repo.create_recommendation(user_id=user_id, text=recommendation_text)

    except Exception as e:
        logger.error(f"Error al generar recomendación con Gemini: {e}")


def _create_prompt_for_gemini(alert_type: str, device_name: str, value: str) -> str | None:
    """
    Crea prompts optimizados para respuestas cortas, directas y accionables.
    """
    if alert_type == "VAMPIRE_CONSUMPTION":
        return (
            f"Detectamos consumo vampiro de {value} en el circuito '{device_name}' durante la noche. "
            f"Da 3 consejos CONCRETOS y BREVES (máximo 2 líneas cada uno) para identificar qué aparato está causándolo. "
            f"Formato: Usa números (1., 2., 3.) y sé MUY específico con ejemplos de aparatos comunes en ese circuito. "
            f"Máximo 60 palabras en total. Sin saludos ni despedidas."
        )
    
    elif alert_type == "HIGH_CONSUMPTION_PEAK":
        return (
            f"Detectamos un pico de {value} en '{device_name}' que duró varios minutos. "
            f"Da 3 posibles causas ESPECÍFICAS (máximo 2 líneas cada una) de qué aparato pudo causar esto en ese circuito. "
            f"Formato: Usa números (1., 2., 3.) y menciona aparatos reales que consumen esa potencia. "
            f"Máximo 60 palabras en total. Sin saludos ni despedidas."
        )
    
    return None