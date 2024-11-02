import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, ContextTypes
import paypalrestsdk
from paypalrestsdk import Payment

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure PayPal
paypalrestsdk.configure({
    "mode": "sandbox",  # Change to "live" for production
    "client_id": "AbyDp03JvRN3XUXvBZyTljsNitpnNQxn_v73oOI9FHLeGgNckYUiLCCejVzIBs1Z2ogvryd0fOCawfEN",
    "client_secret": "EMz8rlUhlborFgJoekCIGIiSltBSQkV8hx-DTd8YbYtEpvu-IxasQKlqkCJmNBYqCL6kHuUZuiC8XK02"
})

# States
PRODUCT, PAYMENT = range(2)

# Product details
PRODUCT_NAME = "Sample Product"
PRODUCT_PRICE = "10.00"
PRODUCT_IMAGE_PATH = "tamra.png"

# Global variable to store payment_id to chat_id mapping
payment_to_chat_id = {}

async def send_product(context: ContextTypes.DEFAULT_TYPE, chat_id):
    with open(PRODUCT_IMAGE_PATH, 'rb') as photo:
        await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=f"Here's your {PRODUCT_NAME}!")
    await context.bot.send_message(chat_id=chat_id, text="Thank you for your purchase!")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Clear any previous data in context
    context.user_data.clear()
    context.user_data['payment_id'] = None

    # Display the initial product offer message
    keyboard = [[InlineKeyboardButton("Buy Product", callback_data='buy')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Welcome! Would you like to buy {PRODUCT_NAME} for ${PRODUCT_PRICE}?",
        reply_markup=reply_markup
    )
    return PRODUCT

async def buy_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    payment = Payment({
        "intent": "sale",
        "payer": {
            "payment_method": "paypal"
        },
        "redirect_urls": {
            "return_url": "http://example.com/return",
            "cancel_url": "http://example.com/cancel"
        },
        "transactions": [{
            "item_list": {
                "items": [{
                    "name": PRODUCT_NAME,
                    "sku": "item",
                    "price": PRODUCT_PRICE,
                    "currency": "USD",
                    "quantity": 1
                }]
            },
            "amount": {
                "total": PRODUCT_PRICE,
                "currency": "USD"
            },
            "description": f"Payment for {PRODUCT_NAME}"
        }]
    })

    if payment.create():
        for link in payment.links:
            if link.rel == "approval_url":
                approval_url = link.href
                keyboard = [[InlineKeyboardButton("Pay Now", url=approval_url)]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    text="Great! Click 'Pay Now' to proceed with the payment. The bot will check the payment status automatically every 30 seconds.",
                    reply_markup=reply_markup
                )
                payment_to_chat_id[payment.id] = update.effective_chat.id
                context.user_data['payment_id'] = payment.id

                # Schedule a job to check payment status every 30 seconds
                context.job_queue.run_repeating(check_payment_job, interval=30, first=30, chat_id=update.effective_chat.id, data={'payment_id': payment.id})

                return PAYMENT
    else:
        await query.edit_message_text(text="Sorry, there was an error creating the payment.")
        return ConversationHandler.END

async def check_payment_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job to check payment status every 30 seconds."""
    job_data = context.job.data
    payment_id = job_data.get('payment_id')
    chat_id = context.job.chat_id

    payment = Payment.find(payment_id)
    if payment.state == "approved":
        await send_product(context, chat_id)
        await context.bot.send_message(chat_id=chat_id, text="Thank you for your purchase!")
        
        # Remove the payment_id from the mapping and stop the job
        payment_to_chat_id.pop(payment_id, None)
        context.job.schedule_removal()
    elif payment.state == "created":
        # Attempt to execute the payment if it’s still in 'created' state
        try:
            payer_id = payment.payer.payer_info.payer_id
            if payment.execute({"payer_id": payer_id}):
                await send_product(context, chat_id)
                await context.bot.send_message(chat_id=chat_id, text="Payment completed successfully! Thank you for your purchase.")
                context.job.schedule_removal()
            else:
                await context.bot.send_message(chat_id=chat_id, text="Payment not yet completed. Checking again in 30 seconds.")
        except Exception as e:
            logger.error(f"Error executing payment: {str(e)}")
            await context.bot.send_message(chat_id=chat_id, text="Error during payment execution. We will check again shortly.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Purchase cancelled.")
    return ConversationHandler.END

def main() -> None:
    application = Application.builder().token("6745270985:AAEVPorf_xWUBdF3-dgzZgDNcNCWw-lTWzw").build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PRODUCT: [CallbackQueryHandler(buy_product, pattern='^buy$')],
            PAYMENT: []
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )
    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
    main()
