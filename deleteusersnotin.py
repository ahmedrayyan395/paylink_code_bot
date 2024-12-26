from telethon.sync import TelegramClient
import os
import asyncio
'''



# Your Telegram API credentials
api_id = '20572087'
api_hash = '044ac78962bfd63b5487896a2cf33151'
CHANNEL_IDS = [-1002424303935]  # Make sure this is an integer ID (without quotes)

'''


# Your Telegram API credentials
api_id = '17658047'
api_hash = '4489c4c573ff32a721965ad55b7e3a18'

CHANNEL_IDS = [-1002318611178, -1002219870155, -1002233639928, -1002271593508, -1002268753574, -1002186636737, -1002247278564, -1002428041845]









# Path to your user data file
user_data_file = "C:\\Users\\Interface\\OneDrive\\سطح المكتب\\paylink_project\\python-package-master\\user_data.txt"

# Function to read user data from the file
def read_user_data():
    users = set()
    if os.path.exists(user_data_file):
        with open(user_data_file, "r") as file:
            for line in file:
                try:
                    user_id, _, _, _, _ = line.strip().split(":")
                    users.add(int(user_id))  # Store user IDs as integers
                except ValueError:
                    # Log or print a message about the malformed line
                    print(f"Skipping malformed line: {line.strip()}")
    return users

# Function to remove users not in the user data file from multiple channels
async def remove_non_members(client):
    valid_user_ids = read_user_data()
    for channel_id in CHANNEL_IDS:
        try:
            channel = await client.get_entity(channel_id)
            async for user in client.iter_participants(channel):
                # Check if the user is an admin
                if user.participant and user.participant.is_admin:
                    continue  # Skip admins

                if user.id not in valid_user_ids:
                    try:
                        await client.kick_participant(channel, user.id)
                        print(f"Removed user {user.id} ({user.username or user.first_name}) from channel {channel_id}.")
                    except Exception as e:
                        print(f"Failed to remove user {user.id} from channel {channel_id}: {str(e)}")
        except Exception as e:
            print(f"Failed to get entity for channel {channel_id}: {str(e)}")


# Function to run the removal process every minute
async def periodic_task(client):
    while True:
        await remove_non_members(client)
        await asyncio.sleep(6)  # Wait for 60 seconds before the next check

async def main():
    # Create a new Telegram client
    async with TelegramClient('session_name2', api_id, api_hash) as client:
        await periodic_task(client)

if __name__ == '__main__':
    asyncio.run(main())