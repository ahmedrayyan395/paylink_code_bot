from telethon.sync import TelegramClient
from telethon.tl.functions.channels import InviteToChannelRequest
import os
import asyncio

# Your Telegram API credentials (for a user account)
api_id = '17658047'
api_hash = '4489c4c573ff32a721965ad55b7e3a18'

# New channel ID where invalid users will be added
NEW_CHANNEL_ID = -1002045422486  # Replace with your new channel ID

# Path to the invalid users file
invalid_users_file = "C:\\Users\\Interface\\OneDrive\\invalid_users.txt"

# Function to read invalid users from the file
def read_invalid_users():
    invalid_users = []
    if os.path.exists(invalid_users_file):
        with open(invalid_users_file, "r") as file:
            for line in file:
                try:
                    user_id = int(line.split(",")[0].split(":")[1].strip())
                    username = line.split(",")[1].split(":")[1].strip()
                    invalid_users.append((user_id, username))
                except (ValueError, IndexError):
                    print(f"Skipping malformed line: {line.strip()}")
    return invalid_users

# Function to add invalid users to the new channel
async def add_invalid_users_to_channel(client):
    invalid_users = read_invalid_users()
    try:
        new_channel = await client.get_entity(NEW_CHANNEL_ID)  # Resolve channel entity
    except Exception as e:
        print(f"Failed to resolve new channel: {str(e)}")
        return

    for user_id, username in invalid_users:
        try:
            await client(InviteToChannelRequest(channel=new_channel, users=[user_id]))
            print(f"Added user {user_id} ({username}) to the new channel.")
        except Exception as e:
            print(f"Failed to add user {user_id} to the new channel: {str(e)}")

async def main():
    # Authenticate using a user account
    async with TelegramClient('session_name3', api_id, api_hash) as client:
        await add_invalid_users_to_channel(client)

if __name__ == '__main__':
    asyncio.run(main())
