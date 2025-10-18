
from firebase_admin import messaging
from app.core import logger
from firebase_admin.exceptions import FirebaseError

def send_push_notification(token:str, title:str, body:str, data:dict = None):
    """
    Envía una notificación push a un token FCM específico.

    Args:
        token: El token FCM del dispositivo destino.
        title: El título de la notificación.
        body: El cuerpo del mensaje de la notificación.
        data: Un diccionario opcional con datos adicionales (clave-valor strings).

    Returns:
        True si el envío fue exitoso, False en caso contrario.
    """

    if not token:
        logger.warning("Intento de enviar una notificacion sin Token FCM")
        return False
    
    if data:
        data = {k: str(v) for k, v in data.items()}

    
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        token=token,
        data=data
    )

    try:
        response = messaging.send(message)
        logger.info(f"Notificación push enviada a token {token[:10]}... ID: {response}")
        return True
    except FirebaseError as e:
        logger.error(f"Error de Firebase al enviar notificación a token {token[:10]}...: {e}")
        return False
    except Exception as e:
        logger.error(f"Error inesperado al enviar notificación push a token {token[:10]}...: {e}")
        return False
