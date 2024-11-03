import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, ContextTypes
from paylink import Paylink, PaylinkProduct
import paypalrestsdk
from paypalrestsdk import Payment
from datetime import datetime
import os

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

paylink=Paylink.test()


'''
# Paylink configuration
paylink = Paylink.production(
    api_id='APP_ID_1712565901914',
    secret_key='1debe73b-3d34-331d-a090-6e8c304309eb'
)
'''


# PayPal configuration
paypalrestsdk.configure({
    "mode": "sandbox",
    "client_id": "AbyDp03JvRN3XUXvBZyTljsNitpnNQxn_v73oOI9FHLeGgNckYUiLCCejVzIBs1Z2ogvryd0fOCawfEN",
    "client_secret": "EMz8rlUhlborFgJoekCIGIiSltBSQkV8hx-DTd8YbYtEpvu-IxasQKlqkCJmNBYqCL6kHuUZuiC8XK02"
})

# States
PAYMENT_SELECTION, PRODUCT_SELECTION, PAYMENT_PROCESSING = range(3)

# Product details
PRODUCT_NAME = "avgo Gamma 1min"
PRODUCT_PRICE = "19.00"

# Channel IDs
INVOICE_CHANNEL_ID = "-1002483849386"

# Global variables
transaction_chat_map = {}
payment_to_chat_id = {}

def update_user_data(user_id, user_name, payment_date):
    filename = "C:\\Users\\Interface\\OneDrive\\سطح المكتب\\paylink_project\\python-package-master\\user_data.txt"
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton("Paylink - $19", callback_data='paylink')],
        [InlineKeyboardButton("PayPal - $19", callback_data='paypal')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = (
        "Welcome to the real-time trading bot for top options contracts in *SPX*, *NASDAQ*, and *Gamma*! 🚀\n\n"
        "Our bot provides live updates on the top 3 *call* and *put* contracts, as well as *NetGex* levels.\n\n"
        "Please select your preferred payment method:"
    )
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')
    return PAYMENT_SELECTION

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




async def payment_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    payment_method = query.data
    
    if payment_method == 'paylink':
        keyboard = [
            [InlineKeyboardButton("Product avgo Gamma 1min  - $19", callback_data='A')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Please confirm your purchase:", reply_markup=reply_markup)
        return PRODUCT_SELECTION
    
    elif payment_method == 'paypal':
        return await handle_paypal_payment(update, context)

# Paylink payment handling
async def product_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    product = PaylinkProduct(title="Product avgo Gamma 1min ", price=19, qty=1)
    
    try:
        invoice_details = paylink.add_invoice(
            amount=19,
            client_mobile="",
            client_name=update.effective_user.full_name,
            order_number=f"ORDER_{update.effective_user.id}",
            products=[product],
            callback_url="https://t.me/+7yafeSiz-55kYmJk",
            cancel_url="https:www.google.com",
            currency="USD"
        )
        
        payment_url = invoice_details.url
        payment_message = (
            "🔴 Please complete the payment through the link below:\n\n"
            f"{payment_url}\n\n"
        )
        
        await query.edit_message_text(payment_message)
        transaction_no = invoice_details.transaction_no
        transaction_chat_map[transaction_no] = update.effective_chat.id
        context.user_data['transaction_no'] = transaction_no
        ###############################################################################
        context.job_queue.run_repeating(
            check_paylink_payment_job,
            interval=30,
            first=30,
            data={
                'chat_id': update.effective_chat.id,
                'transaction_no': transaction_no,
                'start_time': datetime.now()
            }
        )
        ###########################################################################################3
        return PAYMENT_PROCESSING
    
    except Exception as e:
        logger.error(f"Error creating invoice: {str(e)}")
        await query.edit_message_text("Sorry, there was an error creating your invoice. Please try again later.")
        return ConversationHandler.END

# PayPal payment handling
async def handle_paypal_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    
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
                    text="Click 'Pay Now' to proceed with PayPal payment.",
                    reply_markup=reply_markup
                )
                payment_to_chat_id[payment.id] = update.effective_chat.id
                context.user_data['payment_id'] = payment.id


                #####################################################################
                context.job_queue.run_repeating(
                    check_paypal_payment_job,
                    interval=30,
                    first=30,
                    chat_id=update.effective_chat.id,
                    data={
                        'payment_id': payment.id,
                        'start_time': datetime.now()
                    }
                )
                ########################################################################
                return PAYMENT_PROCESSING
    
    await query.edit_message_text(text="Sorry, there was an error creating the PayPal payment.")
    return ConversationHandler.END

async def check_paylink_payment_job(context: ContextTypes.DEFAULT_TYPE):
       
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
           if (datetime.now() - start_time).total_seconds() > 180:
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
   
   
async def check_paypal_payment_job(context: ContextTypes.DEFAULT_TYPE):
     
     """Job to check payment status every 30 seconds."""
     job_data = context.job.data
     payment_id = job_data.get('payment_id')
     chat_id = context.job.chat_id
     start_time = job_data.get('start_time', datetime.now())

     payment = Payment.find(payment_id)
     
     if payment.state == "approved":
         await send_join_message(context, chat_id)
         await context.bot.send_message(chat_id=chat_id, text="Thank you for your purchase!")
         await send_invoice_details(context, chat_id, payment)
         
         # Get user information and update user_data.txt
         payer_info = payment.payer.payer_info
         payment_date = datetime.now().strftime("%Y-%m-%d")
         #username = payer_info.email.split('@')[0]  # Using email username as fallback
         
          # Get Telegram user information
         user = await context.bot.get_chat_member(chat_id, chat_id)
         payment_date = datetime.now().strftime("%Y-%m-%d")
         username = user.user.username or user.user.first_name  # Use username or first name as fallback
        




         # Update user data file
         update_user_data(
             telegram_id=chat_id,
             username=username,
             
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
                 #username = payer_info.email.split('@')[0]  # Using email username as fallback
                 
                  # Get Telegram user information
                 user = await context.bot.get_chat_member(chat_id, chat_id)
                 payment_date = datetime.now().strftime("%Y-%m-%d")
                 username = user.user.username or user.user.first_name  # Use username or first name as fallback
        



                 # Update user data file
                 
                 user_id=chat_id
                 user_name=username
                     
                 payment_date=payment_date

                 filename = "C:\\Users\\Interface\\OneDrive\\سطح المكتب\\paylink_project\\python-package-master\\user_data.txt"
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
                          
             
             
                 
                 
                 context.job.schedule_removal()
             else:
                 await context.bot.send_message(chat_id=chat_id, text="Payment not yet completed. Checking again in 30 seconds.")
         except Exception as e:
             logger.error(f"Error executing payment: {str(e)}")
              # Check if 320 seconds have passed
             if (datetime.now() - start_time).total_seconds() > 180:
                 await context.bot.send_message(
                     chat_id=chat_id,
                     text="Payment failed. Please try again."
                 )
                 # Remove the job after 320 seconds of unsuccessful payment
                 context.job.schedule_removal()
                 # Remove the payment_id from the mapping
                 payment_to_chat_id.pop(payment_id, None)
             else:
                 #log this instead 
                  logger.error(chat_id=chat_id, text="Payment not yet completed. Checking again in 30 seconds.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Purchase cancelled.")
    return ConversationHandler.END

def main() -> None:
    # Use your bot token here
    application = Application.builder().token("6745270985:AAEVPorf_xWUBdF3-dgzZgDNcNCWw-lTWzw").build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PAYMENT_SELECTION: [CallbackQueryHandler(payment_selection)],
            PRODUCT_SELECTION: [CallbackQueryHandler(product_selection)],
            PAYMENT_PROCESSING: [CommandHandler("check", check_paylink_payment_job)]
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)]
    )
    
    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
    main()