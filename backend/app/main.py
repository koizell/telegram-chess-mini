import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from app.config import TELEGRAM_TOKEN
from app.db.client import pb

# ============================================
# CONFIGURACIÓN DE LOGGING
# ============================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ============================================
# COMANDO /start
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Usuario {user.id} ({user.username}) ejecutó /start")

    # Fallback robusto para el nombre
    display_name = user.first_name or user.username or f"Jugador{user.id}"
    if not display_name or display_name.strip() in ("", "...", ".", "-"):
        display_name = f"Jugador{user.id}"

    try:
        pb_user, is_new = pb.get_or_create_user(
            telegram_id=user.id,
            telegram_username=user.username or "",
            display_name=display_name,
        )

        if is_new:
            logger.info(f"✅ Usuario nuevo creado: {user.id}")
            mensaje = (
                f"♟️ ¡Bienvenido a *Telegram Chess Pi*, {display_name}!\n\n"
                "El ajedrez más elegante de Telegram.\n\n"
                "─────────────────────\n"
                "🎁 *Regalo de bienvenida:*\n"
                "   • Skin \"Clásica\" desbloqueada\n"
                "   • 50 puntos de inicio\n"
                "   • ELO inicial: 1200\n\n"
                "Usa /help para ver todos los comandos."
            )
        else:
            logger.info(f"👋 Usuario recurrente: {user.id}")
            elo = pb_user.get("elo", 1200)
            nombre_usuario = pb_user.get("display_name") or display_name
            mensaje = (
                f"♟️ ¡Hola de nuevo, {nombre_usuario}!\n\n"
                f"📊 Tu ELO: *{elo}*\n"
                f"🏆 Victorias: {pb_user.get('wins', 0)}\n"
                f"❌ Derrotas: {pb_user.get('losses', 0)}\n\n"
                "Usa /help para ver todos los comandos."
            )

        await update.message.reply_text(mensaje, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"❌ Error al procesar /start: {e}")
        await update.message.reply_text(
            "⚠️ Hubo un error al guardar tu perfil. Intenta de nuevo."
        )


# ============================================
# COMANDO /help
# ============================================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "♟️ *Comandos disponibles:*\n\n"
        "/start - Mensaje de bienvenida\n"
        "/help - Ver esta ayuda\n"
        "/ping - Probar que el bot responde\n"
        "/perfil - Ver tu perfil\n"
        "/nombre - Cambiar tu nombre (cada 7 días)\n"
        "/debug - Ver tus datos crudos (diagnóstico)\n\n"
        "_Pronto habrá más comandos para jugar._",
        parse_mode="Markdown"
    )


# ============================================
# COMANDO /ping
# ============================================
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 ¡Pong! El bot está funcionando.")


# ============================================
# COMANDO /perfil
# ============================================
async def perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        pb_user = pb.get_user_by_telegram_id(user.id)
        if not pb_user:
            await update.message.reply_text(
                "❌ No tienes perfil todavía. Usa /start primero."
            )
            return

        nombre = pb_user.get("display_name") or user.first_name or f"Jugador{user.id}"
        tema = pb_user.get("theme_id") or "No configurado"
        skin = pb_user.get("skin_id") or "No configurada"

        await update.message.reply_text(
            f"👤 *Perfil de {nombre}*\n\n"
            f"📊 ELO: *{pb_user.get('elo', 1200)}*\n"
            f"🏆 Victorias: {pb_user.get('wins', 0)}\n"
            f"❌ Derrotas: {pb_user.get('losses', 0)}\n"
            f"🤝 Tablas: {pb_user.get('draws', 0)}\n\n"
            f"🎨 Tema: {tema}\n"
            f"♟️ Skin: {skin}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"❌ Error en /perfil: {e}")
        await update.message.reply_text("⚠️ Error al obtener tu perfil.")


# ============================================
# COMANDO /nombre (con límite de tiempo)
# ============================================
async def nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pb_user = pb.get_user_by_telegram_id(user.id)

    if not pb_user:
        await update.message.reply_text("❌ Usa /start primero para crear tu perfil.")
        return

    # Si no escribió un nombre nuevo, mostrar ayuda
    if not context.args:
        await update.message.reply_text(
            "✏️ *Cambiar tu nombre*\n\n"
            "Uso: `/nombre TuNuevoNombre`\n\n"
            "⏳ *Límite:* Solo puedes cambiarlo una vez cada 7 días.",
            parse_mode="Markdown"
        )
        return

    nuevo_nombre = " ".join(context.args).strip()

    # Validar el nuevo nombre
    if len(nuevo_nombre) < 3 or len(nuevo_nombre) > 20:
        await update.message.reply_text("❌ El nombre debe tener entre 3 y 20 caracteres.")
        return

    # Verificar el límite de tiempo (cooldown de 7 días)
    last_change_str = pb_user.get("last_name_change")
    if last_change_str:
        try:
            last_change = datetime.fromisoformat(last_change_str.replace("Z", "+00:00"))
        except ValueError:
            last_change = None

        if last_change:
            tiempo_espera = timedelta(days=7)
            ahora = datetime.now(last_change.tzinfo)
            if ahora - last_change < tiempo_espera:
                restante = tiempo_espera - (ahora - last_change)
                dias = restante.days
                horas = restante.seconds // 3600
                await update.message.reply_text(
                    f"⏳ *Debes esperar para cambiar tu nombre de nuevo.*\n\n"
                    f"Te quedan: *{dias} días y {horas} horas*.",
                    parse_mode="Markdown"
                )
                return

    # Realizar el cambio en PocketBase
    try:
        pb.update_user(
            pb_user["id"],
            display_name=nuevo_nombre,
            last_name_change=datetime.now().isoformat()
        )
        await update.message.reply_text(
            f"✅ ¡Listo! Tu nombre ha sido cambiado a: *{nuevo_nombre}*",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error al cambiar nombre: {e}")
        await update.message.reply_text("⚠️ Hubo un error al guardar tu nombre. Intenta de nuevo.")


# ============================================
# COMANDO /debug (diagnóstico)
# ============================================
async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        pb_user = pb.get_user_by_telegram_id(user.id)
        if not pb_user:
            await update.message.reply_text("❌ Usuario no encontrado en PocketBase.")
            return

        campos = ["id", "telegram_id", "telegram_username", "display_name",
                  "elo", "wins", "losses", "draws", "referral_code",
                  "referral_count", "referral_points", "streak_days",
                  "last_name_change"]

        info = "🔍 *Datos desde PocketBase:*\n\n"
        for key in campos:
            value = pb_user.get(key, "(vacío)")
            info += f"`{key}`: `{value}`\n"

        await update.message.reply_text(info, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"❌ Error en /debug: {e}")
        await update.message.reply_text(f"⚠️ Error: {e}")


# ============================================
# PUNTO DE ENTRADA
# ============================================
def main():
    logger.info("🚀 Iniciando el bot...")

    # Autenticar con PocketBase al arrancar
    try:
        pb.authenticate()
        logger.info("✅ Conectado a PocketBase")
    except Exception as e:
        logger.error(f"❌ Error al conectar con PocketBase: {e}")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Registrar los handlers (comandos)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("perfil", perfil))
    app.add_handler(CommandHandler("nombre", nombre))
    app.add_handler(CommandHandler("debug", debug))

    logger.info("✅ Bot corriendo. Presiona Ctrl+C para detenerlo.")
    app.run_polling()


if __name__ == "__main__":
    main()