import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, ContextTypes
from paylink import Paylink, PaylinkProduct
import os
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Paylink configuration
paylink = Paylink.production(
  api_id='APP_ID_1712565901914',
  secret_key='1debe73b-3d34-331d-a090-6e8c304309eb'
)  

# States for the conversation
PRODUCT_SELECTION, PAYMENT_PROCESSING = range(2)

# Mapping of transaction numbers to Telegram chat IDs
transaction_chat_map = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Clear any existing conversation data
    context.user_data.clear()
    
    keyboard = [
        [InlineKeyboardButton("Product avgo Gamma 1min  - $19", callback_data='A')],
        
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = (
        "Welcome to the real-time trading bot for top options contracts in *SPX*, *NASDAQ*, and *Gamma*! 🚀\n\n"
        "Our bot provides live updates on the top 3 *call* and *put* contracts, as well as *NetGex* levels, to help you make smarter trading decisions.\n\n"
        "What the bot offers:\n"
        "- Top call and put contracts: Real-time display of the highest-performing contracts.\n"
        "- NetGex levels: Track key liquidity and market trend levels.\n\n"
        "Access exclusive trading opportunities and benefit from instant updates to achieve your financial goals!\n\n"
        "To subscribe, please select one of the options below:"
    )
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    return PRODUCT_SELECTION





def update_user_data(user_id, user_name, payment_date):
    filename = "user_data.txt"
    user_data = f"{user_id}:{user_name}:paid:1 month:{payment_date}\n"
    
    if os.path.exists(filename):
        with open(filename, "r") as file:
            lines = file.readlines()
        
        updated = False
        for i, line in enumerate(lines):
            if line.startswith(f"{user_id}:"):
                lines[i] = user_data
                updated = True
                break
        
        if not updated:
            lines.append(user_data)
        
        with open(filename, "w") as file:
            file.writelines(lines)
    else:
        with open(filename, "w") as file:
            file.write(user_data)


async def product_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    product_id = query.data
    if product_id == 'A':
        amount = 19
        product = PaylinkProduct(title="Product avgo Gamma 1min ", price=19, qty=1)
    else:
        amount = 20
        product = PaylinkProduct(title="Product B", price=20, qty=1)
    try:
        invoice_details = paylink.add_invoice(
            amount=amount,
            client_mobile="",  # Replace with user's mobile
            client_name=update.effective_user.full_name,
            order_number=f"ORDER_{update.effective_user.id}",
            products=[product],
            callback_url="https://t.me/+7yafeSiz-55kYmJk",  # Replace with your actual callback URL
            cancel_url="https:www.google.com",
            currency="USD"
        )
        payment_url = invoice_details.url
        payment_message_english = (
    "🔴 Please complete the payment through the link below:\n\n"
    f"{payment_url}\n\n"
)
        
        await query.edit_message_text(payment_message_english)
        
        
        transaction_no = invoice_details.transaction_no
        transaction_chat_map[transaction_no] = update.effective_chat.id
        context.user_data['transaction_no'] = transaction_no
        
        # Start the periodic payment check
        context.job_queue.run_repeating(
                    check_payment_job, 
                    interval=30, 
                    first=30, 
                    data={
                        'chat_id': update.effective_chat.id, 
                        'transaction_no': transaction_no,
                        'start_time': datetime.now()
                    }
                                       )
        return PAYMENT_PROCESSING
    except Exception as e:
        logger.error(f"Error creating invoice: {str(e)}")
        await query.edit_message_text("Sorry, there was an error creating your invoice. Please try again later.")
        return ConversationHandler.END

async def check_payment_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.data['chat_id']
    transaction_no = job.data['transaction_no']
    start_time = job.data.get('start_time', datetime.now())

    status = paylink.order_status(transaction_no)
    if status.lower() == 'paid':
         # Create keyboard with channel link button
        keyboard = [[InlineKeyboardButton("Join Channel", url="https://t.me/+7yafeSiz-55kYmJk")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = "Payment successful! ✅\nClick the button below to join our exclusive channel:"
        await context.bot.send_message(
            chat_id=chat_id, 
            text=message,
            reply_markup=reply_markup
        )

        # Get user information
        user = await context.bot.get_chat_member(chat_id, chat_id)
        user_id = user.user.id
        user_name = user.user.username or user.user.first_name
        payment_date = datetime.now().strftime("%Y-%m-%d")
        
        # Update user data file
        update_user_data(user_id, user_name, payment_date)
        
        # Get invoice details
        invoice_details = paylink.get_invoice(transaction_no=transaction_no)

        text = (
    f"*Transaction Details*\n"
    f"Transaction Number: `{transaction_no}\n"
    f"Amount: {invoice_details.amount}\n"
    f"Status: {invoice_details.order_status}\n\n"
    f"*Receipt Information*\n"
)

        receipt = invoice_details.payment_receipt
        if isinstance(receipt, dict):
            for key, value in receipt.items():
                text += f"{key.capitalize()}: {value}\n"
        else:
            text += f"Receipt: `{receipt}`\n"
        
        # Send invoice details to the active chat
        await context.bot.send_message(
            chat_id=chat_id,

            
           
           
           
            text=text
        
        
        
        )
        
        # List of chat IDs to send the invoice to (excluding the active chat)
        chat_ids_to_notify = [-1002483849386]
        
        # Send invoice to each chat ID (excluding the active chat)
        for notify_chat_id in chat_ids_to_notify:
            if notify_chat_id != chat_id:
                await context.bot.send_message(
                    chat_id=notify_chat_id,
                    text=text
                )
        
        # Remove the transaction from the map and stop the job
        transaction_chat_map.pop(transaction_no, None)
        job.schedule_removal()
    else:
         # Check if 2 minutes have passed
        if (datetime.now() - start_time).total_seconds() > 320:
            await context.bot.send_message(
                chat_id=chat_id,
                text="Payment failed. Please try again."
            )
            # Remove the job after 2 minutes of unsuccessful payment
            job.schedule_removal()
            # Remove the transaction from the map
            transaction_chat_map.pop(transaction_no, None)
        else:
            logger.info(f"Payment not yet completed for transaction {transaction_no}. Current status: {status}")


async def check_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    transaction_no = context.user_data.get('transaction_no')
    if not transaction_no:
        await update.message.reply_text("No pending payment found.")
        return ConversationHandler.END
    status = paylink.order_status(transaction_no)
    if status.lower() == 'paid':
        await update.message.reply_text("Payment successful! Here's your product link: https://example.com/product")
        transaction_chat_map.pop(transaction_no, None)
        # Stop the automatic checking job
        current_jobs = context.job_queue.get_jobs_by_name(str(transaction_no))
        for job in current_jobs:
            job.schedule_removal()
        return ConversationHandler.END
    else:
        await update.message.reply_text(f"Payment status: {status}. Please complete the payment.")
    return PAYMENT_PROCESSING

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    transaction_no = context.user_data.get('transaction_no')
    if transaction_no:
        transaction_chat_map.pop(transaction_no, None)
        # Stop the automatic checking job
        current_jobs = context.job_queue.get_jobs_by_name(str(transaction_no))
        for job in current_jobs:
            job.schedule_removal()
    await update.message.reply_text("Purchase cancelled.")
    return ConversationHandler.END

def main() -> None:
    application = Application.builder().token("6823753494:AAHa41WZgXEJswYiZHMYaUhlfCyn4MhG1so").build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PRODUCT_SELECTION: [CallbackQueryHandler(product_selection)],
            PAYMENT_PROCESSING: [CommandHandler("check", check_payment)]
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel)]
    )
    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
    main()
