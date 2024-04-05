import discord
import json
import sys
sys.path.append(r'C:\Users\HUAWEI\Desktop\Trivia\cogs')
"""sys.path.append(r'/home/container/')"""
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
    

    auc_group = Group(name = 'auction', description= 'just a group for auction subcommands')

    @auc_group.command(name = 'host', description = 'Host an auction' )
    @app_commands.autocomplete()

    async def auction_host(self, interaction : discord.Interaction, member : discord. Member, items : str, item_amount : int,  starting_price : str):

        await interaction.response.defer()
  
        embed = discord.Embed(title = f'{item_amount} {items} auction', description= f'starting price : {starting_price} \nseller : {member.mention}', color = discord.Color.from_str('0x2F3136'))
        embed.set_footer(text= 'auction will start when there\'s 3 reacts')

        ping_role = await utils(interaction.client).get_auction_ping(interaction)
        auction_channel = await utils(interaction.client).get_auction_channel(interaction)

        if interaction.channel != auction_channel:

            await interaction.followup.send('This is not your configured auction channel.', ephemeral= True)

        else:

            if "K" in starting_price:
                the_int = starting_price.replace('K', "")
                full_int = float(the_int) * 1000
            elif "k" in starting_price:
                the_int = starting_price.replace('k', "")
                full_int = float(the_int) * 1000
            elif "M" in starting_price:
                the_int = starting_price.replace("M" , "")
                full_int = float(the_int) * 1000000
            elif "m" in starting_price:
                the_int = starting_price.replace("m" , "")
                full_int = float(the_int) * 1000000

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


            await interaction.followup.send(content=f'{ping_role.mention}', embed=embed, view=auc_buttons(interaction.user), allowed_mentions = discord.AllowedMentions(roles=True))
            await msg.add_reaction('⭐')

    @auction_host.autocomplete('items')
    async def autocomplete_callback(self, interaction : discord.Interaction, current : str):
        
        items = pd.read_csv('DonoList.csv')

        item_list = [item for item in items['name']]

        return [app_commands.Choice(name=suggestion, value=suggestion) for suggestion in item_list if current.lower() in suggestion.lower()]

    @commands.command(name='bid', aliases = ['b'])
    async def auction_bid(self, ctx, bid : str):

        auction_channel = await utils(self.client).get_auction_channel(ctx)

        record = await self.client.db.fetchrow('SELECT min_increment FROM guild_config WHERE guild_id = $1', ctx.guild.id)

        min_increment = record['min_increment']

        if ctx.channel != auction_channel:

            return

        if ctx.author == self.client.log['seller']:
            
            return
    
        else :

            loop_cog = self.client.get_cog('loops')

            if loop_cog.auc_count.is_running():


                if "K" in bid:
                    the_int = bid.replace("K", "")
                    full_int = float(the_int) * 1000
                elif "k" in bid:
                    the_int = bid.replace("k", "")
                    full_int = float(the_int) * 1000
                elif "M" in bid:
                    the_int = bid.replace("M" , "")
                    full_int = float(the_int) * 1000000
                elif "m" in bid:
                    the_int = bid.replace("m" , "")
                    full_int = float(the_int) * 1000000

                if self.client.first_bid[ctx.guild.id] == True:
                    
                    if full_int < float(self.client.start_price[ctx.channel.id]):
                        pass

                    elif full_int >= float(self.client.start_price[ctx.channel.id]):
                        self.client.last_bids[ctx.channel.id] = []
                        self.client.last_bids[ctx.channel.id].append(bid)
                        self.client.bidders[ctx.channel.id] = []
                        self.client.bidders[ctx.channel.id].append(ctx.author.id)


                        self.client.curr_bids[ctx.channel.id] = full_int
                        self.client.first_bid[ctx.guild.id] = False
                        await ctx.send(f'{ctx.author.mention} bidded **{bid}**')

                        loop_cog.auc_count.restart()

                if self.client.first_bid[ctx.guild.id] == False:

                    if full_int < float(self.client.curr_bids[ctx.channel.id]) + min_increment:
                            pass
                    
                    elif full_int >= float(self.client.curr_bids[ctx.channel.id]) + min_increment:
                            self.client.last_bids[ctx.channel.id].append(bid)
                            self.client.bidders[ctx.channel.id].append(ctx.author.id)
                            self.client.curr_bids[ctx.channel.id] = full_int
                            await ctx.send(f'{ctx.author.mention} bid **{bid}**')
                            loop_cog.auc_count.restart()
            else:

                await ctx.message.add_reaction('‼')
           

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
                if "K" in reverted_bid:
                    the_int = reverted_bid.replace('K', "")
                    full_int = float(the_int) * 1000
                elif "k" in reverted_bid:
                    the_int = reverted_bid.replace('k', "")
                    full_int = float(the_int) * 1000
                elif "M" in reverted_bid:
                    the_int = reverted_bid.replace("M" , "")
                    full_int = float(the_int) * 1000000
                elif "m" in reverted_bid:
                    the_int = reverted_bid.replace("m" , "")
                    full_int = float(the_int) * 1000000

                self.client.start_price[ctx.channel.id] = full_int
                self.client.curr_bids[ctx.channel.id] = full_int
                
                await ctx.send(f'{reverted_bidder.mention} bid **{reverted_bid}**')
            
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


        

    



async def setup(client):
    await client.add_cog(auction(client))