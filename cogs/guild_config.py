import discord
import json
import asyncio
from discord import app_commands
from discord.ext import commands
from discord.app_commands import Group, command

class server_config(commands.Cog):
    def __init__(self, client):
        self.client = client
        
    set_group = Group(name= 'set', description= 'just a groupd for the set subcommands')

    @app_commands.command(name = 'setup', description= 'To set everything up for the server')
    async def setup(self, interaction: discord.Interaction, auction_channel : discord.TextChannel, auctioneer_role : discord.Role, ping_role : discord.Role, auction_access_role: discord.Role, tradeout_role : discord.Role, tradeout_channel : discord.TextChannel, minimum_increment : float, auction_log_channel : discord.TextChannel):
        await self.client.db.execute('INSERT INTO "guild_config" (guild_id, auction_channel, auctioneer_role, ping_role, tradeout_role, tradeout_channel, auction_access, auction_log, min_increment ) VALUES($1, $2, $3, $4, $5, $6, $7, $8, $9)', interaction.guild.id, auction_channel.id, auctioneer_role.id, ping_role.id, tradeout_role.id, tradeout_channel.id, auction_access_role.id, auction_log_channel.id, minimum_increment)
        await interaction.response.defer(ephemeral=True)
        await asyncio.sleep(5)
        await interaction.followup.send('Guild configured!')        
    
    @set_group.command(name= 'auction_access', description= 'set the ping role')
    @app_commands.checks.has_permissions(administrator = True)
    async def auction_access(self, interaction : discord.Interaction, role : discord.Role):
        await self.client.db.execute('UPDATE guild_config SET auction_access = $1 WHERE guild_id = $2', role.id, interaction.guild.id)
        await interaction.response.send_message('Updated.')

    @set_group.command(name= 'auction_channel', description= 'set the auction channel')
    @app_commands.checks.has_permissions(administrator = True)
    async def auc_channel(self, interaction : discord.Interaction, channel : discord.TextChannel):
        await self.client.db.execute('UPDATE guild_config SET auction_channel = $1 WHERE guild_id = $2', channel.id, interaction.guild.id)
        await interaction.response.send_message('Updated.')

    @set_group.command(name= 'auctioneer_role', description= 'set the auctioneer role')
    @app_commands.checks.has_permissions(administrator = True)
    async def auc_role(self, interaction : discord.Interaction, role : discord.Role):
        await self.client.db.execute('UPDATE guild_config SET auctioneer_role = $1 WHERE guild_id = $2', role.id, interaction.guild.id)
        await interaction.response.send_message('Updated.')

    @set_group.command(name= 'ping_role', description= 'set the ping role')
    @app_commands.checks.has_permissions(administrator = True)
    async def ping_role(self, interaction : discord.Interaction, role : discord.Role):
        await self.client.db.execute('UPDATE guild_config SET ping_role = $1 WHERE guild_id = $2', role.id, interaction.guild.id)
        await interaction.response.send_message('Updated.')

    @set_group.command(name= 'tradeout_role', description= 'set the tradeout role')
    @app_commands.checks.has_permissions(administrator = True)
    async def tradeout_role(self, interaction : discord.Interaction, role : discord.Role):
        await self.client.db.execute('UPDATE guild_config SET tradeout_role = $1 WHERE guild_id = $2', role.id, interaction.guild.id)
        await interaction.response.send_message('Updated.')

    @set_group.command(name= 'tradeout_channel', description= 'set the tradeout channel')
    @app_commands.checks.has_permissions(administrator = True)
    async def tradeout_channel(self, interaction : discord.Interaction, channel : discord.TextChannel):
        await self.client.db.execute('UPDATE guild_config SET tradeout_channel = $1 WHERE guild_id = $2', channel.id, interaction.guild.id)
        await interaction.response.send_message('Updated.')
    
    @set_group.command(name= 'auction_log_channel', description= 'set the auction log channel')
    @app_commands.checks.has_permissions(administrator = True)
    async def log_channel(self, interaction : discord.Interaction, channel : discord.TextChannel):
        await self.client.db.execute('UPDATE guild_config SET auction_log = $1 WHERE guild_id = $2', channel.id, interaction.guild.id)
        await interaction.response.send_message('Updated.')

    @set_group.command(name='minimum_increment', description= 'sets the minimum increment for bids')
    @app_commands.checks.has_permissions(administrator = True)
    async def min_increment(self, interaction : discord.Interaction, input : float):
        await self.client.db.execute('UPDATE guild_config SET min_increment = $1 WHERE guild_id = $2', input, interaction.guild.id)
        await interaction.response.send_message('Updated.')
        



    @commands.Cog.listener()
    async def on_guild_join(self, guild : discord.Guild):
        await guild.owner.send('Firstly, go through the server configurations to set me up for your server! Run `/setup` !')










async def setup(client):
    await client.add_cog(server_config(client))