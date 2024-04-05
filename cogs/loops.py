import discord
import sys
from cogs.utils import utils
import re
from discord.ext import commands
from discord.ext import tasks, commands
import json

class mark_log(discord.ui.View):
    def __init__(self, client):
        super().__init__()
        self.value = None
        self.client = client

         

class loops(commands.Cog):
    def __init__(self, client):
        self.client = client

        self.client.auction_guild_id = 719180744311701505
        self.client.payout_msgs = {}

    

    @tasks.loop(seconds=10.0, count= 4)
    async def auc_count(self):

        guild = self.client.get_guild(self.client.auction_guild_id)
        

        num = await self.client.db.fetchrow('SELECT "auction_channel" FROM "guild_config" WHERE "guild_id" = $1', guild.id)
        channel_id = int(''.join(re.findall(r'\d+', f'{num}')))
        channel = discord.utils.get(guild.channels, id = channel_id)

        num1 = await self.client.db.fetchrow('SELECT "tradeout_channel" FROM "guild_config" WHERE "guild_id" = $1', guild.id)
        channel_id_2 = int(''.join(re.findall(r'\d+', f'{num1}')))
        channel_2 = discord.utils.get(guild.channels, id = channel_id_2)

        num2 = await self.client.db.fetchrow('SELECT "auction_access" FROM "guild_config" WHERE "guild_id" = $1', guild.id)
        role_id = int(''.join(re.findall(r'\d+', f'{num2}')))
        role = discord.utils.get( channel.guild.roles, id = role_id)

        num3 = await self.client.db.fetchrow('SELECT "tradeout_role" FROM "guild_config" WHERE "guild_id" = $1', guild.id)
        role_id_2 = int(''.join(re.findall(r'\d+', f'{num3}')))
        role_2 = discord.utils.get( channel.guild.roles, id = role_id_2)

        num4 = await self.client.db.fetchrow('SELECT "auction_log" FROM "guild_config" WHERE "guild_id" = $1', guild.id)
        channel_id_3 = num4['auction_log']
        auction_log = discord.utils.get( guild.channels, id = channel_id_3)

        


        if self.auc_count.current_loop == 0:
            await channel.set_permissions(role, overwrite = utils.channel_open(channel, role))
        if self.auc_count.current_loop == 1:
            await channel.send(f'Going Once')
        if self.auc_count.current_loop == 2:
            await channel.send(f'Going Twice')
        if self.auc_count.current_loop == 3:
            self.auc_count.stop()
            await channel.set_permissions(role, overwrite = utils.channel_close(channel, role))
            try :

                winner = discord.utils.get(guild.members, id = int(self.client.bidders[channel_id][-1]))

                winner_embed = discord.Embed(color=discord.Color.from_str('#AC94F4'), title='Auction ended successfully.')
                winner_embed.description = f'{winner.mention} won the auction for **{self.client.last_bids[channel_id][-1]}**. Please head over to {channel_2.mention}.'

                self.client.log.update({
                    'buyer' : winner,
                    'coins' : self.client.curr_bids[channel.id]
                })


                await channel.send('Sold!')
                msg = await channel.send(embed=winner_embed)
                await channel_2.set_permissions(winner, overwrite = utils.tradeout_access(channel, winner))

                payout_log = discord.Embed(color=discord.Color.blue(), title='Auction Logs')
                payout_log.description = (
                                    f"Buyer : {self.client.log['buyer'].mention}\n"
                                    f"Seller : {self.client.log['seller'].mention}\n"
                                    f"Item : {self.client.log['item']}\n"
                                    f"Amount : {self.client.log['item_amount']}\n"
                                    f"Coins : {int(self.client.log['coins'])}"
                                )
                payout_log.set_footer( text= f'auctioner : {self.client.log["auctioneer"].id}')

                view = mark_log(client=self.client)


                view.add_item(discord.ui.Button(label='Jump to auction', url= msg.jump_url))

                embed_msg = await auction_log.send(embed=payout_log, view=view)
                msg1 = await auction_log.send(f"/serverevents payout user:{self.client.log['seller'].id} quantity:{int(self.client.log['coins'])}")
                msg2 = await auction_log.send(f"/serverevents payout user:{self.client.log['buyer'].id} quantity:{self.client.log['item_amount']} item:{self.client.log['item']}")

                self.client.payout_msgs.update({
                    embed_msg.id : [msg1, msg2]
                })

                

            except IndexError:

                payout_log = discord.Embed(color=discord.Color.red(), title='Auction Logs - Cancelled')
                payout_log.description = (
                                    f"Buyer : \n"
                                    f"Seller : {self.client.log['seller'].mention}\n"
                                    f"Item : {self.client.log['item']}\n"
                                    f"Amount : {self.client.log['item_amount']}\n"
                                    f"Coins : "
                                )
                payout_log.set_footer( text= f'auctioner : {self.client.log["auctioneer"].id}')

                end_embed = discord.Embed(color=discord.Color.from_str('#AC94F4'), title='Auction ended unsuccessfully.')
                end_embed.description = f'Auction ended without any bidders.'

                await channel.send(embed = end_embed)
                embed_msg = await auction_log.send(embed = payout_log, view = mark_log(self.client))
                msg = await auction_log.send(f"/serverevents payout user:{self.client.log['seller'].id} quantity:{self.client.log['item_amount']} item:{self.client.log['item']}")

                self.client.payout_msgs.update({
                    embed_msg.id : [msg]
                })

            self.client.last_bids.clear()
            self.client.bidders.clear()
            

       
    @commands.Cog.listener()
    async def on_message(self, msg):
        guild = self.client.get_guild(self.client.auction_guild_id)
        num = await self.client.db.fetchrow('SELECT "auction_channel" FROM "guild_config" WHERE "guild_id" = $1', guild.id)
        channel_id = int(''.join(re.findall(r'\d+', f'{num}')))
        channel = discord.utils.get(guild.channels, id = channel_id)

        num2 = await self.client.db.fetchrow('SELECT "auctioneer_role" FROM "guild_config" WHERE "guild_id" = $1', guild.id)
        auctioneer_role = discord.utils.get(msg.guild.roles, id = num2['auctioneer_role'])


        
        

        
        if self.auc_count.is_running():
            if msg.author == self.client.user:
                return
            if auctioneer_role in msg.author.roles:
                return
            if msg.channel != channel:
                return
            
            else:
                with open('config.json', 'r') as f:
                    data = json.load(f)
                    token = data['TokeN']

                if utils.poll_check(msg.channel.id, token, msg.id):
                    await msg.delete()
                
                else:
                    await msg.delete(delay = 3)
        else:
            return
        

async def setup(client):
    await client.add_cog(loops(client))
