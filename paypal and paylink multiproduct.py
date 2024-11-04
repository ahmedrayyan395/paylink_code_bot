import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    CallbackContext,
)
from paylink import Paylink, PaylinkProduct
import paypalrestsdk
from paypalrestsdk import Payment
from datetime import datetime
import os

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

paylink = Paylink.test()

'''
# Paylink configuration
paylink = Paylink.production(
    api_id='APP_ID_1712565901914',
    secret_key='1debe73b-3d34-331d-a090-6e8c304309eb'
)
'''

# PayPal configuration
paypalrestsdk.configure({
    "mode": "sandbox",  # Change to "live" for production
    "client_id": "AbyDp03JvRN3XUXvBZyTljsNitpnNQxn_v73oOI9FHLeGgNckYUiLCCejVzIBs1Z2ogvryd0fOCawfEN",
    "client_secret": "EMz8rlUhlborFgJoekCIGIiSltBSQkV8hx-DTd8YbYtEpvu-IxasQKlqkCJmNBYqCL6kHuUZuiC8XK02"
})

# States
PAYMENT_SELECTION, PRODUCT_SELECTION = range(2)

# List of Products
PRODUCTS = [
    {"name": "META Gamma 1min", "price": "19.00", "channel_url": "https://t.me/+nyYqvua2iSFlMmE0"},
    {"name": "TSLA 1min", "price": "19.00", "channel_url": "https://t.me/+itft4dGODUlhN2U0"},
    {"name": "NVDA 1min", "price": "19.00", "channel_url": "https://t.me/+LDN2vP5j7xA4OWQ0"},
    {"name": "nflx Gamma 1min", "price": "19.00", "channel_url": "https://t.me/+FuF1dcZNSLszYTk0"},
    {"name": "mstr Gamma 1min", "price": "19.00", "channel_url": "https://t.me/+BpOTS0RWl8lmMGI0"},
    {"name": "SPY 1min", "price": "19.00", "channel_url": "https://t.me/+dTVSXkZ6vo4wZDY0"},
    {"name": "qqq (1min) gamma", "price": "19.00", "channel_url": "https://t.me/+p6pjdnzWPvhiNWRk"},
    #{"name": "avgo Theta 1day", "price": "19.00", "channel_url": "https://t.me/+channel8"}
]
# Global variables
transaction_chat_map = {}
payment_to_chat_id = {}
selected_products = {}  # Add this new dictionary
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
        "Our bot provides live updates on the top 3 *call* and *put* contracts, as well as *NetGex* levels, to help you make smarter trading decisions.\n\n"
        "What the bot offers:\n"
        "- Top call and put contracts: Real-time display of the highest-performing contracts.\n"
        "- NetGex levels: Track key liquidity and market trend levels.\n\n"
        "Access exclusive trading opportunities and benefit from instant updates to achieve your financial goals!\n\n"
        "Please select your preferred payment method:"
    )

    await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')
    return PAYMENT_SELECTION

async def send_join_message(context: ContextTypes.DEFAULT_TYPE, chat_id, channel_url):
    keyboard = [[InlineKeyboardButton("Join Channel", url=channel_url)]]
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
        f"📄 *Invoice Details:*\n"
        f"**Payment ID:** `{payment.id}`\n"
        f"**Payer Name:** {payer_info.first_name} {payer_info.last_name}\n"
        f"**Payer Email:** {payer_info.email}\n"
        f"**Amount:** {transaction.amount.total} {transaction.amount.currency}\n"
        f"**Item:** {transaction.item_list.items[0].name}\n"
        f"**Status:** {payment.state}\n"
        f"**Invoice URL:** {invoice_url}"
    )

    # Send to user's chat
    await context.bot.send_message(chat_id=chat_id, text=invoice_details, parse_mode='Markdown')

    # Send to the invoice channel
    await context.bot.send_message(chat_id=INVOICE_CHANNEL_ID, text=invoice_details, parse_mode='Markdown')

async def payment_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    payment_method = query.data

    if payment_method in ['paylink', 'paypal']:
        keyboard = [
            [InlineKeyboardButton(f"{product['name']} - ${product['price']}", callback_data=f"{payment_method}_{i}")]
            for i, product in enumerate(PRODUCTS)
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Please select the product you want to purchase:", reply_markup=reply_markup)
        return PRODUCT_SELECTION

    await query.edit_message_text("Invalid payment method selected.")
    return ConversationHandler.END

# Paylink payment handling
async def product_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    callback_data = query.data
    try:
        payment_method, product_index = callback_data.split('_')
        product_index = int(product_index)
        selected_product = PRODUCTS[product_index]
    except (ValueError, IndexError):
        await query.edit_message_text("Invalid product selection.")
        return ConversationHandler.END

    if payment_method == 'paylink':
        product = PaylinkProduct(title=selected_product["name"], price=float(selected_product["price"]), qty=1)
        try:
            invoice_details = paylink.add_invoice(
                amount=float(selected_product["price"]),
                client_mobile="",
                client_name=update.effective_user.full_name,
                order_number=f"ORDER_{update.effective_user.id}_{int(datetime.timestamp(datetime.now()))}",
                products=[product],
                callback_url="https://yourdomain.com/paylink_callback",
                cancel_url="https://www.google.com",
                currency="USD"
            )
            payment_url = invoice_details.url
            payment_message = (
                "🔴 Please complete the payment through the link below:\n\n"
                f"{payment_url}\n\n"
                "You have 3 minutes to complete the payment."
            )
            await query.edit_message_text(payment_message)
            transaction_no = invoice_details.transaction_no
            
            # Store selected product after we have the transaction_no
            selected_products[transaction_no] = selected_product
            
            transaction_chat_map[transaction_no] = update.effective_chat.id
            context.user_data['transaction_no'] = transaction_no
            
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
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"Error creating invoice: {str(e)}")
            await query.edit_message_text("Sorry, there was an error creating your invoice. Please try again later.")
            return ConversationHandler.END

    elif payment_method == 'paypal':
        selected_product = PRODUCTS[product_index]
        context.user_data['selected_product'] = selected_product  # Store the selected product

        payment = Payment({
            "intent": "sale",
            "payer": {
                "payment_method": "paypal"
            },
            "redirect_urls": {
                "return_url": "https://yourdomain.com/paypal_return",  # Replace with your actual return URL
                "cancel_url": "https://www.google.com/cancel"
            },
            "transactions": [{
                "item_list": {
                    "items": [{
                        "name": selected_product["name"],
                        "sku": "item",
                        "price": selected_product["price"],
                        "currency": "USD",
                        "quantity": 1
                    }]
                },
                "amount": {
                    "total": selected_product["price"],
                    "currency": "USD"
                },
                "description": f"Payment for {selected_product['name']}"
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

                    # Schedule a job to check the payment status every 30 seconds
                    context.job_queue.run_repeating(
                        check_paypal_payment_job,
                        interval=30,
                        first=30,
                        data={
                            'payment_id': payment.id,
                            'chat_id': update.effective_chat.id,
                            'start_time': datetime.now()
                        }
                    )
                    return ConversationHandler.END

        await query.edit_message_text(text="Sorry, there was an error creating the PayPal payment.")
        return ConversationHandler.END

async def check_paylink_payment_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.data['chat_id']
    transaction_no = job.data['transaction_no']
    start_time = job.data.get('start_time', datetime.now())

    try:
        status = paylink.order_status(transaction_no)
    except Exception as e:
        logger.error(f"Error checking Paylink status for {transaction_no}: {str(e)}")
        return

    if status.lower() == 'paid':

        # Get the selected product from the invoice details
        selected_product = selected_products.get(transaction_no)  # Get from global dictionary
        
        if selected_product:
            # Create keyboard with channel link button
            keyboard = [[InlineKeyboardButton("Join Channel", url=selected_product["channel_url"])]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = "✅ Payment successful! Click the button below to join our exclusive channel:"
            await context.bot.send_message(
                chat_id=chat_id, 
                text=message,
                reply_markup=reply_markup
            )
            
            # Clean up the stored product data
            selected_products.pop(transaction_no, None)
        else:
            logger.error(f"Unable to determine the selected product for transaction {transaction_no}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="Payment successful, but there was an issue retrieving your product details. Please contact support."
            )

        # Get user information
        user = await context.bot.get_chat_member(chat_id, chat_id)
        user_id = user.user.id
        user_name = user.user.username or user.user.first_name
        payment_date = datetime.now().strftime("%Y-%m-%d")

        # Update user data file
        update_user_data(user_id, user_name, payment_date)

        # Get invoice details
        try:
            invoice_details = paylink.get_invoice(transaction_no=transaction_no)
        except Exception as e:
            logger.error(f"Error fetching invoice details for {transaction_no}: {str(e)}")
            invoice_details = None

        if invoice_details:
            text = (
                f"*Transaction Details*\n"
                f"**Transaction Number:** `{transaction_no}`\n"
                f"**Amount:** ${invoice_details.amount}\n"
                f"**Status:** {invoice_details.order_status}\n\n"
                f"*Receipt Information*\n"
            )

            receipt = invoice_details.payment_receipt
            if isinstance(receipt, dict):
                for key, value in receipt.items():
                    text += f"**{key.capitalize()}**: {value}\n"
            else:
                text += f"**Receipt**: `{receipt}`\n"

            # Send invoice details to the user's chat
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='Markdown'
            )

            # Send invoice to the invoice channel
            await context.bot.send_message(
                chat_id=INVOICE_CHANNEL_ID,
                text=text,
                parse_mode='Markdown'
            )

        # Remove the transaction from the map and stop the job
        transaction_chat_map.pop(transaction_no, None)
        job.schedule_removal()

    else:
        # Check if 3 minutes have passed
        if (datetime.now() - start_time).total_seconds() > 180:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⏰ Payment time expired. Please try again."
            )
            # Remove the job after 3 minutes of unsuccessful payment
            job.schedule_removal()
            # Remove the transaction from the map
            transaction_chat_map.pop(transaction_no, None)
        else:
            logger.info(f"Payment not yet completed for transaction {transaction_no}. Current status: {status}")

async def check_paypal_payment_job(context: ContextTypes.DEFAULT_TYPE):
    """Job to check PayPal payment status every 30 seconds."""
    job = context.job
    payment_id = job.data.get('payment_id')
    chat_id = job.data.get('chat_id')
    start_time = job.data.get('start_time', datetime.now())

    try:
        payment = Payment.find(payment_id)
    except Exception as e:
        logger.error(f"Error fetching PayPal payment {payment_id}: {str(e)}")
        return

    if payment.state == "approved":
        # Payment approved, proceed with sending thank you message and updating records
        await send_join_message(context, chat_id)
        await context.bot.send_message(chat_id=chat_id, text="🎉 Thank you for your purchase!")
        await send_invoice_details(context, chat_id, payment)

        # Get user information and update user data
        try:
            user = await context.bot.get_chat_member(chat_id, chat_id)
            user_id = user.user.id
            user_name = user.user.username or user.user.first_name
            payment_date = datetime.now().strftime("%Y-%m-%d")

            update_user_data(user_id, user_name, payment_date)
        except Exception as e:
            logger.error(f"Error fetching user info for chat_id {chat_id}: {str(e)}")

        # Remove the payment from tracking and stop the job
        payment_to_chat_id.pop(payment_id, None)
        job.schedule_removal()

    elif payment.state == "created":
        # Try to execute the payment if it is still in "created" status
        try:
            payer_id = payment.payer.payer_info.payer_id
            if payment.execute({"payer_id": payer_id}):
                # Re-fetch the payment status to confirm execution success
                payment = Payment.find(payment_id)
                if payment.state == "approved":

                     # Get the selected product from the payment details
                    product_name = payment.transactions[0].item_list.items[0].name
                    selected_product = next((p for p in PRODUCTS if p["name"] == product_name), None)
    
                    # Send join message with specific channel URL
                    await send_join_message(context, chat_id, selected_product["channel_url"])
                    await context.bot.send_message(chat_id=chat_id, text="🎉 Thank you for your purchase!")
                    await send_invoice_details(context, chat_id, payment)

                    # Update user data
                    user = await context.bot.get_chat_member(chat_id, chat_id)
                    user_id = user.user.id
                    user_name = user.user.username or user.user.first_name
                    payment_date = datetime.now().strftime("%Y-%m-%d")

                    update_user_data(user_id, user_name, payment_date)
                    
                    # Clean up the job and mapping
                    payment_to_chat_id.pop(payment_id, None)
                    job.schedule_removal()
                else:
                    await context.bot.send_message(chat_id=chat_id, text="Payment not yet approved. Checking again soon.")
            else:
                logger.info(f"PayPal payment {payment_id} execution failed. Retrying.")
        except Exception as e:
            logger.error(f"Error executing payment {payment_id}: {str(e)}")
            # Payment is still pending; check if timeout is reached
            if (datetime.now() - start_time).total_seconds() > 180:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="⏰ Payment time expired. Please try again."
                )
                # Remove the job and payment tracking
                payment_to_chat_id.pop(payment_id, None)
                job.schedule_removal()
            else:
                logger.info(f"PayPal payment {payment_id} still pending. Status: {payment.state}")
    
       
    
    elif payment.state in ["pending"]:
        # Payment is still pending; check if timeout is reached
        if (datetime.now() - start_time).total_seconds() > 180:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⏰ Payment time expired. Please try again."
            )
            # Remove the job and payment tracking
            payment_to_chat_id.pop(payment_id, None)
            job.schedule_removal()
        else:
            logger.info(f"PayPal payment {payment_id} still pending. Status: {payment.state}")

    else:
        # Payment failed or canceled, notify user
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Payment was not successful. Please try again."
        )
        # Remove the job and payment tracking
        payment_to_chat_id.pop(payment_id, None)
        job.schedule_removal()


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Purchase cancelled.")
    return ConversationHandler.END

def main() -> None:
    # Use your bot token here
    application = Application.builder().token("6745270985:AAEVPorf_xWUBdF3-dgzZgDNcNCWw-lTWzw").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PAYMENT_SELECTION: [CallbackQueryHandler(payment_selection)],
            PRODUCT_SELECTION: [CallbackQueryHandler(product_selection)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)]
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
    main()
