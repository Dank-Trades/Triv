import discord
import re
from discord.ext import commands
from discord import app_commands
import requests

class utils(commands.Cog):

        def __init__(self, client):
                self.client = client

        async def get_auction_channel(self, arg):
                num = await self.client.db.fetchrow('SELECT "auction_channel" FROM "guild_config" WHERE "guild_id" = $1', arg.guild.id)
                channel_id = num['auction_channel']
                return self.client.get_channel(channel_id)

        async def get_auctioneer_role(self, arg):
                num = await self.client.db.fetchrow('SELECT "auctioneer_role" FROM "guild_config" WHERE "guild_id" = $1', arg.guild.id)
                role_id = num['auctioneer_role']
                return discord.utils.get(arg.guild.roles, id = role_id)

        async def get_auction_ping(self, arg):
                num = await self.client.db.fetchrow('SELECT "ping_role" FROM "guild_config" WHERE "guild_id" = $1', arg.guild.id)
                role_id = num['ping_role']
                return discord.utils.get(arg.guild.roles, id = role_id)

        async def get_auction_access(self, arg):
                num = await self.client.db.fetchrow('SELECT "auction_access" FROM "guild_config" WHERE "guild_id" = $1', arg.guild.id)
                role_id = num['auction_access']
                return discord.utils.get(arg.guild.roles, id = role_id)
        
        async def get_auction_log(self, arg):
                num = await self.client.db.fetchrow('SELECT "auction_log" FROM "guild_config" WHERE "guild_id" = $1', arg.guild.id)
                channel_id = num['auction_log']
                return discord.utils.get(arg.guild.channels, id = channel_id)

        async def get_tradeout_channel(self, arg):
                num = await self.client.db.fetchrow('SELECT "tradeout_channel" FROM "guild_config" WHERE "guild_id" = $1', arg.guild.id)
                channel_id = num['tradeout_channel']
                return discord.utils.get(arg.guild.channels, id = channel_id)

        async def get_tradeout_role(self, arg):
                num = await self.client.db.fetchrow('SELECT "tradeout_role" FROM "guild_config" WHERE "guild_id" = $1', arg.guild.id)
                role_id = num['tradeout_role']
                return discord.utils.get(arg.guild.roles, id = role_id)
        

        def channel_open(channel, role):
                overwrites = channel.overwrites_for(role)
                overwrites.send_messages = True
                overwrites.read_messages = True
                return overwrites

        def channel_close(channel, role):
                overwrites = channel.overwrites_for(role)
                overwrites.send_messages = False
                overwrites.read_messages = True
                return overwrites
        
        def tradeout_access(channel, member):
                overwrites = channel.overwrites_for(member)
                overwrites.send_messages = True
                return overwrites
        
        def poll_check(channel_id, token, msg_id):

                url = f"https://discord.com/api/v9/channels/{channel_id}/messages/{msg_id}"
                
                header = {
                        'Authorization': f'Bot {token}'
                }

                response = requests.get(url, headers=header)

                if response.status_code == 200:
                        messages = response.json()
                        
                        try :
                                if messages['poll']:
                                        return True

                        except KeyError:
                                return False

                else:

                        return False


async def setup(client):
        await client.add_cog(utils(client))
