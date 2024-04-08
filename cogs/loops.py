import discord
from discord.ext import tasks, commands
import json
import re
from cogs.utils import utils  # Ensure utils are adapted for MongoDB or your specific use case

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
        self.utils = utils(self.client)

    @tasks.loop(seconds=10.0, count=4)
    async def auc_count(self):
        guild = self.client.get_guild(self.client.auction_guild_id)
        config = await self.client.db.guild_config.find_one({"guild_id": guild.id})
        
        if not config:
            return  # Configuration not found for the guild
        
        auction_channel = guild.get_channel(config["auction_channel"])
        tradeout_channel = guild.get_channel(config["tradeout_channel"])
        auction_access_role = guild.get_role(config["auction_access"])
        tradeout_role = guild.get_role(config["tradeout_role"])
        auction_log = guild.get_channel(config["auction_log"])
        
        # Your logic here, following is an adaptation of the original if blocks
        
        if self.auc_count.current_loop == 0:
            await auction_channel.set_permissions(auction_access_role, overwrite=utils.channel_open(auction_channel, auction_access_role))
        elif self.auc_count.current_loop == 1:
            await auction_channel.send('Going Once')
        elif self.auc_count.current_loop == 2:
            await auction_channel.send('Going Twice')
        elif self.auc_count.current_loop == 3:
            self.auc_count.stop()
            await auction_channel.set_permissions(auction_access_role, overwrite=utils.channel_close(auction_channel, auction_access_role))
            try:
                channel_id = auction_channel.id
                winner = discord.utils.get(guild.members, id=int(self.client.bidders[channel_id][-1]))

                winner_embed = discord.Embed(color=discord.Color.from_str('#AC94F4'), title='Auction ended successfully.')
                winner_embed.description = f'{winner.mention} won the auction for **{format(self.client.last_bids[channel_id][-1], ",")}**. Please head over to {tradeout_channel.mention}.'

                self.client.log.update({
                    'buyer': winner,
                    'coins': self.client.curr_bids[channel_id]
                })

                self.client.last_bids.clear()
                self.client.bidders.clear()

                await auction_channel.send('Sold!')
                msg = await auction_channel.send(embed=winner_embed)
                await tradeout_channel.set_permissions(winner, overwrite=utils.tradeout_access(tradeout_channel, winner))

                payout_log = discord.Embed(color=discord.Color.blue(), title='Auction Logs')
                payout_log.description = (
                    f"Buyer : {self.client.log['buyer'].mention}\n"
                    f"Seller : {self.client.log['seller'].mention}\n"
                    f"Item : {self.client.log['item']}\n"
                    f"Amount : {self.client.log['item_amount']}\n"
                    f"Coins : {int(self.client.log['coins'])}"
                )
                payout_log.set_footer(text=f'auctioner : {self.client.log["auctioneer"].id}')

                view = mark_log(client=self.client)

                view.add_item(discord.ui.Button(label='Jump to auction', url=msg.jump_url))

                embed_msg = await auction_log.send(embed=payout_log, view=view)
                msg1 = await auction_log.send(f"/serverevents payout user:{self.client.log['seller'].id} quantity:{int(self.client.log['coins'])}")
                msg2 = await auction_log.send(f"/serverevents payout user:{self.client.log['buyer'].id} quantity:{self.client.log['item_amount']} item:{self.client.log['item']}")

                self.client.payout_msgs.update({
                    embed_msg.id: [msg1, msg2]
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
                payout_log.set_footer(text=f'auctioner : {self.client.log["auctioneer"].id}')

                end_embed = discord.Embed(color=discord.Color.from_str('#AC94F4'), title='Auction ended unsuccessfully.')
                end_embed.description = f'Auction ended without any bidders.'

                msg0 = await auction_channel.send(embed=end_embed)

                view = mark_log(client=self.client)

                view.add_item(discord.ui.Button(label='Jump to auction', url=msg0.jump_url))

                embed_msg = await auction_log.send(embed=payout_log, view=view)
                msg = await auction_log.send(f"/serverevents payout user:{self.client.log['seller'].id} quantity:{self.client.log['item_amount']} item:{self.client.log['item']}")

                self.client.payout_msgs.update({
                    embed_msg.id: [msg]
                })

                self.client.last_bids.clear()
                self.client.bidders.clear()

    @commands.Cog.listener()
    async def on_message(self, msg):
        if not self.auc_count.is_running():
            return
        
        guild = self.client.get_guild(self.client.auction_guild_id)
        
        if (guild is None):
            return
        
        config = await self.client.db.guild_config.find_one({"guild_id": guild.id})
        
        if not config:
            return  # Configuration not found for the guild
        
        auction_channel = guild.get_channel(config["auction_channel"])
        auctioneer_role = guild.get_role(config["auctioneer_role"])
        min_increment = config['min_increment']

        await self.utils.bid(msg ,msg.content, min_increment)
        
        if msg.author == self.client.user or auctioneer_role in msg.author.roles or msg.channel != auction_channel:
            return
        
        else:            
            with open('config.json', 'r') as f:
                data = json.load(f)
                token = data['TokeN']

                if utils.poll_check(msg.channel.id, token, msg.id):
                    await msg.delete()
                
                else:
                    await msg.delete(delay=3)
                
        

async def setup(client):
    await client.add_cog(loops(client))
