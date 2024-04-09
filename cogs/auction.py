import discord
import json
import sys
sys.path.append(r'/home/container/')
from cogs.loops import mark_log
from cogs.utils import utils
import re
import asyncio
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Group, command
from discord.ext import tasks, commands
import pandas as pd



class auc_buttons(discord.ui.View):
    def __init__(self, author):
        self.author = author
        super().__init__()
        self.value = None

    @discord.ui.button(label='Start')
    async def auc_start(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        auction_cog = interaction.client.get_cog('loops')
        channel = await utils(interaction.client).get_auction_channel(interaction)
        role = await utils(interaction.client).get_auction_access(interaction)
        button.disabled = True
        await interaction.message.edit(view=self)
        auction_cog.auc_count.start()
        await channel.set_permissions(role, overwrite = utils.channel_open(channel, role))
        await interaction.followup.send('Auction Started!')
        await interaction.channel.send('Auction has started! Run `t!bid <amount><unit>` to bid. E.g. `t!bid 700k` | `t!bid 6m`.')
        await interaction.channel.send('You can bid just by saying the amount, too! E.g. `3m` | `900k`')
        
    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.author.id

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        org_msg = await interaction.original_response()

        auction_cog = interaction.client.get_cog('loops')
        auc_channel = await utils(interaction.client).get_auction_channel(interaction)
        auc_log = await utils(interaction.client).get_auction_log(interaction)

        role = await utils(interaction.client).get_auction_access(interaction)
        button.disabled = True
        await interaction.message.edit(view=self)

        payout_log = discord.Embed(color=discord.Color.red(), title='Auction Logs - Cancelled')
        payout_log.description = (
                            f"Buyer : \n"
                            f"Seller : {interaction.client.log['seller'].mention}\n"
                            f"Item : {interaction.client.log['item']}\n"
                            f"Amount : {interaction.client.log['item_amount']}\n"
                            f"Coins : "
                        )
        payout_log.set_footer( text= f'auctioner : {interaction.client.log["auctioneer"].id}')

        link_button = mark_log(interaction.client)
        link_button.add_item(discord.ui.Button(label='Jump to auction', url= org_msg.jump_url))

        embed_msg = await auc_log.send(embed=payout_log, view=link_button)

        msg = await auc_log.send(f"/serverevents payout user:{interaction.client.log['seller'].id} quantity:{interaction.client.log['item_amount']} item:{interaction.client.log['item']}")

        interaction.client.payout_msgs.update({
            embed_msg.id : [msg]
        })

        await interaction.followup.send('Auction cancelled!')

    
    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.author.id


class auction(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.client.last_bids  = {}
        self.client.bidders = {}
        self.client.start_price = {}
        self.client.curr_bids = {}
        self.client.first_bid = {}
        self.client.log = {
                'auctioneer' : 0,
                'item' : '',
                'item_amount' : '',
                'seller' : 0,
                'buyer' : 0,
                'coins' : 0
        }
        self.utils = utils(self.client)
    

    auc_group = Group(name = 'auction', description= 'just a group for auction subcommands')

    @auc_group.command(name = 'host', description = 'Host an auction' )
    async def auction_host(self, interaction : discord.Interaction, member : discord. Member, items : str, item_amount : int,  starting_price : str):

        await interaction.response.defer()

        full_int = self.utils.process_shorthand(starting_price)
        full_int = int(full_int)
  
        embed = discord.Embed(title = f'{item_amount} {items} auction', description= f'starting bid : {format(full_int, ",")} \nseller : {member.mention}', color = discord.Color.from_str('0x2F3136'))
        embed.set_footer(text= 'auction will start when there\'s 3 reacts')

        ping_role = await utils(interaction.client).get_auction_ping(interaction)
        auction_channel = await utils(interaction.client).get_auction_channel(interaction)

        if interaction.channel != auction_channel:

            await interaction.followup.send('This is not your configured auction channel.', ephemeral= True)

        else:

            self.client.start_price[interaction.channel.id] = full_int
            self.client.first_bid[interaction.guild.id] = True
            self.client.last_bids[interaction.channel.id] = []
            self.client.bidders[interaction.channel.id] = []
            self.client.curr_bids[interaction.channel.id] = []

            msg = await interaction.original_response()

            self.client.log.update({ 
                'auction_id' : msg.id,
                'auctioneer' : interaction.user,
                'item' : items,
                'item_amount' : item_amount,
                'seller' : member
            })


            await interaction.followup.send(embed=embed, view=auc_buttons(interaction.user))
            await interaction.channel.send(content=f'{ping_role.mention}', allowed_mentions = discord.AllowedMentions(roles=True))
            await msg.add_reaction('⭐')

    @auction_host.autocomplete('items')
    async def autocomplete_callback(self, interaction : discord.Interaction, current : str):
        
        items = pd.read_csv('Item_Pricing_v2_-_IMPORT_1.csv')

        item_list = [item for item in items['name']]

        return [app_commands.Choice(name=suggestion, value=suggestion) for suggestion in item_list if current.lower() in suggestion.lower()]

    @commands.command(name='bid', aliases = ['b'])
    async def auction_bid(self, ctx, bid : str):

        auction_channel = await utils(self.client).get_auction_channel(ctx)

        record = await self.client.db.guild_config.find_one({'guild_id' : ctx.guild.id})

        min_increment = record['min_increment']

        if ctx.channel != auction_channel:
            return

        if ctx.author == self.client.log['seller']:
            return
    
        else :
            await self.utils.bid(ctx, bid, min_increment)
    
    @commands.group(name='queue', aliases=['q'], invoke_without_command=True)
    @commands.has_role(750117211087044679)
    async def auction_queue(self, ctx, page: str = '1'):
        try:
            page = int(page)
        except ValueError:
            page = 1

        auction_queue = await self.client.db.auction_queue.find_one({'guild_id' : ctx.guild.id})

        if not auction_queue:
            await self.client.db.auction_queue.insert_one({'guild_id' : ctx.guild.id, 'queue' : []})
            return await ctx.send('No auctions in queue.')

        # schema = {
        #     'guild_id' : ctx.guild.id,
        #     'queue' : []
        # }

        # the queue is = {
        #     message_id : str,
        #     host : str,
        #     item : str,
        #     item_amount : int,
        #     starting_price : int
        # }

        # process the page, if it is invalid = 1 if it is out of range = 1

        if page < 1:
            page = 1
        elif page > len(auction_queue['queue']) // 5 + 1:
            page = len(auction_queue['queue']) // 5 + 1

        auctions = auction_queue['queue']
        if auctions == []:
            return await ctx.send('No auctions in queue.')
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
                message_id = auction['message_id']
                msg_link = f'https://discord.com/channels/719180744311701505/782483247619112991/{message_id}'
                embed.add_field(name = f'{auction["item_amount"]} {auction["item"]} (index: {i + 1})', value = f'host : <@{auction["host"]}>\nstarting bid : [{format(auction["starting_price"], ",")}]({msg_link})', inline = False)
            embed.set_footer(text = f'Page {page}/{pages}')
            await ctx.send(embed = embed)

    # this is a subcommand of the queue command
    @auction_queue.command(name='remove', description = 'Remove an auction from the queue', aliases = ['r'])
    @commands.has_any_role(750117211087044679)
    async def auction_queue_remove(self, ctx, index : str = ""):
        try:
            index = int(index) - 1
        except ValueError:
            return await ctx.send('Invalid index.')

        auction_queue = await self.client.db.auction_queue.find_one({'guild_id' : ctx.guild.id})

        if not auction_queue:
            return await ctx.send('No auctions in queue.')
        else:
            auctions = auction_queue['queue']
            try:
                auction = auctions.pop(index)
            except IndexError:
                return await ctx.send('Invalid index.')
            await self.client.db.auction_queue.update_one({'guild_id' : ctx.guild.id}, {'$set' : {'queue' : auctions}})
            await ctx.send(f'Removed the auction : {auction["item_amount"]} {auction["item"]} auction hosted by {auction["host"]}')

    @auction_queue.command(name='ra')
    @commands.has_any_role(750117211087044679)
    async def auction_queue_remove_all(self, ctx):
        

        auction_queue = await self.client.db.auction_queue.find_one({'guild_id' : ctx.guild.id})

        if not auction_queue:
            return
        else:
            await self.client.db.auction_queue.update_one({'guild_id' : ctx.guild.id}, {'$set' : {'queue' : [] }})
            await ctx.send(f'Removed all auctions from the queue!')

    @commands.command(name='test')
    async def test(self, ctx):
        embed = discord.Embed(title = 'Action Confirmed', description = 'Are you sure you want to donate your items?\n\n> You will donate **1x :banknote: Bank Note**', color = discord.Color.from_str('0x2F3136'))
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label='Confirm', style=discord.ButtonStyle.green))
        view.add_item(discord.ui.Button(label='Cancel', style=discord.ButtonStyle.red))
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name='test')
    async def test_command(self, interaction : discord.Interaction):
        embed = discord.Embed(title = 'Action Confirmed', description = 'Are you sure you want to donate your items?\n\n> You will donate **1x <:dank_banknote:831787534820442112> Bank Note**', color = discord.Color.from_str('0x2F3136'))
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label='Confirm', style=discord.ButtonStyle.green))
        view.add_item(discord.ui.Button(label='Cancel', style=discord.ButtonStyle.red))
        await interaction.response.send_message(embed=embed, view=view)

    @commands.command(name= 'revert', aliases = ['r'])
    async def auction_revert(self, ctx):
        
        auctioneer_role = await utils(self.client).get_auctioneer_role(ctx)
        auction_channel = await utils(self.client).get_auction_channel(ctx)

        if auctioneer_role not in ctx.author.roles:
            
            return

        if ctx.channel != auction_channel:
            
            return
    
        else :

            loop_cog = self.client.get_cog('loops')

            
            if len(self.client.last_bids[ctx.channel.id]) >= 2:
                reverted_bid = self.client.last_bids[ctx.channel.id][-2]

                self.client.last_bids[ctx.channel.id].pop(-1)
                reverted_bidder = discord.utils.get(ctx.guild.members, id = int(self.client.bidders[ctx.channel.id][-2]))
                self.client.bidders[ctx.channel.id].pop(-1)
                
                reverted_bid = int(reverted_bid)
                full_int = reverted_bid

                self.client.start_price[ctx.channel.id] = full_int
                self.client.curr_bids[ctx.channel.id] = full_int
                
                await ctx.send(f'{reverted_bidder.mention} bid **{format(reverted_bid, ",")}**')
            
            else :

                self.client.last_bids[ctx.channel.id].pop(-1)
                self.client.bidders[ctx.channel.id].pop(-1)
                self.client.first_bid[ctx.guild.id] = True
                await ctx.send(f'Bid reverted and price set to the default price again.')
            
            
            loop_cog.auc_count.restart()

    @auc_group.command(name='end', description = 'Ends the ongoing auction')
    async def auction_end(self, interaction : discord.Interaction):
        auction_channel = await utils(interaction.client).get_auction_channel(interaction)
        
        if interaction.channel != auction_channel:

            await interaction.response.send_message('You can only use this in the configured auction channel.')

        else:

            auc_cog = self.client.get_cog('loops')
            
            if auc_cog.auc_count.is_running():

                auc_cog.auc_count.cancel()
                self.client.first_bid[interaction.guild.id] = True
                role = await utils(interaction.client).get_auction_access(interaction)
                await auction_channel.set_permissions(role, overwrite= utils.channel_close(auction_channel, role))
                await interaction.response.send_message(f'Auction Ended by {interaction.user.mention}. \nChannel locked now.')
                self.client.last_bids  = {}
                self.client.bidders = {}
                self.client.start_price = {}
                self.client.curr_bids = {}
                self.client.first_bid = {}
            
            else :

                await interaction.response.send_message('There\'s no auction running!', ephemeral= True)

    @commands.command()
    @commands.has_any_role(750117211087044679)
    async def ato(self, ctx, member : discord.Member):
        tradeout_channel = self.utils.get_tradeout_channel(ctx)

        permissions = tradeout_channel.permissions_for(member)

        if permissions.send_messages:
            await tradeout_channel.set_permissions(member, send_messages = None)
        else :
            await tradeout_channel.set_permissions(member, send_messages = True)
        
        await ctx.message.add_reaction('✅')
        

    @commands.command()
    @commands.has_any_role(750117211087044679)
    async def adump(self, ctx):
        members = ''

        tradeout_channel = self.utils.get_tradeout_channel(ctx)

        for overwrite in tradeout_channel.overwrites:
            if isinstance(overwrite, discord.Member) and overwrite.permissions_in(tradeout_channel).send_messages:
            
                members = members + f'{overwrite.display_name}({overwrite.id})\n'
        
        await ctx.send(members)


    @commands.command()
    @commands.has_any_role(750117211087044679)
    async def aclear(self, ctx):

        tradeout_channel = self.utils.get_tradeout_channel(ctx)

        for overwrite in tradeout_channel.overwrites:
            if isinstance(overwrite, discord.Member) and overwrite.permissions_in(tradeout_channel).send_messages:
                await tradeout_channel.set_permissions(overwrite, send_messages = None)
        
        await ctx.message.add_reaction('✅')
            

        



        

    @commands.Cog.listener()
    async def on_message(self, msg):
        queue = 782483247619112991
        command_name = 'serverevents donate'
        validate_title = 'Action Confirmed'

        if msg.channel.id != queue or msg.author.bot:
            return
        
        bid_amount = self.utils.process_shorthand(msg.content)
        bid_amount = int(bid_amount)

        if msg.reference is not None:
            replied_to_message = await msg.channel.fetch_message(msg.reference.message_id)
            guild_queue = await self.client.db.auction_queue.find_one({'guild_id' : msg.guild.id})

            if not guild_queue:
                await self.client.db.auction_queue.insert_one({'guild_id' : msg.guild.id, 'queue' : []})
                guild_queue = await self.client.db.auction_queue.find_one({'guild_id' : msg.guild.id})

            user_queue = next((item for item in guild_queue['queue'] if item['host'] == msg.author.id), None)
            
            if bid_amount <= 0 or replied_to_message.interaction is None or replied_to_message.interaction.name != command_name or replied_to_message.interaction.user.id != msg.author.id or user_queue is not None:
                return await msg.add_reaction('❌')
            
            embed = replied_to_message.embeds[0]
            amount, item_name = self.utils.extract_item_and_amount(embed.description)

            if embed.title != validate_title:
                return await msg.add_reaction('❌')

            await msg.add_reaction('✅')
            await self.client.db.auction_queue.update_one({'guild_id' : msg.guild.id}, {'$push' : {'queue' : {'message_id' : replied_to_message.id, 'host' : msg.author.id, 'item' : item_name, 'item_amount' : amount, 'starting_price' : bid_amount}}}, upsert = True)

            return await msg.reply(f'Your starting bid for {amount} {item_name} is {format(bid_amount, ",")}.', mention_author = True)
        else:
            return await msg.add_reaction('❌')

    @commands.Cog.listener()
    async def on_message_edit(self, message_before, message_after):
        queue = 782483247619112991
        command_name = 'serverevents donate'
        validate_title = 'Action Confirmed'

        if message_after.channel.id != queue or message_after.author.bot:
            return
        
        bid_amount = self.utils.process_shorthand(message_after.content)
        bid_amount = int(bid_amount)

        if message_after.reference is not None:
            replied_to_message = await message_after.channel.fetch_message(message_after.reference.message_id)
            guild_queue = await self.client.db.auction_queue.find_one({'guild_id' : message_after.guild.id})

            if not guild_queue:
                await self.client.db.auction_queue.insert_one({'guild_id' : message_after.guild.id, 'queue' : []})
                guild_queue = await self.client.db.auction_queue.find_one({'guild_id' : message_after.guild.id})

            user_queue = next((item for item in guild_queue['queue'] if item['host'] == message_after.author.id), None)
            
            await message_after.clear_reactions()
            
            if bid_amount <= 0 or replied_to_message.interaction is None or replied_to_message.interaction.name != command_name or replied_to_message.interaction.user.id != message_after.author.id or user_queue is None:
                return await message_after.add_reaction('❌')
        
            embed = replied_to_message.embeds[0]

            if embed.title != validate_title:
                return await message_after.add_reaction('❌')
            
            guild_queue['queue'] = [item for item in guild_queue['queue'] if item != user_queue]
            user_queue['starting_price'] = bid_amount
            guild_queue['queue'].append(user_queue)

            await message_after.add_reaction('✅')
            await self.client.db.auction_queue.update_one({'guild_id' : message_after.guild.id}, {'$set' : {'queue' : guild_queue['queue']}}, upsert = True)

            # return await message_after.reply(f'Your starting bid for {amount} {item_name} is {format(bid_amount, ",")}.', mention_author = True)
                


        

    



async def setup(client):
    await client.add_cog(auction(client))