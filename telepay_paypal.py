import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, ContextTypes
import paypalrestsdk
from paypalrestsdk import Payment
from datetime import datetime
import os

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
PRODUCT_NAME = "avgo Gamma 1min"
PRODUCT_PRICE = "19.00"

# Channel ID for sending invoice details
INVOICE_CHANNEL_ID = "-1002483849386"  # Replace with your actual channel ID

# Global variable to store payment_id to chat_id mapping
payment_to_chat_id = {}

def update_user_data(telegram_id, username, payment_status, subscription_period, payment_date):
    filename = "C:\\Users\\Interface\\OneDrive\\سطح المكتب\\paylink_project\\python-package-master\\user_data.txt"
    updated = False
    new_lines = []
    
    # Read existing file if it exists
    if os.path.exists(filename):
        with open(filename, 'r') as file:
            lines = file.readlines()
            for line in lines:
                if line.strip():  # Skip empty lines
                    user_id = line.split(':')[0]
                    if user_id == str(telegram_id):
                        # Update existing record
                        new_lines.append(f"{telegram_id}:{username}:{payment_status}:{subscription_period}:{payment_date}\n")
                        updated = True
                    else:
                        new_lines.append(line)
    
    # If user not found, add new record
    if not updated:
        new_lines.append(f"{telegram_id}:{username}:{payment_status}:{subscription_period}:{payment_date}\n")
    
    # Write all records back to file
    with open(filename, 'w') as file:
        file.writelines(new_lines)

async def send_join_message(context: ContextTypes.DEFAULT_TYPE, chat_id):
    keyboard = [[InlineKeyboardButton("Join Channel", url="https://t.me/+7yafeSiz-55kYmJk")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=chat_id,
        text="You can join the channel now!",
        reply_markup=reply_markup
    )

async def send_invoice_details(context: ContextTypes.DEFAULT_TYPE, chat_id, payment):
    # Extract relevant details from the payment object
    payer_info = payment.payer.payer_info
    transaction = payment.transactions[0]
    invoice_url = next((link.href for link in payment.links if link.rel == "invoice"), "Invoice URL not available")
    
    invoice_details = (
        f"Invoice Details:\n"
        f"Payment ID: {payment.id}\n"
        f"Payer Name: {payer_info.first_name} {payer_info.last_name}\n"
        f"Payer Email: {payer_info.email}\n"
        f"Amount: {transaction.amount.total} {transaction.amount.currency}\n"
        f"Item: {transaction.item_list.items[0].name}\n"
        f"Status: {payment.state}\n"
        f"Invoice URL: {invoice_url}"
    )
    
    # Send to user's chat
    await context.bot.send_message(chat_id=chat_id, text=invoice_details)
    
    # Send to the invoice channel
    await context.bot.send_message(chat_id=INVOICE_CHANNEL_ID, text=invoice_details)

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
            "return_url": "https://t.me/+7yafeSiz-55kYmJk",
            "cancel_url": "http://google.com/cancel"
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
                context.job_queue.run_repeating(check_payment_job, interval=30, first=130, chat_id=update.effective_chat.id, data={'payment_id': payment.id})
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
        await send_join_message(context, chat_id)
        await context.bot.send_message(chat_id=chat_id, text="Thank you for your purchase!")
        await send_invoice_details(context, chat_id, payment)
        
        # Get user information and update user_data.txt
        payer_info = payment.payer.payer_info
        payment_date = datetime.now().strftime("%Y-%m-%d")
        username = payer_info.email.split('@')[0]  # Using email username as fallback
        
        # Update user data file
        update_user_data(
            telegram_id=chat_id,
            username=username,
            payment_status="paid",
            subscription_period="1 month",
            payment_date=payment_date
        )
        
        # Remove the payment_id from the mapping and stop the job
        payment_to_chat_id.pop(payment_id, None)
        context.job.schedule_removal()
        
    elif payment.state == "created":
        try:
            payer_id = payment.payer.payer_info.payer_id
            if payment.execute({"payer_id": payer_id}):
                await send_join_message(context, chat_id)
                await context.bot.send_message(chat_id=chat_id, text="Payment completed successfully! Thank you for your purchase.")
                await send_invoice_details(context, chat_id, payment)
                
                # Get user information and update user_data.txt
                payer_info = payment.payer.payer_info
                payment_date = datetime.now().strftime("%Y-%m-%d")
                username = payer_info.email.split('@')[0]  # Using email username as fallback
                
                # Update user data file
                update_user_data(
                    telegram_id=chat_id,
                    username=username,
                    payment_status="paid",
                    subscription_period="1 month",
                    payment_date=payment_date
                )
                
                context.job.schedule_removal()
            else:
                await context.bot.send_message(chat_id=chat_id, text="Payment not yet completed. Checking again in 30 seconds.")
        except Exception as e:
            logger.error(f"Error executing payment: {str(e)}")
            context.job.schedule_removal()
            await context.bot.send_message(chat_id=chat_id, text="Error during payment execution. Please try again and click /start.")

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
