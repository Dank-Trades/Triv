import discord
import psutil
import json
import io
import os
import sys
import humanize
sys.path.append(r'/home/container/')
from cogs.utils import utils
from datetime import datetime
from discord.ext import commands
from discord import app_commands
from discord.ext import tasks, commands
import subprocess
import pandas as pd

class help_button(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None

class mark_log(discord.ui.View):
    def __init__(self, client):
        super().__init__()
        self.value = None
        self.client = client

class misc(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.process = psutil.Process()
        self.client.launch_time = datetime.utcnow()

    @commands.command()
    async def stats(self, ctx):
        cpu_usage = round(self.process.cpu_percent() / psutil.cpu_count())
        memory_usage = humanize.naturalsize(self.process.memory_full_info().uss / 1024**2)
        available_memory = humanize.naturalsize(psutil.virtual_memory().available - (self.process.memory_full_info().uss) / 1024**2)

        embed = discord.Embed(title = 'System Resource Usage', description = 'See CPU and memory usage of the system.')
        embed.add_field(name = 'CPU Usage', value = f'{cpu_usage}%', inline = False)
        embed.add_field(name = 'Memory Usage', value = f'{memory_usage}', inline = False)
        embed.add_field(name = 'Available Memory', value = f'{available_memory}', inline = False)
        await ctx.send(embed = embed)


    @commands.command(name='sync', hidden = True)
    @commands.is_owner()
    async def sync(self, ctx):
        synced = await self.client.tree.sync()
        await ctx.send("```\n{}```".format('\n'.join([command.name for command in synced])))

    @commands.command(name='reload', hidden = True)
    @commands.is_owner()
    async def _reload(self, ctx, extension):
        await self.client.reload_extension(f'cogs.{extension}')
        await ctx.send(f'Cogs `{extension}` has been reloaded.')
    
    @commands.command(name='ra', hidden = True)
    @commands.is_owner()
    async def _reload_all(self, ctx):
        for file in os.listdir('./cogs'):
            if file.endswith('.py'):
                await self.client.reload_extension(f'cogs.{file[:-3]}')
                await ctx.send(f'Cogs `{file[:-3]}` has been reloaded')


    @app_commands.command(name = 'ping', description= 'gives you the bot latency')
    async def ping(self, interaction : discord.Interaction):
        await interaction.response.send_message(f'Pong! Latency : `{round(self.client.latency * 1000)}ms`')

    
	
    @app_commands.command(name = 'dm-rey')
    async def dm_rey(self, interaction: discord.Interaction, content : str):
        rey = self.client.get_user(692994778136313896)
        embed = discord.Embed(title = interaction.user, description = f'>>> {content}', timestamp = datetime.now(), color = discord.Color.from_str('0x2F3136'))
        await rey.send(embed = embed)
        await interaction.response.send_message('sent to rey', ephemeral = True)

    @commands.command(name = 'uptime')
    @commands.is_owner()
    async def uptime(self, ctx):
        delta_uptime = datetime.utcnow() - self.client.launch_time
        hours, remainder = divmod(int(delta_uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        await ctx.send(f"{days}d, {hours}h, {minutes}m, {seconds}s")

    @commands.command(aliases = ['rs'])
    @commands.is_owner()
    async def restart(self, ctx):

        await ctx.send("Restarting...")
        subprocess.Popen('python main.py', shell= True)
        await self.client.close()
    

    @commands.command(name='confirm')
    async def mark_as_paid(self, ctx ):

        msg = await ctx.fetch_message(ctx.message.reference.message_id)

        payout_embed = msg.embeds[0]
        
        auctioneer_id = int(msg.embeds[0].footer.text.split(' : ')[1])

        sman_role = ctx.guild.get_role(719197064193638402)

        if ctx.author.id != auctioneer_id and sman_role not in ctx.author.roles:
            
            return
        
        else :

            button_url = msg.components[0].children[0].url

            view = mark_log(self.client)
            view.add_item(discord.ui.Button(label='Jump to auction', url=button_url))

            payout_embed.color = discord.Color.green()
            payout_embed.title = 'Auction Logs - Paid'

            await msg.edit(embed = payout_embed, view=view)

            for messages in self.client.payout_msgs[msg.id]:
                await messages.delete()

            del self.client.payout_msgs[msg.id]

            auction_queue = await self.client.db.auction_queue.find_one({'guild_id' : ctx.guild.id})
            auction_queue = auction_queue['queue']

            index = next((index for index, auction in enumerate(auction_queue) if auction['queue_message_id'] == msg.id), None)

            if index == None:
                print('WARNING : Request in queue not found.')

            else :
                auction_queue.pop(index)
                await self.client.db.auction_queue.update_one({'guild_id' : ctx.guild.id}, {'$set' : {'queue' : auction_queue}})

        
        await ctx.message.delete(delay = 2)


    @commands.command(name='cancel')
    async def mark_as_cancelled(self, ctx):

        msg = await ctx.fetch_message(ctx.message.reference.message_id)

        payout_embed = msg.embeds[0]
        
        auctioneer_id = int(msg.embeds[0].footer.text.split(' : ')[1])

        if ctx.author.id != auctioneer_id :
            return
        
        else :

            button_url = button_url = msg.components[0].children[0].url

            view = mark_log(self.client)
            view.add_item(discord.ui.Button(label='Jump to auction', url=button_url))

            payout_embed.color = discord.Color.red()
            payout_embed.title = 'Auction Logs - Cancelled'

            await msg.edit(embed = payout_embed, view=view)

            for messages in self.client.payout_msgs[msg.id]:
                await messages.delete()

            del self.client.payout_msgs[msg.id]

            auction_queue = await self.client.db.auction_queue.find_one({'guild_id' : ctx.guild.id})
            auction_queue = auction_queue['queue']

            index = next((index for index, auction in enumerate(auction_queue) if auction['queue_message_id'] == msg.id), None)

            if index == None:
                print('WARNING : Request in queue not found.')

            else :
                auction_queue.pop(index)
                await self.client.db.auction_queue.update_one({'guild_id' : ctx.guild.id}, {'$set' : {'queue' : auction_queue}})

            await ctx.message.delete(delay = 2)

    
    @app_commands.command(name='update_values')
    @app_commands.checks.has_any_role(719197064193638402, 1220040168992411820)
    async def update_values(self, interaction : discord.Interaction, file : discord.Attachment):
        await interaction.response.defer(ephemeral=True)
        if not file.filename.endswith('.csv'):
            await interaction.followup.send('Please attach a `.csv` file.')
        else :

            if os.path.exists('auctions.csv'):
                os.remove('auctions.csv')
            
            with open('auctions.csv', 'wb') as f:
                await file.save(f)
            

        await interaction.followup.send('Updated successfully!' , ephemeral=True)

    @app_commands.command(name='update_stats')
    async def update_stats(self, interaction : discord.Interaction, table : str, user : discord.Member, to : int):
        await interaction.response.defer()

        table_list = ['auction_hosted', 'total_amount_bid', 'total_amount_sold', 'auction_won', 'auction_joined', 'total_auction_requested']

        if interaction.user.id not in [729643700455604266, 692994778136313896]:
            return await interaction.followup.send('You do not have the permission to update user stats!', ephemeral=True)
        
        if table not in table_list:
            return await interaction.followup.send('Invalid table!', ephemeral=True)

        else :
            table = table.lower()

        await self.client.db.profile.update_one({'user_id' :  user.id, 'guild_id' : interaction.guild.id}, {'$set' : {table : to}})

        await interaction.followup.send(f'Updated {user.mention}\'s stats.')

    @update_stats.autocomplete('table')
    async def autocomplete_callback(self, interaction : discord.Interaction, current : str):
        table_list = ['auction_hosted', 'total_amount_bid', 'total_amount_sold', 'auction_won', 'auction_joined', 'total_auction_requested']

        return [app_commands.Choice(name=suggestion, value=suggestion) for suggestion in table_list if current.lower() in suggestion.lower()]
        

    @app_commands.command(name='help')
    async def help_command(self, interaction : discord.Interaction):
        embed = discord.Embed(title="‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ⋆ ˚｡⋆୨୧˚ Triv's Info & Commands ˚୨୧⋆｡˚ ⋆ ",description= 'Triv is a bot dedicated to <@686644874094837798> and coded for the purpose to host auctions.', color = discord.Color.from_str('0x2F3136'))
        embed.add_field(name= 'Developed by :', value= '<@692994778136313896> (ID : 692994778136313896)\n ‎ ‎ ‎ ', inline= False)
        embed.add_field(name= 'Prefix Commands', value= '`bid, revert`\n \n>>> Triv\'s prefix : `t!` ')
        embed.add_field(name= 'Slash Commands', value= '`ping`, `auction host`, `auction end`, \n`setup`, `invite`, `help`')
        view = help_button()
        view.add_item(discord.ui.Button(label='Join Support Server', url= 'https://discord.gg/qd3cy9qs3R'))
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name= 'invite')
    async def invite(self, interaction : discord.Interaction):
        embed = discord.Embed(title="",description= 'Hi! Triv is only supported for Dank Trades at the moment. Vote in Triv\'s Support Server if it should be launched publicly or not!', color = discord.Color.from_str('0x2F3136'))
        view = help_button()
        view.add_item(discord.ui.Button(label='Join Support Server', url= 'https://discord.gg/qd3cy9qs3R'))
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name='auc_count')
    @app_commands.checks.has_role(1228100188204437596)
    async def auction_count(self, interaction : discord.Interaction):

        await interaction.response.defer(ephemeral=True)
        
        data = await utils(self.client).get_auc_count(guild = interaction.guild)

        await interaction.followup.send(f"Daily: `{data['daily']}`\nWeekly: `{data['weekly']}`\nMonthly: `{data['monthly']}`")


    @app_commands.command(name='get_metrics')
    @app_commands.checks.has_any_role(1228100188204437596)
    async def get_metrics(self, interaction : discord.Interaction, target : str, scope :str = 'today'):

        await interaction.response.defer()

        data = await utils(self.client).get_user_count(guild=interaction.guild, scope=scope, target=target)

        if target == 'auction_users':
            embed = discord.Embed(title='Metrics for Auctions', color= discord.Color.from_str('0x2F3136'))
        elif target == 'queue_users':
            embed = discord.Embed(title='Metrics for Queues', color= discord.Color.from_str('0x2F3136'))
        
        embed.set_image(url = 'attachment://plot.png')
        embed.add_field(name='Unique_Users', value=data['unique_user_count'])
        embed.add_field(name='Avg_User_Count', value=data['avg_user_count'])
        embed.add_field(name=f'{target[:-6].title()} Count', value=data['event_count'])
        embed.add_field(name='Current Time', value=str(datetime.utcnow())[0:-7])
        embed.add_field(name='Scope', value=scope.title())

        await interaction.followup.send(file=data['file'], embed = embed)


    @commands.command(name='alock')
    @commands.has_any_role(750117211087044679,1051128651929882695)
    async def alock(self, ctx):
        queue_channel = self.client.get_channel(782483247619112991)
        auc_access = await utils(self.client).get_auction_access(arg=ctx)
        overwrites = utils(self.client).channel_close(channel=queue_channel, role=auc_access)
        await queue_channel.set_permissions(auc_access ,overwrite=overwrites)
        await ctx.send('✅ Locked down 🍯┃・auction-queue\nBefore requesting an auction please read <#730829517555236864>, violations of these conditions will result in a blacklist from auctions.')

    
    @commands.command(name='aunlock')
    @commands.has_any_role(750117211087044679,1051128651929882695)
    async def aunlock(self, ctx):
        queue_channel = self.client.get_channel(782483247619112991)
        auc_access = await utils(self.client).get_auction_access(arg=ctx)
        overwrites = utils(self.client).channel_open(channel=queue_channel, role=auc_access)
        await queue_channel.set_permissions(auc_access ,overwrite=overwrites)
        await ctx.send('✅ Unlocked **🍯┃・auction-queue**\nBefore requesting an auction please read <#730829517555236864>, violations of these conditions will result in a blacklist from auctions.')

        queue_count = await self.client.db.participants.find_one({'guild_id' : ctx.guild.id})
        queue_users = queue_count['queue_users']
        currn_date = queue_users.get(str(datetime.utcnow().date()), None)
        if not currn_date:
            queue_users.update({str(datetime.utcnow().date()) : {}})
        try:
            queue_users[str(datetime.utcnow().date())]['today_event_count'] += 1
        except  KeyError:
            queue_users[str(datetime.utcnow().date())].update({'today_event_count' : 1})
        await self.client.db.participants.update_one({'guild_id' : ctx.guild.id}, {'$set' : {'queue_users' : queue_users}})

    

async def setup(client):
    await client.add_cog(misc(client))