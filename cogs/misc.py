import discord
import psutil
import json
import io
import os
import sys
import humanize
sys.path.append(r'/home/container/')
from cogs.utils import utils
from cogs.loops import mark_log
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

        if ctx.author.id != auctioneer_id or sman_role not in ctx.author.roles:
            
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
                await self.client.db.auction_queue.update_one({'guild_id' : ctx.guild.id}, {'queue' : auction_queue})

        
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
            
            with open(file.filename, 'wb') as f:
                await file.save(f, filename='auctions.csv')
            

        await interaction.followup.send('Updated successfully!' , ephemeral=True)

            


        

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

    @commands.command()
    async def data_view(self, ctx):
        # Assuming self.client.db is the connection pool to your PostgreSQL database
        pool = self.client.db
        query = 'SELECT * FROM "guild_config"'
        
        # Acquire a connection from the pool
        async with pool.acquire() as connection:
            # Execute the query and fetch data
            data = await connection.fetch(query)
        
        # Extract column names from the result set
        columns = data[0].keys() if data else []
        
        # Convert the fetched data into a DataFrame with column names
        df = pd.DataFrame(data, columns=columns)
        
        # Convert DataFrame to a string and send it as a message
        await ctx.send(f'```sql\n{df.to_string()}```')
    

async def setup(client):
    await client.add_cog(misc(client))