import discord
from discord.ext import tasks, commands
import json
import re
import cogs.auction as auc_cog
from cogs.utils import utils  # Ensure utils are adapted for MongoDB or your specific use case

class log_button(discord.ui.View):
    def __init__(self, client):
        self.client = client
        super().__init__()
        self.value = None
        self.timeout = None

    @discord.ui.button(label='Confirm Payout', style=discord.ButtonStyle.green, custom_id='confirm_payout')
    async def confirm_payout(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # implement the mark_as_paid function here as it was for the message to reply but now this button is directly on that message
        payout_embed = interaction.message.embeds[0]
        auctioneer_id = int(interaction.message.embeds[0].footer.text.split(' : ')[1])
        sman_role = interaction.guild.get_role(719197064193638402)

        if interaction.user.id != auctioneer_id and sman_role not in interaction.user.roles:
            return interaction.author.send('You are not authorized to mark this auction as paid.')
        
        else:
            button_url = interaction.message.components[0].children[2].url
            view = mark_log(self.client)
            view.add_item(discord.ui.Button(label='Jump to auction', url=button_url))
            payout_embed.color = discord.Color.green()
            payout_embed.title = 'Auction Logs - Paid'
            await interaction.message.edit(embed=payout_embed, view=view)
            for messages in self.client.payout_msgs[interaction.message.id]:
                await messages.delete()
            del self.client.payout_msgs[interaction.message.id]
            auction_queue = await self.client.db.auction_queue.find_one({'guild_id': interaction.guild.id})
            auction_queue = auction_queue['queue']
            index = next((index for index, auction in enumerate(auction_queue) if auction.get('queue_message_id') == interaction.message.id), None)
            if index == None:
                print('WARNING : Request in queue not found.')
            else:
                auction_queue.pop(index)
                await self.client.db.auction_queue.update_one({'guild_id': interaction.guild.id}, {'$set': {'queue': auction_queue}})

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red, custom_id='cancel_payout')
    async def cancel_payout(self, interaction: discord.Interaction, button : discord.ui.Button):
        await interaction.response.defer()

        payout_embed = interaction.message.embeds[0]
        auctioneer_id = int(interaction.message.embeds[0].footer.text.split(' : ')[1])
        sman_role = interaction.guild.get_role(719197064193638402)
        payout_embed_title = payout_embed.title.title()

        if interaction.user.id != auctioneer_id and sman_role not in interaction.user.roles:
            return interaction.author.send('You are not authorized to mark this auction as paid.')
        
        else :
            button_url = interaction.message.components[0].children[2].url
            view = mark_log(self.client)
            view.add_item(discord.ui.Button(label='Jump to auction', url=button_url))
            payout_embed.color = discord.Color.green()
            if payout_embed_title == 'Auction Cancelled':
                payout_embed.title = 'Auction Cancelled'
            else :
                payout_embed.title = 'Auction Logs - Cancelled'
            payout_embed.title = 'Auction Logs - Cancelled'
            await interaction.message.edit(embed=payout_embed, view=view)
            for messages in self.client.payout_msgs[interaction.message.id]:
                await messages.delete()
            del self.client.payout_msgs[interaction.message.id]
            if payout_embed != 'Auction Cancelled':
                auction_queue = await self.client.db.auction_queue.find_one({'guild_id': interaction.guild.id})
                auction_queue = auction_queue['queue']
                index = next((index for index, auction in enumerate(auction_queue) if auction.get('queue_message_id') == interaction.message.id), None)
                if index == None:
                    print('WARNING : Request in queue not found.')
                else:
                    auction_queue.pop(index)
                    await self.client.db.auction_queue.update_one({'guild_id': interaction.guild.id}, {'$set': {'queue': auction_queue}})
            else:
                return

class queue_button(discord.ui.View):
    def __init__(self, client):
        super().__init__()
        self.client = client

    @discord.ui.button(label='Upcoming Auctions')
    async def queue(self, interaction : discord.Interaction, button : discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        page = 1
        auction_queue = await self.client.db.auction_queue.find_one({'guild_id' : interaction.guild.id})

        if not auction_queue:
            await self.client.db.auction_queue.insert_one({'guild_id' : interaction.guild.id, 'queue' : []})
            return await interaction.followup.send('No auctions in queue.', ephemeral=True)



        if page < 1:
            page = 1
        elif page > len(auction_queue['queue']) // 5 + 1:
            page = len(auction_queue['queue']) // 5 + 1

        auctions = auction_queue['queue']
        if auctions == []:
            return await interaction.followup.send('No auctions in queue.', ephemeral= True)
        else:
            pages = len(auctions) // 5 + 1
            start = (page - 1) * 5
            end = start + 5
            embed = discord.Embed(title = 'Auction Queue', color = discord.Color.from_str('0x2F3136'))

            for i in range(start, end):
                try:
                    auction = auctions[i]
                except IndexError:
                    break
                item_msg_link = f'https://discord.com/channels/719180744311701505/782483247619112991/{auction["message_id"]}'
                price_msg_link = f'https://discord.com/channels/719180744311701505/782483247619112991/{auction["msg_id"]}'
                embed.add_field(name = f'{auction["item_amount"]} {auction["item"]} (index: {i + 1})', value = f'host : <@{auction["host"]}>\nstarting bid : {format(auction["starting_price"], ",")}\nLinks : [Items]({item_msg_link}) | [Price]({price_msg_link})', inline = False)
            embed.set_footer(text = f'{page}/{pages}')
            await interaction.followup.send(embed = embed, ephemeral=True, view= auc_cog.pagination_buttons(client=interaction.client, author=interaction.user))


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

                bidders = list(set(self.client.bidders[channel_id]))

                for bidder in bidders:
                    await self.client.db.profile.update_one({'user_id': int(bidder), 'guild_id': guild.id}, {'$inc': {'auction_joined': 1}}, upsert=True)

                self.client.last_bids.clear()
                self.client.bidders.clear()

                await auction_channel.send('Sold!')
                msg = await auction_channel.send(embed=winner_embed, view=queue_button(self.client))
                await tradeout_channel.set_permissions(winner, overwrite=utils.tradeout_access(tradeout_channel, winner, set=True))
                await self.client.db.profile.update_one({'user_id': winner.id, 'guild_id': guild.id}, {'$inc': {'auction_won': 1, 'total_amount_bid': self.client.curr_bids[channel_id]}}, upsert=True)
                await self.client.db.profile.update_one({'user_id': self.client.log['seller'].id, 'guild_id': guild.id}, {'$inc': {'total_amount_sold': self.client.curr_bids[channel_id], 'total_auction_requested': 1}}, upsert=True)                
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
                view.add_item(discord.ui.Button(label='Confirm Payout', style=discord.ButtonStyle.green, custom_id='confirm_payout'))

                embed_msg = await auction_log.send(embed=payout_log, view=log_button(self.client).add_item(discord.ui.Button(label='Jump to auction', url=msg.jump_url)))
                msg1 = await auction_log.send(f"/serverevents payout user:{self.client.log['seller'].id} quantity:{int(self.client.log['coins'])}")
                msg2 = await auction_log.send(f"/serverevents payout user:{self.client.log['buyer'].id} quantity:{self.client.log['item_amount']} item:{self.client.log['item']}")

                auction_queue = await self.client.db.auction_queue.find_one({'guild_id' : msg.guild.id})

                if auction_queue:
                    auctions = auction_queue['queue']
                    index = next((index for index, auction in enumerate(auctions) if auction['host'] == self.client.log['seller'].id), None)
                    if index is None:
                        print('WARNING: Auction not found in queue.')
                    else:
                        auction = auctions[index]
                        auction.update({'queue_message_id' : embed_msg.id }) 
                        await self.client.db.auction_queue.update_one({'guild_id' : msg.guild.id}, {'$set' : {'queue' : auctions}})

                self.client.payout_msgs.update({
                    embed_msg.id: [msg1, msg2]
                })

                await self.utils.update_user_roles(guild=guild)

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
                view.add_item(discord.ui.Button(label='Confirm Payout', style=discord.ButtonStyle.green, custom_id='confirm_payout'))

                embed_msg = await auction_log.send(embed=payout_log, view=log_button(self.client).add_item(discord.ui.Button(label='Jump to auction', url=msg0.jump_url)))
                msg = await auction_log.send(f"/serverevents payout user:{self.client.log['seller'].id} quantity:{self.client.log['item_amount']} item:{self.client.log['item']}")

                self.client.payout_msgs.update({
                    embed_msg.id: [msg]
                })

                self.client.last_bids.clear()
                self.client.bidders.clear()

                await self.utils.update_user_roles(guild=guild)

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

        if msg.author == self.client.user or msg.channel != auction_channel:
            return
        
        if auctioneer_role not in msg.author.roles and not msg.author.bot:
            await utils(self.client).update_user_count(guild=msg.guild, user=msg.author, target='auction_users')
        
        if msg.author != self.client.log['seller']:    
            await self.utils.bid(msg ,msg.content, min_increment)

        if auctioneer_role not in msg.author.roles and msg.author.id != 722936235575738419:
            await msg.delete(delay=3)



        
async def setup(client):
    await client.add_cog(loops(client))
