# app/services/recommendation_service.py 

import google.generativeai as genai
from sqlalchemy.orm import Session
from app.repositories import RecommendationRepository
from app.schemas import RecommendationResponse
from app.core import logger, settings

def get_recommendations_by_user_service(db: Session, user_id: int) -> list[RecommendationResponse]:
    # ... (código existente sin cambios)
    rec_repo = RecommendationRepository(db)
    recommendations = rec_repo.get_recommendations_by_user(user_id)
    logger.info(f"Se obtuvieron {len(recommendations)} recomendaciones para el usuario {user_id}")
    return [RecommendationResponse.model_validate(rec) for rec in recommendations]

def generate_recommendation_with_gemini(db: Session, user_id: int, alert_type: str, device_name: str, value: str):
    # ... (lógica de conexión a Gemini sin cambios)
    try:
        genai.configure(api_key=settings.GEMINIS_API_KEY)
        model = genai.GenerativeModel('gemini-pro')

        # 2. Crear el prompt (la instrucción para la IA)
        prompt = _create_prompt_for_gemini(alert_type, device_name, value) # <-- ESTA LÓGICA CAMBIA
        if not prompt:
            logger.warning(f"No se pudo crear un prompt para el tipo de alerta: {alert_type}")
            return

        logger.info("Enviando prompt a la API de Gemini...")
        response = model.generate_content(prompt)
        
        recommendation_text = response.text.strip()
        logger.info(f"Respuesta de Gemini recibida: '{recommendation_text}'")

        rec_repo = RecommendationRepository(db)
        rec_repo.create_recommendation(user_id=user_id, text=recommendation_text)

    except Exception as e:
        logger.error(f"Error al generar recomendación con Gemini: {e}")

# --- ¡AQUÍ ESTÁ EL CAMBIO CLAVE! ---
def _create_prompt_for_gemini(alert_type: str, device_name: str, value: str) -> str | None:
    """
    Función auxiliar para construir el texto del prompt según el tipo de alerta.
    Ahora está adaptado para circuitos.
    """
    if alert_type == "VAMPIRE_CONSUMPTION":
        return (
            "Actúa como un experto en ahorro de energía para el hogar en México. "
            "Un usuario ha detectado un 'consumo vampiro' de {value} en el circuito eléctrico que ha nombrado '{device_name}'. "
            "Esto significa que uno o varios aparatos en esa área están gastando energía innecesariamente durante la noche. "
            "Genera una recomendación corta (máximo 2 párrafos), amigable y en formato de pasos a seguir para ayudar al usuario a IDENTIFICAR el dispositivo culpable. "
            "Ejemplo de pasos: 1. Revisa aparatos con luces piloto. 2. Desconecta dispositivos que no uses. 3. Usa un multicontacto. "
            "Usa un tono proactivo y de detective. No uses markdown."
        ).format(device_name=device_name, value=value)
    
    return None