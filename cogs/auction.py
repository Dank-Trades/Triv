import discord
import json
from cogs.utils import utils
import re
import asyncio
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Group, command
from discord.ext import tasks, commands
import pandas as pd
from datetime import datetime

MIN_BID_AMOUNT = 5e5

class auc_link(discord.ui.View):
    def __init__(self, client):
        super().__init__()
        self.client = client

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
            view = auc_link(self.client)
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
            view = auc_link(self.client)
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
        
class auc_buttons(discord.ui.View):
    def __init__(self, author, client):
        super().__init__()
        self.author = author
        self.client = client
        self.timeout = None
        self.value = None
    
    async def disable_buttons(self):
        for child in self.children:
            if child.label == 'Item Value':
                continue
            else:
                child.disabled = True
    
    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.data['custom_id'] in ['start_button', 'cancel_button']:
            return interaction.user.id == self.author.id
        return True
    

    @discord.ui.button(label='Start', custom_id='start_button')
    async def auc_start(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        auction_cog = interaction.client.get_cog('loops')
        channel = await utils(interaction.client).get_auction_channel(interaction)
        role = await utils(interaction.client).get_auction_access(interaction)
        await self.disable_buttons()
        msg = await interaction.original_response()
        users = []
        async for user in msg.reactions[0].users():
            users.append(user.mention)

        await interaction.message.edit(view=self)
        auction_cog.auc_count.start()
        await channel.set_permissions(role, overwrite = utils.channel_open(channel, role))
        await self.client.db.profile.update_one({'user_id' : interaction.user.id, 'guild_id' : interaction.guild.id}, {'$inc' : {'auction_hosted' : 1}}, upsert = True)
        await self.client.db.auc_count.update_one({'guild_id' : interaction.guild.id, 'year' : datetime.utcnow().year, 'month' : datetime.utcnow().month, 'day' : datetime.utcnow().day}, {'$inc' : {'auc_count' : 1}}, upsert = True)
        await interaction.followup.send('Auction has started!')
        await interaction.channel.send('You can bid just by saying the amount! E.g. `3m` | `900k`')
        await interaction.channel.send(f'Hi{" ".join(users)}! The auction you had reacted to has started.', delete_after=5)
        
    

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey, custom_id='cancel_button')
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        org_msg = await interaction.original_response()

        auction_cog = interaction.client.get_cog('loops')
        auc_channel = await utils(interaction.client).get_auction_channel(interaction)
        auc_log = await utils(interaction.client).get_auction_log(interaction)

        role = await utils(interaction.client).get_auction_access(interaction)
        await self.disable_buttons()
        await interaction.message.edit(view=self)

        payout_log = discord.Embed(color=discord.Color.red(), title='Auction Cancelled')
        payout_log.description = (
                            f"Buyer : \n"
                            f"Seller : {interaction.client.log['seller'].mention}\n"
                            f"Item : {interaction.client.log['item']}\n"
                            f"Amount : {interaction.client.log['item_amount']}\n"
                            f"Coins : "
                        )
        payout_log.set_footer( text= f'auctioner : {interaction.client.log["auctioneer"].id}')

        link_button = log_button(interaction.client)
        link_button.add_item(discord.ui.Button(label='Jump to auction', url= org_msg.jump_url))

        auction_queue = await self.client.db.auction_queue.find_one({'guild_id': interaction.guild.id})
        auction_queue = auction_queue['queue']
        index = next((index for index, auction in enumerate(auction_queue) if auction['host'] == interaction.client.log['seller'].id), None)
        if index == None:
            print('WARNING : Request in queue not found.')
        else:
            auction_queue.pop(index)
            await self.client.db.auction_queue.update_one({'guild_id': interaction.guild.id}, {'$set': {'queue': auction_queue}})


        embed_msg = await auc_log.send(embed=payout_log, view=link_button)

        msg = await auc_log.send(f"/serverevents payout user:{interaction.client.log['seller'].id} quantity:{interaction.client.log['item_amount']} item:{interaction.client.log['item']}")

        interaction.client.payout_msgs.update({
            embed_msg.id : [msg]
        })

        await interaction.followup.send('Auction cancelled!')

    @discord.ui.button(label='Item Value', custom_id='value_button')
    async def value(self, interaction : discord.Interaction, button : discord.ui.Button):

        await interaction.response.defer(ephemeral=True)

        org_msg = await interaction.original_response()
        title = org_msg.embeds[0].title.split(' ')
        item_amount = int(title[0])
        item_name = ' '.join(title[1:-1])


        data = pd.read_json('items.json')
        item_value = data.loc[data['name'].str.lower().str.strip().str.match('^' + re.escape(item_name.strip().lower()) + '$'), 'price']
        item_value = int(item_value.values[0])
        multiplier = item_amount

        item_value = item_value * multiplier

        await interaction.followup.send(f'**Item**: {item_name}\n**Item Amount**: {multiplier}\n**Value**: {format(item_value, ",")}', ephemeral=True)

class pagination_buttons(discord.ui.View):
    def __init__(self, client, author):
        super().__init__()
        self.client = client
        self.author = author

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.author.id

    @discord.ui.button(label='', style=discord.ButtonStyle.grey, emoji='<:doubleleft:875443385308151831>')
    async def skip_start(self, interaction : discord.Interaction, button : discord.ui.Button):
        await interaction.response.defer()

        embed_footer = interaction.message.embeds[0].footer.text.split('/')
        auctions_queue = await self.client.db.auction_queue.find_one({'guild_id' : interaction.guild.id})
        auctions = auctions_queue['queue']

        curr_page = int(embed_footer[0])

        pages = int(embed_footer[1])

        if curr_page == 1:
            return
        
        embed = discord.Embed(title = 'Auction Queue', color = discord.Color.from_str('0x2F3136'))
        
        for i in range(0, 5):
            try:
                auction = auctions[i]
            except IndexError:
                break
            item_msg_link = f'https://discord.com/channels/719180744311701505/782483247619112991/{auction["message_id"]}'
            price_msg_link = f'https://discord.com/channels/719180744311701505/782483247619112991/{auction["msg_id"]}'
            embed.add_field(name = f'{auction["item_amount"]} {auction["item"]} (index: {i + 1})', value = f'host : <@{auction["host"]}>\nstarting bid : {format(auction["starting_price"], ",")}\nLinks : [Items]({item_msg_link}) | [Price]({price_msg_link})', inline = False)
        embed.set_footer(text = f'1/{pages}')
        await interaction.edit_original_response(embed = embed, view=self)
        

        

    @discord.ui.button(label='', style= discord.ButtonStyle.grey, emoji='<:left:875443450080817172>')
    async def previous_button(self, interaction : discord.Interaction, button : discord.ui.Button):

        await interaction.response.defer()
        
        embed_footer = interaction.message.embeds[0].footer.text.split('/')
        auctions_queue = await self.client.db.auction_queue.find_one({'guild_id' : interaction.guild.id})
        auctions = auctions_queue['queue']
        

        curr_page = int(embed_footer[0])

        if curr_page == 1:

            return

        pages = int(embed_footer[1])

        start = (curr_page - 1 - 1) * 5
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
        embed.set_footer(text = f'{curr_page-1}/{pages}')
        await interaction.edit_original_response(embed = embed, view=self)

    

    @discord.ui.button(label='', style= discord.ButtonStyle.grey, emoji='<:right:875443466644095036>')
    async def next_button(self, interaction : discord.Interaction, button : discord.ui.Button):

        await interaction.response.defer()

        embed_footer = interaction.message.embeds[0].footer.text.split('/')
        auctions_queue = await self.client.db.auction_queue.find_one({'guild_id' : interaction.guild.id})
        auctions = auctions_queue['queue']
        

        curr_page = int(embed_footer[0])
        pages = int(embed_footer[1])

        if curr_page == pages:
            return

        start = (curr_page) * 5
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
        embed.set_footer(text = f'{curr_page+1}/{pages}')
        await interaction.edit_original_response(embed = embed, view=self)
    

    @discord.ui.button(label='', style=discord.ButtonStyle.grey, emoji='<:doubleright:875443494259421184>')
    async def skip_end(self, interaction : discord.Interaction, button : discord.ui.Button):

        await interaction.response.defer()

        embed_footer = interaction.message.embeds[0].footer.text.split('/')
        auctions_queue = await self.client.db.auction_queue.find_one({'guild_id' : interaction.guild.id})
        auctions = auctions_queue['queue']

        curr_page = int(embed_footer[0])
        pages = int(embed_footer[1])

        if curr_page == pages:
            return
        
        start = (pages * 5) - 5
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
        embed.set_footer(text = f'{pages}/{pages}')
        await interaction.edit_original_response(embed = embed, view=self)
    
class clear_confirm(discord.ui.View):
    def __init__(self, client, author):
        super().__init__()
        self.client = client
        self.author = author

    async def disable_buttons(self):
        for child in self.children:
            child.disabled = True


    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.author.id

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green, custom_id='confirm_button')
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.disable_buttons()
        await interaction.message.edit(view=self)

        auction_queue = await self.client.db.auction_queue.find_one({'guild_id': interaction.guild.id})

        if not auction_queue:
            return
        else:
            await self.client.db.auction_queue.update_one({'guild_id': interaction.guild.id}, {'$set': {'queue': []}})
            await interaction.followup.send(f'Removed all auctions from the queue!')

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey, custom_id='cancel_button')
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        await self.disable_buttons()
        await interaction.message.edit(view=self)
        await interaction.response.send_message('Aborted.')


class auction(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.client.bot_admins = [692994778136313896, 983505180739907604, 729643700455604266]
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

    # @auc_group.command(name = 'host', description = 'Host an auction' )
    # async def auction_host(self, interaction : discord.Interaction, member : discord. Member, items : str, item_amount : int,  starting_price : str):

        # await interaction.response.defer()

        # full_int = self.utils.process_shorthand(starting_price)
        # full_int = int(full_int)
  
        # embed = discord.Embed(title = f'{item_amount} {items} auction', description= f'starting bid : {format(full_int, ",")} \nseller : {member.mention}', color = discord.Color.from_str('0x2F3136'))
        # embed.set_footer(text= 'auction will start when there\'s 3 reacts')

        # ping_role = await utils(interaction.client).get_auction_ping(interaction)
        # auction_channel = await utils(interaction.client).get_auction_channel(interaction)

        # if interaction.channel != auction_channel:

        #     await interaction.followup.send('This is not your configured auction channel.', ephemeral= True)

        # else:

        #     self.client.start_price[interaction.channel.id] = full_int
        #     self.client.first_bid[interaction.guild.id] = True
        #     self.client.last_bids[interaction.channel.id] = []
        #     self.client.bidders[interaction.channel.id] = []
        #     self.client.curr_bids[interaction.channel.id] = []

        #     msg = await interaction.original_response()

        #     self.client.log.update({ 
        #         'auction_id' : msg.id,
        #         'auctioneer' : interaction.user,
        #         'item' : items,
        #         'item_amount' : item_amount,
        #         'seller' : member
        #     })


        #     await interaction.followup.send(embed=embed, view=auc_buttons(interaction.user))
        #     await interaction.channel.send(content=f'{ping_role.mention}', allowed_mentions = discord.AllowedMentions(roles=True))
        #     await msg.add_reaction('⭐')

    # we want to change it so that it only take in index for the host
    @auc_group.command(name = 'host', description = 'Host an auction')
    async def auction_host(self, interaction : discord.Interaction, index : str):
        await interaction.response.defer()

        try:
            index = int(index) - 1
        except ValueError:
            return await interaction.followup.send('Invalid index.')
        
        auction_queue = await self.client.db.auction_queue.find_one({'guild_id' : interaction.guild.id})
        item_tracker = await self.client.db.item_tracker.find_one({'guild_id' : interaction.guild.id})
        auc_count = await self.client.db.participants.find_one({'guild_id' : interaction.guild.id})
        auction_users = auc_count['auction_users']
        currn_date = auction_users.get(str(datetime.utcnow().date()), None)
        if not currn_date:
            auction_users.update({str(datetime.utcnow().date()) : {}})
        try:
            auction_users[str(datetime.utcnow().date())]['today_event_count'] += 1
        except  KeyError:
            auction_users[str(datetime.utcnow().date())].update({'today_event_count' : 1})
        await self.client.db.participants.update_one({'guild_id' : interaction.guild.id}, {'$set' : {'auction_users' : auction_users} })
        
        
        

        if not auction_queue:
            return await interaction.followup.send('No auctions in queue.')
        else:
            auctions = auction_queue['queue']
            try:
                auction = auctions.pop(index)
            except IndexError:
                return await interaction.followup.send('Invalid index.')

            items = auction['item']
            item_amount = auction['item_amount']
            full_int = auction['starting_price']
            host = interaction.guild.get_member(auction['host'])

            if not item_tracker:
                await self.client.db.item_tracker.insert_one({'guild_id' : interaction.guild.id, items : []})
                item_tracker = await self.client.db.item_tracker.find_one({'guild_id' : interaction.guild.id})
            try :
                trackers = item_tracker[items]
            except KeyError:
                trackers = []


  
            embed = discord.Embed(title = f'{item_amount} {items} auction', description= f'starting bid : {format(full_int, ",")} \nseller : {host.mention}', color = discord.Color.from_str('0x2F3136'))
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
                    'seller' : host
                })


                await interaction.followup.send(embed=embed, view=auc_buttons(interaction.user, self.client))
                await interaction.channel.send(content=f'{ping_role.mention}', allowed_mentions = discord.AllowedMentions(roles=True))
                await msg.add_reaction('⭐')

                view = auc_link(client=self.client)

                view.add_item(discord.ui.Button(label='Jump to auction', url=msg.jump_url))

                for tracker in trackers:
                    user = interaction.guild.get_member(tracker)
                    await user.send(f'Hi! There is a **{items}** auction going on right now!\n \n> If you don\'t want to get notified for this item anymore, use `/auction tracker (toggle: Disable)`', view=view)

                await self.utils.update_auc_stats(guild=interaction.guild, user=interaction.user)
            
    # @auction_host.autocomplete('items')
    # async def autocomplete_callback(self, interaction : discord.Interaction, current : str):
        
    #     items = pd.read_csv('auctions.csv')

    #     item_list = [item for item in items['name']]

    #     return [app_commands.Choice(name=suggestion, value=suggestion) for suggestion in item_list if current.lower() in suggestion.lower()]

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
    
    queue_group = Group(name='queue', description='just a group for queue subcommands')

    @queue_group.command(name='list')
    async def auction_queue(self, interaction: discord.Interaction, page: str = '1'):
        await interaction.response.defer(ephemeral=True)
        try:
            page = int(page)
        except ValueError:
            page = 1

        auction_queue = await self.client.db.auction_queue.find_one({'guild_id' : interaction.guild.id})

        if not auction_queue:
            await self.client.db.auction_queue.insert_one({'guild_id' : interaction.guild.id, 'queue' : []})
            return await interaction.followup.send('No auctions in queue.', ephemeral=True)

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
            return await interaction.followup.send('No auctions in queue.', ephemeral= True)
        else:
            if len(auctions) % 5 != 0:    
                pages = len(auctions) // 5 + 1
            else :
                pages = len(auctions) // 5
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
            await interaction.followup.send(embed = embed, ephemeral=True, view=pagination_buttons(client=interaction.client, author=interaction.user))

    # this is a subcommand of the queue command
    @queue_group.command(name='remove', description = 'Remove an auction from the queue')
    @app_commands.checks.has_any_role(750117211087044679, 1051128651929882695)
    async def auction_queue_remove(self, interaction: discord.Interaction, index : str = ""):
        await interaction.response.defer()
        try:
            index = int(index) - 1
        except ValueError:
            return await interaction.followup.send('Invalid index.')

        auction_queue = await self.client.db.auction_queue.find_one({'guild_id' : interaction.guild.id})

        if not auction_queue:
            return await interaction.followup.send('No auctions in queue.')
        else:
            auctions = auction_queue['queue']
            try:
                auction = auctions.pop(index)
            except IndexError:
                return await interaction.followup.send('Invalid index.')
            await self.client.db.auction_queue.update_one({'guild_id' : interaction.guild.id}, {'$set' : {'queue' : auctions}})
            await interaction.followup.send(f'Removed the auction : {auction["item_amount"]} {auction["item"]} auction hosted by {auction["host"]}')

    @queue_group.command(name='clear')
    @app_commands.checks.has_any_role(750117211087044679,1051128651929882695 )
    async def auction_queue_remove_all(self, interaction : discord.Interaction):

        await interaction.response.send_message('Are you sure you want to clear the auction queue?', view=clear_confirm(client=interaction.client, author=interaction.user))

    @queue_group.command(name='insert')
    @commands.has_any_role(1051128651929882695, 750117211087044679)
    async def insert_queue(self, interaction : discord.Interaction, seller : discord.Member, items : str, item_amount : int, starting_price : str, msg_id : str ):

        await interaction.response.defer()

        if interaction.user.id in self.client.bot_admins:

            queue_chan = interaction.guild.get_channel(782483247619112991) 
            msg = await queue_chan.fetch_message(int(msg_id))

            starting_price = int(self.utils.process_shorthand(starting_price))
            await self.client.db.auction_queue.update_one({'guild_id' : interaction.guild.id}, {'$push' : {'queue' : {'message_id' : msg.id, 'host' : seller.id, 'item' : items, 'item_amount' : item_amount, 'starting_price' : starting_price, 'msg_id' : None}}}, upsert = True)
            await interaction.followup.send('✅')
            await msg.add_reaction('✅')
        
        else :

            queue_chan = interaction.guild.get_channel(782483247619112991) 
            try :
                msg = await queue_chan.fetch_message(int(msg_id))
            except :
                return await interaction.response.send('Invalid message ID.')
            starting_price = int(self.utils.process_shorthand(starting_price))

            for react in msg.reactions:
                if react.emoji == '✅':
                    return await interaction.followup.send('This auction is hosted already.')
                
            try :
                embed = msg.embeds[0]
                if embed.title != 'Action Confirmed' or msg.interaction.name != 'serverevents donate' or msg.interaction.user.id != seller.id: 
                    return await interaction.followup.send('Incorrect message ID.')
            except IndexError:
                return await interaction.followup.send('Incorrect message ID.')
            
            check_amount, check_item = self.utils.extract_item_and_amount(embed.description)

            if item_amount != check_amount or items != check_item:
                return await interaction.followup.send('Incorrect item name or item amount.')

            await self.client.db.auction_queue.update_one({'guild_id' : interaction.guild.id}, {'$push' : {'queue' : {'message_id' : msg.id, 'host' : seller.id, 'item' : items, 'item_amount' : item_amount, 'starting_price' : starting_price, 'msg_id' : None}}}, upsert = True)
            await interaction.followup.send('✅')
            await msg.add_reaction('✅')
        
    @insert_queue.autocomplete('items')
    async def autocomplete_callback(self, interaction : discord.Interaction, current : str):
        
        items = pd.read_json('auctions.json')

        item_list = [item for item in items['name']]

        return [app_commands.Choice(name=suggestion, value=suggestion) for suggestion in item_list if current.lower() in suggestion.lower()]
            

    @commands.command(name='test')
    @commands.has_any_role(1228100188204437596)
    async def test(self, ctx):
        embed = discord.Embed(title = 'Action Confirmed', description = 'Are you sure you want to donate your items?\n\n> You will donate **1x :banknote: Bank Note**', color = discord.Color.from_str('0x2F3136'))
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label='Confirm', style=discord.ButtonStyle.green))
        view.add_item(discord.ui.Button(label='Cancel', style=discord.ButtonStyle.red))
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name='test')
    @app_commands.checks.has_any_role(1228100188204437596)
    async def test_command(self, interaction : discord.Interaction):
        embed = discord.Embed(title = 'Action Confirmed', description = 'Are you sure you want to donate your items?\n\n> You will donate **10x <:dank_banknote:831787534820442112> Bank Note**', color = discord.Color.from_str('0x2F3136'))
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label='Confirm', style=discord.ButtonStyle.green))
        view.add_item(discord.ui.Button(label='Cancel', style=discord.ButtonStyle.red))
        await interaction.response.send_message(embed=embed, view=view)

    @commands.command(name= 'revert', aliases = ['r'])
    @commands.has_any_role(750117211087044679,1051128651929882695)
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
    @app_commands.checks.has_any_role(750117211087044679,1051128651929882695)
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
    @commands.has_any_role(750117211087044679,1051128651929882695)
    async def ato(self, ctx, member : discord.Member):

        if member.bot:
            return

        tradeout_channel = await self.utils.get_tradeout_channel(ctx)

        permissions = tradeout_channel.permissions_for(member)

        if tradeout_channel.overwrites_for(member).send_messages:
            await tradeout_channel.set_permissions(member, overwrite = None)
        else :
            await tradeout_channel.set_permissions(member, send_messages = True)
        
        await ctx.message.add_reaction('✅')
        

    @commands.command()
    @commands.has_any_role(750117211087044679,1051128651929882695)
    async def adump(self, ctx):
        members = ''

        tradeout_channel = await self.utils.get_tradeout_channel(ctx)



        for member in tradeout_channel.overwrites:
            if isinstance(member, discord.Member) and tradeout_channel.overwrites_for(member).send_messages and not member.bot:
            
                members = members + f'{member.display_name} ({member.id})\n'

        if members == '':
            await ctx.send('No one in tradeout.')
            return
        await ctx.send(members)


    @commands.command()
    @commands.has_any_role(750117211087044679,1051128651929882695)
    async def aclear(self, ctx):

        tradeout_channel = await self.utils.get_tradeout_channel(ctx)

        for member in tradeout_channel.overwrites:
            if isinstance(member, discord.Member) and tradeout_channel.overwrites_for(member).send_messages and not member.bot:
                await tradeout_channel.set_permissions(member, overwrite = None)
        
        await ctx.message.add_reaction('✅')
 
    @commands.Cog.listener()
    async def on_message(self, msg):
        # if msg.content == 'e':
        #     return await msg.channel.send('<@729643700455604266>')
        # elif msg.content == 'r':
        #     return await msg.channel.send('<@692994778136313896>')

        queue = 782483247619112991
        command_name = 'serverevents donate'
        validate_title = 'Action Confirmed'

        if msg.channel.id != queue or msg.author.bot:
            return

        config = await self.client.db.guild_config.find_one({"guild_id": msg.guild.id})
        
        if not config:
            return  # Configuration not found for the guild
        
        auctioneer_role = msg.guild.get_role(config["auctioneer_role"])

        bid_amount = self.utils.process_shorthand(msg.content)
        bid_amount = int(bid_amount)

        if msg.reference is not None:
            replied_to_message = await msg.channel.fetch_message(msg.reference.message_id)
            guild_queue = await self.client.db.auction_queue.find_one({'guild_id' : msg.guild.id})

            if not guild_queue:
                await self.client.db.auction_queue.insert_one({'guild_id' : msg.guild.id, 'queue' : []})
                guild_queue = await self.client.db.auction_queue.find_one({'guild_id' : msg.guild.id})

            user_queue = next((item for item in guild_queue['queue'] if item['host'] == msg.author.id), None)

            for react in replied_to_message.reactions:
                if react.emoji == '✅':
                    if user_queue is None:
                        await msg.add_reaction('❌')
                        return await self.utils.send_error_message(msg, 'This auction has requested hosted already!')

            if auctioneer_role not in msg.author.roles:
                await self.utils.update_user_count(guild=msg.guild, user=msg.author, target='queue_users')

            try:
                embed = replied_to_message.embeds[0]
            except IndexError:
                if auctioneer_role in msg.author.roles:
                    return
                await self.utils.send_error_message(msg, 'You have replied to the **WRONG MESSAGE**.\n\n> Please make sure to reply to the ["Action Confirmed" embed](https://cdn.discordapp.com/attachments/1226130635849203782/1229758241840562216/IMG_9001.png?ex=6630d89c&is=661e639c&hm=f3b1531faad5c4b1eb0be928ff3347ebba4027ad86790b4af2e4906a1bbcf64c&) from the item YOU sent to the pool in order to set a starting price.')
                return await msg.add_reaction('❌')

            amount, item_name = self.utils.extract_item_and_amount(embed.description)
            
            # if bid_amount < 5e5 or replied_to_message.interaction is None or replied_to_message.interaction.name != command_name or replied_to_message.interaction.user.id != msg.author.id or user_queue is not None or not self.utils.check_start_price(price=bid_amount, item=item_name, item_amount=amount):
            #     return await msg.add_reaction('❌')

            if replied_to_message.interaction is None or replied_to_message.interaction.name != command_name or replied_to_message.interaction.user.id != msg.author.id:
                if auctioneer_role in msg.author.roles:
                    return
                await self.utils.send_error_message(msg, 'You have replied to the **WRONG MESSAGE**.\n\n> Please make sure to reply to the ["Action Confirmed" embed](https://cdn.discordapp.com/attachments/1226130635849203782/1229758241840562216/IMG_9001.png?ex=6630d89c&is=661e639c&hm=f3b1531faad5c4b1eb0be928ff3347ebba4027ad86790b4af2e4906a1bbcf64c&) from the item YOU sent to the pool in order to set a starting price.')
                return await msg.add_reaction('❌')
            
            if bid_amount < MIN_BID_AMOUNT:
                await self.utils.send_error_message(msg, f'The starting price for all auctions must be more than **{format(int(MIN_BID_AMOUNT), ",")}**.\n\n> Please edit your message to change the starting price')
                return await msg.add_reaction('❌')

            if user_queue is not None:
                await self.utils.send_error_message(msg, 'Failed to register your starting bid to queue. You can only have one item in the queue at a time.')
                return await msg.add_reaction('❌')
            
            inquire_item_list = ['Blob', 'Digging Trophy', "Enchanted Badosz's Card", 'Hunting Trophy', "Melmsie's Banana", 'Pepe Ribbon', 'Pepe Sus', 'Pink Rubber Ducky', 'Puzzle Key', 'Universe Box']
            if item_name in inquire_item_list:
                await self.utils.send_error_message(msg, f'You requested an auction for a special item: **{item_name}**.\nPlease **DM** any of <@692994778136313896>, <@729643700455604266> or <@983505180739907604> first to discuss the starting price for your auction.')
                return await msg.add_reaction('❌')
            
            unavailable_item_list = ['Delta 9', "Dank Memer's Hard Drive", "Delta 9 Roll", "Coin Nuke"]
            if item_name in unavailable_item_list:
                await self.utils.send_error_message(msg, f'**{item_name}** is not available for auctions yet. Your item will be returned.\n \n> Please make sure to check whether the item is available with  `[item <item>` before requesting an auction for **new items**.')
                return await msg.add_reaction('❌')

            min_start_price = self.utils.check_start_price(price=bid_amount, item=item_name, item_amount=amount)
            if min_start_price > 0:
                await self.utils.send_error_message(msg, f"Your starting price is **TOO HIGH**.\nThe maximum starting price for this item is **{format(int(min_start_price), ',')}**\n\n> The starting price for all auctions must also be **below 200 mil**.\n> Please edit your message to change the starting price.")
                return await msg.add_reaction('❌')

            if embed.title != validate_title:
                await self.utils.send_error_message(msg, "Remember to click the confirm button on the embed to ensure the item has been sent to server pool.\n\n> Please edit your message to set the starting price again.")
                return await msg.add_reaction('❌')

            await msg.add_reaction('✅')
            await replied_to_message.add_reaction('✅')
            await self.client.db.auction_queue.update_one({'guild_id' : msg.guild.id}, {'$push' : {'queue' : {'message_id' : replied_to_message.id, 'host' : msg.author.id, 'item' : item_name, 'item_amount' : amount, 'starting_price' : bid_amount, 'msg_id' : msg.id}}}, upsert = True)

            return await msg.reply(f'Your starting bid for {amount} {item_name} is {format(bid_amount, ",")}.', mention_author = True)
        else:
            if auctioneer_role in msg.author.roles:
                return
            await self.utils.send_error_message(msg, 'You have replied to the **WRONG MESSAGE**.\n\n> Please make sure to reply to the ["Action Confirmed" embed](https://cdn.discordapp.com/attachments/1226130635849203782/1229758241840562216/IMG_9001.png?ex=6630d89c&is=661e639c&hm=f3b1531faad5c4b1eb0be928ff3347ebba4027ad86790b4af2e4906a1bbcf64c&) from the item YOU sent to the pool in order to set a starting price.')
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

            for react in replied_to_message.reactions:
                if react.emoji == '✅':
                    if user_queue is None:
                        await message_after.add_reaction('❌')
                        return await self.utils.send_error_message(message_after, 'This auction has been requested already!')

            for react in message_after.reactions:
                if react.emoji == '✅':
                    if user_queue is None:
                        return await self.utils.send_error_message(message_after, 'This auction has been requested already!')
            
            await message_after.clear_reactions()
            
            embed = replied_to_message.embeds[0]
            amount, item_name = self.utils.extract_item_and_amount(embed.description)
            
            # if bid_amount < 5e5 or replied_to_message.interaction is None or replied_to_message.interaction.name != command_name or replied_to_message.interaction.user.id != message_after.author.id or user_queue is None or not self.utils.check_start_price(price=bid_amount, item=item_name, item_amount=amount):
            #     return await message_after.add_reaction('❌')

            if replied_to_message.interaction is None or replied_to_message.interaction.name != command_name or replied_to_message.interaction.user.id != message_after.author.id:
                await self.utils.send_error_message(message_after, 'You have replied to the **WRONG MESSAGE**.\n\n> Please make sure to reply to the ["Action Confirmed" embed](https://cdn.discordapp.com/attachments/1226130635849203782/1229758241840562216/IMG_9001.png?ex=6630d89c&is=661e639c&hm=f3b1531faad5c4b1eb0be928ff3347ebba4027ad86790b4af2e4906a1bbcf64c&) from the item YOU sent to the pool in order to set a starting price.')
                return await message_after.add_reaction('❌')

            if bid_amount < MIN_BID_AMOUNT:
                await self.utils.send_error_message(message_after, f'The starting price for all auctions must be more than **{format(int(MIN_BID_AMOUNT), ",")}**.\n\n> Please edit your message to change the starting price')
                return await message_after.add_reaction('❌')
            
            # if user_queue is None:
            #     await self.utils.send_error_message(message_after, 'Failed to register your starting bid to queue. You must have an item in the queue to edit.')
            #     return await message_after.add_reaction('❌')

            inquire_item_list = ['Blob', 'Digging Trophy', "Enchanted Badosz's Card", 'Hunting Trophy', "Melmsie's Banana", 'Pepe Ribbon', 'Pepe Sus', 'Pink Rubber Ducky', 'Puzzle Key', 'Universe Box']
            if item_name in inquire_item_list:
                await self.utils.send_error_message(message_after, f'You requested an auction for a special item: **{item_name}**.\nPlease **DM** any of <@692994778136313896>, <@729643700455604266> or <@983505180739907604> first to discuss the starting price for your auction.')
                return await message_after.add_reaction('❌')
            
            unavailable_item_list = ['Delta 9', "Dank Memer's Hard Drive", "Delta 9 Roll", "Coin Nuke"]
            if item_name in unavailable_item_list:
                await self.utils.send_error_message(message_after, f'**{item_name}** is not available for auctions yet. Your item will be returned.\n \n> Please make sure to check whether the item is available with  `[item <item>` before requesting an auction for **new items**.')
                return await message_after.add_reaction('❌')
            
            min_start_price = self.utils.check_start_price(price=bid_amount, item=item_name, item_amount=amount)
            if min_start_price > 0:
                await self.utils.send_error_message(message_after, f"Your starting price is **TOO HIGH**.\nThe maximum starting price for this item is **{format(int(min_start_price), ',')}**\n\n> The starting price for all auctions must also be **below 200 mil**.\n> Please edit your message to change the starting price.")
                return await message_after.add_reaction('❌')
            
            if embed.title != validate_title:
                await self.utils.send_error_message(message_after, "Remember to click the confirm button on the embed to ensure the item has been sent to server pool.\n\n> Please edit your message to set the starting price again.")
                return await message_after.add_reaction('❌')
            
            if user_queue is not None:
                guild_queue['queue'] = [item for item in guild_queue['queue'] if item != user_queue]
                user_queue['starting_price'] = bid_amount
                guild_queue['queue'].append(user_queue)
            else:
                guild_queue['queue'].append({'message_id' : replied_to_message.id, 'host' : message_after.author.id, 'item' : item_name, 'item_amount' : amount, 'starting_price' : bid_amount, 'msg_id' : message_after.id})

            await message_after.add_reaction('✅')
            await self.client.db.auction_queue.update_one({'guild_id' : message_after.guild.id}, {'$set' : {'queue' : guild_queue['queue']}}, upsert = True)

            # return await message_after.reply(f'Your starting bid for {amount} {item_name} is {format(bid_amount, ",")}.', mention_author = True)

    @auc_group.command(name='profile')
    async def profile(self, interaction : discord.Interaction, user: discord.Member = None):
        await interaction.response.defer()
        if user is None:
            user = interaction.user
    
        profile = await self.client.db.profile.find_one({'user_id' : user.id, 'guild_id' : interaction.guild.id})
    
        if not profile:
            await self.client.db.profile.insert_one({'user_id' : user.id, 'guild_id' : interaction.guild.id, 'auction_hosted' : 0, 'total_amount_bid' : 0, 'total_amount_sold' : 0, 'auction_won': 0, 'auction_joined' : 0})
            profile = await self.client.db.profile.find_one({'user_id' : user.id, 'guild_id' : interaction.guild.id})

        auction_hosted = profile.get('auction_hosted', 0)
        total_amount_bid = profile.get('total_amount_bid', 0)
        total_amount_sold = profile.get('total_amount_sold', 0)
        auction_won = profile.get('auction_won', 0)
        auction_joined = profile.get('auction_joined', 0)
        auction_requested = profile.get('total_auction_requested', 0)
    
        embed = discord.Embed(title = 'Profile', color = discord.Color.from_str('0x2F3136'))
        embed.set_author(name=str(user), icon_url=user.avatar.url)
        embed.add_field(name = 'Auctions Hosted', value = format(int(auction_hosted), ","))
        embed.add_field(name = 'Total Amount Bid', value = format(int(total_amount_bid), ","))
        embed.add_field(name = 'Total Amount Sold', value = format(int(total_amount_sold), ","))
        embed.add_field(name = 'Auctions Won', value = format(int(auction_won), ","))
        embed.add_field(name = 'Auctions Joined', value = format(int(auction_joined), ","))
        embed.add_field(name = 'Total Auction Requested', value = format(int(auction_requested), ","))

        await interaction.followup.send(embed=embed)

    @auc_group.command(name='leaderboard')
    async def leaderboard(self, interaction : discord.Interaction, table : str):

        await interaction.response.defer()

        # Fetch profiles for all users in the guild
        profiles = await self.client.db.profile.find({'guild_id': interaction.guild.id}).to_list(length=None)

        # Sort users based on each stat
        sorted_profiles_hosted = sorted(profiles, key=lambda x: x.get('auction_hosted', 0), reverse=True)[:10]
        sorted_profiles_bid = sorted(profiles, key=lambda x: x.get('total_amount_bid', 0), reverse=True)[:10]
        sorted_profiles_sold = sorted(profiles, key=lambda x: x.get('total_amount_sold', 0), reverse=True)[:10]
        sorted_profiles_won = sorted(profiles, key=lambda x: x.get('auction_won', 0), reverse=True)[:10]
        sorted_profiles_joined = sorted(profiles, key=lambda x: x.get('auction_joined', 0), reverse=True)[:10]
        sorted_profiles_requested = sorted(profiles, key=lambda x: x.get('total_auction_requested', 0), reverse=True)[:10]    

        # Add fields for each stat leaderboard
        table = table.lower()

        if table == 'auctions hosted':
            embed = discord.Embed(title='Leaderboard', color=discord.Color.from_str('0x2F3136'))
            embed.add_field(name='Auctions Hosted', value='\n'.join([f"{index+1}. {interaction.guild.get_member(profile['user_id'])}: {format(int(profile.get('auction_hosted', 0)), ',')}" for index, profile in enumerate(sorted_profiles_hosted)]), inline=False)
        
        elif table == 'bid amount':
            embed = discord.Embed(title='Leaderboard', color=discord.Color.from_str('0x2F3136'))
            embed.add_field(name='Total Amount Bid', value='\n'.join([f"{index+1}. {interaction.guild.get_member(profile['user_id'])}: {format(int(profile['total_amount_bid']), ',')}" for index, profile in enumerate(sorted_profiles_bid)]), inline=False)
        
        elif table == 'sold amount':
            embed = discord.Embed(title='Leaderboard', color=discord.Color.from_str('0x2F3136'))
            embed.add_field(name='Total Amount Sold', value='\n'.join([f"{index+1}. {interaction.guild.get_member(profile['user_id'])}: {format(int(profile['total_amount_sold']), ',')}" for index, profile in enumerate(sorted_profiles_sold)]), inline=False)
        
        elif table == 'auctions won':
            embed = discord.Embed(title='Leaderboard', color=discord.Color.from_str('0x2F3136'))
            embed.add_field(name='Auctions Won', value='\n'.join([f"{index+1}. {interaction.guild.get_member(profile['user_id'])}: {format(int(profile['auction_won']), ',')}" for index, profile in enumerate(sorted_profiles_won)]), inline=False)
        
        elif table == 'auctions joined':
            embed = discord.Embed(title='Leaderboard', color=discord.Color.from_str('0x2F3136'))
            embed.add_field(name='Auctions Joined', value='\n'.join([f"{index+1}. {interaction.guild.get_member(profile['user_id'])}: {format(int(profile['auction_joined']), ',')}" for index, profile in enumerate(sorted_profiles_joined)]), inline=False)
        
        elif table == 'auctions requested':
            embed = discord.Embed(title='Leaderboard', color=discord.Color.from_str('0x2F3136'))
            embed.add_field(name='Total Auctions Requested', value='\n'.join([f"{index+1}. {interaction.guild.get_member(profile['user_id'])}: {format(int(profile.get('total_auction_requested', 0)), ',')}" for index, profile in enumerate(sorted_profiles_requested)]), inline=False)
            
        else :
            await interaction.followup.send('Invalid table selection.')

        await interaction.followup.send(embed=embed)
    
    @leaderboard.autocomplete('table')
    async def autocomplete_callback(self, interaction : discord.Interaction, current : str):
        table_list = ['Auctions Hosted', 'Bid Amount', 'Sold Amount', 'Auctions Won', 'Auctions Joined', 'Auctions Requested']

        return [app_commands.Choice(name=suggestion, value=suggestion) for suggestion in table_list if current.lower() in suggestion.lower()]
    
    @auc_group.command(name='tracker')
    async def tracker(self, interaction : discord.Interaction, toggle : str, item : str):

        await interaction.response.defer()

        guild_items = await self.client.db.item_tracker.find_one({'guild_id' : interaction.guild.id})
        if not guild_items:
            await self.client.db.item_tracker.insert_one({'guild_id' : interaction.guild.id, item : []})
            guild_items = await self.client.db.item_tracker.find_one({'guild_id' : interaction.guild.id})

        items = pd.read_json('auctions.json')
        item_list = [item for item in items['name']]

        if item not in item_list or toggle not in ['Enable', 'Disable']:
            return await interaction.followup.send('Invalid input.\nPlease make sure to pick from the bot suggestions for the inputs.')

        try :
            users = guild_items[item]

        except KeyError:

            guild_items[item]  = []
            users = guild_items[item]

        if toggle == 'Enable':
            if interaction.user.id not in users:
                users.append(interaction.user.id)
            else :
                return await interaction.followup.send(f'You already enabled tracker for {item}.')

        elif toggle == 'Disable':
            if interaction.user.id in users:
                users.remove(interaction.user.id)
            else :
                return await interaction.followup.send('You already disabled tracker for this item.')

        await self.client.db.item_tracker.update_one({'guild_id' : interaction.guild.id}, {'$set' : {item : users}})
        await interaction.followup.send(f'**{toggle}d** tracking for {item}!')

    @tracker.autocomplete('toggle')
    async def autocomplete_callback(self, interaction : discord.Interaction, current : str):

        the_list = ['Enable', 'Disable']
        
        return [app_commands.Choice(name=suggestion, value=suggestion) for suggestion in the_list if current.lower() in suggestion.lower()]

    @tracker.autocomplete('item')
    async def autocomplete_callback(self, interaction : discord.Interaction, current : str):
        items = pd.read_json('auctions.json')

        item_list = [item for item in items['name']]

        return [app_commands.Choice(name=suggestion, value=suggestion) for suggestion in item_list if current.lower() in suggestion.lower()]
        
    
        
async def setup(client):
    await client.add_cog(auction(client))
