import discord
import asyncio
import sys
import argparse
import re
import time
import tqdm

# Set your defaults below, or specify with the respective arguments
prefix = "#DEL"
token = ""
heartbeat = 86400
serverpurge = "#PS"
nooutput = True
count_before_delete = False

# Helper function to check if a string contains numbers
def has_numbers(input_string):
    return bool(re.search(r'\d', input_string))

class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.delay_between_deletions = 1.7  # Initial delay between deletions to avoid rate limits
        self.deleted_count = 0  # Track number of deleted messages

    async def delete_message_safe(self, message):
        try:
            await message.delete()
            self.deleted_count += 1  # Increment count after successful deletion
            if not nooutput:
                tqdm.tqdm.write(f"Deleted message: {message.content}")  # Output deleted message without interfering with progress bar
        except discord.errors.HTTPException as e:
            if e.status == 429:  # Rate limit error
                retry_after = e.retry_after  # Discord tells us how long to wait
                self.delay_between_deletions += 0.1  # Increase the delay between deletions by 0.1 seconds after each rate limit
                retry_after = max(retry_after, self.delay_between_deletions)  # Ensure the delay doesn't go below the current delay between deletions
                print(f"Rate limit hit. Retrying in {retry_after} seconds.")
                await asyncio.sleep(retry_after)  # Wait for the retry_after time before proceeding
            else:
                print(f"Error occurred: {e}")  # Handle other HTTP exceptions

    async def on_message(self, message):
        # Only process messages sent by the bot itself
        if message.author != self.user:
            return

        channels = []
        contains_numbers = False
        messages_to_del = None

        # Check if the message is for server purge
        if message.content == serverpurge:
            # Get all channels and threads in the guild
            channels = [channel for channel in message.channel.guild.channels if isinstance(channel, (discord.TextChannel, discord.Thread))]
        elif prefix in message.content:  # Check if the prefix is present in the message
            tmp_str_conv = message.content.replace(prefix, '').strip()  # Remove the prefix and strip whitespace
            contains_numbers = has_numbers(tmp_str_conv)  # Check if the message contains a number

            if contains_numbers:
                messages_to_del = int(tmp_str_conv)  # Convert the number of messages to delete
            channels.append(message.channel)  # Only operate in the current channel
        else:
            return

        # Iterate over the identified channels and delete messages
        for channel in channels:
            if not nooutput:
                print(channel)  # Output channel info if nooutput is False

            try:
                # Count total messages if the user chose to count before deletion
                total_messages = 0
                if count_before_delete:
                    print(f"Counting messages in channel {channel.name}... Please wait.")
                    async for mss in channel.history(limit=messages_to_del + 1 if contains_numbers else None):
                        if mss.author == self.user:
                            total_messages += 1
                    print(f"Total messages found in channel {channel.name}: {total_messages}")

                # Now proceed to delete messages
                limit = messages_to_del + 1 if contains_numbers else None  # Set limit if specified
                progress_bar = tqdm.tqdm(total=total_messages, unit="msg", desc="Deleting messages") if count_before_delete else None
                async for mss in channel.history(limit=limit):
                    if mss.author == self.user:  # Only delete messages sent by the bot
                        await self.delete_message_safe(mss)  # Attempt to delete the message
                        await asyncio.sleep(self.delay_between_deletions)  # Add a delay between each deletion to avoid rate limits
                        if progress_bar:
                            progress_bar.update(1)  # Update the progress bar
                            if progress_bar.n == progress_bar.total:
                                progress_bar.n = progress_bar.total  # Ensure progress reaches 100%
                if progress_bar:
                    progress_bar.close()
            except discord.Forbidden:
                print(f"Permission denied for channel: {channel}")  # Handle forbidden error if lacking permissions
            except discord.HTTPException as e:
                print(f"HTTP error occurred: {e}")  # Handle other HTTP errors

# Create arguments for command line input
parser = argparse.ArgumentParser(description='Discord message purger')
parser.add_argument('-t', '--token', dest='token', type=str, help='Token to use with message purger')
parser.add_argument('-p', '--prefix', dest='prefix', type=str, help='Prefix to use with message purger')
parser.add_argument('-s', '--serverpurge', dest='serverpurge', type=str, help='Specify a prefix to use for Server Purge')
parser.add_argument('-b', '--heartbeat', dest='heartbeat', type=int, help='Heartbeat timeout to use')
parser.add_argument('-o', '--output', action='store_true', help='Enable console output of deleted messages (Good for debugging)')
parser.add_argument('-c', '--count', action='store_true', help='Count messages before deletion (Display progress bar and ETA)')
args = parser.parse_args()

# Set values from arguments or prompts
token = args.token or input("Please input a Token: ")
prefix = args.prefix or input("Please input a prefix (leave blank for the default '#DEL'): ") or "#DEL"
serverpurge = args.serverpurge or input("Please input a server purge prefix (leave blank for the default '#PS'): ") or "#PS"
heartbeat = args.heartbeat or int(input("Please input a heartbeat timeout (leave blank for the default 86400): ") or 86400)
nooutput = not args.output and input("Do you want to log console output? (Y/N): ").strip().lower() not in ["y", "yes"]
count_before_delete = args.count or input("Do you want to count messages before deletion? (Y/N): ").strip().lower() in ["y", "yes"]

# Inform user about commands
print(f"\nTo delete all messages in one channel, type: {prefix} in Discord, \nor delete a set amount of messages by adding a number after the prefix\n")
print(f"To delete all messages from the server type: {serverpurge} in Discord.")
if sys.platform.lower() in ["darwin"]:
    print("\nTo stop the program, press " + u"\u2318" + " + C in the console.")
else:
    print("\nTo stop the program, press CTRL + C in the console.")

# Run the self-bot and await prefix commands
client = MyClient(heartbeat_timeout=heartbeat, guild_subscriptions=False, chunk_guilds_at_startup=False)
client.run(token)
