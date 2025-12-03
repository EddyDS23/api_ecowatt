"""
Script para probar notificaciones FCM.
Uso: python test_notifications.py
"""

import sys
import os

# Añadir el directorio raíz al path para importar módulos de la app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.settings import settings
from app.core import logger
from app.services.notification_service import send_push_notification
import firebase_admin
from firebase_admin import credentials


def initialize_firebase():
    """Inicializa Firebase Admin SDK si no está inicializado"""
    if not firebase_admin._apps:
        try:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred)
            logger.info("✅ Firebase inicializado correctamente")
            return True
        except Exception as e:
            logger.error(f"❌ Error inicializando Firebase: {e}")
            return False
    else:
        logger.info("✅ Firebase ya estaba inicializado")
        return True


def test_single_notification():
    """Prueba enviar una notificación a un token específico"""
    print("\n" + "="*70)
    print("🔔 PRUEBA DE NOTIFICACIÓN INDIVIDUAL")
    print("="*70)
    
    # Solicitar token al usuario
    token = input("\n📱 Ingresa el token FCM del dispositivo: ").strip()
    
    if not token or len(token) < 100:
        print("❌ Token inválido (debe tener al menos 100 caracteres)")
        return False
    
    # Datos de la notificación de prueba
    title = "🧪 Prueba EcoWatt"
    body = "Esta es una notificación de prueba desde el backend"
    data = {
        "type": "test",
        "timestamp": str(int(os.times().elapsed * 1000))
    }
    
    print(f"\n📤 Enviando notificación...")
    print(f"   Título: {title}")
    print(f"   Cuerpo: {body}")
    print(f"   Token: {token[:20]}...{token[-10:]}")
    
    # Enviar notificación
    success = send_push_notification(
        token=token,
        title=title,
        body=body,
        data=data
    )
    
    if success:
        print("\n✅ ¡Notificación enviada exitosamente!")
        print("   Revisa tu dispositivo móvil.")
        return True
    else:
        print("\n❌ Error al enviar la notificación")
        print("   Revisa los logs para más detalles.")
        return False


def test_user_notifications():
    """Prueba enviar notificaciones a todos los tokens de un usuario"""
    print("\n" + "="*70)
    print("👤 PRUEBA DE NOTIFICACIONES POR USUARIO")
    print("="*70)
    
    from app.database import SessionLocal
    from app.repositories import FCMTokenRepository
    
    # Solicitar user_id
    try:
        user_id = int(input("\n🆔 Ingresa el ID del usuario: ").strip())
    except ValueError:
        print("❌ ID de usuario inválido")
        return False
    
    # Obtener tokens del usuario
    db = SessionLocal()
    try:
        fcm_repo = FCMTokenRepository(db)
        tokens = fcm_repo.get_active_tokens(user_id)
        
        if not tokens:
            print(f"\n⚠️  El usuario {user_id} no tiene tokens FCM registrados")
            return False
        
        print(f"\n📱 Tokens encontrados: {len(tokens)}")
        for i, token in enumerate(tokens, 1):
            device_info = f"{token.fcm_device_name or 'Sin nombre'} ({token.fcm_platform or 'desconocido'})"
            print(f"   {i}. {device_info}")
            print(f"      Token: {token.fcm_token[:20]}...{token.fcm_token[-10:]}")
            print(f"      Último uso: {token.fcm_last_used}")
        
        # Confirmar envío
        confirm = input(f"\n¿Enviar notificación de prueba a estos {len(tokens)} dispositivos? (s/n): ").strip().lower()
        if confirm != 's':
            print("❌ Operación cancelada")
            return False
        
        # Enviar a todos los tokens
        title = "🧪 Prueba EcoWatt"
        body = f"Notificación de prueba para el usuario {user_id}"
        data = {
            "type": "test",
            "user_id": str(user_id),
            "timestamp": str(int(os.times().elapsed * 1000))
        }
        
        print(f"\n📤 Enviando notificaciones...")
        
        success_count = 0
        for i, token in enumerate(tokens, 1):
            print(f"\n   Dispositivo {i}/{len(tokens)}...")
            success = send_push_notification(
                token=token.fcm_token,
                title=title,
                body=body,
                data=data
            )
            if success:
                success_count += 1
                print(f"      ✅ Enviada")
            else:
                print(f"      ❌ Error")
        
        print(f"\n📊 Resultado: {success_count}/{len(tokens)} notificaciones enviadas exitosamente")
        return success_count > 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False
    finally:
        db.close()


def test_firebase_connection():
    """Verifica la configuración de Firebase"""
    print("\n" + "="*70)
    print("🔥 VERIFICACIÓN DE FIREBASE")
    print("="*70)
    
    try:
        import json
        
        # Leer archivo de credenciales
        with open(settings.FIREBASE_CREDENTIALS_PATH, 'r') as f:
            creds = json.load(f)
        
        project_id = creds.get('project_id')
        client_email = creds.get('client_email')
        
        print(f"\n✅ Archivo de credenciales encontrado")
        print(f"   📁 Ruta: {settings.FIREBASE_CREDENTIALS_PATH}")
        print(f"   🆔 Project ID: {project_id}")
        print(f"   📧 Client Email: {client_email}")
        
        print(f"\n⚠️  IMPORTANTE:")
        print(f"   Tu app móvil debe usar el proyecto: '{project_id}'")
        print(f"   Verifica en google-services.json (Android) o GoogleService-Info.plist (iOS)")
        
        return True
        
    except FileNotFoundError:
        print(f"\n❌ No se encontró el archivo de credenciales")
        print(f"   Ruta esperada: {settings.FIREBASE_CREDENTIALS_PATH}")
        return False
    except Exception as e:
        print(f"\n❌ Error leyendo credenciales: {e}")
        return False


def main_menu():
    """Menú principal"""
    while True:
        print("\n" + "="*70)
        print("🧪 HERRAMIENTA DE PRUEBA DE NOTIFICACIONES FCM")
        print("="*70)
        print("\nOpciones:")
        print("  1. Verificar configuración de Firebase")
        print("  2. Probar notificación a un token específico")
        print("  3. Probar notificaciones a un usuario (por user_id)")
        print("  4. Salir")
        
        choice = input("\nSelecciona una opción (1-4): ").strip()
        
        if choice == "1":
            test_firebase_connection()
        elif choice == "2":
            if not initialize_firebase():
                print("\n❌ No se pudo inicializar Firebase")
                continue
            test_single_notification()
        elif choice == "3":
            if not initialize_firebase():
                print("\n❌ No se pudo inicializar Firebase")
                continue
            test_user_notifications()
        elif choice == "4":
            print("\n👋 ¡Hasta luego!")
            break
        else:
            print("\n❌ Opción inválida")
        
        input("\nPresiona Enter para continuar...")


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\n👋 Programa interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        logger.exception("Error en script de pruebas")
        sys.exit(1)