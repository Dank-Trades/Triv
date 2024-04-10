import discord
from discord.ext import commands
import requests
import re
import pandas as pd

class utils(commands.Cog):
    def __init__(self, client):
        self.client = client

    def extract_item_and_amount(self, text):
        pattern = r'\*\*(\d+)x <a?:(?:[a-zA-Z0-9_]+):[0-9]+> ([^\*]+)\*\*'
        match = re.search(pattern, text)

        if match:
            amount = match.group(1)
            item_name = match.group(2)
            return int(amount), item_name
        else:
            return None, None

    def process_shorthand(self, input_str):
        try:
            return float(input_str)
        except ValueError:
            pass

        shorthand_map = {
            'k': 1e3, 'm': 1e6, 'mil': 1e6, 'b': 1e9, 'bil': 1e9,
            't': 1e12, 'trillion': 1e12, 'million': 1e6, 'billion': 1e9
        }

        regex = r'^([+-]?[0-9]*\.?[0-9]+)([a-zA-Z]+)?$'
        match = re.match(regex, input_str)

        if not match:
            return 0

        numeric_part = match.group(1)
        shorthand_part = match.group(2)

        try:
            numeric_value = float(numeric_part)
        except ValueError:
            return 0

        if shorthand_part:
            shorthand_part = shorthand_part.lower()
            multiplier = shorthand_map.get(shorthand_part)
            if multiplier:
                return numeric_value * multiplier
            else:
                return 0

        return numeric_value
    
    def check_start_price(self, item : str, item_amount : int, price : int):

        file = pd.read_csv('auctions.csv')

        avg_price = int(file.loc[ file['name'] == item, 'value'].values[0]) * item_amount

        if avg_price < 5e5:
            return False

        if avg_price <= 1e7:
            max_price = avg_price * 0.6
        
        elif avg_price <= 3e7:
            max_price = avg_price * 0.55
        
        elif avg_price <= 7e7:
            max_price = avg_price * 5
        
        elif avg_price <= 12e7:
            max_price = avg_price * 0.45
        
        elif avg_price <= 2e8:
            max_price = avg_price * 0.4

        if price > max_price:
            return False
        else :
            return True
    


    async def bid(self, ctx, bid, min_increment):
        loop_cog = self.client.get_cog('loops')

        if loop_cog.auc_count.is_running():
            full_int = self.process_shorthand(bid)
            full_int = int(full_int)

            if self.client.first_bid[ctx.guild.id] == True:
                
                if full_int < float(self.client.start_price[ctx.channel.id]):
                    pass

                elif full_int >= float(self.client.start_price[ctx.channel.id]):
                    self.client.last_bids[ctx.channel.id] = []
                    self.client.last_bids[ctx.channel.id].append(full_int)
                    self.client.bidders[ctx.channel.id] = []
                    self.client.bidders[ctx.channel.id].append(ctx.author.id)


                    self.client.curr_bids[ctx.channel.id] = full_int
                    self.client.first_bid[ctx.guild.id] = False
                    await ctx.channel.send(f'{ctx.author.mention} bidded **{format(full_int, ",")}**')

                    loop_cog.auc_count.restart()

            if self.client.first_bid[ctx.guild.id] == False:

                if full_int < float(self.client.curr_bids[ctx.channel.id]) + min_increment:
                    pass
                
                elif full_int >= float(self.client.curr_bids[ctx.channel.id]) + min_increment:
                    self.client.last_bids[ctx.channel.id].append(full_int)
                    self.client.bidders[ctx.channel.id].append(ctx.author.id)
                    self.client.curr_bids[ctx.channel.id] = full_int
                    await ctx.channel.send(f'{ctx.author.mention} bid **{format(full_int, ",")}**')
                    loop_cog.auc_count.restart()
        else:
            try:
                await ctx.message.add_reaction('‼')
            except:
                pass

    async def get_auction_channel(self, arg):
        doc = await self.client.db.guild_config.find_one({"guild_id": arg.guild.id})
        if doc:
            return arg.guild.get_channel(doc["auction_channel"])

    async def get_auctioneer_role(self, arg):
        doc = await self.client.db.guild_config.find_one({"guild_id": arg.guild.id})
        if doc:
            return discord.utils.get(arg.guild.roles, id=doc["auctioneer_role"])

    async def get_auction_ping(self, arg):
        doc = await self.client.db.guild_config.find_one({"guild_id": arg.guild.id})
        if doc:
            return discord.utils.get(arg.guild.roles, id=doc["ping_role"])

    async def get_auction_access(self, arg):
        doc = await self.client.db.guild_config.find_one({"guild_id": arg.guild.id})
        if doc:
            return discord.utils.get(arg.guild.roles, id=doc["auction_access"])

    async def get_auction_log(self, arg):
        doc = await self.client.db.guild_config.find_one({"guild_id": arg.guild.id})
        if doc:
            return discord.utils.get(arg.guild.channels, id=doc["auction_log"])

    async def get_tradeout_channel(self, arg):
        doc = await self.client.db.guild_config.find_one({"guild_id": arg.guild.id})
        if doc:
            return discord.utils.get(arg.guild.channels, id=doc["tradeout_channel"])

    async def get_tradeout_role(self, arg):
        doc = await self.client.db.guild_config.find_one({"guild_id": arg.guild.id})
        if doc:
            return discord.utils.get(arg.guild.roles, id=doc["tradeout_role"])

    @staticmethod
    def channel_open(channel, role):
        overwrites = channel.overwrites_for(role)
        overwrites.send_messages = True
        overwrites.read_messages = True
        return overwrites

    @staticmethod
    def channel_close(channel, role):
        overwrites = channel.overwrites_for(role)
        overwrites.send_messages = False
        overwrites.read_messages = True
        return overwrites

    @staticmethod
    def tradeout_access(channel, member, set : bool):
        overwrites = channel.overwrites_for(member)
        overwrites.send_messages = set
        return overwrites

    @staticmethod
    def poll_check(channel_id, token, msg_id):
        url = f"https://discord.com/api/v9/channels/{channel_id}/messages/{msg_id}"
        headers = {'Authorization': f'Bot {token}'}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            messages = response.json()
            return 'poll' in messages
        else:
            return False

async def setup(client):
    await client.add_cog(utils(client))